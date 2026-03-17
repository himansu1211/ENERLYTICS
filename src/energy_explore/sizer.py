""" 
sizer.py — ENERLYTICS System Sizer, Appliance Load Builder & Energy Audit 
===================================================================== 

Standalone module — zero NASA API calls, zero simulation required. 
All calculations run instantly from user inputs alone. 

Public API: 
  size_solar_system(...)        → full system spec + financials 
  energy_audit(...)             → load breakdown + priority actions 
  compare_energy_sources(...)   → solar vs wind vs hybrid comparison 
  compute_load(appliances)      → daily/monthly/annual kWh from appliance list 
  total_monthly_kwh(appliances) → float shorthand 
  appliance_monthly_kwh(w, h)   → float for one appliance 
  category_breakdown(appliances)→ {category: kwh} dict 

Constants: 
  DEFAULT_APPLIANCES   — pre-loaded typical Indian home 
  ADDON_APPLIANCES     — additional appliances for the builder 
  REGION_SUN_HOURS     — peak sun hours by India region 
  STATE_TARIFFS        — residential tariff + net metering by state 
""" 
from __future__ import annotations
import numpy as np 


# ── Region → peak sun hours ─────────────────────────────────────────────────── 
REGION_SUN_HOURS: dict[str, float] = { 
    "Rajasthan / Gujarat":       5.5, 
    "Delhi / UP / MP / Bihar":   5.0, 
    "Punjab / Haryana":          4.9, 
    "Maharashtra / Karnataka":   4.8, 
    "Tamil Nadu / Andhra":       4.7, 
    "West Bengal / Odisha":      4.5, 
    "Kerala":                    4.2, 
    "NE India / Himachal":       4.0, 
} 

# ── State tariff + net metering database (FY 2024-25 SERC rates) ───────────── 
STATE_TARIFFS: dict[str, dict] = { 
    "maharashtra":       {"tariff": 8.50, "net_meter": 2.90}, 
    "gujarat":           {"tariff": 5.50, "net_meter": 2.25}, 
    "karnataka":         {"tariff": 6.50, "net_meter": 3.82}, 
    "rajasthan":         {"tariff": 6.00, "net_meter": 2.87}, 
    "delhi":             {"tariff": 4.50, "net_meter": 10.50}, 
    "uttar_pradesh":     {"tariff": 5.50, "net_meter": 2.98}, 
    "tamil_nadu":        {"tariff": 4.50, "net_meter": 3.47}, 
    "andhra_pradesh":    {"tariff": 4.50, "net_meter": 2.09}, 
    "telangana":         {"tariff": 4.50, "net_meter": 2.85}, 
    "punjab":            {"tariff": 5.00, "net_meter": 2.65}, 
    "haryana":           {"tariff": 6.00, "net_meter": 2.75}, 
    "madhya_pradesh":    {"tariff": 4.50, "net_meter": 2.14}, 
    "west_bengal":       {"tariff": 5.00, "net_meter": 2.09}, 
    "assam":             {"tariff": 6.50, "net_meter": 5.33}, 
    "kerala":            {"tariff": 4.50, "net_meter": 3.00}, 
    "bihar":             {"tariff": 5.50, "net_meter": 2.50}, 
    "odisha":            {"tariff": 4.50, "net_meter": 2.30}, 
    "chhattisgarh":      {"tariff": 4.00, "net_meter": 2.20}, 
    "jharkhand":         {"tariff": 5.00, "net_meter": 2.40}, 
    "himachal_pradesh":  {"tariff": 3.50, "net_meter": 2.10}, 
    "uttarakhand":       {"tariff": 4.50, "net_meter": 2.30}, 
    "goa":               {"tariff": 3.50, "net_meter": 2.80}, 
    "default":           {"tariff": 5.00, "net_meter": 2.50}, 
} 


def _get_tariff(state_name: str) -> dict: 
    """Case-insensitive fuzzy match against STATE_TARIFFS. Returns default on no match.""" 
    key = state_name.lower().strip().replace(" ", "_").replace("-", "_") 
    if key in STATE_TARIFFS: 
        return dict(STATE_TARIFFS[key]) 
    # Partial match 
    for k in STATE_TARIFFS: 
        if k != "default" and (k in key or key in k): 
            return dict(STATE_TARIFFS[k]) 
    return dict(STATE_TARIFFS["default"]) 


