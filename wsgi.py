# ==============================================================================
# ARQUIVO DE CONFIGURAÇÃO WSGI PARA PYTHONANYWHERE
# ==============================================================================
# No PythonAnywhere, configure o arquivo WSGI na aba "Web" apontando para este arquivo
# ou copie o conteúdo abaixo para o arquivo /var/www/seu_usuario_pythonanywhere_com_wsgi.py

import sys
import os

# 1. Defina o caminho absoluto da pasta do seu projeto no PythonAnywhere
# Exemplo: /home/seu_usuario/erbs
project_home = os.path.dirname(os.path.abspath(__file__))

if project_home not in sys.path:
    sys.path.insert(0, project_home)

# 2. Configurações de Variáveis de Ambiente (Opcional, mas recomendado)
os.environ['SECRET_KEY'] = 'erbs-prod-secret-key-pythonanywhere-948271'

# 3. Importa e instancia a aplicação Flask
from app import create_app

# O PythonAnywhere procura obrigatoriamente por um objeto chamado 'application'
application = create_app()
