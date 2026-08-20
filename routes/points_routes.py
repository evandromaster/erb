from flask import Blueprint, flash, g, jsonify, redirect, render_template, request, url_for

from services.point_service import PointService, PointValidationError


points_bp = Blueprint('points', __name__)


def _point_json(point):
    return dict(point) if point is not None else None

def _project_id():
    return g.active_project['id'] if g.active_project else None

def _project_required():
    return jsonify({'success': False, 'error': 'Selecione um projeto antes de gerenciar pontos.'}), 409


@points_bp.route('/pontos')
def list_points():
    if not _project_id():
        flash('Selecione um projeto antes de gerenciar pontos.', 'warning')
        return redirect(url_for('projects.list_projects'))
    return render_template(
        'pontos.html',
        pontos=PointService.get_all(_project_id()),
        point_types=PointService.ALLOWED_TYPES,
    )


@points_bp.route('/api/pontos', methods=['GET'])
def list_points_api():
    if not _project_id(): return _project_required()
    points = PointService.get_all(_project_id())
    return jsonify({'total': len(points), 'data': [_point_json(point) for point in points]})


@points_bp.route('/api/pontos', methods=['POST'])
def create_point():
    try:
        if not _project_id(): return _project_required()
        point = PointService.create(request.get_json(silent=True), _project_id(), g.current_user['id'])
        return jsonify({'success': True, 'data': _point_json(point)}), 201
    except PointValidationError as error:
        return jsonify({'success': False, 'error': str(error)}), 400


@points_bp.route('/api/pontos/<int:point_id>', methods=['GET'])
def get_point(point_id):
    if not _project_id(): return _project_required()
    point = PointService.get_by_id(point_id, _project_id())
    if point is None:
        return jsonify({'success': False, 'error': 'Ponto nao encontrado.'}), 404
    return jsonify({'success': True, 'data': _point_json(point)})


@points_bp.route('/api/pontos/<int:point_id>', methods=['PUT', 'PATCH'])
def update_point(point_id):
    try:
        if not _project_id(): return _project_required()
        point = PointService.update(point_id, request.get_json(silent=True), _project_id())
        if point is None:
            return jsonify({'success': False, 'error': 'Ponto nao encontrado.'}), 404
        return jsonify({'success': True, 'data': _point_json(point)})
    except PointValidationError as error:
        return jsonify({'success': False, 'error': str(error)}), 400


@points_bp.route('/api/pontos/<int:point_id>', methods=['DELETE'])
def delete_point(point_id):
    if not _project_id(): return _project_required()
    if not PointService.delete(point_id, _project_id()):
        return jsonify({'success': False, 'error': 'Ponto nao encontrado.'}), 404
    return jsonify({'success': True})
