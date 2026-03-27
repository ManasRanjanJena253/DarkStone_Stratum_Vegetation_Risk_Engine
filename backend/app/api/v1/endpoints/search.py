from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func, text
from typing import Optional
import redis.asyncio as redis_mod
import json

from ....db.session import get_analysis_db, get_redis
from ....models.analysis_models import VegetationRecord
from ....schemas.analysis_schema import SearchResponse, VegetationRecordResponse
from ....ml_engine.fusion import cosine_similarity

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=SearchResponse)
async def hybrid_search(
    keyword: Optional[str] = Query(None),
    sector_id: Optional[str] = Query(None),
    risk_label: Optional[str] = Query(None),
    similar_to: Optional[str] = Query(None, description="record_id to find similar records"),
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(get_analysis_db),
    cache: redis_mod.Redis = Depends(get_redis),
):
    query = select(VegetationRecord)

    if sector_id:
        query = query.where(VegetationRecord.sector_id == sector_id)

    if risk_label:
        query = query.where(VegetationRecord.risk_label == risk_label)

    if keyword:
        ts_query = func.plainto_tsquery("english", keyword)
        query = query.where(
            or_(
                VegetationRecord.species.ilike(f"%{keyword}%"),
                VegetationRecord.sector_id.ilike(f"%{keyword}%"),
                func.to_tsvector("english", func.coalesce(VegetationRecord.species, "")).op("@@")(ts_query),
            )
        )

    result = await db.execute(query.limit(limit * 5 if similar_to else limit))
    records = result.scalars().all()

    if similar_to:
        ref_result = await db.execute(
            select(VegetationRecord).where(VegetationRecord.record_id == similar_to)
        )
        ref = ref_result.scalar_one_or_none()
        if ref and ref.embedding:
            ref_vec = ref.embedding
            scored = []
            for r in records:
                if r.embedding:
                    sim = cosine_similarity(ref_vec, r.embedding)
                    scored.append((sim, r))
            scored.sort(key=lambda x: x[0], reverse=True)
            records = [r for _, r in scored[:limit]]
        else:
            records = records[:limit]
    else:
        records = records[:limit]

    if risk_label in ("Critical", "High"):
        for r in records:
            cache_key = f"risk_cache:{r.record_id}"
            await cache.set(cache_key, json.dumps({
                "risk_score": r.risk_score,
                "risk_label": r.risk_label,
                "sector_id": r.sector_id,
            }), ex=600)

    return SearchResponse(
        results=[VegetationRecordResponse.model_validate(r) for r in records],
        total=len(records),
    )