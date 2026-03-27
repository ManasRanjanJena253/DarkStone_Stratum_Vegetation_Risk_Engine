import numpy as np
from typing import Optional
import os


def extract_canopy_height(dem_path: str, dtm_path: Optional[str] = None) -> Optional[float]:
    try:
        import rasterio
        with rasterio.open(dem_path) as src:
            arr = src.read(1).astype(float)
            arr[arr == src.nodata] = np.nan
        if dtm_path and os.path.exists(dtm_path):
            with rasterio.open(dtm_path) as src_dtm:
                dtm = src_dtm.read(1).astype(float)
                dtm[dtm == src_dtm.nodata] = np.nan
            chm = arr - dtm
        else:
            chm = arr
        valid = chm[~np.isnan(chm)]
        if len(valid) == 0:
            return None
        return float(np.percentile(valid, 95))
    except Exception:
        return None


def estimate_wire_height_from_dem(dem_path: str) -> Optional[float]:
    try:
        import rasterio
        with rasterio.open(dem_path) as src:
            arr = src.read(1).astype(float)
            arr[arr == src.nodata] = np.nan
        valid = arr[~np.isnan(arr)]
        if len(valid) == 0:
            return None
        return float(np.percentile(valid, 10)) + 10.0
    except Exception:
        return None


def compute_clearance(wire_height: Optional[float], tree_height: Optional[float]) -> Optional[float]:
    if wire_height is None or tree_height is None:
        return None
    return round(wire_height - tree_height, 3)