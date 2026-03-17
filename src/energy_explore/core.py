import numpy as np
import pandas as pd
import hashlib
from typing import Any
from .config import GLOBAL_SEED

I_SC: float = 1367.0

def stable_rng(grid_id: str, global_seed: int = GLOBAL_SEED) -> np.random.Generator:
    s = f"{grid_id}:{global_seed}".encode("utf-8")
    h = hashlib.sha256(s).hexdigest()
    seed_int = int(h[:16], 16) % (2**32 - 1)
    return np.random.default_rng(seed_int)

def day_angle(n: np.ndarray) -> np.ndarray:
    return 2.0 * np.pi * (n - 1) / 365.0

def declination(n: np.ndarray) -> np.ndarray:
    g = day_angle(n)
    return (0.006918
            - 0.399912 * np.cos(g)
            + 0.070257 * np.sin(g)
            - 0.006758 * np.cos(2 * g)
            + 0.000907 * np.sin(2 * g)
            - 0.002697 * np.cos(3 * g)
            + 0.00148  * np.sin(3 * g))

def solar_geometry_lst(lat_deg: float) -> dict[str, np.ndarray]:
    h = np.arange(8760, dtype=np.int32)
    doy = 1 + (h // 24)
    hod = h % 24
    phi = np.deg2rad(lat_deg)
    delta = declination(doy)
    H = np.deg2rad(15.0 * (hod - 12.0))
    
    # Zenith calculation
    cos_zen = np.clip(np.sin(phi) * np.sin(delta) + np.cos(phi) * np.cos(delta) * np.cos(H), 0.0, None)
    
    # Solar Azimuth calculation
    # cos(az) = (sin(delta)*cos(phi) - cos(delta)*sin(phi)*cos(H)) / sin(zenith)
    sin_zen = np.sqrt(1 - cos_zen**2)
    cos_az = (np.sin(delta) * np.cos(phi) - np.cos(delta) * np.sin(phi) * np.cos(H)) / np.maximum(sin_zen, 1e-6)
    # az = 0 is South, positive West (matches our gamma convention)
    sol_az = np.where(H >= 0, np.rad2deg(np.arccos(np.clip(cos_az, -1, 1))), 
                      -np.rad2deg(np.arccos(np.clip(cos_az, -1, 1))))
    
    e0 = 1.0 + 0.033 * np.cos(2.0 * np.pi * doy / 365.0)
    I0 = I_SC * e0
    return {
        "doy": doy.astype(np.int32), 
        "hod": hod.astype(np.int32), 
        "cos_zenith": cos_zen.astype(np.float32), 
        "solar_azimuth": sol_az.astype(np.float32),
        "I0": I0.astype(np.float32)
    }

def clear_sky_ghi(I0: np.ndarray, cos_zen: np.ndarray, tau: float = 0.75) -> np.ndarray:
    """
    Computes clear-sky GHI with a zenith-dependent transmittance.
    """
    # Simple zenith-dependent transmittance model
    cz = np.maximum(cos_zen, 0.01)
    ghi_clear = I0 * cz * (tau ** (1.0 / cz))
    return np.where(cos_zen > 0.0, ghi_clear, 0.0).astype(np.float32)

def ar1_series(length: int, phi: float, sigma: float, rng: np.random.Generator,
               init: float = 0.8, bounds: tuple[float, float] = (0.2, 1.1)) -> np.ndarray:
    x = np.empty(length, dtype=np.float32)
    x[0] = np.clip(init, bounds[0], bounds[1])
    for t in range(1, length):
        x[t] = phi * x[t - 1] + rng.normal(0.0, sigma)
        if x[t] < bounds[0]:
            x[t] = bounds[0]
        elif x[t] > bounds[1]:
            x[t] = bounds[1]
    return x

def monthly_indices() -> list[np.ndarray]:
    h = np.arange(8760, dtype=np.int32)
    doy = 1 + (h // 24)
    month_lengths = np.array([31,28,31,30,31,30,31,31,30,31,30,31])
    idx = []
    start = 1
    for m in range(12):
        end = start + month_lengths[m] - 1
        mask = (doy >= start) & (doy <= end)
        idx.append(np.where(mask)[0])
        start = end + 1
    return idx

def renormalize_monthly(y: np.ndarray, target_monthly_means: np.ndarray) -> np.ndarray:
    y = y.copy()
    idxs = monthly_indices()
    for m in range(12):
        s = float(y[idxs[m]].mean())
        t = float(target_monthly_means[m])
        scale = t / s if s > 0 else 1.0
        y[idxs[m]] *= scale
    return y

def reindl_separation(ghi: np.ndarray, I0: np.ndarray, cos_zen: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Separates GHI into DNI and DHI using the Reindl model.
    """
    eps = 1e-6
    # Clearness index Kt = GHI / I0_horizontal
    I0_h = np.maximum(I0 * cos_zen, eps)
    Kt = np.clip(ghi / I0_h, 0.0, 1.2)
    
    # Reindl diffuse fraction model
    fd = np.empty_like(Kt, dtype=np.float32)
    
    # Interval 1: Kt <= 0.3
    mask1 = (Kt <= 0.3) & (cos_zen > 0)
    fd[mask1] = 1.020 - 0.254 * Kt[mask1] + 0.012 * cos_zen[mask1]
    
    # Interval 2: 0.3 < Kt < 0.78
    mask2 = (Kt > 0.3) & (Kt < 0.78) & (cos_zen > 0)
    fd[mask2] = 1.400 - 1.749 * Kt[mask2] + 0.177 * cos_zen[mask2]
    
    # Interval 3: Kt >= 0.78
    mask3 = (Kt >= 0.78) & (cos_zen > 0)
    fd[mask3] = 0.486 * Kt[mask3] - 0.182 * cos_zen[mask3]
    
    # Default for night or very low angles
    fd[cos_zen <= 0] = 0.0
    
    # Physical constraints
    fd = np.clip(fd, 0.0, 1.0)
    
    dhi = ghi * fd
    beam_horizontal = np.maximum(ghi - dhi, 0.0)
    dni = np.where(cos_zen > 0.01, beam_horizontal / np.maximum(cos_zen, eps), 0.0).astype(np.float32)
    
    return dni.astype(np.float32), dhi.astype(np.float32)

def separate_ghi(ghi: np.ndarray, I0: np.ndarray, cos_zen: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    return reindl_separation(ghi, I0, cos_zen)

def temperature_series(monthly_means: np.ndarray, elevation_m: float,
                       rng: np.random.Generator, phi: float = 0.7, sigma: float = 0.8,
                       amp_by_month: np.ndarray | None = None, h_shift: float = 16.0) -> np.ndarray:
    h = np.arange(8760, dtype=np.float32)
    idxs = monthly_indices()
    base = np.empty(8760, dtype=np.float32)
    if amp_by_month is None:
        amp_by_month = np.clip(0.15 * monthly_means, 2.0, 8.0).astype(np.float32)
    for m in range(12):
        A = float(amp_by_month[m])
        mu = float(monthly_means[m])
        t = h[idxs[m]] % 24
        base[idxs[m]] = mu + A * np.sin(2.0 * np.pi * (t - h_shift) / 24.0)
    res = ar1_series(8760, phi=phi, sigma=sigma, rng=rng, init=0.0, bounds=(-10.0, 10.0))
    lapse = -6.5 * elevation_m / 1000.0
    return (base + res + lapse).astype(np.float32)

def wind_series(monthly_means: np.ndarray, 
                monthly_dir: np.ndarray,
                rng: np.random.Generator,
                phi: float = 0.4, sigma: float = 0.7) -> tuple[np.ndarray, np.ndarray]:
    idxs = monthly_indices()
    y_speed = np.empty(8760, dtype=np.float32)
    y_dir = np.empty(8760, dtype=np.float32)
    for m in range(12):
        y_speed[idxs[m]] = float(monthly_means[m])
        y_dir[idxs[m]] = float(monthly_dir[m])
        
    res_speed = ar1_series(8760, phi=phi, sigma=sigma, rng=rng, init=0.0, bounds=(-3.0, 3.0))
    # Small variations in direction (stochastic)
    res_dir = rng.normal(0.0, 5.0, 8760)
    
    return np.maximum(y_speed + res_speed, 0.0).astype(np.float32), (y_dir + res_dir) % 360.0

def compute_monthly_means(y: np.ndarray) -> np.ndarray:
    idxs = monthly_indices()
    return np.array([float(y[idxs[m]].mean()) for m in range(12)], dtype=np.float32)

def simulate_pv_power(ghi: np.ndarray, temp: np.ndarray, 
                      capacity_kw: float = 1.0, 
                      temp_coeff: float = -0.004) -> np.ndarray:
    """
    Simulates hourly PV power production (kW) for a standard silicon module.
    """
    t_ref = 25.0
    t_cell = temp + 0.03 * ghi
    temp_factor = 1.0 + temp_coeff * (t_cell - t_ref)
    power = capacity_kw * (ghi / 1000.0) * temp_factor
    return np.maximum(power, 0.0).astype(np.float32)

def simulate_wind_power(wind_speed: np.ndarray, 
                        capacity_kw: float = 1.0,
                        cut_in: float = 3.0,
                        rated_speed: float = 12.0,
                        cut_out: float = 25.0) -> np.ndarray:
    """
    Simulates hourly Wind power production (kW) using a simplified power curve.
    """
    power = np.zeros_like(wind_speed)
    
    # Simple power curve: linear between cut-in and rated, constant at capacity until cut-out
    mask_gen = (wind_speed >= cut_in) & (wind_speed < rated_speed)
    mask_rated = (wind_speed >= rated_speed) & (wind_speed < cut_out)
    
    power[mask_gen] = capacity_kw * ((wind_speed[mask_gen] - cut_in) / (rated_speed - cut_in))**3
    power[mask_rated] = capacity_kw
    
    return power.astype(np.float32)

def generate_cell(row: dict[str, Any], tau: float = 0.75) -> dict[str, np.ndarray]:
    rng = stable_rng(str(row["grid_id"]))
    geom = solar_geometry_lst(float(row["lat"]))
    ghi_clear = clear_sky_ghi(geom["I0"], geom["cos_zenith"], tau=tau)
    kt = ar1_series(8760, phi=0.85, sigma=0.07, rng=rng, init=0.8, bounds=(0.2, 1.1))
    ghi_syn = ghi_clear * kt
    ghi_monthly = np.array(row["monthly_ghi_means"], dtype=np.float32)
    ghi = renormalize_monthly(ghi_syn, ghi_monthly)
    
    # Correctly separated components using I0 and Zenith
    dni, dhi = separate_ghi(ghi, geom["I0"], geom["cos_zenith"])
    
    # Calculate UV rays (approx 4.5% of GHI)
    uv = (ghi * 0.045).astype(np.float32)
    
    t_means = np.array(row["monthly_temp_means"], dtype=np.float32)
    wind_means = np.array(row["monthly_wind_means"], dtype=np.float32)
    wind_dir_means = np.array(row["monthly_wind_dir"], dtype=np.float32)
    
    temp = temperature_series(t_means, float(row["elevation"]), rng)
    wind_speed, wind_dir = wind_series(wind_means, wind_dir_means, rng)
    
    return {
        "ghi": ghi.astype(np.float32), 
        "dni": dni, 
        "dhi": dhi, 
        "uv": uv,
        "temp": temp, 
        "wind": wind_speed,
        "wind_dir": wind_dir,
        "cos_zenith": geom["cos_zenith"],
        "solar_azimuth": geom["solar_azimuth"],
        "I0": geom["I0"]
    }
