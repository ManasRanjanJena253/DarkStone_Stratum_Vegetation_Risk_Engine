import asyncio
import tempfile
import os
from datetime import datetime, timezone
from celery import Task
from sqlalchemy import select, update

from .celery_app import celery_app
from ..db.session import analysis_session, user_session
from ..models.analysis_models import VegetationRecord, AnalysisJob, VegetationSector
from ..models.user_models import User, User_Logs
from ..ml_engine.ingestion import fetch_sentinel2_ndvi, fetch_lidar_point_cloud
from ..ml_engine.lidar_ops import extract_canopy_height, estimate_wire_height_from_dem
from ..ml_engine.fusion import fuse_analysis_result
from uuid import uuid4


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@celery_app.task(
    bind=True,
    max_retries=5,
    default_retry_delay=10,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
)
def run_sector_analysis(self: Task, job_id: str, sector_id: str, user_id: str):
    async def _inner():
        async with analysis_session() as db:
            result = await db.execute(select(VegetationSector).where(VegetationSector.sector_id == sector_id))
            sector = result.scalar_one_or_none()
            if not sector:
                raise ValueError(f"Sector {sector_id} not found.")

            await db.execute(
                update(AnalysisJob)
                .where(AnalysisJob.job_id == job_id)
                .values(status="running", celery_task_id=self.request.id)
            )
            await db.commit()

            meta = sector.metadata or {}
            bbox = meta.get("bbox", [-77.5, 38.8, -77.0, 39.2])

            ndvi = await fetch_sentinel2_ndvi(bbox)

            tmp_dem = tempfile.mktemp(suffix=".tif")
            lidar_ok = await fetch_lidar_point_cloud(bbox, tmp_dem)

            tree_height = None
            wire_height = None
            if lidar_ok:
                tree_height = extract_canopy_height(tmp_dem)
                wire_height = estimate_wire_height_from_dem(tmp_dem)
                try:
                    os.remove(tmp_dem)
                except OSError:
                    pass

            fused = fuse_analysis_result(tree_height, wire_height, ndvi)

            species_list = meta.get("species", ["Unknown"])
            records_created = 0
            for species in species_list:
                existing = await db.execute(
                    select(VegetationRecord).where(
                        VegetationRecord.sector_id == sector_id,
                        VegetationRecord.species == species,
                        VegetationRecord.human_override == False,
                    )
                )
                record = existing.scalar_one_or_none()
                if record:
                    record.tree_height_m = tree_height
                    record.wire_height_m = wire_height
                    record.clearance_m = fused["clearance_m"]
                    record.ndvi = ndvi
                    record.risk_score = fused["risk_score"]
                    record.risk_label = fused["risk_label"]
                    record.embedding = fused["embedding"]
                    record.sentinel_metadata = {"ndvi": ndvi, "bbox": bbox}
                    record.lidar_metadata = {"tree_height_m": tree_height, "wire_height_m": wire_height}
                    record.updated_at = datetime.now(timezone.utc)
                else:
                    new_record = VegetationRecord(
                        record_id=str(uuid4()),
                        sector_id=sector_id,
                        species=species,
                        tree_height_m=tree_height,
                        wire_height_m=wire_height,
                        clearance_m=fused["clearance_m"],
                        ndvi=ndvi,
                        risk_score=fused["risk_score"],
                        risk_label=fused["risk_label"],
                        embedding=fused["embedding"],
                        sentinel_metadata={"ndvi": ndvi, "bbox": bbox},
                        lidar_metadata={"tree_height_m": tree_height, "wire_height_m": wire_height},
                        status="analyzed",
                    )
                    db.add(new_record)
                    records_created += 1

            await db.execute(
                update(AnalysisJob)
                .where(AnalysisJob.job_id == job_id)
                .values(
                    status="completed",
                    completed_at=datetime.now(timezone.utc),
                    result_summary={
                        "risk_label": fused["risk_label"],
                        "risk_score": fused["risk_score"],
                        "records_updated": len(species_list) - records_created,
                        "records_created": records_created,
                    },
                )
            )
            await db.commit()

        async with user_session() as udb:
            await udb.execute(
                update(User)
                .where(User.user_id == user_id)
                .values(max_requests=User.max_requests - 1)
            )
            log = User_Logs(
                req_id=str(uuid4()),
                user_id=user_id,
                req_received=True,
                req_processed=True,
                task="sector_analysis",
            )
            udb.add(log)
            await udb.commit()

    try:
        _run(_inner())
    except Exception as exc:
        async def _fail():
            async with analysis_session() as db:
                await db.execute(
                    update(AnalysisJob)
                    .where(AnalysisJob.job_id == job_id)
                    .values(status="failed", error=str(exc))
                )
                await db.commit()
        _run(_fail())
        raise self.retry(exc=exc)