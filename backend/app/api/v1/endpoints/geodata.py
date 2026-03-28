from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import shape, mapping
from uuid import uuid4
import redis.asyncio as redis_mod
import json

from ....db.session import get_analysis_db, get_user_db, get_redis
from ....models.geodata_models import PowerlineSegment, ForestPolygon, HazardZone
from ....schemas.geodata_schema import PowerlineCreate, DashboardGeoData
from ....core.security import get_session_user
from ....ml_engine.hazard_engine import compute_hazards_for_user

router = APIRouter(prefix="/geodata", tags=["geodata"])

INDIA_FORESTS = [
    {"forest_id": "f-sun",  "name": "Sundarbans Reserve Forest",    "density": "high",   "area_hectares": 102000, "geojson": {"type": "Polygon", "coordinates": [[[88.8,21.9],[89.2,21.9],[89.2,22.4],[88.8,22.4],[88.8,21.9]]]}},
    {"forest_id": "f-wgh",  "name": "Western Ghats Forest Belt",    "density": "high",   "area_hectares": 56000,  "geojson": {"type": "Polygon", "coordinates": [[[76.1,11.5],[76.6,11.5],[76.6,12.1],[76.1,12.1],[76.1,11.5]]]}},
    {"forest_id": "f-cor",  "name": "Corbett National Park Buffer", "density": "medium", "area_hectares": 31200,  "geojson": {"type": "Polygon", "coordinates": [[[78.7,29.4],[79.3,29.4],[79.3,29.9],[78.7,29.9],[78.7,29.4]]]}},
    {"forest_id": "f-sat",  "name": "Satpura Forest Reserve",       "density": "medium", "area_hectares": 28900,  "geojson": {"type": "Polygon", "coordinates": [[[77.5,22.2],[78.2,22.2],[78.2,22.7],[77.5,22.7],[77.5,22.2]]]}},
    {"forest_id": "f-kan",  "name": "Kanha Tiger Reserve Edge",     "density": "high",   "area_hectares": 19500,  "geojson": {"type": "Polygon", "coordinates": [[[80.5,22.1],[81.0,22.1],[81.0,22.5],[80.5,22.5],[80.5,22.1]]]}},
    {"forest_id": "f-raj",  "name": "Rajasthan Sparse Scrublands",  "density": "low",    "area_hectares": 9800,   "geojson": {"type": "Polygon", "coordinates": [[[73.5,26.0],[74.2,26.0],[74.2,26.5],[73.5,26.5],[73.5,26.0]]]}},
]


def _geojson_from_wkb(geom_col) -> dict | None:
    if geom_col is None:
        return None
    try:
        return mapping(to_shape(geom_col))
    except Exception:
        return None


@router.post("/powerlines", status_code=status.HTTP_201_CREATED)
async def upload_powerline(
    payload: PowerlineCreate,
    session_id: str = "",
    cache: redis_mod.Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_analysis_db),
    udb: AsyncSession = Depends(get_user_db),
):
    user = await get_session_user(session_id, cache, udb)

    geom = from_shape(shape(payload.geojson_linestring), srid=4326)
    seg = PowerlineSegment(
        segment_id=str(uuid4()),
        user_id=user.user_id,
        name=payload.name,
        voltage_kv=payload.voltage_kv,
        company_name=payload.company_name or user.organization_name,
        geometry=geom,
        segment_metadata=payload.metadata or {},
    )
    db.add(seg)
    await db.commit()
    await cache.delete(f"dashboard:{user.user_id}")
    return {"segment_id": seg.segment_id, "name": seg.name}


@router.delete("/powerlines/{segment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_powerline(
    segment_id: str,
    session_id: str = "",
    cache: redis_mod.Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_analysis_db),
    udb: AsyncSession = Depends(get_user_db),
):
    user = await get_session_user(session_id, cache, udb)
    result = await db.execute(
        select(PowerlineSegment).where(
            PowerlineSegment.segment_id == segment_id,
            PowerlineSegment.user_id == user.user_id,
        )
    )
    seg = result.scalar_one_or_none()
    if not seg:
        raise HTTPException(status_code=404, detail="Powerline not found.")
    await db.delete(seg)
    await db.commit()
    await cache.delete(f"dashboard:{user.user_id}")


