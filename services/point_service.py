import math

from database import get_db_connection


class PointValidationError(ValueError):
    """Erro de validacao seguro para ser apresentado ao usuario."""


class PointService:
    ALLOWED_TYPES = ('Casa', 'Trabalho', 'Comparsa', 'Empresa', 'Antena', 'Crime', 'Outro')
    MAX_DESCRIPTION_LENGTH = 1000

    @classmethod
    def validate(cls, payload):
        if not isinstance(payload, dict):
            raise PointValidationError('Dados do ponto invalidos.')

        tipo = str(payload.get('tipo') or '').strip()
        if tipo not in cls.ALLOWED_TYPES:
            raise PointValidationError('Selecione um tipo de ponto valido.')

        descricao = str(payload.get('descricao') or '').strip()
        if not descricao:
            raise PointValidationError('A descricao e obrigatoria.')
        if len(descricao) > cls.MAX_DESCRIPTION_LENGTH:
            raise PointValidationError(
                f'A descricao deve ter no maximo {cls.MAX_DESCRIPTION_LENGTH} caracteres.'
            )

        try:
            latitude = float(payload.get('latitude'))
            longitude = float(payload.get('longitude'))
        except (TypeError, ValueError):
            raise PointValidationError('Latitude e longitude devem ser numeros validos.')

        if not math.isfinite(latitude) or not -90 <= latitude <= 90:
            raise PointValidationError('Latitude deve estar entre -90 e 90.')
        if not math.isfinite(longitude) or not -180 <= longitude <= 180:
            raise PointValidationError('Longitude deve estar entre -180 e 180.')

        return {
            'tipo': tipo,
            'descricao': descricao,
            'latitude': latitude,
            'longitude': longitude,
        }

    @staticmethod
    def get_all(projeto_id):
        if not projeto_id:
            return []
        conn = get_db_connection()
        try:
            return conn.execute(
                "SELECT * FROM pontos WHERE projeto_id = ? ORDER BY data_criacao DESC, id DESC",
                (projeto_id,)
            ).fetchall()
        finally:
            conn.close()

    @staticmethod
    def get_by_id(point_id, projeto_id):
        conn = get_db_connection()
        try:
            return conn.execute(
                "SELECT * FROM pontos WHERE id = ? AND projeto_id = ?",
                (point_id, projeto_id)
            ).fetchone()
        finally:
            conn.close()

    @classmethod
    def create(cls, payload, projeto_id, created_by=None):
        if not projeto_id:
            raise PointValidationError('Selecione um projeto antes de adicionar pontos.')
        data = cls.validate(payload)
        conn = get_db_connection()
        try:
            cursor = conn.execute(
                """
                INSERT INTO pontos (tipo, descricao, latitude, longitude, projeto_id, created_by)
                VALUES (:tipo, :descricao, :latitude, :longitude, :projeto_id, :created_by)
                """,
                {**data, 'projeto_id': projeto_id, 'created_by': created_by},
            )
            point_id = cursor.lastrowid
            conn.commit()
            return conn.execute(
                "SELECT * FROM pontos WHERE id = ? AND projeto_id = ?",
                (point_id, projeto_id)
            ).fetchone()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @classmethod
    def update(cls, point_id, payload, projeto_id):
        data = cls.validate(payload)
        data['id'] = point_id
        data['projeto_id'] = projeto_id
        conn = get_db_connection()
        try:
            cursor = conn.execute(
                """
                UPDATE pontos SET
                    tipo = :tipo,
                    descricao = :descricao,
                    latitude = :latitude,
                    longitude = :longitude,
                    data_atualizacao = CURRENT_TIMESTAMP
                WHERE id = :id AND projeto_id = :projeto_id
                """,
                data,
            )
            if cursor.rowcount == 0:
                conn.rollback()
                return None
            conn.commit()
            return conn.execute(
                "SELECT * FROM pontos WHERE id = ? AND projeto_id = ?",
                (point_id, projeto_id)
            ).fetchone()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def delete(point_id, projeto_id):
        conn = get_db_connection()
        try:
            cursor = conn.execute(
                "DELETE FROM pontos WHERE id = ? AND projeto_id = ?",
                (point_id, projeto_id)
            )
            if cursor.rowcount == 0:
                conn.rollback()
                return False
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
