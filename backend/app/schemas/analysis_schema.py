from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime


class SectorCreate(BaseModel):
    sector_name: str
    geojson_polygon: Optional[dict] = None
    metadata: Optional[dict] = {}


class SectorResponse(BaseModel):
    model_config = {"from_attributes": True}
    sector_id: str
    sector_name: str
    metadata: Optional[dict]
    created_at: Optional[datetime]


class AnalysisRequest(BaseModel):
    sector_id: str


class AnalysisJobResponse(BaseModel):
    model_config = {"from_attributes": True}
    job_id: str
    celery_task_id: Optional[str]
    status: str
    sector_id: str
    created_at: Optional[datetime]
    result_summary: Optional[dict]


class VegetationRecordResponse(BaseModel):
    model_config = {"from_attributes": True}
    record_id: str
    sector_id: str
    species: Optional[str]
    tree_height_m: Optional[float]
    wire_height_m: Optional[float]
    clearance_m: Optional[float]
    ndvi: Optional[float]
    risk_score: Optional[float]
    risk_label: Optional[str]
    status: str
    human_override: bool
    override_at: Optional[datetime]
    created_at: Optional[datetime]


class SyncRecord(BaseModel):
    sync_id: str = Field(..., description="Client-generated UUID for idempotency")
    record_id: Optional[str] = None
    sector_id: str
    status: str
    override_by: Optional[str] = None
    override_at: Optional[datetime] = None
    species: Optional[str] = None
    location_lat: Optional[float] = None
    location_lon: Optional[float] = None


class SyncBatchRequest(BaseModel):
    records: List[SyncRecord]


class SyncBatchResponse(BaseModel):
    accepted: int
    skipped: int
    conflicts_resolved: int


class SearchRequest(BaseModel):
    keyword: Optional[str] = None
    vector_reference_record_id: Optional[str] = None
    sector_id: Optional[str] = None
    risk_label: Optional[str] = None
    limit: int = 20


class SearchResponse(BaseModel):
    results: List[VegetationRecordResponse]
    total: int