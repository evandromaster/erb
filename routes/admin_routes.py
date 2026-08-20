import sqlite3
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from werkzeug.security import generate_password_hash
from auth import admin_required
from control_database import ADMIN_USERNAME, get_control_connection, normalize_cpf, validate_cpf
from routes.auth_routes import save_photo

admin_bp=Blueprint('admin',__name__,url_prefix='/admin')

@admin_bp.route('/')
@admin_required
def index():
    conn=get_control_connection()
    try:
        users=conn.execute('''SELECT id,nome_completo,cidade,activated,type_user,username
                              FROM users ORDER BY nome_completo COLLATE NOCASE, id''').fetchall()
    finally:conn.close()
    return render_template('admin.html',users=users)

@admin_bp.route('/users/<int:user_id>/edit')
@admin_required
def edit_user(user_id):
    conn=get_control_connection()
    try:
        user=conn.execute('SELECT * FROM users WHERE id=?',(user_id,)).fetchone()
    finally:conn.close()
    if user is None:abort(404)
    return render_template('admin_edit_user.html',user=user)

@admin_bp.route('/users/<int:user_id>/update',methods=['POST'])
@admin_required
def update_user(user_id):
    fields=('nome_completo','email','telefone','rua','numero','bairro','cidade','cep',
            'instituicao','departamento','matricula','unidade','ueop','secao')
    values={field:request.form.get(field,'').strip() for field in fields}
    values['nome_completo']=' '.join(values['nome_completo'].split())
    values['cidade']=' '.join(values['cidade'].split())
    username=request.form.get('username','').strip()
    cpf=normalize_cpf(request.form.get('cpf'))
    role=request.form.get('type_user','').strip()
    activated=request.form.get('activated')
    new_password=request.form.get('new_password','')
    password_confirm=request.form.get('password_confirm','')
    if not values['nome_completo'] or not username or not cpf:
        flash('Nome, CPF e username são obrigatórios.','danger')
        return redirect(url_for('admin.edit_user',user_id=user_id))
    if len(values['nome_completo'])>200 or len(values['cidade'])>120 or len(username)>120:
        flash('Nome, cidade ou username excede o tamanho permitido.','danger')
        return redirect(url_for('admin.edit_user',user_id=user_id))
    if values['email'] and ('@' not in values['email'] or len(values['email'])>255):
        flash('Informe um e-mail válido.','danger')
        return redirect(url_for('admin.edit_user',user_id=user_id))
    if role not in ('admin','editor','view') or activated not in ('0','1'):
        flash('Status ou perfil inválido.','danger')
        return redirect(url_for('admin.edit_user',user_id=user_id))
    if new_password and (len(new_password)<6 or new_password!=password_confirm):
        flash('A nova senha deve ter ao menos 6 caracteres e confirmação igual.','danger')
        return redirect(url_for('admin.edit_user',user_id=user_id))
    conn=get_control_connection()
    try:
        user=conn.execute('SELECT * FROM users WHERE id=?',(user_id,)).fetchone()
        if not user:abort(404)
        if cpf!=user['cpf'] and not validate_cpf(cpf):
            flash('CPF inválido.','danger')
            return redirect(url_for('admin.edit_user',user_id=user_id))
        if conn.execute('SELECT 1 FROM users WHERE username=? COLLATE NOCASE AND id!=?',
                        (username,user_id)).fetchone():
            flash('Este username já está cadastrado.','danger')
            return redirect(url_for('admin.edit_user',user_id=user_id))
        if conn.execute('SELECT 1 FROM users WHERE cpf=? AND id!=?',(cpf,user_id)).fetchone():
            flash('Este CPF já está cadastrado.','danger')
            return redirect(url_for('admin.edit_user',user_id=user_id))
        active=int(activated)
        if user['username']==ADMIN_USERNAME and (role!='admin' or not active or username!=ADMIN_USERNAME):
            flash('O administrador principal não pode ser renomeado, desativado ou rebaixado.','danger')
            return redirect(url_for('admin.edit_user',user_id=user_id))
        try:
            photo=save_photo(request.files.get('photo')) or user['photo']
        except ValueError as error:
            flash(str(error),'danger')
            return redirect(url_for('admin.edit_user',user_id=user_id))
        available_columns={row['name'] for row in conn.execute('PRAGMA table_info(users)')}
        update_data={
            'nome_completo':values['nome_completo'],'cpf':cpf,'username':username,
            'email':values['email'],'telefone':values['telefone'],'rua':values['rua'],
            'numero':values['numero'],'bairro':values['bairro'],'cidade':values['cidade'],
            'cep':values['cep'],'instituicao':values['instituicao'],
            'departamento':values['departamento'],'photo':photo,'type_user':role,
            'activated':active,
        }
        for legacy_field in ('matricula','unidade','ueop','secao'):
            if legacy_field in available_columns:
                update_data[legacy_field]=values[legacy_field]
        assignments=','.join(f'{field}=?' for field in update_data)+',updated_at=CURRENT_TIMESTAMP'
        params=tuple(update_data.values())
        if new_password:
            assignments+=',password=?'
            params+=(generate_password_hash(new_password),)
        conn.execute(f'UPDATE users SET {assignments} WHERE id=?',params+(user_id,))
        conn.commit()
        flash('Usuário atualizado com sucesso.','success')
    except sqlite3.IntegrityError:
        conn.rollback()
        flash('CPF ou username já cadastrado.','danger')
        return redirect(url_for('admin.edit_user',user_id=user_id))
    finally:
        conn.close()
    return redirect(url_for('admin.index'))

