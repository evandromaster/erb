import os
import folium
from branca.element import MacroElement, Template
from markupsafe import escape
from folium import plugins
from folium.plugins import MarkerCluster, Fullscreen, MeasureControl
from config import Config


class PointSelectionBridge(MacroElement):
    """Conecta o clique no mapa Folium ao template pai, limitado a mesma origem."""

    _template = Template("""
        {% macro script(this, kwargs) %}
        (function () {
            const map = {{ this._parent.get_name() }};
            let pointSelectionActive = false;
            window.addEventListener('message', function (event) {
                if (event.origin !== window.location.origin) return;
                if (!event.data || event.data.type !== 'erb:set-point-selection') return;
                pointSelectionActive = Boolean(event.data.active);
                map.getContainer().style.cursor = pointSelectionActive ? 'crosshair' : '';
            });
            map.on('click', function (event) {
                if (!pointSelectionActive) return;
                pointSelectionActive = false;
                map.getContainer().style.cursor = '';
                window.parent.postMessage({
                    type: 'erb:map-point-selected',
                    latitude: event.latlng.lat,
                    longitude: event.latlng.lng
                }, window.location.origin);
            });
        })();
        {% endmacro %}
    """)

class MapService:
    @staticmethod
    def generate_map(antennas, enable_cluster=False, custom_center=None, zoom=None,
                     points=None, enable_point_selection=False):
        """
        Gera o mapa Folium completo preservando fielmente a lógica do map.py
        com melhorias em responsividade, popups estilizados e controle de camadas.
        """
        # Converter sqlite3.Row para dict caso necessário
        ant_list = [dict(a) if not isinstance(a, dict) else a for a in antennas]
        point_list = [dict(p) if not isinstance(p, dict) else p for p in (points or [])]

        # Determinar centro e limites do mapa
        if custom_center:
            center = custom_center
            init_zoom = zoom if zoom else Config.DEFAULT_ZOOM
        elif ant_list or point_list:
            lats = [a['latitude'] for a in ant_list if a.get('latitude') is not None]
            lons = [a['longitude'] for a in ant_list if a.get('longitude') is not None]
            lats.extend(p['latitude'] for p in point_list if p.get('latitude') is not None)
            lons.extend(p['longitude'] for p in point_list if p.get('longitude') is not None)
            if lats and lons:
                center = [sum(lats) / len(lats), sum(lons) / len(lons)]
            else:
                center = Config.DEFAULT_LOCATION
            init_zoom = zoom if zoom else 13
        else:
            center = Config.DEFAULT_LOCATION
            init_zoom = Config.DEFAULT_ZOOM

        # 1. Instanciar o Mapa Base Folium
        m = folium.Map(
            location=center,
            zoom_start=init_zoom,
            tiles=None,
            prefer_canvas=True
        )

        # 2. Camadas de Mapa Base (Google, OSM, Mapbox, CartoDB)
        # Google Satélite (idêntico ao map.py)
        folium.raster_layers.TileLayer(
            tiles="https://{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
            attr="Google Satellite",
            name="Google Satélite",
            max_zoom=20,
            subdomains=["mt0", "mt1", "mt2", "mt3"],
            overlay=False,
            control=True
        ).add_to(m)

        # Google Ruas (idêntico ao map.py)
        folium.raster_layers.TileLayer(
            tiles="https://{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}",
            attr="Google Streets",
            name="Google Ruas",
            max_zoom=20,
            subdomains=["mt0", "mt1", "mt2", "mt3"],
            overlay=False,
            control=True
        ).add_to(m)

        # OpenStreetMap
        folium.TileLayer('openstreetmap', name='OpenStreetMap', overlay=False).add_to(m)

        # CartoDB Positron (Visão clara minimalista)
        folium.TileLayer('CartoDB positron', name='CartoDB Claro', overlay=False).add_to(m)

        # Mapbox Satélite (se token existir)
        if Config.MAPBOX_TOKEN:
            try:
                mapbox_url = f"https://api.mapbox.com/v4/mapbox.satellite/{{z}}/{{x}}/{{y}}@2x.png?access_token={Config.MAPBOX_TOKEN}"
                folium.TileLayer(mapbox_url, attr='Mapbox', name='Drone / Mapbox Sat', overlay=False).add_to(m)
            except Exception:
                pass

        # 3. Grupos de Camadas (Feature Groups)
        radar_group = folium.FeatureGroup(name='Radar / Setores de Cobertura', show=True)
        antenas_group = folium.FeatureGroup(name='Marcadores de Antenas', show=True)
        points_group = folium.FeatureGroup(name='Pontos', show=True)
        
        # Cluster opcional para grandes volumes de dados
        cluster_group = MarkerCluster(name='Agrupamento de Antenas (Cluster)', show=False) if enable_cluster else None

        # 4. Adicionar Elementos Geográficos ao Mapa
        for a in ant_list:
            # Só plota se o campo plotar estiver ativo (1)
            if a.get('plotar') == 0:
                continue

            lat = a['latitude']
            lon = a['longitude']
            azimute = float(a.get('azimute') or 0.0)
            distancia = float(a.get('distancia') or 1000.0)
            raio = float(a.get('raio') or 60.0)
            fill_color = a.get('preenchimento') or '#FFFF00'
            fill_opacity = float(a.get('opacidade') or 0.2)
            border_color = a.get('borda') or '#FF0000'
            nome = a.get('nome') or 'ERB'
            crime = a.get('crime') or 'N/A'
            descricao = a.get('descricao') or ''
            operadora = a.get('operadora_nome') or 'N/A'
            municipio = a.get('municipio_nome') or 'N/A'
            data_reg = a.get('data_registro') or ''
            hora_reg = a.get('hora_registro') or ''
            fonte = a.get('fonte') or ''

            # HTML do Popup Estruturado e Limpo
            popup_html = f"""
            <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 13px; line-height: 1.4; color: #1e293b; min-width: 220px; padding: 4px;">
                <div style="font-weight: 700; font-size: 14px; margin-bottom: 6px; border-bottom: 2px solid #3b82f6; padding-bottom: 4px; display: flex; justify-content: space-between; align-items: center;">
                    <span>📍 {nome}</span>
                    <span style="font-size: 11px; background: #e0f2fe; color: #0369a1; padding: 2px 6px; border-radius: 4px;">{operadora}</span>
                </div>
                <table style="width: 100%; border-collapse: collapse; font-size: 12px;">
                    <tr><td style="color: #64748b; padding: 2px 0;">Crime/Delito:</td><td style="font-weight: 600; text-align: right; color: #dc2626;">{crime}</td></tr>
                    {f'<tr><td style="color: #64748b; padding: 2px 0;">Descrição:</td><td style="text-align: right;">{descricao}</td></tr>' if descricao else ''}
                    <tr><td style="color: #64748b; padding: 2px 0;">Município:</td><td style="text-align: right;">{municipio}</td></tr>
                    <tr><td style="color: #64748b; padding: 2px 0;">Latitude:</td><td style="text-align: right; font-family: monospace;">{lat:.6f}</td></tr>
                    <tr><td style="color: #64748b; padding: 2px 0;">Longitude:</td><td style="text-align: right; font-family: monospace;">{lon:.6f}</td></tr>
                    <tr><td style="color: #64748b; padding: 2px 0;">Azimute:</td><td style="text-align: right; font-weight: 600;">{azimute:.0f}°</td></tr>
                    <tr><td style="color: #64748b; padding: 2px 0;">Alcance / Raio:</td><td style="text-align: right; font-weight: 600;">{distancia:.0f} m (abertura {raio:.0f}°)</td></tr>
                    {f'<tr><td style="color: #64748b; padding: 2px 0;">Data/Hora:</td><td style="text-align: right;">{data_reg} {hora_reg}</td></tr>' if data_reg or hora_reg else ''}
                    {f'<tr><td style="color: #64748b; padding: 2px 0;">Fonte:</td><td style="text-align: right;">{fonte}</td></tr>' if fonte else ''}
                </table>
            </div>
            """
            iframe = folium.IFrame(html=popup_html, width=260, height=210)
            popup = folium.Popup(iframe, max_width=300)
            tooltip_text = f"<b>{nome}</b> | {operadora} | Az: {azimute:.0f}° | Dist: {distancia:.0f}m"

            # 4.1. SemiCírculo / Setor de Radar (Lógica preservada de map.py)
            radar_sector = plugins.SemiCircle(
                location=[lat, lon],
                radius=distancia,
                direction=azimute,
                arc=raio,
                fill=True,
                fill_color=fill_color,
                fill_opacity=fill_opacity,
                color=border_color,
                opacity=1.0,
                popup=popup,
                tooltip=tooltip_text
            )
            radar_group.add_child(radar_sector)

            # 4.2. Marcador da Antena ERB (CustomIcon com resolução de path)
            icon_file = a.get('icone') or 'antena1.png'
            icon_disk_path = os.path.join(Config.BASE_DIR, 'static', 'images', icon_file)

            if os.path.exists(icon_disk_path):
                marker_icon = folium.features.CustomIcon(
                    icon_image=icon_disk_path,
                    icon_size=(30, 30)
                )
            else:
                marker_icon = folium.Icon(color='blue', icon='signal', prefix='fa')

            marker = folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(folium.IFrame(html=popup_html, width=260, height=210), max_width=300),
                tooltip=f"ERB: {nome} ({operadora})",
                icon=marker_icon
            )
            antenas_group.add_child(marker)

            if cluster_group:
                cluster_marker = folium.Marker(
                    location=[lat, lon],
                    popup=folium.Popup(folium.IFrame(html=popup_html, width=260, height=210), max_width=300),
                    tooltip=f"ERB: {nome} ({operadora})"
                )
                cluster_group.add_child(cluster_marker)

        point_colors = {
            'Casa': 'green',
            'Trabalho': 'blue',
            'Comparsa': 'purple',
            'Empresa': 'cadetblue',
            'Antena': 'orange',
            'Crime': 'red',
            'Outro': 'gray',
        }
        point_icons = {
            'Casa': 'home',
            'Trabalho': 'briefcase',
            'Comparsa': 'users',
            'Empresa': 'building',
            'Antena': 'signal',
            'Crime': 'exclamation-triangle',
            'Outro': 'map-marker',
        }
        for point in point_list:
            point_id = int(point['id'])
            point_type = str(escape(point.get('tipo') or 'Outro'))
            description = str(escape(point.get('descricao') or ''))
            lat = float(point['latitude'])
            lon = float(point['longitude'])
            popup_html = f"""
            <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; min-width: 220px; font-size: 12px; color: #1e293b;">
                <div style="font-size: 14px; font-weight: 700; padding-bottom: 5px; margin-bottom: 5px; border-bottom: 2px solid #2563eb;">Ponto #{point_id}</div>
                <div><strong>Tipo:</strong> {point_type}</div>
                <div><strong>Descricao:</strong> {description}</div>
                <div><strong>Latitude:</strong> {lat:.6f}</div>
                <div><strong>Longitude:</strong> {lon:.6f}</div>
                <div style="margin-top: 8px;"><a href="/pontos?edit={point_id}" target="_top" style="color: #1d4ed8; font-weight: 600;">Editar / Excluir</a></div>
            </div>
            """
            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(popup_html, max_width=320),
                tooltip=f"{point_type}: {description}",
                icon=folium.Icon(
                    color=point_colors.get(point.get('tipo'), 'gray'),
                    icon=point_icons.get(point.get('tipo'), 'map-marker'),
                    prefix='fa',
                ),
            ).add_to(points_group)

        # Adicionar os grupos ao mapa
        radar_group.add_to(m)
        antenas_group.add_to(m)
        points_group.add_to(m)
        if cluster_group:
            cluster_group.add_to(m)

        # 5. Ajuste automático dos limites (fit_bounds) se houver múltiplos pontos
        if len(ant_list) + len(point_list) > 1 and not custom_center:
            lats = [a['latitude'] for a in ant_list if a.get('plotar') != 0 and a.get('latitude') is not None]
            lons = [a['longitude'] for a in ant_list if a.get('plotar') != 0 and a.get('longitude') is not None]
            lats.extend(p['latitude'] for p in point_list if p.get('latitude') is not None)
            lons.extend(p['longitude'] for p in point_list if p.get('longitude') is not None)
            if lats and lons:
                m.fit_bounds([[min(lats), min(lons)], [max(lats), max(lons)]], padding=(30, 30))

        # 6. Plugins Adicionais: Tela Cheia e Ferramenta de Medição de Distâncias
        Fullscreen(position='topleft', title='Tela Cheia', title_cancel='Sair da Tela Cheia').add_to(m)
        MeasureControl(position='bottomleft', primary_length_unit='meters', secondary_length_unit='kilometers').add_to(m)

        # 7. Controle de Camadas (LayerControl com suporte mobile)
        m.add_child(folium.LayerControl(position='topright', collapsed=False))

        if enable_point_selection:
            PointSelectionBridge().add_to(m)

        return m
