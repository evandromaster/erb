import sqlite3
import os
from config import Config

def get_db_connection():
    """Retorna uma conexão ativa com o banco SQLite com suporte a dicionário de linhas (Row)."""
    Config.init_app(None)
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    """Inicializa todas as tabelas e índices necessários no banco de dados SQLite."""
    Config.init_app(None)
    conn = get_db_connection()
    cursor = conn.cursor()

    # Contextos logicos que isolam ERBs, pontos e historicos de importacao.
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS projetos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL COLLATE NOCASE UNIQUE,
        data_criacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        data_atualizacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    # 1. Tabela de Importações (Histórico de uploads de arquivos Excel)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS importacoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome_arquivo TEXT NOT NULL,
        nome_original TEXT NOT NULL,
        aba_selecionada TEXT,
        data_importacao DATETIME DEFAULT CURRENT_TIMESTAMP,
        total_registros INTEGER DEFAULT 0,
        registros_importados INTEGER DEFAULT 0,
        registros_erro INTEGER DEFAULT 0,
        status TEXT DEFAULT 'sucesso',
        detalhes_erro TEXT,
        projeto_id INTEGER REFERENCES projetos(id) ON DELETE RESTRICT
    );
    """)
    
    # 2. Tabela de Operadoras (VIVO, CLARO, TIM, ALGAR, OI, etc.)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS operadoras (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT UNIQUE NOT NULL,
        cor_padrao TEXT DEFAULT '#3388ff'
    );
    """)
    
    # 3. Tabela de Municípios
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS municipios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        uf TEXT DEFAULT 'MG',
        UNIQUE(nome, uf)
    );
    """)
    
    # 4. Tabela de Tecnologias (2G, 3G, 4G, 5G, etc.)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tecnologias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT UNIQUE NOT NULL
    );
    """)
    
    # 5. Tabela Principal de Antenas ERB / Setores
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS antenas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        importacao_id INTEGER,
        ponto INTEGER,
        nome TEXT,
        descricao TEXT,
        crime TEXT,
        operadora_id INTEGER,
        municipio_id INTEGER,
        tecnologia_id INTEGER,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        azimute REAL DEFAULT 0,
        distancia REAL DEFAULT 1000,
        raio REAL DEFAULT 60,
        opacidade REAL DEFAULT 0.2,
        borda TEXT DEFAULT '#FF0000',
        preenchimento TEXT DEFAULT '#FFFF00',
        data_registro TEXT,
        hora_registro TEXT,
        fonte TEXT,
        plotar INTEGER DEFAULT 1,
        icone TEXT DEFAULT 'antena1.png',
        criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
        projeto_id INTEGER,
        FOREIGN KEY (importacao_id) REFERENCES importacoes(id) ON DELETE CASCADE,
        FOREIGN KEY (operadora_id) REFERENCES operadoras(id) ON DELETE SET NULL,
        FOREIGN KEY (municipio_id) REFERENCES municipios(id) ON DELETE SET NULL,
        FOREIGN KEY (tecnologia_id) REFERENCES tecnologias(id) ON DELETE SET NULL,
        FOREIGN KEY (projeto_id) REFERENCES projetos(id) ON DELETE RESTRICT
    );
    """)
    
    # Índices para alta performance nas consultas do Folium e dos filtros
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_antenas_coords ON antenas(latitude, longitude);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_antenas_importacao ON antenas(importacao_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_antenas_operadora ON antenas(operadora_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_antenas_municipio ON antenas(municipio_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_antenas_plotar ON antenas(plotar);")

    # 6. Pontos personalizados inseridos manualmente no Mapa Interativo
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pontos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tipo TEXT NOT NULL CHECK (
            tipo IN ('Casa', 'Trabalho', 'Comparsa', 'Empresa', 'Antena', 'Crime', 'Outro')
        ),
        descricao TEXT NOT NULL,
        latitude REAL NOT NULL CHECK (latitude >= -90 AND latitude <= 90),
        longitude REAL NOT NULL CHECK (longitude >= -180 AND longitude <= 180),
        data_criacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        data_atualizacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        created_by INTEGER,
        projeto_id INTEGER REFERENCES projetos(id) ON DELETE RESTRICT
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pontos_tipo ON pontos(tipo);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pontos_coords ON pontos(latitude, longitude);")

    # Migracao incremental para bancos criados por versoes anteriores.
    def ensure_column(table, column, definition):
        columns = {row[1] for row in cursor.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    ensure_column('antenas', 'projeto_id', 'INTEGER REFERENCES projetos(id) ON DELETE RESTRICT')
    ensure_column('pontos', 'projeto_id', 'INTEGER REFERENCES projetos(id) ON DELETE RESTRICT')
    ensure_column('pontos', 'created_by', 'INTEGER')
    ensure_column('importacoes', 'projeto_id', 'INTEGER REFERENCES projetos(id) ON DELETE RESTRICT')

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_antenas_projeto ON antenas(projeto_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pontos_projeto ON pontos(projeto_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_importacoes_projeto ON importacoes(projeto_id);")

    legacy_tables = ('antenas', 'pontos', 'importacoes')
    has_legacy_data = any(
        cursor.execute(f"SELECT 1 FROM {table} WHERE projeto_id IS NULL LIMIT 1").fetchone()
        for table in legacy_tables
    )
    if has_legacy_data:
        cursor.execute("INSERT OR IGNORE INTO projetos (nome) VALUES (?)", ('Projeto Legado',))
        legacy_id = cursor.execute(
            "SELECT id FROM projetos WHERE nome = ? COLLATE NOCASE", ('Projeto Legado',)
        ).fetchone()[0]
        for table in legacy_tables:
            cursor.execute(
                f"UPDATE {table} SET projeto_id = ? WHERE projeto_id IS NULL", (legacy_id,)
            )
    
    # Inserção de cores padrão para operadoras conhecidas
    operadoras_default = [
        ('VIVO', '#9400D3'),
        ('CLARO', '#E60000'),
        ('TIM', '#005CA9'),
        ('ALGAR', '#00A859'),
        ('OI', '#FFD100'),
        ('OUTRA', '#6c757d')
    ]
    for nome, cor in operadoras_default:
        cursor.execute("INSERT OR IGNORE INTO operadoras (nome, cor_padrao) VALUES (?, ?);", (nome, cor))
        
    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print("Banco de dados SQLite inicializado com sucesso!")
