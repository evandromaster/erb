from flask import Blueprint, g, render_template, request, Response

from services.antenna_service import AntennaService
from services.map_service import MapService
from services.point_service import PointService


map_bp = Blueprint('map', __name__)


def _project_id():
    return g.active_project['id'] if g.active_project else None


def _get_filters():
    return {
        'operadora_id': request.args.get('operadora_id'),
        'municipio_id': request.args.get('municipio_id'),
        'tecnologia_id': request.args.get('tecnologia_id'),
        'crime': request.args.get('crime'), 'fonte': request.args.get('fonte'),
        'q': request.args.get('q'), 'plotar': request.args.get('plotar', '1'),
    }


def _generate_current_map(enable_point_selection=False):
    custom_center = None
    zoom = None
    focus_id = request.args.get('focus_id')
    if focus_id:
        antenna = AntennaService.get_antenna_by_id(focus_id, _project_id())
        if antenna:
            custom_center = [antenna['latitude'], antenna['longitude']]
            zoom = 16
    antennas, _ = AntennaService.get_antennas(
        _project_id(), filters=_get_filters(), return_all=True
    )
    return MapService.generate_map(
        antennas=antennas,
        points=PointService.get_all(_project_id()),
        enable_cluster=request.args.get('cluster') == '1',
        custom_center=custom_center, zoom=zoom,
        enable_point_selection=enable_point_selection and bool(_project_id()),
    )


@map_bp.route('/map')
def view_map():
    filters = _get_filters()
    _, total_count = AntennaService.get_antennas(
        _project_id(), filters=filters, return_all=True
    )
    return render_template(
        'map.html',
        filter_options=AntennaService.get_filter_options(_project_id()),
        current_filters=filters, total_count=total_count,
        query_string=request.query_string.decode('utf-8'),
        point_types=PointService.ALLOWED_TYPES,
    )


@map_bp.route('/map/embed')
def embed_map():
    return Response(
        _generate_current_map(enable_point_selection=True).get_root().render(),
        mimetype='text/html',
    )


@map_bp.route('/map/export')
def export_map():
    return Response(
        _generate_current_map().get_root().render(), mimetype='text/html',
        headers={'Content-Disposition': 'attachment; filename="mapa_erbs.html"'},
    )
