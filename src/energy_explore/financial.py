"""
Financial analysis module for ENERLYTICS.
Includes PM Surya Ghar subsidy, state tariffs, ROI, LCOE, NPV, and BESS dispatch.
"""
import numpy as np
from scipy.optimize import brentq
from typing import Dict, Any, List

# --- PM Surya Ghar CFA (Central Financial Assistance) ---
def pm_surya_ghar_subsidy(
    capacity_kw: float,
    is_special_category_state: bool = False,
) -> dict:
    """
    Calculates PM Surya Ghar central subsidy (CFA) based on 2024-25 slabs.
    """
    if capacity_kw <= 0:
        return {"gross_capex_inr": 0.0, "subsidy_inr": 0.0, "net_capex_inr": 0.0, "subsidy_pct": 0.0}
    
    # Slabs for General Category States
    # 1 kW: 30k, 2 kW: 60k, 3 kW+: 78k (cap)
    benchmark_cost_per_kw = 55000.0 if is_special_category_state else 50000.0
    gross_capex = capacity_kw * benchmark_cost_per_kw
    
    if capacity_kw < 1.0:
        subsidy = 30000 * capacity_kw
    elif capacity_kw < 2.0:
        subsidy = 30000 + (capacity_kw - 1.0) * 30000
    elif capacity_kw < 3.0:
        subsidy = 60000 + (capacity_kw - 2.0) * 18000
    else:
        subsidy = 78000.0 # Max cap for residential
    
    net_capex = max(gross_capex - subsidy, 0)
    subsidy_pct = (subsidy / gross_capex) * 100 if gross_capex > 0 else 0
    
    return {
        "gross_capex_inr": gross_capex,
        "subsidy_inr": subsidy,
        "net_capex_inr": net_capex,
        "subsidy_pct": subsidy_pct,
        "scheme": "PM Surya Ghar Muft Bijli Yojana"
    }

# --- State-wise tariff lookup ---
DISCOM_TARIFFS = {
    "Maharashtra": {"tariff": 8.50, "net_meter": 2.90, "notes": "High residential slabs"},
    "Gujarat": {"tariff": 5.50, "net_meter": 2.25, "notes": "Strong solar adoption"},
    "Karnataka": {"tariff": 6.50, "net_meter": 3.82, "notes": "Favorable net metering"},
    "Rajasthan": {"tariff": 6.00, "net_meter": 2.87, "notes": "High insolation zone"},
    "Delhi": {"tariff": 4.50, "net_meter": 10.50, "notes": "Aggressive solar incentive"},
    "Uttar Pradesh": {"tariff": 5.50, "net_meter": 2.98, "notes": "Growing market"},
    "Tamil Nadu": {"tariff": 4.50, "net_meter": 3.47, "notes": "Established RE base"},
    "Andhra Pradesh": {"tariff": 4.50, "net_meter": 2.09, "notes": "Utility scale leader"},
    "Punjab": {"tariff": 5.00, "net_meter": 2.65, "notes": "Net metering capped"},
    "Madhya Pradesh": {"tariff": 4.50, "net_meter": 2.14, "notes": "Central hub"},
    "West Bengal": {"tariff": 5.00, "net_meter": 2.09, "notes": "Net billing policy"},
    "Assam": {"tariff": 6.50, "net_meter": 5.33, "notes": "High APPC rate"},
    "Kerala": {"tariff": 4.50, "net_meter": 3.00, "notes": "Hilly terrain benefits"},
    "Haryana": {"tariff": 6.00, "net_meter": 2.75, "notes": "Suburban demand"},
    "Telangana": {"tariff": 4.50, "net_meter": 2.85, "notes": "IT hub demand"},
    "Bihar": {"tariff": 5.50, "net_meter": 2.50, "notes": "Developing grid"},
    "Odisha": {"tariff": 4.50, "net_meter": 2.30, "notes": "Coastal risk focus"},
    "Chhattisgarh": {"tariff": 4.00, "net_meter": 2.20, "notes": "Low tariff zone"},
    "Jharkhand": {"tariff": 5.00, "net_meter": 2.40, "notes": "Industrial demand"},
    "Himachal Pradesh": {"tariff": 3.50, "net_meter": 2.10, "notes": "Special category state"},
    "Uttarakhand": {"tariff": 4.50, "net_meter": 2.30, "notes": "Hilly terrain"},
    "Goa": {"tariff": 3.50, "net_meter": 2.80, "notes": "Tourism focus"},
    "Default": {"tariff": 5.00, "net_meter": 2.50, "notes": "National average"}
}

