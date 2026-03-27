import httpx
import asyncio
from typing import Optional
from ..core.config import settings


SENTINEL_BASE = "https://services.sentinel-hub.com/api/v1"
OPENTOPO_BASE = "https://portal.opentopography.org/API"


async def fetch_sentinel2_metadata(bbox: list[float], date_from: str, date_to: str) -> dict:
    headers = {"Authorization": f"Bearer {settings.sentinel_api_key}"}
    payload = {
        "bbox": bbox,
        "datetime": f"{date_from}/{date_to}",
        "collections": ["sentinel-2-l2a"],
        "limit": 1,
        "sortby": [{"field": "properties.eo:cloud_cover", "direction": "asc"}],
    }
    for attempt in range(5):
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(f"{SENTINEL_BASE}/catalog/search", json=payload, headers=headers)
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError:
            wait = 2 ** attempt
            await asyncio.sleep(wait)
    return {}


async def fetch_sentinel2_ndvi(bbox: list[float]) -> Optional[float]:
    headers = {"Authorization": f"Bearer {settings.sentinel_api_key}"}
    evalscript = """
    //VERSION=3
    function setup() { return { input: ["B04","B08"], output: { bands: 1 } }; }
    function evaluatePixel(s) { return [(s.B08 - s.B04) / (s.B08 + s.B04)]; }
    """
    payload = {
        "input": {
            "bounds": {"bbox": bbox, "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"}},
            "data": [{"type": "sentinel-2-l2a", "dataFilter": {"maxCloudCoverage": 20}}],
        },
        "evalscript": evalscript,
        "output": {"width": 1, "height": 1, "responses": [{"identifier": "default", "format": {"type": "application/json"}}]},
    }
    for attempt in range(5):
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(f"{SENTINEL_BASE}/process", json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                return float(data["outputs"]["default"]["bands"]["B0"][0][0])
        except Exception:
            await asyncio.sleep(2 ** attempt)
    return None


async def fetch_lidar_point_cloud(bbox: list[float], output_path: str) -> bool:
    params = {
        "demtype": "SRTMGL1",
        "west": bbox[0], "south": bbox[1], "east": bbox[2], "north": bbox[3],
        "outputFormat": "GTiff",
        "API_Key": settings.opentopo_api_key,
    }
    for attempt in range(5):
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.get(f"{OPENTOPO_BASE}/globaldem", params=params)
                resp.raise_for_status()
                with open(output_path, "wb") as f:
                    f.write(resp.content)
                return True
        except Exception:
            await asyncio.sleep(2 ** attempt)
    return False