from sqlalchemy import Column, String, Float, Boolean, DateTime, Integer, Text, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func
from geoalchemy2 import Geometry
from ..db.base import AnalysisBase
import uuid


class VegetationSector(AnalysisBase):
    __tablename__ = "vegetation_sectors"

    sector_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    sector_name = Column(String, index=True, nullable=False)
    geometry = Column(Geometry(geometry_type="POLYGON", srid=4326), nullable=True)
    metadata = Column(JSONB, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        Index("idx_sector_geometry", "geometry", postgresql_using="gist"),
    )


class VegetationRecord(AnalysisBase):
    __tablename__ = "vegetation_records"

    record_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    sector_id = Column(String, nullable=False, index=True)
    species = Column(String, index=True)
    location = Column(Geometry(geometry_type="POINT", srid=4326))
    tree_height_m = Column(Float)
    wire_height_m = Column(Float)
    clearance_m = Column(Float)
    ndvi = Column(Float)
    risk_score = Column(Float)
    risk_label = Column(String)
    status = Column(String, default="pending")
    human_override = Column(Boolean, default=False)
    override_by = Column(String)
    override_at = Column(DateTime(timezone=True))
    sentinel_metadata = Column(JSONB, default={})
    lidar_metadata = Column(JSONB, default={})
    embedding = Column(JSONB, default=[])
    search_vector = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    sync_id = Column(String, unique=True, nullable=True)

    __table_args__ = (
        Index("idx_vegetation_location", "location", postgresql_using="gist"),
        Index("idx_vegetation_sector", "sector_id"),
    )


class AnalysisJob(AnalysisBase):
    __tablename__ = "analysis_jobs"

    job_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    celery_task_id = Column(String, index=True, unique=True, nullable=True)
    user_id = Column(String, index=True, nullable=False)
    sector_id = Column(String, nullable=False)
    status = Column(String, default="queued")
    error = Column(Text, nullable=True)
    result_summary = Column(JSONB, default={})
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)