@admin_bp.route('/users/<int:user_id>/password',methods=['POST'])
@admin_required
def reset_password(user_id):
    password=request.form.get('password','')
    if len(password)<6:flash('A senha deve ter pelo menos 6 caracteres.','danger')
    else:
        conn=get_control_connection()
        try:conn.execute('UPDATE users SET password=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',(generate_password_hash(password),user_id));conn.commit()
        finally:conn.close()
        flash('Senha redefinida.','success')
    return redirect(url_for('admin.index'))

@admin_bp.route('/users/<int:user_id>/delete',methods=['POST'])
@admin_required
def delete_user(user_id):
    conn=get_control_connection()
    try:
        user=conn.execute('SELECT username,cpf FROM users WHERE id=?',(user_id,)).fetchone()
        if user is None:
            abort(404)
        if user['username']==ADMIN_USERNAME:
            flash('O administrador principal não pode ser excluído.','danger')
        else:
            # Compatibilidade com o control.db legado: access_controls referencia
            # users.cpf com ON DELETE RESTRICT.
            has_access_controls=conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='access_controls'"
            ).fetchone()
            if has_access_controls and user['cpf']:
                conn.execute('DELETE FROM access_controls WHERE cpf=?',(user['cpf'],))
            conn.execute('DELETE FROM users WHERE id=?',(user_id,))
            conn.commit()
            flash('Usuário excluído com sucesso.','success')
    except Exception:
        conn.rollback()
        raise
    finally:conn.close()
    return redirect(url_for('admin.index'))

@admin_bp.route('/users/<int:user_id>/projects',methods=['POST'])
@admin_required
def set_project(user_id):
    project_id=request.form.get('project_id',type=int);permission=request.form.get('permission')
    if permission not in ('admin','editor','view'):abort(400)
    conn=get_control_connection()
    try:
        conn.execute('''INSERT INTO user_projects(user_id,project_id,permission) VALUES(?,?,?)
          ON CONFLICT(user_id,project_id) DO UPDATE SET permission=excluded.permission''',(user_id,project_id,permission));conn.commit()
    except sqlite3.IntegrityError:abort(400)
    finally:conn.close()
    flash('Acesso ao projeto atualizado.','success')
    return redirect(url_for('admin.index'))

@admin_bp.route('/users/<int:user_id>/projects/<int:project_id>/delete',methods=['POST'])
@admin_required
def remove_project(user_id,project_id):
    conn=get_control_connection()
    try:conn.execute('DELETE FROM user_projects WHERE user_id=? AND project_id=?',(user_id,project_id));conn.commit()
    finally:conn.close()
    flash('Acesso ao projeto removido.','success')
    return redirect(url_for('admin.index'))

@admin_bp.route('/projects/<int:project_id>/status',methods=['POST'])
@admin_required
def project_status(project_id):
    active=1 if request.form.get('activated')=='1' else 0
    conn=get_control_connection()
    try:
        cursor=conn.execute('UPDATE projects SET activated=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',(active,project_id))
        conn.commit()
    finally:conn.close()
    if not cursor.rowcount:abort(404)
    flash('Status do projeto atualizado.','success')
    return redirect(url_for('admin.index'))
