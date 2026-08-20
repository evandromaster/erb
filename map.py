from folium.plugins import MarkerCluster
from folium import plugins
import folium
import pandas as pd
import numpy as np
dir = r"D:\Cloud\Jupyter\mapas\antenas.xlsx"  # Home
# dir_crimes = r'D:\SQLite\10 - Tbl_dimensao\gdo\tbl_base_GDO_2020.xls'#Officee
df_antenas = pd.read_excel(dir, sheet_name='tbl_antenas')
# df_antenas

token = "pk.eyJ1IjoiZXZhbmRyb21hc3RlciIsImEiOiJjamVpcTM1dW4zN2ZqMnFxZWhyMmVxazc0In0.yRc9A7HcmbNaQGW5teN1TA"  # your mapbox token
tileurl = 'https://api.mapbox.com/v4/mapbox.satellite/{z}/{x}/{y}@2x.png?access_token=' + str(
    token)
m = folium.Map(
    # Coordenadas retiradas do Google Maps
    location=[-20.14724867843028, -44.88813307146979],
    tiles=None,  # 'openstreetmap',
    zoom_start=12)

folium.raster_layers.TileLayer(
    tiles="http://{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
    attr="google",
    name="GSat Maps",
    max_zoom=20,
    subdomains=["mt0", "mt1", "mt2", "mt3"],
    overlay=False,
    control=True,
).add_to(m)

folium.raster_layers.TileLayer(
    tiles="http://{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}",
    attr="google",
    name="GStr Maps",
    max_zoom=20,
    subdomains=["mt0", "mt1", "mt2", "mt3"],
    overlay=False,
    control=True,
).add_to(m)


folium.TileLayer(tileurl, attr='Mapbox', name='Drone 7ª RPM',
                 overlay=False).add_to(m)
folium.TileLayer('openstreetmap', name='OSM',
                 overlay=False).add_to(m)

############################################################
radar = folium.FeatureGroup(name='Radar', show=True)

# Criando SEMICIRCULO
for index, linha in df_antenas.iterrows():
    radar.add_child(plugins.SemiCircle(
                    # Location of center
                    location=[linha['LATITUDE'], linha['LONGITUDE']],
                    # DISTANCIA EM METROS
                    radius=linha['DISTANCIA'],
                    # Direction of cone center (0 to 360 degrees)
                    direction=linha['AZIMUTE'],
                    # RAIO /  ANGULO
                    arc=linha['RAIO'],
                    fill=True,
                    fill_color=linha['PREENCHIMENTO'],
                    fill_opacity=0.1,
                    color=linha['BORDA'],
                    opacity=1
                    )).add_to(m)
#################################################


antenas = folium.FeatureGroup(name='Antenas', show=True)

# Criando PONTOS DA ANTENA
for index, linha in df_antenas.iterrows():
    icon_radar = folium.features.CustomIcon(
        './images/antena1.png', icon_size=(30, 30))
    antenas.add_child(folium.Marker([linha['LATITUDE'], linha['LONGITUDE']],
                                    popup=linha['NOME'],
                                    tooltip=linha['CRIME'],
                                    opacity=1,
                                    icon=icon_radar
                                    )).add_to(m)

m.add_child(folium.LayerControl('topright', collapsed=False))
m.save('Monitoramento_8.html')

