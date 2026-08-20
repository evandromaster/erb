from flask import Blueprint, g, jsonify, request
from services.antenna_service import AntennaService

api_bp = Blueprint('api', __name__, url_prefix='/api')

def _active_project_id():
    return g.active_project['id'] if g.active_project else None

def _project_required():
    return jsonify({'success': False, 'error': 'Selecione um projeto ativo.'}), 409

@api_bp.route('/metrics')
def metrics():
    """Retorna métricas consolidadas em JSON."""
    if not _active_project_id(): return _project_required()
    data = AntennaService.get_dashboard_metrics(_active_project_id())
    # Converte sqlite3.Row para dict
    result = {
        'total_antenas': data['total_antenas'],
        'total_municipios': data['total_municipios'],
        'total_operadoras': data['total_operadoras'],
        'ultima_importacao': dict(data['ultima_importacao']) if data['ultima_importacao'] else None,
        'dist_operadoras': [dict(r) for r in data['dist_operadoras']],
        'dist_tecnologias': [dict(r) for r in data['dist_tecnologias']]
    }
    return jsonify(result)

@api_bp.route('/antenas')
def list_antenas_json():
    """Retorna a lista de antenas filtradas em formato JSON com propriedades geográficas."""
    filters = {
        'operadora_id': request.args.get('operadora_id'),
        'municipio_id': request.args.get('municipio_id'),
        'tecnologia_id': request.args.get('tecnologia_id'),
        'crime': request.args.get('crime'),
        'fonte': request.args.get('fonte'),
        'q': request.args.get('q'),
        'plotar': request.args.get('plotar')
    }
    if not _active_project_id(): return _project_required()
    rows, total_count = AntennaService.get_antennas(_active_project_id(), filters=filters, return_all=True)
    return jsonify({
        'total': total_count,
        'data': [dict(r) for r in rows]
    })

@api_bp.route('/filters')
def get_filters_json():
    """Retorna as opções de filtro para renderização dinâmica no cliente."""
    if not _active_project_id(): return _project_required()
    options = AntennaService.get_filter_options(_active_project_id())
    return jsonify({
        'operadoras': [dict(r) for r in options['operadoras']],
        'municipios': [dict(r) for r in options['municipios']],
        'tecnologias': [dict(r) for r in options['tecnologias']],
        'crimes': options['crimes'],
        'fontes': options['fontes']
    })