# ── Default appliance lists ─────────────────────────────────────────────────── 
DEFAULT_APPLIANCES: list[dict] = [ 
    {"name": "LED lights × 8",        "watts": 64,   "hours": 6.0,  "category": "lighting"}, 
    {"name": "Ceiling fan × 3",        "watts": 210,  "hours": 10.0, "category": "cooling"}, 
    {"name": "Refrigerator",           "watts": 150,  "hours": 24.0, "category": "appliances"}, 
    {"name": "LED TV 32\"",            "watts": 40,   "hours": 5.0,  "category": "entertainment"}, 
    {"name": "Air conditioner (1.5T)", "watts": 1500, "hours": 8.0,  "category": "cooling"}, 
    {"name": "Laptop / desktop",       "watts": 150,  "hours": 6.0,  "category": "appliances"}, 
    {"name": "Phone charging × 4",     "watts": 80,   "hours": 4.0,  "category": "appliances"}, 
] 

ADDON_APPLIANCES: list[dict] = [ 
    {"name": "Washing machine",        "watts": 1500, "hours": 1.0,  "category": "appliances"}, 
    {"name": "Water heater / geyser",  "watts": 2000, "hours": 1.0,  "category": "heating"}, 
    {"name": "Microwave",              "watts": 1000, "hours": 0.5,  "category": "appliances"}, 
    {"name": "Water pump (0.5 HP)",    "watts": 373,  "hours": 2.0,  "category": "appliances"}, 
    {"name": "Electric iron",          "watts": 1200, "hours": 0.3,  "category": "heating"}, 
    {"name": "EV charger (2.2 kW)",    "watts": 2200, "hours": 4.0,  "category": "transport"}, 
    {"name": "WiFi router",            "watts": 15,   "hours": 24.0, "category": "appliances"}, 
    {"name": "Exhaust fan",            "watts": 60,   "hours": 6.0,  "category": "cooling"}, 
    {"name": "Desktop computer",       "watts": 300,  "hours": 8.0,  "category": "appliances"}, 
    {"name": "Security cameras × 4",   "watts": 40,   "hours": 24.0, "category": "appliances"}, 
    {"name": "Mixer / grinder",        "watts": 750,  "hours": 0.5,  "category": "appliances"}, 
    {"name": "Air purifier",           "watts": 50,   "hours": 8.0,  "category": "cooling"}, 
    {"name": "Treadmill",              "watts": 800,  "hours": 1.0,  "category": "appliances"}, 
    {"name": "Room heater",            "watts": 1500, "hours": 4.0,  "category": "heating"}, 
    {"name": "Printer / scanner",      "watts": 100,  "hours": 1.0,  "category": "appliances"}, 
] 


# ── Appliance helpers ───────────────────────────────────────────────────────── 

def appliance_monthly_kwh(watts: float, hours_per_day: float) -> float: 
    """kWh consumed in 30 days for a single appliance.""" 
    return round(watts * hours_per_day * 30 / 1000.0, 1) 


def total_monthly_kwh(appliances: list[dict]) -> float: 
    """Total monthly kWh for a list of appliance dicts.""" 
    return round(sum(a["watts"] * a["hours"] * 30 / 1000.0 for a in appliances), 1) 


def category_breakdown(appliances: list[dict]) -> dict[str, float]: 
    """Monthly kWh grouped by category, sorted descending.""" 
    cats: dict[str, float] = {} 
    for a in appliances: 
        cat = a.get("category", "other") 
        cats[cat] = cats.get(cat, 0.0) + a["watts"] * a["hours"] * 30 / 1000.0 
    return {k: round(v, 1) for k, v in sorted(cats.items(), key=lambda x: -x[1])} 


def compute_load(appliances: list[dict]) -> dict: 
    """Full load computation from appliance list.""" 
    if not appliances: 
        return {"daily_kwh": 0.0, "monthly_kwh": 0.0, "annual_kwh": 0.0, 
                "peak_kw": 0.0, "categories": {}} 
    daily_wh = sum(float(a["watts"]) * float(a["hours"]) for a in appliances) 
    return { 
        "daily_kwh":   round(daily_wh / 1000.0, 2), 
        "monthly_kwh": round(daily_wh * 30 / 1000.0, 1), 
        "annual_kwh":  round(daily_wh * 365 / 1000.0, 0), 
        "peak_kw":     round(sum(float(a["watts"]) for a in appliances) / 1000.0, 2), 
        "categories":  category_breakdown(appliances), 
    } 


