import numpy as np
import pytest
from energy_explore.financial import pm_surya_ghar_subsidy, get_state_tariff, calculate_roi, co2_and_environment

def test_pm_surya_ghar_1kw():
    res = pm_surya_ghar_subsidy(1.0)
    assert res["subsidy_inr"] == 30000.0
    assert res["net_capex_inr"] == 20000.0 # 50k - 30k

def test_pm_surya_ghar_3kw():
    res = pm_surya_ghar_subsidy(3.0)
    assert res["subsidy_inr"] == 78000.0 # capped

def test_pm_surya_ghar_5kw():
    res = pm_surya_ghar_subsidy(5.0)
    assert res["subsidy_inr"] == 78000.0 # still capped at 3kW level

def test_state_tariff_maharashtra():
    res = get_state_tariff("Maharashtra")
    assert res["tariff"] == 8.50

def test_state_tariff_fuzzy():
    # lowercase
    res1 = get_state_tariff("maharashtra")
    assert res1["tariff"] == 8.50
    # partial
    res2 = get_state_tariff("Maha")
    assert res2["tariff"] == 8.50

def test_roi_payback_positive():
    # payback_yr > 0 for any positive annual_energy
    res = calculate_roi(1000.0, 1.0, 50000.0, 5.0, 2.50, 30000.0)
    assert res["simple_payback_yr"] > 0
    assert res["net_capex_inr"] == 20000.0

def test_roi_npv_increases_with_tariff():
    res_low = calculate_roi(1000.0, 1.0, 50000.0, 4.0, 2.0, 0)
    res_high = calculate_roi(1000.0, 1.0, 50000.0, 8.0, 4.0, 0)
    assert res_high["npv_25yr_inr"] > res_low["npv_25yr_inr"]

def test_co2_calculation():
    # 1000 kWh * 0.82 = 820 kg CO2 = 0.82 tonnes
    res = calculate_roi(1000.0, 1.0)
    assert np.allclose(res["co2_avoided_tonnes_yr"], 0.82, atol=0.01)
