import os, sqlite3, uuid
from urllib.parse import urlsplit
from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from config import Config
from control_database import get_control_connection, normalize_cpf, validate_cpf
from auth import login_required

auth_bp=Blueprint('auth',__name__)
FIELDS=('nome_completo','email','telefone','rua','numero','bairro','cidade','cep','instituicao','departamento')

def safe_next(value):
    parsed=urlsplit(value or '')
    return value if value and not parsed.scheme and not parsed.netloc and value.startswith('/') else url_for('main.index')

def save_photo(file):
    if not file or not file.filename:return None
    ext=file.filename.rsplit('.',1)[-1].lower() if '.' in file.filename else ''
    if ext not in Config.ALLOWED_PHOTO_EXTENSIONS or not (file.mimetype or '').startswith('image/'):
        raise ValueError('Foto inválida. Use JPG, PNG ou WEBP.')
    data=file.read(Config.MAX_PHOTO_SIZE+1)
    if len(data)>Config.MAX_PHOTO_SIZE:raise ValueError('A foto deve ter no máximo 2 MB.')
    name=f'{uuid.uuid4().hex}_{secure_filename(file.filename)}'
    with open(os.path.join(Config.USER_UPLOAD_FOLDER,name),'wb') as target:target.write(data)
    return name

@auth_bp.route('/login',methods=['GET','POST'])
def login():
    if g.current_user:return redirect(url_for('main.index'))
    if request.method=='POST':
        username=request.form.get('username','').strip()
        conn=get_control_connection()
        try:user=conn.execute('SELECT * FROM users WHERE username=? COLLATE NOCASE',(username,)).fetchone()
        finally:conn.close()
        if not user or not check_password_hash(user['password'],request.form.get('password','')):
            flash('Usuário ou senha inválidos.','danger')
        elif not user['activated']:
            flash('Sua conta ainda não foi aprovada ou está desativada.','warning')
        else:
            session.clear()
            session.update(user_id=user['id'],username=user['username'],type_user=user['type_user'])
            return redirect(safe_next(request.form.get('next') or request.args.get('next')))
    return render_template('login.html')

@auth_bp.route('/register',methods=['GET','POST'])
def register():
    if request.method=='POST':
        values={field:request.form.get(field,'').strip() for field in FIELDS}
        cpf=normalize_cpf(request.form.get('cpf'))
        username=request.form.get('username','').strip()
        password=request.form.get('password','')
        error=None
        if not values['nome_completo'] or not username or not password:error='Preencha nome, CPF, usuário e senha.'
        elif not validate_cpf(cpf):error='CPF inválido.'
        elif password!=request.form.get('password_confirm'):error='A confirmação da senha não confere.'
        elif len(password)<6:error='A senha deve ter pelo menos 6 caracteres.'
        try:photo=save_photo(request.files.get('photo')) if not error else None
        except ValueError as exc:error=str(exc);photo=None
        if not error:
            conn=get_control_connection()
            try:
                conn.execute('''INSERT INTO users(nome_completo,cpf,username,password,email,telefone,rua,numero,
                 bairro,cidade,cep,instituicao,departamento,photo,type_user,activated)
                 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,'view',0)''',
                 (values['nome_completo'],cpf,username,generate_password_hash(password),values['email'],
                  values['telefone'],values['rua'],values['numero'],values['bairro'],values['cidade'],
                  values['cep'],values['instituicao'],values['departamento'],photo))
                conn.commit()
                flash('Cadastro realizado. Sua conta aguarda aprovação do administrador.','success')
                return redirect(url_for('auth.login'))
            except sqlite3.IntegrityError as exc:
                conn.rollback()
                error='CPF ou nome de usuário já cadastrado.'
            finally:conn.close()
        flash(error,'danger')
    return render_template('register.html')

@auth_bp.route('/logout',methods=['POST'])
@login_required
def logout():
    session.clear();flash('Você saiu do sistema.','success')
    return redirect(url_for('auth.login'))

@auth_bp.route('/change-password',methods=['GET','POST'])
@login_required
def change_password():
    if request.method=='POST':
        current=request.form.get('current_password','');new=request.form.get('new_password','')
        if not check_password_hash(g.current_user['password'],current):flash('Senha atual incorreta.','danger')
        elif len(new)<6:flash('A nova senha deve ter pelo menos 6 caracteres.','danger')
        elif new!=request.form.get('password_confirm'):flash('A confirmação da nova senha não confere.','danger')
        else:
            conn=get_control_connection()
            try:
                conn.execute('UPDATE users SET password=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',
                             (generate_password_hash(new),g.current_user['id']));conn.commit()
            finally:conn.close()
            flash('Senha alterada com sucesso.','success');return redirect(url_for('main.index'))
    return render_template('change_password.html')