# ── PM Surya Ghar subsidy (FY 2024-25 MNRE) ────────────────────────────────── 

def _pm_subsidy(kw: float) -> tuple[float, str]: 
    """Return (subsidy_inr, note) for a given system capacity.""" 
    if kw <= 1.0:   return 30_000.0, "PM Surya Ghar: ₹30,000" 
    if kw <= 2.0:   return 60_000.0, "PM Surya Ghar: ₹60,000" 
    if kw <= 10.0:  return 78_000.0, "PM Surya Ghar: ₹78,000 (max cap)" 
    return 0.0, "No residential subsidy above 10 kW" 


# ── Core solar sizing engine ────────────────────────────────────────────────── 

def size_solar_system( 
    monthly_kwh: float, 
    peak_sun_hours: float = 5.0, 
    self_consumption_pct: float = 80.0, 
    system_efficiency_pct: float = 80.0, 
    panel_watt_peak: float = 360.0, 
    panel_length_m: float = 2.0, 
    panel_width_m: float = 1.0, 
    capex_per_kw_inr: float = 55_000.0, 
    apply_subsidy: bool = True, 
    include_battery: bool = False, 
    battery_backup_hours: float = 4.0, 
    state_name: str = "default", 
) -> dict: 
    """ 
    Size a solar PV system from monthly kWh consumption. 

    Returns a dict with system spec, cost breakdown, financial returns, 
    and environmental impact. All values are floats or ints — no units embedded. 
    Caller formats for display. 
    """ 
    monthly_kwh = max(float(monthly_kwh), 1.0) 
    sc = max(0.1, min(1.0, self_consumption_pct / 100.0)) 
    eff = max(0.5, min(1.0, system_efficiency_pct / 100.0)) 
    psh = max(1.0, float(peak_sun_hours)) 

    tariff_data = _get_tariff(state_name) 
    tariff = tariff_data["tariff"] 
    net_meter = tariff_data["net_meter"] 

    daily_kwh = monthly_kwh / 30.0 

    # Required solar capacity 
    raw_kw = daily_kwh / (psh * eff * sc) 
    solar_kw = float(max(0.5, np.ceil(raw_kw * 2) / 2))   # round up to nearest 0.5 kW 

    # Inverter: 20% headroom, round to 0.5 kVA 
    inverter_kva = float(np.ceil(solar_kw * 1.2 * 2) / 2) 

    # Panels and roof area (25% extra for row spacing) 
    panel_count = int(np.ceil(solar_kw * 1000 / panel_watt_peak)) 
    roof_area_m2 = float(round(panel_count * panel_length_m * panel_width_m * 1.25, 1)) 

    # Battery (covers backup_hours at 50% of daily demand, 90% DoD LFP) 
    battery_kwh: float = 0.0 
    if include_battery: 
        raw_bat = (daily_kwh * 0.5) * (battery_backup_hours / 24) / 0.9 
        battery_kwh = float(max(2.0, np.ceil(raw_bat * 2) / 2)) 

    # Generation 
    daily_gen = solar_kw * psh * eff 
    annual_gen = daily_gen * 365 
    self_consumed = annual_gen * sc 
    exported = annual_gen * (1.0 - sc) 

    # Cost 
    gross_capex = solar_kw * capex_per_kw_inr 
    bat_capex = battery_kwh * 17_000.0 if include_battery else 0.0  # ₹17,000/kWh LFP installed 
    total_capex = gross_capex + bat_capex 

    subsidy_inr, subsidy_note = _pm_subsidy(solar_kw) if apply_subsidy else (0.0, "Subsidy not applied") 
    net_capex = max(0.0, total_capex - subsidy_inr) 

    # Annual financials 
    annual_savings = self_consumed * tariff + exported * net_meter 
    annual_opex = solar_kw * 750.0          # ₹750/kW/yr O&M 
    net_annual = annual_savings - annual_opex 
    payback = net_capex / max(net_annual, 1.0) 

    # LCOE (9% WACC, 25-year life) 
    r, n = 0.09, 25 
    crf = r * (1 + r) ** n / ((1 + r) ** n - 1) 
    lcoe = (net_capex * crf + annual_opex) / max(annual_gen, 1.0) 

    # CO₂ (CEA 2023: 0.82 kg/kWh) 
    co2_kg = annual_gen * 0.82 
    trees = int(co2_kg / 22)             # 22 kg CO₂ absorbed per tree per year 
    coal_kg = annual_gen * 0.40 

    # Size label 
    if solar_kw <= 3:     label, use = "Small home",         "2BHK — fans, lights, fridge, TV" 
    elif solar_kw <= 6:   label, use = "Medium home",        "3BHK — +1 AC, washing machine" 
    elif solar_kw <= 10:  label, use = "Large home / villa",  "Bungalow — 2+ ACs, EV charging" 
    elif solar_kw <= 50:  label, use = "Small commercial",   "Office / shop — 3-phase" 
    else:                 label, use = "Industrial / C&I",   "Factory — ground-mount system" 

    return { 
        # System spec 
        "solar_kw":          solar_kw, 
        "inverter_kva":      inverter_kva, 
        "battery_kwh":       battery_kwh, 
        "panels":       panel_count, 
        "panel_wp":          int(panel_watt_peak), 
        "roof_area_m2":      roof_area_m2, 
        # Generation 
        "daily_gen_kwh":     round(daily_gen, 1), 
        "annual_gen_kwh":    round(annual_gen, 0), 
        "self_consumed_kwh": round(self_consumed, 0), 
        "exported_kwh":      round(exported, 0), 
        # Cost 
        "capex_inr":         round(total_capex, 0), 
        "gross_capex_inr":   round(gross_capex, 0), 
        "bat_capex_inr":     round(bat_capex, 0), 
        "subsidy_inr":       round(subsidy_inr, 0), 
        "subsidy_note":      subsidy_note, 
        "net_capex_inr":     round(net_capex, 0), 
        # Financials 
        "tariff_inr_kwh":    tariff, 
        "net_meter_inr_kwh": net_meter, 
        "annual_savings_inr": round(annual_savings, 0), 
        "annual_opex_inr":   round(annual_opex, 0), 
        "simple_payback_yr": round(min(payback, 30.0), 1), 
        "lcoe_inr_per_kwh":  round(lcoe, 2), 
        # Environment 
        "co2_kg_yr": round(co2_kg, 0), 
        "trees_equiv":  trees, 
        "coal_kg_yr":  round(coal_kg, 0), 
        # Label 
        "size_label":        label, 
        "use_case":          use, 
    } 