def get_state_tariff(state_name: str) -> dict:
    if not state_name: return DISCOM_TARIFFS["Default"]
    s_clean = state_name.lower().strip()
    for k, v in DISCOM_TARIFFS.items():
        if k.lower() in s_clean or s_clean in k.lower():
            return v
    return DISCOM_TARIFFS["Default"]

# --- LCOE and financial metrics ---
def calculate_roi(
    annual_energy_kwh: float,
    capacity_kw: float,
    capex_inr_per_kw: float = 55000.0,
    tariff_inr_per_kwh: float = 5.0,
    net_meter_rate: float = 2.50,
    subsidy_inr: float = 0.0,
    opex_inr_per_kw_yr: float = 750.0,
    degradation_pct_yr: float = 0.5,
    tariff_escalation_pct_yr: float = 3.0,
    discount_rate_pct: float = 9.0,
    lifetime_yr: int = 25,
    self_consumption_pct: float = 80.0,
    loan_rate_pct: float = 7.0,
    loan_fraction: float = 0.70,
) -> dict:
    gross_capex = capacity_kw * capex_inr_per_kw
    net_capex = max(gross_capex - subsidy_inr, 0)
    
    annual_self_consumed = annual_energy_kwh * (self_consumption_pct / 100.0)
    annual_exported = annual_energy_kwh * (1 - self_consumption_pct / 100.0)
    
    # Year 1 savings
    savings_yr1 = (annual_self_consumed * tariff_inr_per_kwh) + (annual_exported * net_meter_rate)
    annual_opex = capacity_kw * opex_inr_per_kw_yr
    
    # Year-by-year cash flows
    energy_gen = []
    savings = []
    cash_flows = [-net_capex]
    
    for yr in range(1, lifetime_yr + 1):
        y_gen = annual_energy_kwh * (1 - (degradation_pct_yr / 100.0))**(yr - 1)
        y_tariff = tariff_inr_per_kwh * (1 + (tariff_escalation_pct_yr / 100.0))**(yr - 1)
        y_net_meter = net_meter_rate * (1 + (tariff_escalation_pct_yr / 100.0))**(yr - 1)
        
        y_self = y_gen * (self_consumption_pct / 100.0)
        y_exp = y_gen * (1 - self_consumption_pct / 100.0)
        
        y_sav = (y_self * y_tariff) + (y_exp * y_net_meter)
        y_opex = annual_opex * (1 + (tariff_escalation_pct_yr / 100.0))**(yr - 1)
        
        energy_gen.append(y_gen)
        savings.append(y_sav)
        cash_flows.append(y_sav - y_opex)

    # Financial Metrics
    total_savings = sum(savings)
    simple_payback = net_capex / (savings_yr1 - annual_opex) if (savings_yr1 - annual_opex) > 0 else float('inf')
    
    # NPV
    r = discount_rate_pct / 100.0
    npv = sum(cf / (1 + r)**t for t, cf in enumerate(cash_flows))
    
    # IRR calculation
    def npv_func(rate):
        return sum(cf / (1 + rate)**t for t, cf in enumerate(cash_flows))
    
    try:
        irr = brentq(npv_func, -0.1, 1.0) * 100.0
    except:
        irr = 0.0
    
    # LCOE
    total_energy_discounted = sum(e / (1 + r)**t for t, e in enumerate([0] + energy_gen))
    total_cost_discounted = net_capex + sum((annual_opex * (1+0.03)**t) / (1 + r)**t for t in range(1, lifetime_yr + 1))
    lcoe = total_cost_discounted / total_energy_discounted if total_energy_discounted > 0 else 0
    
    # Environmental
    co2_saved = (annual_energy_kwh * 0.82) / 1000.0 # Tonnes
    trees = int(co2_saved / 0.022)
    
    year_by_year = []
    cum_savings = 0
    for i in range(lifetime_yr):
        cum_savings += savings[i]
        year_by_year.append({
            "year": i + 1,
            "energy_kwh": energy_gen[i],
            "savings_inr": savings[i],
            "cumulative_savings": cum_savings
        })
        
    return {
        "gross_capex_inr": gross_capex,
        "net_capex_inr": net_capex,
        "annual_self_consumed_kwh": annual_self_consumed,
        "annual_exported_kwh": annual_exported,
        "annual_savings_inr_yr1": savings_yr1,
        "simple_payback_yr": simple_payback,
        "lcoe_inr_per_kwh": lcoe,
        "npv_25yr_inr": npv,
        "irr_pct": irr,
        "co2_avoided_tonnes_yr": co2_saved,
        "trees_equivalent": trees,
        "year_by_year": year_by_year
    }

