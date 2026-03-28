from sqlalchemy import Column, String, Float, DateTime, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from geoalchemy2 import Geometry
from sqlalchemy import Index
from ..db.base import AnalysisBase
import uuid


class PowerlineSegment(AnalysisBase):
    __tablename__ = "powerline_segments"

    segment_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    voltage_kv = Column(Float, nullable=True)
    company_name = Column(String, nullable=True)
    geometry = Column(Geometry(geometry_type="LINESTRING", srid=4326), nullable=False)
    metadata = Column(JSONB, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_powerline_geom", "geometry", postgresql_using="gist"),
    )


class ForestPolygon(AnalysisBase):
    __tablename__ = "forest_polygons"

    forest_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False, index=True)
    density = Column(String, default="medium")
    area_hectares = Column(Float, nullable=True)
    geometry = Column(Geometry(geometry_type="POLYGON", srid=4326), nullable=False)
    metadata = Column(JSONB, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_forest_geom", "geometry", postgresql_using="gist"),
    )


class HazardZone(AnalysisBase):
    __tablename__ = "hazard_zones"

    hazard_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    powerline_id = Column(String, nullable=False)
    forest_id = Column(String, nullable=False)
    powerline_name = Column(String)
    forest_name = Column(String)
    forest_density = Column(String)
    risk_level = Column(String, index=True)
    distance_to_forest_m = Column(Float)
    buffer_radius_m = Column(Float)
    area_m2 = Column(Float)
    geometry = Column(Geometry(geometry_type="POLYGON", srid=4326), nullable=True)
    computed_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_hazard_geom", "geometry", postgresql_using="gist"),
        Index("idx_hazard_user", "user_id"),
    )