@router.post("/hazards/recompute", status_code=status.HTTP_200_OK)
async def recompute_hazards(
    session_id: str = "",
    cache: redis_mod.Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_analysis_db),
    udb: AsyncSession = Depends(get_user_db),
):
    user = await get_session_user(session_id, cache, udb)

    pl_result = await db.execute(
        select(PowerlineSegment).where(PowerlineSegment.user_id == user.user_id)
    )
    powerlines_db = pl_result.scalars().all()
    if not powerlines_db:
        return {"hazards_computed": 0}

    powerlines = [
        {
            "segment_id": p.segment_id,
            "name": p.name,
            "voltage_kv": p.voltage_kv,
            "company_name": p.company_name,
            "geojson": _geojson_from_wkb(p.geometry),
        }
        for p in powerlines_db
    ]

    hazards = compute_hazards_for_user(powerlines, INDIA_FORESTS)

    await db.execute(delete(HazardZone).where(HazardZone.user_id == user.user_id))
    for h in hazards:
        geom = from_shape(shape(h["geojson"]), srid=4326) if h.get("geojson") else None
        zone = HazardZone(
            hazard_id=str(uuid4()),
            user_id=user.user_id,
            powerline_id=h["powerline_id"],
            forest_id=h["forest_id"],
            powerline_name=h["powerline_name"],
            forest_name=h["forest_name"],
            forest_density=h["forest_density"],
            risk_level=h["risk_level"],
            distance_to_forest_m=h["distance_to_forest_m"],
            buffer_radius_m=h["buffer_radius_m"],
            area_m2=h["area_m2"],
            geometry=geom,
        )
        db.add(zone)
    await db.commit()

    await cache.delete(f"dashboard:{user.user_id}")
    return {"hazards_computed": len(hazards)}


@router.get("/dashboard", response_model=DashboardGeoData)
async def get_dashboard_geodata(
    session_id: str = "",
    cache: redis_mod.Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_analysis_db),
    udb: AsyncSession = Depends(get_user_db),
):
    user = await get_session_user(session_id, cache, udb)
    cache_key = f"dashboard:{user.user_id}"
    cached = await cache.get(cache_key)
    if cached:
        return json.loads(cached)

    pl_result = await db.execute(
        select(PowerlineSegment).where(PowerlineSegment.user_id == user.user_id)
    )
    powerlines_db = pl_result.scalars().all()

    hz_result = await db.execute(
        select(HazardZone).where(HazardZone.user_id == user.user_id)
    )
    hazards_db = hz_result.scalars().all()

    powerlines_out = [
        {
            "segment_id": p.segment_id,
            "name": p.name,
            "voltageKV": p.voltage_kv,
            "companyName": p.company_name,
            "geometry": _geojson_from_wkb(p.geometry),
        }
        for p in powerlines_db
    ]

    forests_out = [
        {
            "forest_id": f["forest_id"],
            "name": f["name"],
            "density": f["density"],
            "areaHectares": f["area_hectares"],
            "geometry": f["geojson"],
        }
        for f in INDIA_FORESTS
    ]

    hazards_out = [
        {
            "hazard_id": h.hazard_id,
            "powerlineName": h.powerline_name,
            "forestName": h.forest_name,
            "forestDensity": h.forest_density,
            "riskLevel": h.risk_level,
            "distanceToForestM": h.distance_to_forest_m,
            "bufferRadiusM": h.buffer_radius_m,
            "areaM2": h.area_m2,
            "geometry": _geojson_from_wkb(h.geometry),
        }
        for h in hazards_db
    ]

    high   = sum(1 for h in hazards_out if h["riskLevel"] == "high")
    medium = sum(1 for h in hazards_out if h["riskLevel"] == "medium")
    low    = sum(1 for h in hazards_out if h["riskLevel"] == "low")

    out = DashboardGeoData(
        powerlines=powerlines_out,
        forests=forests_out,
        hazards=hazards_out,
        stats={"powerlines": len(powerlines_out), "forests": len(forests_out), "high": high, "medium": medium, "low": low},
    )
    out_json = out.model_dump(mode="json")
    await cache.set(cache_key, json.dumps(out_json), ex=300)
    return out_json