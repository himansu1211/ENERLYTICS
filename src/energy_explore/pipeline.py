import os
import numpy as np
import requests
from typing import Iterable, Dict, Any, List

def _extract_nasa_monthly(param_data: Dict[str, Any]) -> np.ndarray:
    """
    Extracts 12 monthly values from NASA POWER climatology dictionary or list.
    NASA returns keys like '01'..'12' or a list of 13 values.
    """
    if isinstance(param_data, dict):
        keys = [f"{i:02d}" for i in range(1, 13)]
        return np.array([param_data[k] for k in keys], dtype=np.float32)
    elif isinstance(param_data, list):
        return np.array(param_data[:12], dtype=np.float32)
    else:
        # Fallback if it's already a nested dict under 'parameter' key
        if 'parameter' in param_data:
            return _extract_nasa_monthly(param_data['parameter'])
        return np.zeros(12, dtype=np.float32)

def fetch_nasa_power_climatology(lat: float, lon: float) -> Dict[str, Any]:
    """
    Fetches real-world 30-year monthly climatology from NASA POWER API.
    Parameters: GHI, Temperature, Wind Speed, Wind Direction.
    """
    url = "https://power.larc.nasa.gov/api/temporal/climatology/point"
    params = {
        "parameters": "ALLSKY_SFC_SW_DWN,T2M,WS2M,WD10M",
        "community": "RE",
        "longitude": lon,
        "latitude": lat,
        "format": "JSON"
    }
    
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        params_data = data['properties']['parameter']
        
        ghi = _extract_nasa_monthly(params_data['ALLSKY_SFC_SW_DWN'])
        ghi = (ghi * 1000.0) / 24.0 # kWh/m2/day to W/m2
        
        temp = _extract_nasa_monthly(params_data['T2M'])
        wind_speed = _extract_nasa_monthly(params_data['WS2M'])
        wind_dir = _extract_nasa_monthly(params_data['WD10M'])
        
        return {
            "monthly_ghi_means": ghi,
            "monthly_temp_means": temp,
            "monthly_wind_means": wind_speed,
            "monthly_wind_dir": wind_dir,
            "is_fallback": False,
            "nasa_data_used": True
        }
    except Exception as e:
        # Fallback to a safer "representative" India mean if API fails
        months = np.arange(12)
        return {
            "monthly_ghi_means": (180.0 + 40.0 * np.sin(2.0 * np.pi * (months - 1) / 12.0)).astype(np.float32),
            "monthly_temp_means": (24.0 + 8.0 * np.sin(2.0 * np.pi * (months - 3) / 12.0)).astype(np.float32),
            "monthly_wind_means": (3.5 + 1.0 * np.sin(2.0 * np.pi * (months + 2) / 12.0)).astype(np.float32),
            "monthly_wind_dir": np.full(12, 270.0, dtype=np.float32),
            "is_fallback": True,
            "nasa_data_used": False
        }

def generate_grid(lat_min: float, lat_max: float, lon_min: float, lon_max: float, res_deg: float = 0.25) -> List[Dict[str, Any]]:
    lats = np.arange(lat_min, lat_max + 1e-6, res_deg)
    lons = np.arange(lon_min, lon_max + 1e-6, res_deg)
    cells: List[Dict[str, Any]] = []
    gid = 0
    for lat in lats:
        for lon in lons:
            gid += 1
            cells.append({"grid_id": f"{lat:.2f}_{lon:.2f}", "lat": float(lat), "lon": float(lon), "elevation": 0.0})
    return cells

def enrich_cell_with_climatology(cell: Dict[str, Any], clim: Dict[str, np.ndarray]) -> Dict[str, Any]:
    out = dict(cell)
    out.update(clim)
    return out

def process_cells(cells: Iterable[Dict[str, Any]], output_dir: str, tau: float = 0.75) -> list[str]:
    from .core import generate_cell
    from .storage import write_parquet_row
    from tqdm import tqdm
    
    os.makedirs(output_dir, exist_ok=True)
    paths: list[str] = []
    for cell in tqdm(cells, desc="Processing Grid Cells"):
        # Use real NASA data for bulk processing
        clim = fetch_nasa_power_climatology(cell["lat"], cell["lon"])
        row = enrich_cell_with_climatology(cell, clim)
        arrays = generate_cell(row, tau=tau)
        p = write_parquet_row(row, arrays, output_dir)
        paths.append(p)
    return paths