import math
from typing import Optional
from shapely.geometry import shape, LineString, Polygon, mapping
from shapely.ops import transform
import pyproj
from functools import partial


# Risk thresholds in metres
RISK_THRESHOLDS = {
    "high":   300,
    "medium": 600,
    "low":    1000,
}


def _get_utm_proj(lon: float, lat: float):
    zone = int((lon + 180) / 6) + 1
    hemisphere = "north" if lat >= 0 else "south"
    return pyproj.CRS(f"+proj=utm +zone={zone} +{hemisphere} +ellps=WGS84")


def _to_utm(geom, lon: float, lat: float):
    wgs84 = pyproj.CRS("EPSG:4326")
    utm = _get_utm_proj(lon, lat)
    project = pyproj.Transformer.from_crs(wgs84, utm, always_xy=True).transform
    return transform(project, geom)


def _to_wgs84(geom, lon: float, lat: float):
    wgs84 = pyproj.CRS("EPSG:4326")
    utm = _get_utm_proj(lon, lat)
    project = pyproj.Transformer.from_crs(utm, wgs84, always_xy=True).transform
    return transform(project, geom)


def compute_hazards_for_user(
    powerlines: list[dict],
    forests: list[dict],
) -> list[dict]:
    """
    Computes hazard zones between powerline segments and forest polygons.

    Each powerline dict must have: segment_id, name, voltage_kv, company_name, geojson
    Each forest dict must have:   forest_id, name, density, area_hectares, geojson

    Returns a list of hazard dicts ready for DB insert + frontend rendering.

    How it works:
    - Convert each powerline LineString and forest Polygon to UTM (metric CRS).
    - Compute the actual distance in metres between them using Shapely.
    - If distance < 1000m, classify risk level, build a circular buffer polygon
      centred on the nearest point of the powerline, convert back to WGS84.
    - This replaces the frontend's crude degree-distance approximation with
      proper geodesic math.
    """
    hazards = []

    for pl in powerlines:
        pl_geom = shape(pl["geojson"])
        if pl_geom.is_empty:
            continue

        ref_lon, ref_lat = pl_geom.centroid.x, pl_geom.centroid.y
        pl_utm = _to_utm(pl_geom, ref_lon, ref_lat)

        for forest in forests:
            forest_geom = shape(forest["geojson"])
            if forest_geom.is_empty:
                continue

            forest_utm = _to_utm(forest_geom, ref_lon, ref_lat)
            distance_m = pl_utm.distance(forest_utm)

            risk_level = None
            buffer_m = None
            for level in ("high", "medium", "low"):
                if distance_m < RISK_THRESHOLDS[level]:
                    risk_level = level
                    buffer_m = RISK_THRESHOLDS[level]
                    break

            if risk_level is None:
                continue

            nearest_point_utm = pl_utm.interpolate(pl_utm.project(forest_utm.centroid))
            buffer_polygon_utm = nearest_point_utm.buffer(buffer_m, resolution=16)
            buffer_polygon_wgs84 = _to_wgs84(buffer_polygon_utm, ref_lon, ref_lat)

            area_m2 = math.pi * buffer_m * buffer_m

            hazards.append({
                "powerline_id": pl["segment_id"],
                "forest_id": forest["forest_id"],
                "powerline_name": pl["name"],
                "forest_name": forest["name"],
                "forest_density": forest["density"],
                "risk_level": risk_level,
                "distance_to_forest_m": round(distance_m, 1),
                "buffer_radius_m": float(buffer_m),
                "area_m2": round(area_m2, 1),
                "geojson": mapping(buffer_polygon_wgs84),
            })

    return hazards