# ── Energy audit ────────────────────────────────────────────────────────────── 

# Base consumption fractions for a typical Indian household (BEE 2023 survey) 
_BASE_FRACTIONS: dict[str, dict] = { 
    "cooling":    {"pct": 0.42, "label": "Cooling (AC / fans)",   "efficiency_tip": "Set AC to 24°C. Each degree saves 6% energy.",        "solar_offset": 0.80}, 
    "lighting":   {"pct": 0.12, "label": "Lighting",               "efficiency_tip": "Switch remaining CFL/halogen to LED. Saves 80%.",     "solar_offset": 0.60}, 
    "appliances": {"pct": 0.18, "label": "Appliances (fridge etc.)","efficiency_tip": "5-star rated appliances use 30–40% less energy.",     "solar_offset": 0.70}, 
    "water_heat": {"pct": 0.09, "label": "Water heating",          "efficiency_tip": "Solar water heater payback is 2–3 years.",             "solar_offset": 0.90}, 
    "washing":    {"pct": 0.08, "label": "Washing / pumping",      "efficiency_tip": "Run washing machine on full load only.",              "solar_offset": 0.85}, 
    "cooking":    {"pct": 0.11, "label": "Cooking / misc",         "efficiency_tip": "Induction cooktop is 90% efficient vs 40% gas.",       "solar_offset": 0.25}, 
} 

# Per-AC addition to cooling fraction 
_AC_EXTRA_PER_UNIT = 0.07 

# Benchmark monthly kWh per bedroom (BEE 2023, India) 
_BENCHMARK_KWH_PER_BED = { 
    "apartment":        65.0, 
    "independent house": 80.0, 
    "villa":             120.0, 
} 

