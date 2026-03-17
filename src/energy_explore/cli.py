"""
Command line interface for bulk generating ENERLYTICS data.
"""
import argparse
import os
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
from .pipeline import generate_grid, fetch_nasa_power_climatology, enrich_cell_with_climatology
from .core import generate_cell
from .storage import write_parquet_row

def process_single_cell(cell, output_dir, tau, resume):
    grid_id = cell["grid_id"]
    lat = cell["lat"]
    # Check resume
    from .storage import lat_band_2deg
    band = lat_band_2deg(lat)
    path = f"{output_dir}/lat_band={band}/cell_{grid_id}.parquet"
    if resume and os.path.exists(path):
        return None

    try:
        clim = fetch_nasa_power_climatology(cell["lat"], cell["lon"])
        row = enrich_cell_with_climatology(cell, clim)
        arrays = generate_cell(row, tau=tau)
        # Note: pv_power and wind_power are not in arrays by default now, 
        # write_parquet_row handles fallback to zeros.
        write_parquet_row(row, arrays, output_dir)
        return path
    except Exception as e:
        print(f"Error processing cell {grid_id}: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="ENERLYTICS Bulk Grid Generator")
    parser.add_argument("--lat-min", type=float, default=8.0)
    parser.add_argument("--lat-max", type=float, default=37.0)
    parser.add_argument("--lon-min", type=float, default=68.0)
    parser.add_argument("--lon-max", type=float, default=97.0)
    parser.add_argument("--res", type=float, default=0.25)
    parser.add_argument("--output", type=str, default="./database")
    parser.add_argument("--tau", type=float, default=0.75)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    
    args = parser.parse_args()
    
    cells = generate_grid(args.lat_min, args.lat_max, args.lon_min, args.lon_max, args.res)
    print(f"Total cells to process: {len(cells)}")
    
    if args.dry_run:
        print("Dry run enabled. Exiting.")
        return

    os.makedirs(args.output, exist_ok=True)
    
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        list(tqdm(executor.map(lambda c: process_single_cell(c, args.output, args.tau, args.resume), cells), 
                  total=len(cells), desc="Generating Grid"))

if __name__ == "__main__":
    main()
