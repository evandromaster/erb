from database import get_db_connection


class AntennaService:
    @staticmethod
    def get_dashboard_metrics(projeto_id):
        empty = {
            'total_antenas': 0, 'total_municipios': 0, 'total_operadoras': 0,
            'ultima_importacao': None, 'dist_operadoras': [],
            'dist_tecnologias': [], 'ultimas_importacoes': [],
        }
        if not projeto_id:
            return empty

        conn = get_db_connection()
        try:
            total_antenas = conn.execute(
                "SELECT COUNT(*) total FROM antenas WHERE projeto_id = ?", (projeto_id,)
            ).fetchone()['total']
            total_municipios = conn.execute(
                "SELECT COUNT(DISTINCT municipio_id) total FROM antenas WHERE projeto_id = ? AND municipio_id IS NOT NULL",
                (projeto_id,)
            ).fetchone()['total']
            total_operadoras = conn.execute(
                "SELECT COUNT(DISTINCT operadora_id) total FROM antenas WHERE projeto_id = ? AND operadora_id IS NOT NULL",
                (projeto_id,)
            ).fetchone()['total']
            ultima_importacao = conn.execute(
                "SELECT * FROM importacoes WHERE projeto_id = ? ORDER BY data_importacao DESC LIMIT 1",
                (projeto_id,)
            ).fetchone()
            dist_operadoras = conn.execute("""
                SELECT COALESCE(o.nome, 'NAO INFORMADA') operadora,
                       COALESCE(o.cor_padrao, '#6c757d') cor, COUNT(a.id) total
                FROM antenas a LEFT JOIN operadoras o ON a.operadora_id = o.id
                WHERE a.projeto_id = ?
                GROUP BY o.nome, o.cor_padrao ORDER BY total DESC
            """, (projeto_id,)).fetchall()
            dist_tecnologias = conn.execute("""
                SELECT COALESCE(t.nome, 'NAO INFORMADA') tecnologia, COUNT(a.id) total
                FROM antenas a LEFT JOIN tecnologias t ON a.tecnologia_id = t.id
                WHERE a.projeto_id = ?
                GROUP BY t.nome ORDER BY total DESC
            """, (projeto_id,)).fetchall()
            ultimas_importacoes = conn.execute(
                "SELECT * FROM importacoes WHERE projeto_id = ? ORDER BY data_importacao DESC LIMIT 5",
                (projeto_id,)
            ).fetchall()
            return {
                'total_antenas': total_antenas,
                'total_municipios': total_municipios,
                'total_operadoras': total_operadoras,
                'ultima_importacao': ultima_importacao,
                'dist_operadoras': dist_operadoras,
                'dist_tecnologias': dist_tecnologias,
                'ultimas_importacoes': ultimas_importacoes,
            }
        finally:
            conn.close()

    @staticmethod
    def get_filter_options(projeto_id):
        if not projeto_id:
            return {'operadoras': [], 'municipios': [], 'tecnologias': [], 'crimes': [], 'fontes': []}
        conn = get_db_connection()
        try:
            operadoras = conn.execute("""
                SELECT DISTINCT o.id, o.nome FROM operadoras o
                JOIN antenas a ON a.operadora_id = o.id
                WHERE a.projeto_id = ? ORDER BY o.nome
            """, (projeto_id,)).fetchall()
            municipios = conn.execute("""
                SELECT DISTINCT m.id, m.nome, m.uf FROM municipios m
                JOIN antenas a ON a.municipio_id = m.id
                WHERE a.projeto_id = ? ORDER BY m.nome
            """, (projeto_id,)).fetchall()
            tecnologias = conn.execute("""
                SELECT DISTINCT t.id, t.nome FROM tecnologias t
                JOIN antenas a ON a.tecnologia_id = t.id
                WHERE a.projeto_id = ? ORDER BY t.nome
            """, (projeto_id,)).fetchall()
            crimes = [row['crime'] for row in conn.execute("""
                SELECT DISTINCT crime FROM antenas
                WHERE projeto_id = ? AND crime IS NOT NULL AND crime != '' ORDER BY crime
            """, (projeto_id,)).fetchall()]
            fontes = [row['fonte'] for row in conn.execute("""
                SELECT DISTINCT fonte FROM antenas
                WHERE projeto_id = ? AND fonte IS NOT NULL AND fonte != '' ORDER BY fonte
            """, (projeto_id,)).fetchall()]
            return {
                'operadoras': operadoras, 'municipios': municipios,
                'tecnologias': tecnologias, 'crimes': crimes, 'fontes': fontes,
            }
        finally:
            conn.close()

    @staticmethod
    def get_antennas(projeto_id, filters=None, page=1, per_page=50, return_all=False):
        if not projeto_id:
            return ([], 0) if return_all else ([], 0, 1)
        conn = get_db_connection()
        cur = conn.cursor()
        query_base = """
            FROM antenas a
            LEFT JOIN operadoras o ON a.operadora_id = o.id
            LEFT JOIN municipios m ON a.municipio_id = m.id
            LEFT JOIN tecnologias t ON a.tecnologia_id = t.id
            LEFT JOIN importacoes imp ON a.importacao_id = imp.id
            WHERE a.projeto_id = ?
        """
        params = [projeto_id]
        if filters:
            mappings = (
                ('operadora_id', 'a.operadora_id = ?'),
                ('municipio_id', 'a.municipio_id = ?'),
                ('tecnologia_id', 'a.tecnologia_id = ?'),
                ('importacao_id', 'a.importacao_id = ?'),
                ('fonte', 'a.fonte = ?'),
            )
            for key, clause in mappings:
                if filters.get(key):
                    query_base += f" AND {clause}"
                    params.append(filters[key])
            if filters.get('crime'):
                query_base += " AND a.crime LIKE ?"
                params.append(f"%{filters['crime']}%")
            if filters.get('q'):
                search = f"%{filters['q']}%"
                query_base += " AND (a.nome LIKE ? OR a.descricao LIKE ? OR a.crime LIKE ? OR m.nome LIKE ?)"
                params.extend([search] * 4)
            if filters.get('plotar') is not None and filters.get('plotar') != '':
                query_base += " AND a.plotar = ?"
                params.append(int(filters['plotar']))
            if filters.get('data_inicio'):
                query_base += " AND a.data_registro >= ?"
                params.append(filters['data_inicio'])
            if filters.get('data_fim'):
                query_base += " AND a.data_registro <= ?"
                params.append(filters['data_fim'])

        try:
            cur.execute(f"SELECT COUNT(*) total {query_base}", params)
            total_items = cur.fetchone()['total']
            fields = """
                SELECT a.id, a.importacao_id, a.ponto, a.nome, a.descricao, a.crime,
                       a.latitude, a.longitude, a.azimute, a.distancia, a.raio,
                       a.opacidade, a.borda, a.preenchimento, a.data_registro, a.hora_registro,
                       a.fonte, a.plotar, a.icone, a.criado_em, a.projeto_id,
                       o.nome operadora_nome, o.cor_padrao operadora_cor,
                       m.nome municipio_nome, m.uf municipio_uf,
                       t.nome tecnologia_nome, imp.nome_original arquivo_origem
            """
            if return_all:
                cur.execute(f"{fields} {query_base} ORDER BY a.id", params)
                return cur.fetchall(), total_items
            offset = (page - 1) * per_page
            cur.execute(
                f"{fields} {query_base} ORDER BY a.id LIMIT ? OFFSET ?",
                params + [per_page, offset],
            )
            rows = cur.fetchall()
            total_pages = (total_items + per_page - 1) // per_page if total_items else 1
            return rows, total_items, total_pages
        finally:
            conn.close()

    @staticmethod
    def get_antenna_by_id(antenna_id, projeto_id):
        conn = get_db_connection()
        try:
            return conn.execute("""
                SELECT a.*, o.nome operadora_nome, o.cor_padrao operadora_cor,
                       m.nome municipio_nome, m.uf municipio_uf,
                       t.nome tecnologia_nome, imp.nome_original arquivo_origem,
                       imp.data_importacao
                FROM antenas a
                LEFT JOIN operadoras o ON a.operadora_id = o.id
                LEFT JOIN municipios m ON a.municipio_id = m.id
                LEFT JOIN tecnologias t ON a.tecnologia_id = t.id
                LEFT JOIN importacoes imp ON a.importacao_id = imp.id
                WHERE a.id = ? AND a.projeto_id = ?
            """, (antenna_id, projeto_id)).fetchone()
        finally:
            conn.close()

    @staticmethod
    def delete_antenna(antenna_id, projeto_id):
        conn = get_db_connection()
        try:
            cursor = conn.execute(
                "DELETE FROM antenas WHERE id = ? AND projeto_id = ?",
                (antenna_id, projeto_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
