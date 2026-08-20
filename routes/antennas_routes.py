from flask import Blueprint, flash, g, jsonify, redirect, render_template, request, url_for

from models.models import ImportacaoModel
from services.antenna_service import AntennaService


antennas_bp = Blueprint('antennas', __name__)


def _project_id():
    return g.active_project['id'] if g.active_project else None


@antennas_bp.route('/antenas')
def list_antenas():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)
    filters = {
        'operadora_id': request.args.get('operadora_id'),
        'municipio_id': request.args.get('municipio_id'),
        'tecnologia_id': request.args.get('tecnologia_id'),
        'crime': request.args.get('crime'), 'fonte': request.args.get('fonte'),
        'q': request.args.get('q'), 'plotar': request.args.get('plotar'),
    }
    rows, total_items, total_pages = AntennaService.get_antennas(
        _project_id(), filters=filters, page=page, per_page=per_page
    )
    return render_template(
        'antenas.html', antenas=rows, page=page, total_pages=total_pages,
        total_items=total_items, per_page=per_page,
        filter_options=AntennaService.get_filter_options(_project_id()),
        current_filters=filters,
    )


@antennas_bp.route('/antenas/<int:antenna_id>')
def get_antenna_detail(antenna_id):
    antenna = AntennaService.get_antenna_by_id(antenna_id, _project_id())
    if not antenna:
        return jsonify({'error': 'Antena nao encontrada no projeto ativo.'}), 404
    return jsonify(dict(antenna))


@antennas_bp.route('/antenas/<int:antenna_id>/delete', methods=['POST'])
def delete_antenna(antenna_id):
    if AntennaService.delete_antenna(antenna_id, _project_id()):
        flash('Antena excluida com sucesso!', 'success')
    else:
        flash('Antena nao encontrada no projeto ativo.', 'warning')
    return redirect(request.referrer or url_for('antennas.list_antenas'))


@antennas_bp.route('/history')
def history():
    imports = ImportacaoModel.get_all(_project_id()) if _project_id() else []
    return render_template('history.html', importacoes=imports)


@antennas_bp.route('/history/<int:import_id>/delete', methods=['POST'])
def delete_history(import_id):
    if _project_id() and ImportacaoModel.delete_by_id(import_id, _project_id()):
        flash('Lote de importacao e registros associados excluidos com sucesso!', 'success')
    else:
        flash('Importacao nao encontrada no projeto ativo.', 'warning')
    return redirect(url_for('antennas.history'))
