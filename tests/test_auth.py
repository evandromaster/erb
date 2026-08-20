import os, tempfile, unittest
from werkzeug.security import generate_password_hash
from config import Config

class AuthIsolationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        Config.DATABASE_FOLDER=self.tmp.name
        Config.DATABASE_PATH=os.path.join(self.tmp.name,'antenas.db')
        Config.CONTROL_DATABASE_PATH=os.path.join(self.tmp.name,'control.db')
        Config.UPLOAD_FOLDER=os.path.join(self.tmp.name,'uploads')
        Config.USER_UPLOAD_FOLDER=os.path.join(self.tmp.name,'photos')
        from app import create_app
        self.app=create_app(Config);self.app.config.update(TESTING=True,SECRET_KEY='test')
        from database import get_db_connection
        db=get_db_connection()
        db.execute("INSERT INTO projetos(nome) VALUES('Projeto A')");self.a=db.execute("SELECT id FROM projetos WHERE nome='Projeto A'").fetchone()[0]
        db.execute("INSERT INTO projetos(nome) VALUES('Projeto B')");self.b=db.execute("SELECT id FROM projetos WHERE nome='Projeto B'").fetchone()[0]
        db.commit();db.close()
        from control_database import get_control_connection, sync_projects
        sync_projects();c=get_control_connection()
        c.execute("INSERT INTO users(nome_completo,cpf,username,password,type_user,activated) VALUES(?,?,?,?,?,1)",
                  ('Editor A','52998224725','editor_a',generate_password_hash('abcdef'),'editor'))
        self.uid=c.execute("SELECT id FROM users WHERE username='editor_a'").fetchone()[0]
        c.execute("INSERT INTO user_projects(user_id,project_id,permission) VALUES(?,?,'editor')",(self.uid,self.a))
        c.commit();c.close();self.client=self.app.test_client()

    def tearDown(self): self.tmp.cleanup()
    def login(self,password='abcdef'):
        return self.client.post('/login',data={'username':'editor_a','password':password})

    def test_login_wrong_password_and_logout(self):
        self.assertEqual(self.login('wrong').status_code,200)
        self.assertEqual(self.login().status_code,302)
        self.assertEqual(self.client.post('/logout').status_code,302)

    def test_project_tampering_is_blocked(self):
        self.login()
        self.assertEqual(self.client.post('/projetos/selecionar',data={'project_id':self.b}).status_code,403)
        with self.client.session_transaction() as s:self.assertNotIn('active_project_id',s)
        with self.client.session_transaction() as s:s['active_project_id']=self.b
        self.assertEqual(self.client.post('/api/pontos',json={'tipo':'Casa','descricao':'x','latitude':-20,'longitude':-44}).status_code,403)

    def test_authorized_project_and_created_by(self):
        self.login();self.client.post('/projetos/selecionar',data={'project_id':self.a})
        response=self.client.post('/api/pontos',json={'tipo':'Casa','descricao':'x','latitude':-20,'longitude':-44})
        self.assertEqual(response.status_code,201)
        self.assertEqual(response.get_json()['data']['created_by'],self.uid)

    def test_view_cannot_write(self):
        from control_database import get_control_connection
        c=get_control_connection();c.execute("UPDATE users SET type_user='view' WHERE id=?",(self.uid,));c.commit();c.close()
        self.login()
        with self.client.session_transaction() as s:s['active_project_id']=self.a
        self.assertEqual(self.client.post('/api/pontos',json={}).status_code,403)

    def test_admin_deletes_user_with_legacy_access_history(self):
        from control_database import get_control_connection
        c=get_control_connection()
        c.execute('''CREATE TABLE access_controls(
          id INTEGER PRIMARY KEY,cpf TEXT NOT NULL,
          data_hora_login DATETIME NOT NULL,
          FOREIGN KEY(cpf) REFERENCES users(cpf) ON DELETE RESTRICT)''')
        c.execute("INSERT INTO access_controls(cpf,data_hora_login) VALUES('52998224725',CURRENT_TIMESTAMP)")
        admin=c.execute("SELECT id FROM users WHERE username='admin'").fetchone()[0]
        c.commit();c.close()
        with self.client.session_transaction() as s:
            s['user_id']=admin;s['username']='admin';s['type_user']='admin'
        response=self.client.post(f'/admin/users/{self.uid}/delete')
        self.assertEqual(response.status_code,302)
        c=get_control_connection()
        self.assertIsNone(c.execute('SELECT 1 FROM users WHERE id=?',(self.uid,)).fetchone())
        self.assertIsNone(c.execute("SELECT 1 FROM access_controls WHERE cpf='52998224725'").fetchone())
        c.close()

    def test_admin_list_contains_only_requested_user_columns(self):
        from control_database import get_control_connection
        c=get_control_connection()
        admin=c.execute("SELECT id FROM users WHERE username='admin'").fetchone()[0]
        c.close()
        with self.client.session_transaction() as s:
            s['user_id']=admin;s['username']='admin';s['type_user']='admin'
        response=self.client.get('/admin/')
        self.assertEqual(response.status_code,200)
        html=response.get_data(as_text=True)
        for heading in ('Nome','Cidade','Status','Perfil','Ações'):
            self.assertIn(heading,html)
        self.assertNotIn('52998224725',html)
        self.assertNotIn('editor_a',html)

    def test_admin_edits_all_profile_fields_and_preserves_password_when_blank(self):
        from control_database import get_control_connection
        c=get_control_connection()
        admin=c.execute("SELECT id FROM users WHERE username='admin'").fetchone()[0]
        before=c.execute('SELECT password,cpf,email FROM users WHERE id=?',(self.uid,)).fetchone()
        c.close()
        with self.client.session_transaction() as s:
            s['user_id']=admin;s['username']='admin';s['type_user']='admin'
        self.assertEqual(self.client.get(f'/admin/users/{self.uid}/edit').status_code,200)
        response=self.client.post(f'/admin/users/{self.uid}/update',data={
            'nome_completo':'  Editor Atualizado  ','cidade':'  Divinópolis ',
            'activated':'0','type_user':'view','username':'editor_novo',
            'cpf':'529.982.247-25','email':'novo@example.com','telefone':'37999999999',
            'rua':'Rua Um','numero':'10','bairro':'Centro','cep':'35500-000',
            'instituicao':'Instituição','departamento':'TI','matricula':'123',
            'unidade':'Unidade A','ueop':'UEOP A','secao':'Seção A',
            'new_password':'','password_confirm':''})
        self.assertEqual(response.status_code,302)
        c=get_control_connection()
        after=c.execute('SELECT * FROM users WHERE id=?',(self.uid,)).fetchone()
        c.close()
        self.assertEqual((after['nome_completo'],after['cidade'],after['activated'],after['type_user']),
                         ('Editor Atualizado','Divinópolis',0,'view'))
        self.assertEqual(after['password'],before['password'])
        self.assertEqual((after['cpf'],after['username'],after['email'],after['telefone']),
                         ('52998224725','editor_novo','novo@example.com','37999999999'))
        self.assertEqual((after['rua'],after['numero'],after['bairro'],after['cep']),
                         ('Rua Um','10','Centro','35500-000'))
        self.assertEqual((after['instituicao'],after['departamento']),('Instituição','TI'))

    def test_non_admin_cannot_access_user_management(self):
        self.login()
        for method,path in (
            ('get','/admin/'),('get',f'/admin/users/{self.uid}/edit'),
            ('post',f'/admin/users/{self.uid}/update'),('post',f'/admin/users/{self.uid}/delete')):
            response=getattr(self.client,method)(path,data={
                'nome_completo':'Teste','cidade':'Teste','activated':'1','type_user':'editor'})
            self.assertEqual(response.status_code,403,path)

class CPFTests(unittest.TestCase):
    def test_cpf(self):
        from control_database import normalize_cpf,validate_cpf
        self.assertTrue(validate_cpf('529.982.247-25'))
        self.assertEqual(normalize_cpf('529.982.247-25'),'52998224725')
        self.assertFalse(validate_cpf('111.111.111-11'))
        self.assertFalse(validate_cpf('123'))

if __name__=='__main__':unittest.main()