def _energy_rating(kwh: float, benchmark: float) -> tuple[str, str]: 
    """Return (rating label, color) based on usage vs benchmark.""" 
    ratio = kwh / max(benchmark, 1.0) 
    if ratio < 0.8:   return "Excellent (A+)", "green" 
    if ratio < 1.0:   return "Good (A)",        "teal" 
    if ratio < 1.3:   return "Average (B)",     "amber" 
    if ratio < 1.7:   return "High (C)",        "orange" 
    return "Very High (D)", "red" 


def energy_audit( 
    monthly_kwh: float, 
    num_ac_units: int = 1, 
    num_bedrooms: int = 2, 
    has_geyser: bool = True, 
    has_ev: bool = False, 
    home_type: str = "apartment", 
    grid_tariff_inr: float = 5.0, 
) -> dict: 
    """ 
    Estimate load breakdown, efficiency opportunities, and solar offset potential. 

    Returns: 
        breakdown_kwh        — {category: kWh/month} 
        savings_by_cat_kwh   — {category: potential savings kWh/month} 
        priority_actions     — list of {action, saving, cost, priority} 
        energy_rating        — e.g. "Good (A)" 
        energy_rating_color  — green / teal / amber / orange / red 
        kwh_per_bedroom      — float 
        total_savings_potential_kwh 
        total_savings_potential_pct 
    """ 
    monthly_kwh = max(float(monthly_kwh), 10.0) 

    # Build adjusted fractions 
    fracs = {k: dict(v) for k, v in _BASE_FRACTIONS.items()} 

    # Scale cooling for multiple ACs 
    ac_extra = max(0.0, (num_ac_units - 1) * _AC_EXTRA_PER_UNIT) 
    fracs["cooling"]["pct"] = min(0.68, fracs["cooling"]["pct"] + ac_extra) 

    # Add geyser boost to water_heat 
    if not has_geyser: 
        fracs["water_heat"]["pct"] *= 0.4   # mostly gas or solar thermal 

    # Add EV fraction 
    if has_ev: 
        fracs["ev"] = { 
            "pct": 0.12, 
            "label": "EV charging", 
            "efficiency_tip": "Charge EV during 10 AM–3 PM to maximise solar self-consumption.", 
            "solar_offset": 0.75, 
        } 

    # Normalise to sum = 1.0 
    total_frac = sum(v["pct"] for v in fracs.values()) 
    for v in fracs.values(): 
        v["pct"] = v["pct"] / total_frac 

    # Compute kWh and savings per category 
    breakdown_kwh: dict[str, float] = {} 
    savings_by_cat_kwh: dict[str, float] = {} 
    for cat, v in fracs.items(): 
        kwh = monthly_kwh * v["pct"] 
        breakdown_kwh[cat] = round(kwh, 1) 
        savings_by_cat_kwh[cat] = round(kwh * (1.0 - v["solar_offset"]) * 0.30, 1)  # 30% efficiency gains realistic 

    total_savings = sum(savings_by_cat_kwh.values()) 
    total_savings_pct = round(total_savings / monthly_kwh * 100, 1) 

    # Energy rating 
    benchmark_per_bed = _BENCHMARK_KWH_PER_BED.get(home_type, 80.0) 
    benchmark = benchmark_per_bed * max(1, num_bedrooms) 
    kwh_per_bed = round(monthly_kwh / max(num_bedrooms, 1), 1) 
    rating, rating_color = _energy_rating(monthly_kwh, benchmark) 

    # Priority actions 
    actions: list[dict] = [] 

    if num_ac_units > 0: 
        ac_kwh = breakdown_kwh.get("cooling", 0) 
        actions.append({ 
            "action": f"Set all {num_ac_units} AC(s) to 24°C (currently many set to 18–20°C)", 
            "saving":   f"~{round(ac_kwh * 0.18)} kWh/month (₹{round(ac_kwh*0.18*grid_tariff_inr):,})", 
            "cost":     "Free", 
            "priority": "Quick win", 
        }) 
        actions.append({ 
            "action": "Clean AC filters monthly — dirty filters increase power draw by 10–15%", 
            "saving":   f"~{round(ac_kwh * 0.12)} kWh/month", 
            "cost":     "Free", 
            "priority": "Quick win", 
        }) 

    if has_geyser: 
        geyser_kwh = breakdown_kwh.get("water_heat", 0) 
        actions.append({ 
            "action": "Install a solar water heater (150–200L ETC type)", 
            "saving":   f"~{round(geyser_kwh * 0.75)} kWh/month (₹{round(geyser_kwh*0.75*grid_tariff_inr):,}/mo)", 
            "cost":     "₹15,000–25,000 (payback ~2.5 yr)", 
            "priority": "High", 
        }) 

    light_kwh = breakdown_kwh.get("lighting", 0) 
    if light_kwh > 5: 
        actions.append({ 
            "action": "Replace remaining non-LED bulbs with LED (5W LED = 60W incandescent)", 
            "saving":   f"~{round(light_kwh * 0.50)} kWh/month", 
            "cost":     "₹100–300 per bulb", 
            "priority": "Quick win", 
        }) 

    solar_size = size_solar_system(monthly_kwh) 
    solar_offset_kwh = round(solar_size["self_consumed_kwh"] / 12, 1) 
    actions.append({ 
        "action": f"Install {solar_size['solar_kw']} kW rooftop solar system via ENERLYTICS", 
        "saving":   f"~{solar_offset_kwh} kWh/month (₹{round(solar_offset_kwh*grid_tariff_inr):,}/mo)", 
        "cost":     f"₹{solar_size['net_capex_inr']:,.0f} net after subsidy (payback {solar_size['simple_payback_yr']} yr)", 
        "priority": "High", 
    }) 

    if has_ev: 
        ev_kwh = breakdown_kwh.get("ev", 0) 
        actions.append({ 
            "action": "Shift EV charging to 10 AM–3 PM to use solar generation directly", 
            "saving":   f"~{round(ev_kwh * 0.65)} kWh grid import offset/month", 
            "cost":     "Free (timer / smart charger optional)", 
            "priority": "Quick win", 
        }) 

    return { 
        "breakdown_kwh":               breakdown_kwh, 
        "savings_by_cat_kwh":          savings_by_cat_kwh, 
        "priority_actions":            actions, 
        "energy_rating":               rating, 
        "energy_rating_color":         rating_color, 
        "kwh_per_bedroom":             kwh_per_bed, 
        "benchmark_kwh":               round(benchmark, 0), 
        "total_savings_potential_kwh": round(total_savings, 1), 
        "total_savings_potential_pct": total_savings_pct, 
        "category_labels":             {k: v["label"] for k, v in fracs.items()}, 
        "efficiency_tips":             {k: v["efficiency_tip"] for k, v in fracs.items()}, 
    } 


