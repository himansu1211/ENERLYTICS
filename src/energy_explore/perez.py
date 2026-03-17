"""
Perez Sky Diffuse Model (1990) implementation for anisotropic sky transposition.
Ref: Perez, R. et al. (1990). Solar Energy, 44(5), 271–289.
"""
import numpy as np

def _get_epsilon_bin(epsilon: np.ndarray) -> np.ndarray:
    """
    Returns the Perez bin index (0-7) for sky clearness epsilon.
    """
    bins = np.array([1.065, 1.23, 1.5, 1.95, 2.8, 4.5, 6.2])
    return np.digitize(epsilon, bins)

def perez_diffuse(
    dhi: np.ndarray,
    dni: np.ndarray,
    I0: np.ndarray,
    cos_zenith: np.ndarray,
    tilt_deg: float,
    azimuth_deg: float,
    solar_azimuth: np.ndarray | None = None,
) -> np.ndarray:
    """
    Computes diffuse POA irradiance [W/m²] using the Perez 1990 model.
    """
    n = len(dhi)
    tilt = np.deg2rad(tilt_deg)
    # Our convention: 180 = South, 90 = East, 270 = West (matching pvlib/standard)
    panel_az = np.deg2rad(azimuth_deg)
    
    # Zenith in radians and degrees
    zenith_rad = np.arccos(np.clip(cos_zenith, 0, 1))
    zenith_deg = np.rad2deg(zenith_rad)
    
    # Solar Azimuth estimation if not provided
    if solar_azimuth is None:
        # Simplified placeholder for vectorised solar azimuth if needed
        # In this project, solar_azimuth is passed from core.py
        solar_az_rad = np.zeros(n)
    else:
        solar_az_rad = np.deg2rad(solar_azimuth)

    # Angle of Incidence (AOI)
    # cos(AOI) = cos(zen)*cos(tilt) + sin(zen)*sin(tilt)*cos(sol_az - panel_az)
    sin_zen = np.sin(zenith_rad)
    cos_aoi = cos_zenith * np.cos(tilt) + sin_zen * np.sin(tilt) * np.cos(solar_az_rad - panel_az)
    a = np.maximum(0, cos_aoi)
    b = np.maximum(0.087, cos_zenith) # cos(85 deg) approx
    
    # Airmass (Kasten-Young approximation)
    am = 1.0 / (cos_zenith + 0.50572 * (96.07995 - zenith_deg)**-1.6364)
    am = np.clip(am, 1, 20)
    
    # Sky brightness delta
    delta = dhi * am / np.maximum(I0, 1e-6)
    
    # Sky clearness epsilon
    # eps = [ (dhi+dni)/dhi + 1.041*z^3 ] / [ 1 + 1.041*z^3 ]
    z3 = zenith_rad**3
    epsilon = (((dhi + dni) / np.maximum(dhi, 1e-6)) + 1.041 * z3) / (1 + 1.041 * z3)
    
    # Perez Coefficients (All-sites composite 1990)
    f11 = np.array([-0.008, 0.130, 0.330, 0.568, 0.873, 1.132, 1.060, 0.678])
    f12 = np.array([0.588, 0.683, 0.487, 0.187, -0.392, -1.237, -1.600, -0.327])
    f13 = np.array([-0.062, -0.151, -0.221, -0.295, -0.362, -0.412, -0.359, -0.250])
    f21 = np.array([-0.060, -0.019, 0.055, 0.109, 0.226, 0.288, 0.264, 0.156])
    f22 = np.array([0.072, 0.066, -0.064, -0.152, -0.462, -0.823, -1.127, -1.377])
    f23 = np.array([-0.022, -0.029, -0.026, -0.014, 0.001, 0.056, 0.131, 0.251])
    
    idx = _get_epsilon_bin(epsilon)
    
    F1 = np.maximum(0, f11[idx] + f12[idx]*delta + f13[idx]*zenith_rad)
    F2 = f21[idx] + f22[idx]*delta + f23[idx]*zenith_rad
    
    # Perez diffuse on tilted surface
    term1 = (1 - F1) * (1 + np.cos(tilt)) / 2
    term2 = F1 * (a / b)
    term3 = F2 * np.sin(tilt)
    
    ed_tilted = dhi * (term1 + term2 + term3)
    
    # Day/Night mask
    ed_tilted = np.where(cos_zenith > 0, np.maximum(ed_tilted, 0), 0)
    
    return ed_tilted.astype(np.float32)

def perez_poa_total(
    ghi: np.ndarray,
    dni: np.ndarray,
    dhi: np.ndarray,
    I0: np.ndarray,
    cos_zenith: np.ndarray,
    tilt_deg: float,
    azimuth_deg: float,
    solar_azimuth: np.ndarray | None = None,
    albedo: float = 0.20,
) -> np.ndarray:
    """
    Computes total POA irradiance [W/m²] using Perez diffuse model.
    Total = Beam + Perez Diffuse + Ground Reflected.
    """
    tilt = np.deg2rad(tilt_deg)
    panel_az = np.deg2rad(azimuth_deg)
    zenith_rad = np.arccos(np.clip(cos_zenith, 0, 1))
    
    if solar_azimuth is None:
        solar_az_rad = np.zeros_like(ghi)
    else:
        solar_az_rad = np.deg2rad(solar_azimuth)

    # 1. Beam Component
    sin_zen = np.sin(zenith_rad)
    cos_aoi = cos_zenith * np.cos(tilt) + sin_zen * np.sin(tilt) * np.cos(solar_az_rad - panel_az)
    poa_beam = dni * np.maximum(0, cos_aoi)
    
    # 2. Diffuse Component (Perez)
    poa_diffuse = perez_diffuse(dhi, dni, I0, cos_zenith, tilt_deg, azimuth_deg, solar_azimuth)
    
    # 3. Ground Reflected (Isotropic)
    poa_ground = ghi * albedo * (1 - np.cos(tilt)) / 2
    
    total_poa = poa_beam + poa_diffuse + poa_ground
    return np.where(cos_zenith > 0, np.maximum(total_poa, 0), 0).astype(np.float32)
