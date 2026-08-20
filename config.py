import os
from pathlib import Path

class Config:
    """Configuração centralizada da aplicação Flask ERB Maps."""
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    MUNICIPIOS_GPKG = Path(BASE_DIR) / 'geo' / 'mg_municipios.gpkg'
    MUNICIPIOS_LAYER = os.environ.get('MUNICIPIOS_LAYER') or None
    
    # Segurança
    SECRET_KEY = os.environ.get('SECRET_KEY', 'erbs-secret-key-chv8471920-antenas-map')
    
    # Armazenamento e Banco de Dados
    DATABASE_FOLDER = os.path.join(BASE_DIR, 'database')
    DATABASE_PATH = os.path.join(DATABASE_FOLDER, 'antenas.db')
    CONTROL_DATABASE_PATH = os.path.join(DATABASE_FOLDER, 'control.db')
    
    # Uploads
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB máximo
    ALLOWED_EXTENSIONS = {'xlsx', 'xls'}
    USER_UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads', 'users')
    ALLOWED_PHOTO_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}
    MAX_PHOTO_SIZE = 2 * 1024 * 1024
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', '').lower() in {'1', 'true', 'yes'}
    
    # Configurações de Mapa e Folium
    DEFAULT_LOCATION = [-20.147248, -44.888133]  # Ponto padrão (Minas Gerais / Divinópolis)
    DEFAULT_ZOOM = 12
    MAPBOX_TOKEN = os.environ.get('MAPBOX_TOKEN', 'pk.eyJ1IjoiZXZhbmRyb21hc3RlciIsImEiOiJjamVpcTM1dW4zN2ZqMnFxZWhyMmVxazc0In0.yRc9A7HcmbNaQGW5teN1TA')

    @classmethod
    def init_app(cls, app):
        """Garante que os diretórios necessários existam no sistema de arquivos."""
        os.makedirs(cls.DATABASE_FOLDER, exist_ok=True)
        os.makedirs(cls.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(os.path.join(cls.BASE_DIR, 'static', 'images'), exist_ok=True)
        os.makedirs(cls.USER_UPLOAD_FOLDER, exist_ok=True)