# ── Energy source comparison ────────────────────────────────────────────────── 

def compare_energy_sources( 
    monthly_kwh: float, 
    peak_sun_hours: float = 5.0, 
    mean_wind_ms: float = 3.5, 
    state_name: str = "default", 
) -> list[dict]: 
    """ 
    Compare solar-only, wind-only, and hybrid options for a given consumption. 

    Returns a list of option dicts suitable for side-by-side display. 
    Each dict includes: option, capacity, net_capex_inr, subsidy_inr, 
    annual_savings_inr, payback_yr, note, recommended (bool). 
    """ 
    tariff_data = _get_tariff(state_name) 
    tariff = tariff_data["tariff"] 
    net_meter = tariff_data["net_meter"] 

    options: list[dict] = [] 

    # ── Option 1: Solar only ───────────────────────────────────────────────── 
    sol = size_solar_system( 
        monthly_kwh, peak_sun_hours=peak_sun_hours, 
        state_name=state_name, include_battery=False, 
    ) 
    options.append({ 
        "option":            "Solar only", 
        "capacity":          f"{sol['solar_kw']} kW solar", 
        "net_capex_inr":     sol["net_capex_inr"], 
        "subsidy_inr":       sol["subsidy_inr"], 
        "annual_savings_inr": sol["annual_savings_inr"], 
        "payback_yr":        sol["simple_payback_yr"], 
        "note":              f"Best choice for most urban/suburban homes. {sol['roof_area_m2']} m² roof needed.", 
        "recommended":       False, 
        "color":             "#f39c12", 
    }) 

    # ── Option 2: Solar + Battery ──────────────────────────────────────────── 
    sol_bat = size_solar_system( 
        monthly_kwh, peak_sun_hours=peak_sun_hours, 
        state_name=state_name, include_battery=True, battery_backup_hours=4.0, 
    ) 
    options.append({ 
        "option":            "Solar + Battery", 
        "capacity":          f"{sol_bat['solar_kw']} kW + {sol_bat['battery_kwh']} kWh", 
        "net_capex_inr":     sol_bat["net_capex_inr"], 
        "subsidy_inr":       sol_bat["subsidy_inr"], 
        "annual_savings_inr": sol_bat["annual_savings_inr"], 
        "payback_yr":        sol_bat["simple_payback_yr"], 
        "note":              f"Add {sol_bat['battery_kwh']} kWh LFP battery for ~4h backup. Ideal for areas with frequent outages.", 
        "recommended":       False, 
        "color":             "#2ecc71", 
    }) 

    # ── Option 3: Wind only (if viable) ───────────────────────────────────── 
    monthly_kwh_f = max(float(monthly_kwh), 1.0) 
    wind_viable = mean_wind_ms >= 4.0 
    if wind_viable: 
        # P = 0.5 * rho * A * v³ * Cp; for typical small turbine: capacity factor ~25% 
        cf = 0.25 
        wind_kw = float(np.ceil((monthly_kwh_f / (cf * 730)) * 2) / 2)  # 730h/month 
        wind_capex = wind_kw * 100_000.0   # ₹1 lakh/kW for small wind turbine installed 
        wind_savings = wind_kw * cf * 730 * 12 * tariff 
        wind_payback = round(wind_capex / max(wind_savings, 1), 1) 
        options.append({ 
            "option":            "Small wind turbine", 
            "capacity":          f"{wind_kw} kW wind", 
            "net_capex_inr":     wind_capex, 
            "subsidy_inr":       0.0, 
            "annual_savings_inr": round(wind_savings, 0), 
            "payback_yr":        min(wind_payback, 30.0), 
            "note":              f"Viable at {mean_wind_ms} m/s. Needs open site, 20–30m clearance from obstructions.", 
            "recommended":       False, 
            "color":             "#3498db", 
        }) 

    # ── Option 4: Hybrid (solar + small wind) ─────────────────────────────── 
    if wind_viable: 
        hybrid_solar_kw = float(np.ceil(sol["solar_kw"] * 0.6 * 2) / 2) 
        hybrid_wind_kw = float(np.ceil(sol["solar_kw"] * 0.4 * 2) / 2) 
        hybrid_capex = hybrid_solar_kw * 55_000 + hybrid_wind_kw * 100_000 
        sub_h, _ = _pm_subsidy(hybrid_solar_kw) 
        hybrid_net = max(0.0, hybrid_capex - sub_h) 
        sol_gen = hybrid_solar_kw * peak_sun_hours * 0.80 * 365 
        wind_gen = hybrid_wind_kw * 0.25 * 8760 
        hybrid_savings = (sol_gen + wind_gen) * 0.80 * tariff + (sol_gen + wind_gen) * 0.20 * net_meter 
        hybrid_payback = round(hybrid_net / max(hybrid_savings, 1), 1) 
        options.append({ 
            "option":            "Hybrid (solar + wind)", 
            "capacity":          f"{hybrid_solar_kw} kW + {hybrid_wind_kw} kW", 
            "net_capex_inr":     round(hybrid_net, 0), 
            "subsidy_inr":       round(sub_h, 0), 
            "annual_savings_inr": round(hybrid_savings, 0), 
            "payback_yr":        min(float(hybrid_payback), 30.0), 
            "note":              "Solar for daytime, wind for nights/monsoon. Reduces seasonal dependency.", 
            "recommended":       False, 
            "color":             "#9b59b6", 
        }) 

    # Mark best payback as recommended 
    best_idx = min(range(len(options)), key=lambda i: options[i]["payback_yr"]) 
    options[best_idx]["recommended"] = True 

    # Round all money values for clean display 
    for opt in options: 
        opt["net_capex_inr"] = round(float(opt["net_capex_inr"]), 0) 
        opt["annual_savings_inr"] = round(float(opt["annual_savings_inr"]), 0) 

    return options
