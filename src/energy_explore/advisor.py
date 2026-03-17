"""
Installation advisory module for ENERLYTICS.
Includes solar tilt optimization, row spacing, and wind resource assessment.
"""
import numpy as np
from typing import Dict, Any
from scipy.stats import weibull_min

HELLMANN_EXPONENTS = {
    "open_flat": 0.143,
    "agricultural": 0.20,
    "suburban": 0.25,
    "urban_forest": 0.30,
    "coastal": 0.12
}

# Indian Benchmark Vendor Panel Data
VENDOR_PANELS = {
    "Waaree Bi-550": {"wattage": 550, "eff": 21.3, "temp_coeff": -0.34, "bifacial": True},
    "Adani Shine 540": {"wattage": 540, "eff": 20.9, "temp_coeff": -0.35, "bifacial": False},
    "Vikram Somera 550": {"wattage": 550, "eff": 21.1, "temp_coeff": -0.36, "bifacial": False},
    "Tata Power Solar 545": {"wattage": 545, "eff": 21.0, "temp_coeff": -0.35, "bifacial": False},
    "Goldi HELOC 550": {"wattage": 550, "eff": 21.3, "temp_coeff": -0.35, "bifacial": True}
}

def compute_tilted_irradiance(
    ghi: np.ndarray,
    dni: np.ndarray,
    dhi: np.ndarray,
    cos_zenith: np.ndarray,
    tilt_deg: float,
    azimuth_deg: float,
    I0: np.ndarray | None = None,
    solar_azimuth: np.ndarray | None = None,
    use_perez: bool = True,
    albedo: float = 0.20
) -> np.ndarray:
    """
    Computes POA irradiance using either Perez (anisotropic) or Liu-Jordan (isotropic).
    """
    if use_perez:
        from .perez import perez_poa_total
        # Ensure I0 is not None for Perez
        if I0 is None:
            I0 = np.full_like(ghi, 1367.0)
        return perez_poa_total(ghi, dni, dhi, I0, cos_zenith, tilt_deg, azimuth_deg, solar_azimuth, albedo)
    else:
        # Fallback to Isotropic Liu & Jordan
        tilt = np.deg2rad(tilt_deg)
        panel_az = np.deg2rad(azimuth_deg)
        zenith_rad = np.arccos(np.clip(cos_zenith, 0, 1))
        
        if solar_azimuth is None:
            solar_az_rad = np.zeros_like(ghi)
        else:
            solar_az_rad = np.deg2rad(solar_azimuth)
            
        # Beam
        sin_zen = np.sin(zenith_rad)
        cos_aoi = cos_zenith * np.cos(tilt) + sin_zen * np.sin(tilt) * np.cos(solar_az_rad - panel_az)
        poa_beam = dni * np.maximum(0, cos_aoi)
        
        # Sky diffuse (isotropic)
        poa_diffuse = dhi * (1 + np.cos(tilt)) / 2
        
        # Ground reflected
        poa_ground = ghi * albedo * (1 - np.cos(tilt)) / 2
        
        total = poa_beam + poa_diffuse + poa_ground
        return np.where(cos_zenith > 0, np.maximum(total, 0), 0).astype(np.float32)

def optimal_solar_tilt(
    lat_deg: float,
    ghi: np.ndarray,
    dni: np.ndarray,
    dhi: np.ndarray,
    cos_zenith: np.ndarray,
    I0: np.ndarray,
    solar_azimuth: np.ndarray,
    use_perez: bool = True
) -> Dict[str, Any]:
    """
    Sweeps tilts from 0 to 70 to find the optimal annual energy yield point.
    """
    tilts = np.arange(0, 71, 2.5)
    yields = []
    
    # We only sweep South (180 deg) for N. Hemisphere India
    azimuth = 180.0
    
    for t in tilts:
        poa = compute_tilted_irradiance(ghi, dni, dhi, cos_zenith, t, azimuth, I0, solar_azimuth, use_perez)
        yields.append(poa.sum())
        
    idx_opt = np.argmax(yields)
    opt_tilt = tilts[idx_opt]
    
    # Gain vs flat
    gain_pct = (yields[idx_opt] / yields[0] - 1) * 100 if yields[0] > 0 else 0
    
    return {
        "optimal_tilt": float(opt_tilt),
        "optimal_azimuth": 180.0,
        "annual_poa_kwh": float(yields[idx_opt] / 1000.0),
        "gain_vs_flat_pct": float(gain_pct),
        "model_used": "Perez 1990" if use_perez else "Isotropic (Liu-Jordan)"
    }

