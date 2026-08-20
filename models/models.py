from database import get_db_connection

class OperadoraModel:
    @staticmethod
    def get_or_create(conn, nome, cor=None):
        if not nome or not str(nome).strip():
            return None
        nome_clean = str(nome).strip().upper()
        cur = conn.cursor()
        cur.execute("SELECT id FROM operadoras WHERE nome = ?", (nome_clean,))
        row = cur.fetchone()
        if row:
            return row['id']
        
        cor_final = cor if cor else '#3388ff'
        cur.execute("INSERT INTO operadoras (nome, cor_padrao) VALUES (?, ?)", (nome_clean, cor_final))
        return cur.lastrowid

    @staticmethod
    def get_all():
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM operadoras ORDER BY nome ASC")
        rows = cur.fetchall()
        conn.close()
        return rows


class MunicipioModel:
    @staticmethod
    def get_or_create(conn, nome, uf='MG'):
        if not nome or not str(nome).strip():
            return None
        # Preserva exatamente a grafia oficial recebida de NM_MUN.
        nome_clean = str(nome).strip()
        uf_clean = str(uf).strip().upper() if uf else 'MG'
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM municipios WHERE nome = ? COLLATE NOCASE AND uf = ?",
            (nome_clean, uf_clean)
        )
        row = cur.fetchone()
        if row:
            return row['id']
        cur.execute("INSERT INTO municipios (nome, uf) VALUES (?, ?)", (nome_clean, uf_clean))
        return cur.lastrowid

    @staticmethod
    def get_all():
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM municipios ORDER BY nome ASC")
        rows = cur.fetchall()
        conn.close()
        return rows


class TecnologiaModel:
    @staticmethod
    def get_or_create(conn, nome):
        if not nome or not str(nome).strip():
            return None
        nome_clean = str(nome).strip().upper()
        cur = conn.cursor()
        cur.execute("SELECT id FROM tecnologias WHERE nome = ?", (nome_clean,))
        row = cur.fetchone()
        if row:
            return row['id']
        cur.execute("INSERT INTO tecnologias (nome) VALUES (?)", (nome_clean,))
        return cur.lastrowid

    @staticmethod
    def get_all():
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM tecnologias ORDER BY nome ASC")
        rows = cur.fetchall()
        conn.close()
        return rows


class ImportacaoModel:
    @staticmethod
    def create(conn, nome_arquivo, nome_original, aba_selecionada, total_registros, registros_importados, registros_erro, status, detalhes_erro=None, projeto_id=None):
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO importacoes (
                nome_arquivo, nome_original, aba_selecionada, total_registros,
                registros_importados, registros_erro, status, detalhes_erro, projeto_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (nome_arquivo, nome_original, aba_selecionada, total_registros, registros_importados, registros_erro, status, detalhes_erro, projeto_id))
        return cur.lastrowid

    @staticmethod
    def get_latest(projeto_id):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM importacoes WHERE projeto_id = ? ORDER BY data_importacao DESC LIMIT 1", (projeto_id,))
        row = cur.fetchone()
        conn.close()
        return row

    @staticmethod
    def get_all(projeto_id):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM importacoes WHERE projeto_id = ? ORDER BY data_importacao DESC", (projeto_id,))
        rows = cur.fetchall()
        conn.close()
        return rows

    @staticmethod
    def delete_by_id(importacao_id, projeto_id):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM antenas WHERE importacao_id = ? AND projeto_id = ?", (importacao_id, projeto_id))
        cur.execute("DELETE FROM importacoes WHERE id = ? AND projeto_id = ?", (importacao_id, projeto_id))
        deleted = cur.rowcount > 0
        conn.commit()
        conn.close()
        return deleted


class AntenaModel:
    @staticmethod
    def insert(conn, data_dict):
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO antenas (
                importacao_id, ponto, nome, descricao, crime,
                operadora_id, municipio_id, tecnologia_id,
                latitude, longitude, azimute, distancia, raio,
                opacidade, borda, preenchimento, data_registro,
                hora_registro, fonte, plotar, icone, projeto_id
            ) VALUES (
                :importacao_id, :ponto, :nome, :descricao, :crime,
                :operadora_id, :municipio_id, :tecnologia_id,
                :latitude, :longitude, :azimute, :distancia, :raio,
                :opacidade, :borda, :preenchimento, :data_registro,
                :hora_registro, :fonte, :plotar, :icone, :projeto_id
            )
        """, data_dict)
        return cur.lastrowid
