from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
from uuid import uuid4
import redis.asyncio as redis_mod

from ....db.session import get_analysis_db, get_user_db, get_redis
from ....models.analysis_models import VegetationRecord
from ....schemas.analysis_schema import SyncBatchRequest, SyncBatchResponse
from ....core.security import get_session_user

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("", response_model=SyncBatchResponse, status_code=status.HTTP_200_OK)
async def sync_field_updates(
    payload: SyncBatchRequest,
    session_id: str = "",
    cache: redis_mod.Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_analysis_db),
    udb: AsyncSession = Depends(get_user_db),
):
    user = await get_session_user(session_id, cache, udb)
    accepted = skipped = conflicts_resolved = 0

    for rec in payload.records:
        idempotency_key = f"sync:{rec.sync_id}"
        already = await cache.get(idempotency_key)
        if already:
            skipped += 1
            continue

        result = await db.execute(
            select(VegetationRecord).where(VegetationRecord.sync_id == rec.sync_id)
        )
        existing_by_sync = result.scalar_one_or_none()
        if existing_by_sync:
            skipped += 1
            await cache.set(idempotency_key, "1", ex=86400 * 7)
            continue

        db_record = None
        if rec.record_id:
            r = await db.execute(
                select(VegetationRecord).where(VegetationRecord.record_id == rec.record_id)
            )
            db_record = r.scalar_one_or_none()

        if db_record:
            human_ts = rec.override_at or datetime.now(timezone.utc)
            satellite_ts = db_record.updated_at or datetime.min.replace(tzinfo=timezone.utc)

            if db_record.risk_label in ("Critical", "High") and not db_record.human_override:
                conflicts_resolved += 1

            if human_ts >= satellite_ts.replace(tzinfo=timezone.utc) if satellite_ts.tzinfo is None else satellite_ts:
                db_record.status = rec.status
                db_record.human_override = True
                db_record.override_by = rec.override_by or user.user_id
                db_record.override_at = human_ts
                db_record.sync_id = rec.sync_id
                accepted += 1
            else:
                skipped += 1
        else:
            location = None
            if rec.location_lat is not None and rec.location_lon is not None:
                from geoalchemy2.shape import from_shape
                from shapely.geometry import Point
                location = from_shape(Point(rec.location_lon, rec.location_lat), srid=4326)

            new_rec = VegetationRecord(
                record_id=str(uuid4()),
                sector_id=rec.sector_id,
                species=rec.species,
                location=location,
                status=rec.status,
                human_override=True,
                override_by=rec.override_by or user.user_id,
                override_at=rec.override_at or datetime.now(timezone.utc),
                sync_id=rec.sync_id,
            )
            db.add(new_rec)
            accepted += 1

        await cache.set(idempotency_key, "1", ex=86400 * 7)

    await db.commit()
    return SyncBatchResponse(accepted=accepted, skipped=skipped, conflicts_resolved=conflicts_resolved)