# --- Battery storage dispatch ---
def simulate_battery_dispatch(
    pv_power: np.ndarray,
    load_profile: np.ndarray | None = None,
    battery_kwh: float = 0.0,
    charge_rate_kw: float | None = None,
    discharge_rate_kw: float | None = None,
    eta_charge: float = 0.95,
    eta_discharge: float = 0.97,
    dod: float = 0.90,
    initial_soc_pct: float = 0.50,
) -> dict:
    if battery_kwh <= 0:
        return {"soc_hourly": np.zeros(8760), "grid_import_kwh": 0.0, "grid_export_kwh": 0.0, "self_sufficiency_pct": 0.0, "battery_cycles": 0.0}

    if charge_rate_kw is None: charge_rate_kw = battery_kwh / 2.0
    if discharge_rate_kw is None: discharge_rate_kw = battery_kwh / 2.0
    
    n = len(pv_power)
    if load_profile is None:
        # 5kWh/day default
        lp = np.full(24, 0.1)
        lp[6:10] = 0.3
        lp[18:24] = 0.4
        load_profile = np.tile(lp, n // 24)
        # scale to solar capacity (rough heuristic)
        load_profile *= (pv_power.mean() / 0.1) if pv_power.mean() > 0 else 1.0

    soc = np.zeros(n)
    grid_import = np.zeros(n)
    grid_export = np.zeros(n)
    
    current_soc = battery_kwh * initial_soc_pct
    min_soc = battery_kwh * (1 - dod)
    max_soc = battery_kwh
    total_throughput = 0.0
    
    for t in range(n):
        net = pv_power[t] - load_profile[t]
        
        if net > 0: # Excess PV
            # Charge battery
            charge_amt = min(net, charge_rate_kw, (max_soc - current_soc) / eta_charge)
            current_soc += charge_amt * eta_charge
            total_throughput += charge_amt * eta_charge
            grid_export[t] = net - charge_amt
        else: # Deficit
            # Discharge battery
            discharge_amt = min(-net, discharge_rate_kw, (current_soc - min_soc) * eta_discharge)
            current_soc -= discharge_amt / eta_discharge
            total_throughput += discharge_amt / eta_discharge
            grid_import[t] = -net - discharge_amt
            
        soc[t] = current_soc
        
    return {
        "soc_hourly": soc.astype(np.float32),
        "grid_import_kwh": float(grid_import.sum()),
        "grid_export_kwh": float(grid_export.sum()),
        "self_sufficiency_pct": (1 - grid_import.sum() / load_profile.sum()) * 100 if load_profile.sum() > 0 else 0,
        "battery_cycles": total_throughput / battery_kwh if battery_kwh > 0 else 0
    }

INDIA_GRID_EMISSION_FACTOR_KG_PER_KWH = 0.82
TREE_CO2_ABSORPTION_KG_PER_YEAR = 22.0

def co2_and_environment(annual_kwh: float) -> dict:
    co2_kg = annual_kwh * INDIA_GRID_EMISSION_FACTOR_KG_PER_KWH
    return {
        "co2_avoided_kg": co2_kg,
        "co2_avoided_tonnes": co2_kg / 1000.0,
        "trees_equivalent": int(co2_kg / TREE_CO2_ABSORPTION_KG_PER_YEAR),
        "coal_saved_kg": annual_kwh * 0.4,
        "homes_powered": int(annual_kwh / 1200)
    }
