import re
import sqlite3
from werkzeug.security import generate_password_hash
from config import Config
from database import get_db_connection

ADMIN_USERNAME = 'admin'

def get_control_connection():
    Config.init_app(None)
    conn = sqlite3.connect(Config.CONTROL_DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn

def normalize_cpf(value):
    return re.sub(r'\D', '', value or '')

def validate_cpf(value):
    cpf = normalize_cpf(value)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for length in (9, 10):
        total = sum(int(cpf[i]) * (length + 1 - i) for i in range(length))
        digit = (total * 10) % 11
        if digit == 10: digit = 0
        if digit != int(cpf[length]): return False
    return True

def sync_projects(conn=None):
    own = conn is None
    conn = conn or get_control_connection()
    operational = get_db_connection()
    try:
        for p in operational.execute('SELECT id,nome,data_criacao,data_atualizacao FROM projetos'):
            conn.execute('''INSERT INTO projects(id,name,created_at,updated_at,activated)
                VALUES(?,?,?,?,1) ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,updated_at=excluded.updated_at''',
                (p['id'], p['nome'], p['data_criacao'], p['data_atualizacao']))
        if own: conn.commit()
    finally:
        operational.close()
        if own: conn.close()

def init_control_db():
    conn = get_control_connection()
    try:
        conn.executescript('''
        CREATE TABLE IF NOT EXISTS users(
          id INTEGER PRIMARY KEY AUTOINCREMENT,nome_completo TEXT NOT NULL,
          cpf TEXT NOT NULL UNIQUE,username TEXT NOT NULL COLLATE NOCASE UNIQUE,
          password TEXT NOT NULL,email TEXT,telefone TEXT,rua TEXT,numero TEXT,
          bairro TEXT,cidade TEXT,cep TEXT,instituicao TEXT,departamento TEXT,photo TEXT,
          type_user TEXT NOT NULL DEFAULT 'view' CHECK(type_user IN('admin','editor','view')),
          activated INTEGER NOT NULL DEFAULT 0 CHECK(activated IN(0,1)),
          created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS projects(
          id INTEGER PRIMARY KEY,name TEXT NOT NULL,description TEXT,
          created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
          created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          activated INTEGER NOT NULL DEFAULT 1 CHECK(activated IN(0,1)));
        CREATE TABLE IF NOT EXISTS user_projects(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          permission TEXT NOT NULL DEFAULT 'view' CHECK(permission IN('admin','editor','view')),
          created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(user_id,project_id));
        CREATE INDEX IF NOT EXISTS idx_up_user ON user_projects(user_id);
        CREATE INDEX IF NOT EXISTS idx_up_project ON user_projects(project_id);
        ''')
        # Migração compatível com versões anteriores do control.db.
        user_columns={row['name'] for row in conn.execute('PRAGMA table_info(users)')}
        additions={
            'nome_completo':'TEXT','cpf':'TEXT','rua':'TEXT','numero':'TEXT',
            'bairro':'TEXT','cidade':'TEXT','cep':'TEXT','instituicao':'TEXT',
            'departamento':'TEXT','created_at':'DATETIME','updated_at':'DATETIME'
        }
        for name,definition in additions.items():
            if name not in user_columns:
                conn.execute(f'ALTER TABLE users ADD COLUMN {name} {definition}')
        conn.execute("UPDATE users SET created_at=COALESCE(created_at,CURRENT_TIMESTAMP)")
        conn.execute("UPDATE users SET updated_at=COALESCE(updated_at,CURRENT_TIMESTAMP)")
        conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username_unique ON users(username COLLATE NOCASE)')
        conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_users_cpf_unique ON users(cpf) WHERE cpf IS NOT NULL')
        if not conn.execute('SELECT 1 FROM users WHERE username=? COLLATE NOCASE',(ADMIN_USERNAME,)).fetchone():
            conn.execute('''INSERT INTO users(nome_completo,cpf,username,password,email,type_user,activated)
              VALUES(?,?,?,?,?,'admin',1)''',
              ('Administrador do sistema','00000000000',ADMIN_USERNAME,
               generate_password_hash('123456'),'admin@localhost'))
        sync_projects(conn)
        conn.commit()
    finally: conn.close()
