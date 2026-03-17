import numpy as np
import pytest
from energy_explore.advisor import weibull_fit, HELLMANN_EXPONENTS, optimal_wind_height

def test_weibull_fit_valid():
    # Generate some random wind data following a Weibull-like distribution
    rng = np.random.default_rng(42)
    wind_speed = rng.weibull(2, 8760) * 5.0
    res = weibull_fit(wind_speed)
    
    assert res["k"] > 0
    assert res["c_ms"] > 0
    assert 0 <= res["capacity_factor_pct"] <= 100
    assert res["p50_speed_ms"] > 0
    assert res["p90_speed_ms"] > 0

def test_weibull_fit_empty():
    wind_speed = np.zeros(10)
    res = weibull_fit(wind_speed)
    assert res["k"] == 0.0
    assert res["capacity_factor_pct"] == 0.0

def test_optimal_wind_height():
    wind_2m = np.ones(8760) * 4.0
    res = optimal_wind_height(wind_2m, terrain_type="open_flat")
    
    assert len(res["height_data"]) == 6
    # At 100m, speed should be higher than at 2m
    assert res["height_data"][-1]["mean_speed_ms"] > 4.0
