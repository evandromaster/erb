import os
import uuid
from flask import Blueprint, g, render_template, request, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename
from config import Config
from services.excel_service import ExcelService
from database import get_db_connection

upload_bp = Blueprint('upload', __name__)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS

@upload_bp.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'GET':
        return render_template('upload.html')

    if not g.active_project:
        flash('Selecione um projeto antes de importar os dados.', 'warning')
        return redirect(url_for('projects.list_projects'))

    # Validação do arquivo na requisição
    if 'file' not in request.files:
        flash('Nenhum arquivo enviado.', 'danger')
        return redirect(request.url)

    file = request.files['file']
    if file.filename == '':
        flash('Nenhum arquivo selecionado.', 'warning')
        return redirect(request.url)

    if not allowed_file(file.filename):
        flash('Formato inválido! Por favor, envie apenas arquivos Excel (.xlsx ou .xls).', 'danger')
        return redirect(request.url)

    try:
        original_name = file.filename
        safe_name = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex[:8]}_{safe_name}"
        save_path = os.path.join(Config.UPLOAD_FOLDER, unique_filename)
        file.save(save_path)

        # Verificar se foi solicitada uma aba específica
        sheet_name = request.form.get('sheet_name', '').strip()
        if not sheet_name:
            sheet_name = None

        # Processar a planilha Excel
        result = ExcelService.process_excel(
            filepath=save_path,
            filename=unique_filename,
            original_filename=original_name,
            sheet_name=sheet_name,
            projeto_id=g.active_project['id']
        )

        return render_template('upload_result.html', result=result, original_name=original_name, sheet_name=sheet_name)

    except Exception as e:
        flash(f'Erro inesperado no servidor ao processar o upload: {str(e)}', 'danger')
        return redirect(request.url)

@upload_bp.route('/upload/sheets', methods=['POST'])
def get_sheets():
    """Endpoint AJAX para listar as abas de uma planilha antes de confirmar o envio."""
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'Nenhum arquivo enviado'}), 400
    
    file = request.files['file']
    if not allowed_file(file.filename):
        return jsonify({'success': False, 'error': 'Extensão inválida'}), 400

    try:
        temp_name = f"temp_{uuid.uuid4().hex[:8]}_{secure_filename(file.filename)}"
        temp_path = os.path.join(Config.UPLOAD_FOLDER, temp_name)
        file.save(temp_path)

        sheets = ExcelService.get_sheet_names(temp_path)

        # Deletar arquivo temporário de inspeção
        if os.path.exists(temp_path):
            os.remove(temp_path)

        return jsonify({'success': True, 'sheets': sheets})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
