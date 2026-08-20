import pandas as pd
import unicodedata
from database import get_db_connection
from models.models import OperadoraModel, MunicipioModel, TecnologiaModel, ImportacaoModel, AntenaModel
from services.coordinate_service import CoordinateParser
from services.municipality_service import MunicipalityService

def normalize_col_name(col):
    """Normaliza nome de coluna removendo acentos, espaços e convertendo para minúsculas."""
    if not isinstance(col, str):
        col = str(col)
    nfkd = unicodedata.normalize('NFKD', col)
    ascii_str = "".join([c for c in nfkd if not unicodedata.combining(c)])
    return ascii_str.strip().lower().replace(' ', '_').replace('-', '_')

# Dicionário de mapeamento de variações de cabeçalhos
COLUMN_MAPPINGS = {
    'latitude': ['latitude', 'lat', 'lat_erb', 'latitud', 'lat_wgs84', 'y'],
    'longitude': ['longitude', 'long', 'lon', 'lng', 'long_erb', 'long_wgs84', 'x'],
    'ponto': ['ponto', 'ponto_id', 'id', 'num', 'numero', 'codigo', 'item'],
    'nome': ['nome', 'alvo', 'erb', 'nome_erb', 'estacao', 'site', 'local', 'nome_estacao'],
    'descricao': ['descricao', 'desc', 'observacao', 'obs', 'detalhes', 'posto', 'grad', 'info'],
    'crime': ['crime', 'delito', 'inquerito', 'processo', 'reds', 'ip', 'ocorrencia', 'bo'],
    'azimute': ['azimute', 'azimuth', 'direcao', 'direction', 'ang_central', 'dir'],
    'distancia': ['distancia', 'alcance', 'radius', 'raio_metros', 'dist', 'cobertura_m', 'range'],
    'raio': ['raio', 'abertura', 'arc', 'angulo', 'angulo_abertura', 'beamwidth'],
    'opacidade': ['opacidade', 'opacity', 'transparencia', 'alpha'],
    'borda': ['borda', 'cor_borda', 'color', 'stroke', 'stroke_color'],
    'preenchimento': ['preenchimento', 'cor_preenchimento', 'cor', 'fill', 'fill_color'],
    'data_registro': ['data', 'date', 'data_hora', 'dt_fato', 'dt'],
    'hora_registro': ['hora', 'time', 'hr', 'horario'],
    'operadora': ['operadora', 'carrier', 'empresa', 'telecom'],
    'municipio': ['municipio', 'cidade', 'city', 'localidade'],
    'uf': ['uf', 'estado', 'state'],
    'tecnologia': ['tecnologia', 'tech', 'tipo_rede', 'geracao', 'rede'],
    'fonte': ['fonte', 'tipo', 'origem_destino', 'origem', 'destino'],
    'plotar': ['plotar', 'exibir', 'ativo', 'show', 'visivel']
}

