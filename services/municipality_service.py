import logging
from functools import lru_cache

import geopandas as gpd
import pandas as pd

from config import Config


logger = logging.getLogger(__name__)


class MunicipalityService:
    """Resolve municipios de MG em lote usando exclusivamente o GeoPackage oficial."""

    NAME_COLUMN = 'NM_MUN'
    POINTS_CRS = 'EPSG:4326'

    @classmethod
    @lru_cache(maxsize=1)
    def _load_municipalities(cls):
        gpkg_path = Config.MUNICIPIOS_GPKG
        if not gpkg_path.is_file():
            raise FileNotFoundError(f"GeoPackage de municipios nao encontrado: {gpkg_path}")

        layers = gpd.list_layers(gpkg_path)
        if layers.empty:
            raise ValueError(f"Nenhuma camada encontrada no GeoPackage: {gpkg_path}")

        configured_layer = Config.MUNICIPIOS_LAYER
        if configured_layer:
            if configured_layer not in layers['name'].tolist():
                raise ValueError(
                    f"Camada configurada '{configured_layer}' nao existe em {gpkg_path}. "
                    f"Camadas disponiveis: {', '.join(layers['name'])}"
                )
            candidate_layers = [configured_layer]
        else:
            candidate_layers = layers['name'].tolist()

        selected_layer = None
        municipalities = None
        for layer_name in candidate_layers:
            candidate = gpd.read_file(gpkg_path, layer=layer_name)
            if cls.NAME_COLUMN in candidate.columns:
                selected_layer = layer_name
                municipalities = candidate
                break

        if municipalities is None:
            raise ValueError(
                f"Coluna obrigatoria {cls.NAME_COLUMN} nao encontrada nas camadas "
                f"{', '.join(candidate_layers)} de {gpkg_path}"
            )
        if municipalities.crs is None:
            raise ValueError(
                f"CRS ausente na camada '{selected_layer}' do GeoPackage {gpkg_path}"
            )
        if municipalities.geometry.name not in municipalities.columns:
            raise ValueError(f"Camada '{selected_layer}' nao possui geometria")

        municipalities = municipalities[[cls.NAME_COLUMN, municipalities.geometry.name]].copy()
        municipalities = municipalities[
            municipalities.geometry.notna() & ~municipalities.geometry.is_empty
        ]
        if municipalities.empty:
            raise ValueError(f"Camada '{selected_layer}' nao possui poligonos validos")

        logger.info(
            "Municipios carregados: %d | camada: %s | CRS: %s | arquivo: %s",
            len(municipalities), selected_layer, municipalities.crs, gpkg_path,
        )
        return municipalities

    @classmethod
    def resolve_batch(cls, coordinates):
        """Retorna NM_MUN por indice; falhas e pontos sem correspondencia recebem None."""
        if not isinstance(coordinates, pd.DataFrame):
            coordinates = pd.DataFrame(coordinates)
        required = {'latitude', 'longitude'}
        if not required.issubset(coordinates.columns):
            raise ValueError("coordinates deve conter as colunas latitude e longitude")

        result = pd.Series(None, index=coordinates.index, dtype='object', name='municipio')
        latitudes = pd.to_numeric(coordinates['latitude'], errors='coerce')
        longitudes = pd.to_numeric(coordinates['longitude'], errors='coerce')
        valid_mask = latitudes.between(-90, 90) & longitudes.between(-180, 180)
        valid = coordinates.loc[valid_mask, ['latitude', 'longitude']].copy()

        logger.info(
            "ERBs processadas: %d | ERBs com coordenadas validas: %d",
            len(coordinates), len(valid),
        )
        if valid.empty:
            logger.info("ERBs associadas a municipios: 0 | ERBs sem municipio: %d", len(coordinates))
            return result

        try:
            municipalities = cls._load_municipalities()
            points = gpd.GeoDataFrame(
                valid,
                geometry=gpd.points_from_xy(valid['longitude'], valid['latitude']),
                crs=cls.POINTS_CRS,
            ).to_crs(municipalities.crs)

            within = gpd.sjoin(
                points[['geometry']], municipalities, how='left', predicate='within'
            )
            matched = within[within[cls.NAME_COLUMN].notna()]
            if not matched.empty:
                result.loc[matched.index] = matched[cls.NAME_COLUMN]

            # ``within`` exclui a borda. ``intersects`` trata esses pontos em
            # segunda passagem; empates sao resolvidos de forma deterministica.
            unmatched_index = valid.index[result.loc[valid.index].isna()]
            if len(unmatched_index):
                boundary = gpd.sjoin(
                    points.loc[unmatched_index, ['geometry']],
                    municipalities,
                    how='left',
                    predicate='intersects',
                )
                boundary = boundary[boundary[cls.NAME_COLUMN].notna()]
                if not boundary.empty:
                    counts = boundary.groupby(level=0)[cls.NAME_COLUMN].nunique()
                    ambiguous = counts[counts > 1]
                    if not ambiguous.empty:
                        logger.warning(
                            "%d ERBs estao sobre limites com mais de um municipio; "
                            "sera usado o primeiro NM_MUN em ordem alfabetica",
                            len(ambiguous),
                        )
                    boundary_names = boundary.groupby(level=0)[cls.NAME_COLUMN].agg(
                        lambda names: sorted(set(names))[0]
                    )
                    result.loc[boundary_names.index] = boundary_names

        except Exception:
            logger.exception(
                "Falha ao identificar municipios por Spatial Join; "
                "as ERBs serao mantidas com municipio nao identificado"
            )

        associated = int(result.notna().sum())
        logger.info(
            "ERBs associadas a municipios: %d | ERBs sem municipio: %d",
            associated, len(result) - associated,
        )
        # Atribuicoes vindas do GeoPandas podem materializar ausencias como NaN.
        # O restante do projeto usa None/NULL para municipio nao identificado.
        result = result.astype(object)
        result.loc[result.isna()] = None
        return result
