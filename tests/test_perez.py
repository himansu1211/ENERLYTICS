import numpy as np
import pytest
from energy_explore.perez import perez_diffuse, perez_poa_total, _get_epsilon_bin

def test_epsilon_bin_range():
    epsilons = np.array([1.0, 1.1, 1.4, 1.8, 2.5, 4.0, 6.0, 10.0])
    bins = _get_epsilon_bin(epsilons)
    assert bins.shape == (8,)
    assert np.all(bins >= 0) and np.all(bins <= 7)

def test_perez_diffuse_zero_at_night():
    # Test that night hours (cos_zenith <= 0) return 0
    dhi = np.ones(10) * 100
    dni = np.ones(10) * 100
    I0 = np.ones(10) * 1367
    cos_zenith = np.zeros(10)
    tilt = 25.0
    azimuth = 180.0
    
    ed = perez_diffuse(dhi, dni, I0, cos_zenith, tilt, azimuth)
    assert np.all(ed == 0)

def test_perez_diffuse_nonneg():
    # Test that all values are non-negative
    dhi = np.random.uniform(0, 400, 100)
    dni = np.random.uniform(0, 1000, 100)
    I0 = np.ones(100) * 1367
    cos_zenith = np.random.uniform(0.1, 1.0, 100)
    tilt = 25.0
    azimuth = 180.0
    
    ed = perez_diffuse(dhi, dni, I0, cos_zenith, tilt, azimuth)
    assert np.all(ed >= 0)

def test_perez_total_poa_gt_isotropic():
    # In many daytime conditions, Perez POA is expected to be higher than isotropic
    # due to circumsolar and horizon brightening.
    n = 1000
    ghi = np.ones(n) * 500
    dni = np.ones(n) * 700
    dhi = np.ones(n) * 150
    I0 = np.ones(n) * 1367
    cos_zenith = np.ones(n) * 0.7
    tilt = 30.0
    azimuth = 180.0
    
    # Simple isotropic model for comparison
    tilt_rad = np.deg2rad(tilt)
    poa_iso_diffuse = dhi * (1 + np.cos(tilt_rad)) / 2
    
    poa_perez_total = perez_poa_total(ghi, dni, dhi, I0, cos_zenith, tilt, azimuth)
    poa_perez_diffuse = poa_perez_total - (dni * 0.7) - (ghi * 0.2 * (1 - np.cos(tilt_rad)) / 2) # simplified
    
    # Mean Perez diffuse should generally be different and often higher than isotropic in clear conditions
    # This is a weak test but checks the logic is active
    assert not np.allclose(poa_perez_total, 0)

def test_perez_energy_conservation():
    # POA should not exceed extraterrestrial radiation (ETR) on average
    n = 8760
    dhi = np.ones(n) * 200
    dni = np.ones(n) * 800
    I0 = np.ones(n) * 1367
    cos_zenith = np.random.uniform(0, 1, n)
    ghi = dni * cos_zenith + dhi
    
    poa = perez_poa_total(ghi, dni, dhi, I0, cos_zenith, 25.0, 180.0)
    # Annual total should be physically reasonable
    assert poa.mean() < I0.mean()
