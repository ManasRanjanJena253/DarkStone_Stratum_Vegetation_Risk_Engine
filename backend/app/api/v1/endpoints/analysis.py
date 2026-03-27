from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
from uuid import uuid4
import redis.asyncio as redis_mod
import json

from ....db.session import get_analysis_db, get_user_db, get_redis
from ....models.analysis_models import VegetationSector, AnalysisJob, VegetationRecord
from ....models.user_models import User, User_Logs
from ....schemas.analysis_schema import (
    SectorCreate, SectorResponse,
    AnalysisRequest, AnalysisJobResponse,
    VegetationRecordResponse,
)
from ....core.security import get_session_user, require_active_quota
from ....worker.tasks import run_sector_analysis

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post("/sectors", response_model=SectorResponse, status_code=status.HTTP_201_CREATED)
async def create_sector(
    payload: SectorCreate,
    db: AsyncSession = Depends(get_analysis_db),
    session_id: str = "",
    cache: redis_mod.Redis = Depends(get_redis),
    udb: AsyncSession = Depends(get_user_db),
):
    user = await get_session_user(session_id, cache, udb)
    geom = None
    if payload.geojson_polygon:
        from geoalchemy2.shape import from_shape
        from shapely.geometry import shape
        geom = from_shape(shape(payload.geojson_polygon), srid=4326)

    sector = VegetationSector(
        sector_id=str(uuid4()),
        sector_name=payload.sector_name,
        geometry=geom,
        metadata=payload.metadata or {},
    )
    db.add(sector)
    await db.commit()
    await db.refresh(sector)
    return sector


@router.post("/jobs", response_model=AnalysisJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def submit_analysis_job(
    payload: AnalysisRequest,
    session_id: str = "",
    cache: redis_mod.Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_analysis_db),
    udb: AsyncSession = Depends(get_user_db),
):
    user = await get_session_user(session_id, cache, udb)
    require_active_quota(user)

    result = await db.execute(select(VegetationSector).where(VegetationSector.sector_id == payload.sector_id))
    sector = result.scalar_one_or_none()
    if not sector:
        raise HTTPException(status_code=404, detail="Sector not found.")

    job = AnalysisJob(
        job_id=str(uuid4()),
        user_id=user.user_id,
        sector_id=payload.sector_id,
        status="queued",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    log = User_Logs(
        req_id=str(uuid4()),
        user_id=user.user_id,
        req_received=True,
        req_processed=False,
        task="sector_analysis",
    )
    udb.add(log)
    await udb.commit()

    run_sector_analysis.apply_async(
        kwargs={"job_id": job.job_id, "sector_id": payload.sector_id, "user_id": user.user_id},
        task_id=job.job_id,
    )
    return job


@router.get("/jobs/{job_id}", response_model=AnalysisJobResponse)
async def get_job_status(
    job_id: str,
    db: AsyncSession = Depends(get_analysis_db),
):
    result = await db.execute(select(AnalysisJob).where(AnalysisJob.job_id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


@router.get("/sectors/{sector_id}/records", response_model=list[VegetationRecordResponse])
async def get_sector_records(
    sector_id: str,
    db: AsyncSession = Depends(get_analysis_db),
    cache: redis_mod.Redis = Depends(get_redis),
):
    cache_key = f"sector_records:{sector_id}"
    cached = await cache.get(cache_key)
    if cached:
        return json.loads(cached)

    result = await db.execute(
        select(VegetationRecord).where(VegetationRecord.sector_id == sector_id)
    )
    records = result.scalars().all()
    out = [VegetationRecordResponse.model_validate(r).model_dump(mode="json") for r in records]
    await cache.set(cache_key, json.dumps(out), ex=300)
    return out