class ExcelService:
    @staticmethod
    def get_sheet_names(filepath):
        """Retorna os nomes de todas as abas presentes na planilha Excel."""
        try:
            with pd.ExcelFile(filepath) as xl:
                return list(xl.sheet_names)
        except Exception as e:
            return []

    @staticmethod
    def process_excel(filepath, filename, original_filename, sheet_name=None, projeto_id=None):
        """
        Lê e valida a planilha, inserindo os dados no SQLite.
        Retorna um dicionário com o resumo da importação.
        """
        try:
            if not projeto_id:
                return {
                    'success': False,
                    'message': 'Selecione um projeto antes de importar os dados.',
                    'total': 0, 'imported': 0, 'errors': 0,
                    'error_list': ['Nenhum projeto ativo.']
                }
            with pd.ExcelFile(filepath) as xl:
                if not sheet_name or sheet_name not in xl.sheet_names:
                    sheet_name = xl.sheet_names[0]
                df = pd.read_excel(xl, sheet_name=sheet_name)
        except Exception as e:
            return {
                'success': False,
                'message': f"Erro ao abrir arquivo Excel: {str(e)}",
                'total': 0,
                'imported': 0,
                'errors': 0,
                'error_list': [str(e)]
            }

        if df.empty:
            return {
                'success': False,
                'message': "A planilha selecionada está vazia.",
                'total': 0,
                'imported': 0,
                'errors': 0,
                'error_list': ["A aba não contém linhas de dados."]
            }

        # Mapeamento de colunas do DataFrame para os campos do banco
        normalized_cols = {normalize_col_name(c): c for c in df.columns}
        field_to_col = {}
        
        for field, aliases in COLUMN_MAPPINGS.items():
            for alias in aliases:
                norm_alias = normalize_col_name(alias)
                if norm_alias in normalized_cols:
                    field_to_col[field] = normalized_cols[norm_alias]
                    break

        # Validação de campos obrigatórios mínimos
        if 'latitude' not in field_to_col or 'longitude' not in field_to_col:
            missing = []
            if 'latitude' not in field_to_col: missing.append('LATITUDE')
            if 'longitude' not in field_to_col: missing.append('LONGITUDE')
            return {
                'success': False,
                'message': f"Colunas obrigatórias ausentes na planilha: {', '.join(missing)}.",
                'total': len(df),
                'imported': 0,
                'errors': len(df),
                'error_list': [f"Cabeçalho inválido. É obrigatório ter colunas para Latitude e Longitude."]
            }

        conn = get_db_connection()
        error_list = []
        imported_count = 0
        total_rows = len(df)

        # Normaliza as coordenadas uma vez e resolve todos os municipios em lote.
        # A coluna de municipio da planilha e ignorada: NM_MUN e a fonte oficial.
        parsed_coordinates = pd.DataFrame(index=df.index)
        parsed_coordinates['latitude'] = df[field_to_col['latitude']].map(
            lambda value: CoordinateParser.parse_coordinate(value, is_latitude=True)
        )
        parsed_coordinates['longitude'] = df[field_to_col['longitude']].map(
            lambda value: CoordinateParser.parse_coordinate(value, is_latitude=False)
        )
        spatial_municipalities = MunicipalityService.resolve_batch(parsed_coordinates)

        try:
            # Iniciar transação
            for idx, row in df.iterrows():
                row_num = idx + 2  # Linha visual no Excel (1-index + cabeçalho)
                
                raw_lat = row[field_to_col['latitude']]
                raw_lon = row[field_to_col['longitude']]
                
                lat = parsed_coordinates.at[idx, 'latitude']
                lon = parsed_coordinates.at[idx, 'longitude']
                
                if lat is None or lon is None:
                    err_msg = f"Linha {row_num}: Coordenadas inválidas (Lat: '{raw_lat}', Lon: '{raw_lon}')."
                    error_list.append(err_msg)
                    continue

                # Extração e normalização dos demais campos
                def get_val(field_name, default=None):
                    if field_name in field_to_col:
                        val = row[field_to_col[field_name]]
                        if pd.isna(val):
                            return default
                        return val
                    return default

                # Operadora, Município, Tecnologia
                op_nome = get_val('operadora')
                mun_nome = spatial_municipalities.at[idx]
                uf_nome = 'MG'
                tec_nome = get_val('tecnologia')
                
                # Cores
                cor_preenchimento = str(get_val('preenchimento', '#FFFF00')).strip()
                if not cor_preenchimento.startswith('#') and len(cor_preenchimento) == 6:
                    cor_preenchimento = f"#{cor_preenchimento}"
                elif not cor_preenchimento.startswith('#') and len(cor_preenchimento) not in [4, 7]:
                    cor_preenchimento = '#FFFF00'

                cor_borda = str(get_val('borda', '#FF0000')).strip()
                if not cor_borda.startswith('#') and len(cor_borda) == 6:
                    cor_borda = f"#{cor_borda}"
                elif not cor_borda.startswith('#') and len(cor_borda) not in [4, 7]:
                    cor_borda = '#FF0000'

                # Obter ou criar chaves estrangeiras
                operadora_id = OperadoraModel.get_or_create(conn, op_nome, cor_preenchimento) if op_nome else None
                municipio_id = (
                    MunicipioModel.get_or_create(conn, mun_nome, uf_nome)
                    if pd.notna(mun_nome) and str(mun_nome).strip()
                    else None
                )
                tecnologia_id = TecnologiaModel.get_or_create(conn, tec_nome) if tec_nome else None

                # Azimute, Distância, Raio (abertura)
                try:
                    azimute = float(get_val('azimute', 0))
                    azimute = azimute % 360
                except (ValueError, TypeError):
                    azimute = 0.0

                try:
                    distancia = float(get_val('distancia', 1000))
                    if distancia <= 0: distancia = 1000.0
                except (ValueError, TypeError):
                    distancia = 1000.0

                try:
                    raio = float(get_val('raio', 60))
                    if raio <= 0 or raio > 360: raio = 60.0
                except (ValueError, TypeError):
                    raio = 60.0

                try:
                    opacidade_raw = get_val('opacidade', 0.2)
                    opacidade = float(opacidade_raw)
                    if opacidade > 1.0:
                        opacidade = opacidade / 100.0  # Se veio em porcentagem como 80 -> 0.8
                    if opacidade < 0.05:
                        opacidade = 0.1
                except (ValueError, TypeError):
                    opacidade = 0.2

                # Ponto ID
                try:
                    ponto_val = int(get_val('ponto', idx + 1))
                except (ValueError, TypeError):
                    ponto_val = idx + 1

                # Plotar (SIM/NÃO, 1/0, TRUE/FALSE)
                plotar_raw = str(get_val('plotar', 'SIM')).strip().upper()
                plotar_val = 1 if plotar_raw in ['SIM', '1', 'TRUE', 'S', 'YES', 'Y'] else 0

                # Formatar Datas e Horas
                data_val = get_val('data_registro', '')
                if isinstance(data_val, pd.Timestamp):
                    data_val = data_val.strftime('%d/%m/%Y')
                else:
                    data_val = str(data_val).strip() if data_val else ''

                hora_val = get_val('hora_registro', '')
                if isinstance(hora_val, pd.Timestamp):
                    hora_val = hora_val.strftime('%H:%M:%S')
                else:
                    hora_val = str(hora_val).strip() if hora_val else ''

                # Se a importação ainda não teve ID gerado, criamos a importação
                if imported_count == 0:
                    importacao_id = ImportacaoModel.create(
                        conn=conn,
                        nome_arquivo=filename,
                        nome_original=original_filename,
                        aba_selecionada=sheet_name,
                        total_registros=total_rows,
                        registros_importados=0,
                        registros_erro=0,
                        status='processando',
                        projeto_id=projeto_id
                    )

                # Montagem do dicionário para inserção
                antena_dict = {
                    'importacao_id': importacao_id,
                    'ponto': ponto_val,
                    'nome': str(get_val('nome', f"Ponto {ponto_val}")).strip(),
                    'descricao': str(get_val('descricao', '')).strip(),
                    'crime': str(get_val('crime', '')).strip(),
                    'operadora_id': operadora_id,
                    'municipio_id': municipio_id,
                    'tecnologia_id': tecnologia_id,
                    'latitude': lat,
                    'longitude': lon,
                    'azimute': azimute,
                    'distancia': distancia,
                    'raio': raio,
                    'opacidade': opacidade,
                    'borda': cor_borda,
                    'preenchimento': cor_preenchimento,
                    'data_registro': data_val,
                    'hora_registro': hora_val,
                    'fonte': str(get_val('fonte', '')).strip(),
                    'plotar': plotar_val,
                    'icone': 'antena1.png',
                    'projeto_id': projeto_id
                }

                AntenaModel.insert(conn, antena_dict)
                imported_count += 1

            # Atualiza o registro da importação com totais consolidados
            status_final = 'sucesso' if len(error_list) == 0 else ('parcial' if imported_count > 0 else 'erro')
            detalhes_erro_str = "\n".join(error_list[:50]) if error_list else None
            
            if imported_count > 0:
                cur = conn.cursor()
                cur.execute("""
                    UPDATE importacoes SET
                        registros_importados = ?,
                        registros_erro = ?,
                        status = ?,
                        detalhes_erro = ?
                    WHERE id = ?
                """, (imported_count, len(error_list), status_final, detalhes_erro_str, importacao_id))
            else:
                # Se nada foi importado
                importacao_id = ImportacaoModel.create(
                    conn=conn,
                    nome_arquivo=filename,
                    nome_original=original_filename,
                    aba_selecionada=sheet_name,
                    total_registros=total_rows,
                    registros_importados=0,
                    registros_erro=len(error_list),
                    status='erro',
                    detalhes_erro=detalhes_erro_str,
                    projeto_id=projeto_id
                )

            conn.commit()
            
            return {
                'success': imported_count > 0,
                'importacao_id': importacao_id if imported_count > 0 else None,
                'message': f"Importação concluída: {imported_count} registros gravados com sucesso.",
                'total': total_rows,
                'imported': imported_count,
                'errors': len(error_list),
                'error_list': error_list
            }

        except Exception as e:
            conn.rollback()
            return {
                'success': False,
                'message': f"Erro no processamento do banco de dados: {str(e)}",
                'total': total_rows,
                'imported': imported_count,
                'errors': len(error_list) + 1,
                'error_list': error_list + [str(e)]
            }
        finally:
            conn.close()
