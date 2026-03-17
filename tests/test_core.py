"""
Unit tests for ENERLYTICS core physics module.
"""
import pytest
import numpy as np
from energy_explore.core import stable_rng, solar_geometry_lst, clear_sky_ghi, ar1_series, renormalize_monthly, reindl_separation, compute_monthly_means

def test_stable_rng_deterministic():
    rng1 = stable_rng("12.34_56.78", 42)
    rng2 = stable_rng("12.34_56.78", 42)
    assert rng1.random() == rng2.random()

def test_solar_geometry_daytime():
    # New Delhi noon
    geom = solar_geometry_lst(28.6)
    # Hour 12 (approx index 12 in first day)
    assert geom["cos_zenith"][12] > 0

def test_solar_geometry_nighttime():
    geom = solar_geometry_lst(28.6)
    # Hour 0
    assert geom["cos_zenith"][0] == 0

def test_clear_sky_ghi_zero_at_night():
    cos_zen = np.array([0.0, 0.5, 1.0])
    I0 = np.array([1360.0, 1360.0, 1360.0])
    ghi = clear_sky_ghi(I0, cos_zen)
    assert ghi[0] == 0

def test_reindl_energy_balance():
    ghi = np.array([500.0], dtype=np.float32)
    I0 = np.array([1360.0], dtype=np.float32)
    cos_zen = np.array([0.7], dtype=np.float32)
    dni, dhi = reindl_separation(ghi, I0, cos_zen)
    # GHI = DNI*cos_zen + DHI
    assert pytest.approx(float(dni[0] * cos_zen[0] + dhi[0]), rel=0.01) == 500.0

def test_ar1_bounds():
    rng = np.random.default_rng(42)
    series = ar1_series(1000, 0.8, 0.1, rng, bounds=(0.2, 0.8))
    assert np.all(series >= 0.2)
    assert np.all(series <= 0.8)

def test_renormalize_monthly():
    y = np.ones(8760, dtype=np.float32)
    target = np.array([2.0]*12, dtype=np.float32)
    y_norm = renormalize_monthly(y, target)
    means = compute_monthly_means(y_norm)
    assert np.allclose(means, target, rtol=0.001)
