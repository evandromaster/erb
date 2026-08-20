from urllib.parse import urlsplit

from flask import Blueprint, abort, flash, g, redirect, render_template, request, session, url_for
from auth import user_has_project_access

from services.project_service import ProjectService, ProjectValidationError


projects_bp = Blueprint('projects', __name__)


def _safe_destination(value):
    if value:
        parsed = urlsplit(value)
        if not parsed.scheme and not parsed.netloc and value.startswith('/'):
            return value
    return url_for('main.index')


@projects_bp.route('/projetos')
def list_projects():
    return render_template('projetos.html', projetos=ProjectService.get_with_counts())


@projects_bp.route('/projetos', methods=['POST'])
def create_project():
    try:
        project = ProjectService.create(request.form.get('nome'))
        session['active_project_id'] = project['id']
        flash(f"Projeto '{project['nome']}' criado e selecionado.", 'success')
        return redirect(url_for('projects.list_projects'))
    except ProjectValidationError as error:
        flash(str(error), 'danger')
        return redirect(url_for('projects.list_projects'))


@projects_bp.route('/projetos/selecionar', methods=['POST'])
def select_project():
    project_id = request.form.get('project_id', type=int)
    project = ProjectService.get_by_id(project_id)
    if project is None or not user_has_project_access(g.current_user['id'], project_id):
        session.pop('active_project_id', None)
        abort(403)
    else:
        session['active_project_id'] = project['id']
        flash(f"Projeto ativo: {project['nome']}", 'success')
    return redirect(_safe_destination(request.form.get('next')))


@projects_bp.route('/projetos/<int:project_id>/editar', methods=['POST'])
def edit_project(project_id):
    try:
        project = ProjectService.update(project_id, request.form.get('nome'))
        if project is None:
            flash('Projeto nao encontrado.', 'warning')
        else:
            flash(f"Projeto renomeado para '{project['nome']}'.", 'success')
    except ProjectValidationError as error:
        flash(str(error), 'danger')
    return redirect(url_for('projects.list_projects'))


@projects_bp.route('/projetos/<int:project_id>/excluir', methods=['POST'])
def delete_project(project_id):
    result = ProjectService.delete_if_empty(project_id)
    if result == 'deleted':
        if session.get('active_project_id') == project_id:
            session.pop('active_project_id', None)
        flash('Projeto excluido com sucesso.', 'success')
    elif result == 'not_empty':
        flash(
            'O projeto possui ERBs, pontos ou importacoes e nao pode ser excluido.',
            'warning',
        )
    else:
        flash('Projeto nao encontrado.', 'warning')
    return redirect(url_for('projects.list_projects'))
