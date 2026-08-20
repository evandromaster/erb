import os
from flask import Flask, abort, g, redirect, render_template, request, session, url_for
from config import Config
from database import init_db
from control_database import get_control_connection, init_control_db, sync_projects
from auth import ROLE_LEVEL, user_has_project_access

def create_app(config_class=Config):
    """Fábrica de aplicação Flask com inicialização modular de blueprints e banco de dados."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Garantir que diretórios de storage e banco existam
    config_class.init_app(app)

    # Inicializar o banco SQLite com as tabelas e índices
    init_db()
    init_control_db()

    # Registrar Blueprints
    from routes.main import main_bp
    from routes.upload import upload_bp
    from routes.map_routes import map_bp
    from routes.antennas_routes import antennas_bp
    from routes.api import api_bp
    from routes.points_routes import points_bp
    from routes.projects_routes import projects_bp
    from routes.auth_routes import auth_bp
    from routes.admin_routes import admin_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(map_bp)
    app.register_blueprint(antennas_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(points_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)

    from services.project_service import ProjectService

    @app.before_request
    def load_active_project():
        g.current_user = None
        user_id = session.get('user_id')
        if user_id:
            conn = get_control_connection()
            try:
                g.current_user = conn.execute('SELECT * FROM users WHERE id=? AND activated=1',(user_id,)).fetchone()
            finally: conn.close()
            if g.current_user is None: session.clear()
            else:
                session['username'], session['type_user'] = g.current_user['username'], g.current_user['type_user']
        if request.endpoint not in {'auth.login','auth.register','static'} and not g.current_user:
            if request.path.startswith('/api/'): abort(401)
            return redirect(url_for('auth.login',next=request.path))
        sync_projects()
        """Resolve o ID da sessao contra o banco antes de qualquer operacao."""
        project_id = session.get('active_project_id')
        g.active_project = ProjectService.get_by_id(project_id) if project_id else None
        if project_id and (g.active_project is None or not g.current_user or not user_has_project_access(g.current_user['id'],project_id)):
            session.pop('active_project_id', None)
            g.active_project = None
            if g.current_user:
                abort(403)
        if not g.current_user: return None
        admin_only={'admin.index','admin.edit_user','admin.update_user','admin.reset_password','admin.delete_user','admin.set_project','admin.remove_project','admin.project_status','projects.list_projects','projects.create_project','projects.edit_project','projects.delete_project'}
        editor_only={'upload.upload_file','upload.get_sheets','points.create_point','points.update_point','points.delete_point','antennas.delete_antenna','antennas.delete_history'}
        if request.endpoint in admin_only and g.current_user['type_user']!='admin': abort(403)
        if request.endpoint in editor_only and ROLE_LEVEL[g.current_user['type_user']]<2: abort(403)
        if request.endpoint in editor_only and g.active_project and not user_has_project_access(g.current_user['id'],g.active_project['id'],'editor'):
            abort(403)

    @app.context_processor
    def inject_project_context():
        projects=[]
        if g.get('current_user'):
            conn=get_control_connection()
            try:
                if g.current_user['type_user']=='admin':
                    projects=conn.execute('SELECT id,name AS nome FROM projects WHERE activated=1 ORDER BY name').fetchall()
                else:
                    projects=conn.execute('''SELECT p.id,p.name AS nome FROM projects p JOIN user_projects up ON up.project_id=p.id WHERE up.user_id=? AND p.activated=1 ORDER BY p.name''',(g.current_user['id'],)).fetchall()
            finally: conn.close()
        return {
            'active_project': g.get('active_project'),
            'available_projects': projects,
            'current_user': g.get('current_user'),
        }

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('403.html'), 403

    # Tratamento de Erros Amigável (Não exibe tracebacks crus para o usuário)
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('base.html', content="""
            <div class="result-wrapper">
                <div class="result-card">
                    <div class="result-header header-warning">
                        <div class="result-icon">🔍</div>
                        <h1 class="result-title">Página Não Encontrada (404)</h1>
                    </div>
                    <div class="result-body text-center">
                        <p>O recurso solicitado não existe ou foi movido.</p>
                        <a href="/" class="btn btn-primary mt-4">Voltar ao Início</a>
                    </div>
                </div>
            </div>
        """), 404

    @app.errorhandler(413)
    def request_entity_too_large(e):
        return render_template('base.html', content="""
            <div class="result-wrapper">
                <div class="result-card">
                    <div class="result-header header-danger">
                        <div class="result-icon">⚠️</div>
                        <h1 class="result-title">Arquivo Muito Grande (413)</h1>
                    </div>
                    <div class="result-body text-center">
                        <p>O arquivo enviado excede o limite máximo permitido de 16MB.</p>
                        <a href="/upload" class="btn btn-primary mt-4">Tentar Novamente</a>
                    </div>
                </div>
            </div>
        """), 413

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('base.html', content="""
            <div class="result-wrapper">
                <div class="result-card">
                    <div class="result-header header-danger">
                        <div class="result-icon">🚨</div>
                        <h1 class="result-title">Erro Interno no Servidor (500)</h1>
                    </div>
                    <div class="result-body text-center">
                        <p>Ocorreu uma falha inesperada durante o processamento da sua solicitação.</p>
                        <a href="/" class="btn btn-primary mt-4">Voltar ao Início</a>
                    </div>
                </div>
            </div>
        """), 500

    return app

app = create_app()

if __name__ == '__main__':
    # Execução local
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
