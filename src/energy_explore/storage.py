import os
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

def lat_band_2deg(lat: float) -> str:
    low = 2.0 * np.floor(lat / 2.0)
    high = low + 2.0
    return f"{low:.0f}_{high:.0f}"

def write_parquet_row(row: dict, arrays: dict, output_dir: str) -> str:
    # Use .get() to handle missing optional keys like pv_power or wind_power
    # Fallback to zero arrays if they are not provided (e.g., during CLI bulk generation)
    length = len(arrays["ghi"])
    
    data = {
        "grid_id": [row["grid_id"]],
        "lat": [row["lat"]],
        "lon": [row["lon"]],
        "ghi": [arrays["ghi"]],
        "dni": [arrays["dni"]],
        "dhi": [arrays["dhi"]],
        "uv": [arrays["uv"]],
        "temp": [arrays["temp"]],
        "wind": [arrays["wind"]],
        "wind_dir": [arrays["wind_dir"]],
        "pv_power": [arrays.get("pv_power", np.zeros(length, dtype=np.float32))],
        "wind_power": [arrays.get("wind_power", np.zeros(length, dtype=np.float32))],
    }
    schema = pa.schema([
        pa.field("grid_id", pa.string()),
        pa.field("lat", pa.float32()),
        pa.field("lon", pa.float32()),
        pa.field("ghi", pa.list_(pa.float32())),
        pa.field("dni", pa.list_(pa.float32())),
        pa.field("dhi", pa.list_(pa.float32())),
        pa.field("uv", pa.list_(pa.float32())),
        pa.field("temp", pa.list_(pa.float32())),
        pa.field("wind", pa.list_(pa.float32())),
        pa.field("wind_dir", pa.list_(pa.float32())),
        pa.field("pv_power", pa.list_(pa.float32())),
        pa.field("wind_power", pa.list_(pa.float32())),
    ])
    
    table = pa.Table.from_pydict(data, schema=schema)
    band = lat_band_2deg(float(row["lat"]))
    os.makedirs(f"{output_dir}/lat_band={band}", exist_ok=True)
    path = f"{output_dir}/lat_band={band}/cell_{row['grid_id']}.parquet"
    pq.write_table(table, path)
    return path
