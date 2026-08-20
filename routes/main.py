from flask import Blueprint, g, render_template
from services.antenna_service import AntennaService

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Dashboard principal da aplicação com estatísticas em tempo real do SQLite."""
    project_id = g.active_project['id'] if g.active_project else None
    metrics = AntennaService.get_dashboard_metrics(project_id)
    return render_template('index.html', metrics=metrics)
