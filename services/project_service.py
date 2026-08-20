from database import get_db_connection


class ProjectValidationError(ValueError):
    pass


class ProjectService:
    MAX_NAME_LENGTH = 120

    @classmethod
    def validate_name(cls, name):
        clean_name = ' '.join(str(name or '').split())
        if not clean_name:
            raise ProjectValidationError('Informe o nome do projeto.')
        if len(clean_name) > cls.MAX_NAME_LENGTH:
            raise ProjectValidationError(
                f'O nome deve ter no maximo {cls.MAX_NAME_LENGTH} caracteres.'
            )
        return clean_name

    @staticmethod
    def get_all():
        conn = get_db_connection()
        try:
            return conn.execute(
                "SELECT * FROM projetos ORDER BY nome COLLATE NOCASE"
            ).fetchall()
        finally:
            conn.close()

    @staticmethod
    def get_by_id(project_id):
        if not project_id:
            return None
        conn = get_db_connection()
        try:
            return conn.execute(
                "SELECT * FROM projetos WHERE id = ?", (project_id,)
            ).fetchone()
        finally:
            conn.close()

    @classmethod
    def create(cls, name):
        clean_name = cls.validate_name(name)
        conn = get_db_connection()
        try:
            existing = conn.execute(
                "SELECT * FROM projetos WHERE nome = ? COLLATE NOCASE", (clean_name,)
            ).fetchone()
            if existing:
                raise ProjectValidationError('Ja existe um projeto com esse nome.')
            cursor = conn.execute("INSERT INTO projetos (nome) VALUES (?)", (clean_name,))
            project_id = cursor.lastrowid
            conn.commit()
            return conn.execute(
                "SELECT * FROM projetos WHERE id = ?", (project_id,)
            ).fetchone()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def get_with_counts():
        conn = get_db_connection()
        try:
            return conn.execute("""
                SELECT p.*,
                       (SELECT COUNT(*) FROM antenas a WHERE a.projeto_id = p.id) AS total_antenas,
                       (SELECT COUNT(*) FROM pontos pt WHERE pt.projeto_id = p.id) AS total_pontos,
                       (SELECT COUNT(*) FROM importacoes i WHERE i.projeto_id = p.id) AS total_importacoes
                FROM projetos p
                ORDER BY p.nome COLLATE NOCASE
            """).fetchall()
        finally:
            conn.close()

    @classmethod
    def update(cls, project_id, name):
        clean_name = cls.validate_name(name)
        conn = get_db_connection()
        try:
            project = conn.execute(
                "SELECT id FROM projetos WHERE id = ?", (project_id,)
            ).fetchone()
            if project is None:
                return None
            duplicate = conn.execute(
                "SELECT id FROM projetos WHERE nome = ? COLLATE NOCASE AND id != ?",
                (clean_name, project_id),
            ).fetchone()
            if duplicate:
                raise ProjectValidationError('Ja existe um projeto com esse nome.')
            conn.execute(
                """
                UPDATE projetos SET nome = ?, data_atualizacao = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (clean_name, project_id),
            )
            conn.commit()
            return conn.execute(
                "SELECT * FROM projetos WHERE id = ?", (project_id,)
            ).fetchone()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def delete_if_empty(project_id):
        conn = get_db_connection()
        try:
            project = conn.execute(
                "SELECT id FROM projetos WHERE id = ?", (project_id,)
            ).fetchone()
            if project is None:
                return 'not_found'
            for table in ('antenas', 'pontos', 'importacoes'):
                if conn.execute(
                    f"SELECT 1 FROM {table} WHERE projeto_id = ? LIMIT 1", (project_id,)
                ).fetchone():
                    return 'not_empty'
            conn.execute("DELETE FROM projetos WHERE id = ?", (project_id,))
            conn.commit()
            return 'deleted'
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
