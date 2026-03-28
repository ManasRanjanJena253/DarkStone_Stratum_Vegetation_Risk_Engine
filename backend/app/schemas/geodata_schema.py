from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class PowerlineCreate(BaseModel):
    name: str
    voltage_kv: Optional[float] = None
    company_name: Optional[str] = None
    geojson_linestring: dict
    metadata: Optional[dict] = {}


class PowerlineResponse(BaseModel):
    model_config = {"from_attributes": True}
    segment_id: str
    name: str
    voltage_kv: Optional[float]
    company_name: Optional[str]
    geojson_linestring: Optional[dict] = None
    created_at: Optional[datetime]


class ForestResponse(BaseModel):
    model_config = {"from_attributes": True}
    forest_id: str
    name: str
    density: str
    area_hectares: Optional[float]
    geojson_polygon: Optional[dict] = None
    created_at: Optional[datetime]


class HazardZoneResponse(BaseModel):
    model_config = {"from_attributes": True}
    hazard_id: str
    powerline_name: Optional[str]
    forest_name: Optional[str]
    forest_density: Optional[str]
    risk_level: str
    distance_to_forest_m: Optional[float]
    buffer_radius_m: Optional[float]
    area_m2: Optional[float]
    geojson_polygon: Optional[dict] = None
    computed_at: Optional[datetime]


class GeoJSONFeatureCollection(BaseModel):
    type: str = "FeatureCollection"
    features: List[dict]


class DashboardGeoData(BaseModel):
    powerlines: List[dict]
    forests: List[dict]
    hazards: List[dict]
    stats: dict