def compute_row_spacing(tilt_deg: float, lat_deg: float, module_length: float = 2.0) -> Dict[str, float]:
    """
    Computes shadow-free spacing at winter solstice noon.
    """
    # Solar altitude at winter solstice noon: alpha = 90 - lat - 23.45
    solar_alt = 90 - abs(lat_deg) - 23.45
    solar_alt = max(solar_alt, 5.0)
    
    alpha_rad = np.deg2rad(solar_alt)
    beta_rad = np.deg2rad(tilt_deg)
    
    # h = L * sin(beta)
    h = module_length * np.sin(beta_rad)
    # spacing = h / tan(alpha)
    pitch = h / np.tan(alpha_rad) + module_length * np.cos(beta_rad)
    
    return {
        "min_row_spacing_m": float(h / np.tan(alpha_rad)),
        "row_pitch_m": float(pitch),
        "gcr": float(module_length / pitch) if pitch > 0 else 0
    }

def optimal_wind_height(
    wind_speed_2m: np.ndarray,
    terrain_type: str = "open_flat"
) -> Dict[str, Any]:
    """
    Evaluates wind resource at multiple hub heights.
    """
    heights = [10, 20, 30, 50, 80, 100]
    alpha = HELLMANN_EXPONENTS.get(terrain_type, 0.143)
    
    results = []
    for h in heights:
        # v_h = v_ref * (h / h_ref)^alpha
        v_h = wind_speed_2m * (h / 2.0)**alpha
        results.append({
            "height_m": h,
            "mean_speed_ms": float(v_h.mean()),
            "power_density_wm2": float(0.5 * 1.225 * np.mean(v_h**3))
        })
        
    return {
        "height_data": results,
        "recommended_height_m": 80 if results[-1]["mean_speed_ms"] > 5.0 else 30
    }

def weibull_fit(wind_speed: np.ndarray) -> dict:
    """
    Fits Weibull distribution to wind speed data.
    """
    valid = wind_speed[wind_speed > 0.5]
    if len(valid) < 100:
        return {"k": 0.0, "c_ms": 0.0, "capacity_factor_pct": 0.0, "p50_speed_ms": 0.0, "p90_speed_ms": 0.0}
        
    shape, loc, scale = weibull_min.fit(valid, floc=0)
    
    # P90: speed exceeded 90% of time -> 10th percentile of CDF
    p90 = weibull_min.ppf(0.1, shape, loc=0, scale=scale)
    p50 = weibull_min.ppf(0.5, shape, loc=0, scale=scale)
    
    # Capacity Factor integration (numerical)
    v_range = np.linspace(0, 25, 100)
    pdf = weibull_min.pdf(v_range, shape, loc=0, scale=scale)
    # Simple power curve: 0 below 3, cubic to 12, 1 until 25
    power = np.where(v_range < 3, 0, np.where(v_range < 12, (v_range - 3)**3 / (12 - 3)**3, 1))
    cf = np.trapezoid(pdf * power, v_range) * 100
    
    return {
        "k": float(shape),
        "c_ms": float(scale),
        "capacity_factor_pct": float(cf),
        "p50_speed_ms": float(p50),
        "p90_speed_ms": float(p90)
    }

def generate_installation_advisory(
    data: Dict[str, np.ndarray],
    lat_deg: float,
    use_perez: bool = True,
    module_length: float = 2.0
) -> Dict[str, Any]:
    """
    Top-level function to generate both solar and wind advisories.
    """
    solar = optimal_solar_tilt(
        lat_deg, data["ghi"], data["dni"], data["dhi"], 
        data["cos_zenith"], data["I0"], data["solar_azimuth"], use_perez
    )
    
    # Compute isotropic for comparison gain metric
    if use_perez:
        iso = optimal_solar_tilt(
            lat_deg, data["ghi"], data["dni"], data["dhi"], 
            data["cos_zenith"], data["I0"], data["solar_azimuth"], False
        )
        solar["perez_gain_vs_isotropic_pct"] = ((solar["annual_poa_kwh"] / iso["annual_poa_kwh"]) - 1) * 100
    
    spacing = compute_row_spacing(solar["optimal_tilt"], lat_deg, module_length)
    solar.update(spacing)
    
    wind = optimal_wind_height(data["wind"])
    wb = weibull_fit(data["wind"])
    wind.update(wb)
    
    return {
        "solar": solar,
        "wind": wind
    }
