import streamlit as st
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import pgeocode
import json
import sys
import os
from datetime import datetime

# --- 1. Path Setup (Fix for ModuleNotFoundError) ---
file_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(file_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# --- 2. Imports from Local Modules ---
from energy_explore.pipeline import fetch_nasa_power_climatology
from energy_explore.core import generate_cell, compute_monthly_means, simulate_pv_power, simulate_wind_power, monthly_indices
from energy_explore.financial import pm_surya_ghar_subsidy, calculate_roi, get_state_tariff, DISCOM_TARIFFS, co2_and_environment
from energy_explore.sizer import size_solar_system, energy_audit, DEFAULT_APPLIANCES, ADDON_APPLIANCES, REGION_SUN_HOURS, compare_energy_sources, VENDOR_PANELS
from energy_explore.report import generate_pdf_report

# --- 3. Page Config (MUST BE FIRST Streamlit command) ---
st.set_page_config(page_title="ENERLYTICS", page_icon="☀️", layout="wide")

# --- 4. Session State Initialization ---
if 'results' not in st.session_state:
    st.session_state.results = None
if 'loc' not in st.session_state:
    st.session_state.loc = {"lat": 28.61, "lon": 77.23, "name": "New Delhi", "state": "Delhi"}
if 'pincode' not in st.session_state:
    st.session_state.pincode = "110001"
if 'appliances' not in st.session_state:
    st.session_state.appliances = [dict(a) for a in DEFAULT_APPLIANCES]
if 'custom_units' not in st.session_state:
    st.session_state.custom_units = 300
if 'theme' not in st.session_state:
    st.session_state.theme = "Bright"

# --- 5. Responsive & Themed CSS ---
theme_colors = {
    "Bright": {
        "bg": "#ffffff",
        "text": "#1e293b",
        "sub_text": "#334155",
        "metric_bg": "#f8fafc",
        "metric_border": "#e2e8f0",
        "card_bg": "#f1f5f9",
        "sidebar_bg": "#f8fafc",
        "plotly_theme": "simple_white"
    },
    "Dark": {
        "bg": "#0f172a",
        "text": "#f1f5f9",
        "sub_text": "#cbd5e1",
        "metric_bg": "#1e293b",
        "metric_border": "#334155",
        "card_bg": "#1e293b",
        "sidebar_bg": "#1e293b",
        "plotly_theme": "plotly_dark"
    }
}
tc = theme_colors[st.session_state.theme]

st.markdown(f"""
    <style>
    /* Global Overrides */
    * {{ transition: none !important; animation: none !important; }}
    
    .stApp {{
        background-color: {tc['bg']};
        color: {tc['text']};
    }}
    
    /* Responsive Metric Cards */
    [data-testid="stMetric"] {{
        background: {tc['metric_bg']};
        padding: 15px;
        border-radius: 12px;
        border: 1px solid {tc['metric_border']};
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
        transition: transform 0.2s ease-in-out;
    }}
    
    [data-testid="stMetric"]:hover {{
        transform: translateY(-2px);
    }}

    /* Sidebar Styling */
    [data-testid="stSidebar"] {{
        background-color: {tc['sidebar_bg']};
    }}
    
    /* Input Labels */
    label {{
        color: {tc['text']} !important;
    }}
    
    /* Tabs Styling */
    .stTabs [data-baseweb="tab"] {{
        color: {tc['text']};
    }}
    
    .stTabs [data-baseweb="tab"]:hover {{
        color: #F59E0B;
    }}
    
    #MainMenu, footer, header {{visibility: hidden;}}
    [data-testid="stStatusWidget"] {{display: none;}}
    
    .stTabs [data-baseweb="tab-panel"] {{ padding-top: 1.5rem; }}
    
    [data-testid="stSidebarCollapseButton"] {{
        visibility: visible !important;
        background-color: #F59E0B !important;
        color: white !important;
        border-radius: 50% !important;
    }}

    /* Typography & Layout */
    .main-header {{
        font-size: clamp(1.8rem, 5vw, 2.5rem);
        font-weight: 800;
        color: {tc['text']};
        margin-bottom: 1.5rem;
        letter-spacing: -0.025em;
    }}
    
    .sub-header {{
        font-size: clamp(1.2rem, 3vw, 1.6rem);
        font-weight: 700;
        color: {tc['sub_text']};
        margin-top: 2rem;
        margin-bottom: 1rem;
    }}
    
    .info-card {{
        background: {tc['card_bg']};
        padding: 24px;
        border-radius: 16px;
        border-left: 6px solid #F59E0B;
        color: {tc['text']};
        box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1);
    }}

    /* Mobile Optimization */
    @media (max-width: 768px) {{
        .main-header {{ text-align: center; }}
        [data-testid="column"] {{
            width: 100% !important;
            flex: 1 1 100% !important;
            min-width: 100% !important;
            margin-bottom: 1rem;
        }}
    }}
    
    /* Dark Mode specific text fixes */
    {"[data-testid='stMarkdownContainer'] p, [data-testid='stMarkdownContainer'] span, [data-testid='stMarkdownContainer'] li { color: " + tc['text'] + " !important; }" if st.session_state.theme == "Dark" else ""}
    {"[data-testid='stExpander'] label { color: " + tc['text'] + " !important; }" if st.session_state.theme == "Dark" else ""}
    </style>
""", unsafe_allow_html=True)

# --- 6. Caching for Rapid Response ---
@st.cache_data(ttl=3600)
def get_weather(lat, lon, elev):
    clim = fetch_nasa_power_climatology(lat, lon)
    row = {"grid_id": "m", "lat": lat, "lon": lon, "elevation": elev, **clim}
    return generate_cell(row), clim

@st.cache_data(ttl=3600)
def get_detailed_roi(yield_kwh, kw, cost, tariff, net, subsidy, sc):
    return calculate_roi(yield_kwh, kw, cost, tariff, net, subsidy, sc)

# --- 7. Sidebar ---
with st.sidebar:
    st.markdown("<h1 style='color:#F59E0B; text-align:center;'>ENERLYTICS</h1>", unsafe_allow_html=True)
    
    # Theme Toggle
    theme_btn = st.radio("🌗 Theme", ["Bright", "Dark"], index=0 if st.session_state.theme == "Bright" else 1, horizontal=True)
    if theme_btn != st.session_state.theme:
        st.session_state.theme = theme_btn
        st.rerun()

    nav = st.radio("Navigation", ["Explorer", "Comparison", "System Sizer", "ROI Analysis", "About"], key="nav")
    
    st.divider()
    pincode = st.text_input("📍 PIN Code (India)", value=st.session_state.pincode, max_chars=6)
    
    if pincode and pincode != st.session_state.pincode and len(pincode) == 6:
        nomi = pgeocode.Nominatim('in')
        geo = nomi.query_postal_code(pincode)
        if not pd.isna(geo.latitude):
            st.session_state.loc = {
                "lat": round(geo.latitude*4)/4, 
                "lon": round(geo.longitude*4)/4, 
                "name": geo.place_name, 
                "state": geo.state_name
            }
            st.session_state.pincode = pincode
            st.session_state.results = None # Reset results on location change

    solar_kw = st.slider("☀️ Solar (kW)", 0.0, 50.0, 5.0, 0.5)
    wind_kw = st.slider("💨 Wind (kW)", 0.0, 20.0, 0.0, 0.5)
    
    with st.expander("💰 Financial Overrides"):
        state_info = get_state_tariff(st.session_state.loc["state"])
        t_in = st.number_input("Grid Tariff (₹/kWh)", value=state_info["tariff"], step=0.1)
        n_in = st.number_input("Net Meter (₹/kWh)", value=state_info["net_meter"], step=0.1)
        c_in = st.number_input("Cost per kW (₹)", value=55000, step=1000)
        sc_in = st.slider("Self Consumption (%)", 50, 100, 80)

# --- 8. Data Pre-computation ---
if st.session_state.results is None or solar_kw != st.session_state.get('last_solar') or wind_kw != st.session_state.get('last_wind'):
    data, clim = get_weather(st.session_state.loc["lat"], st.session_state.loc["lon"], 200.0)
    pv_power = simulate_pv_power(data['ghi'], data['temp'], solar_kw)
    wind_power = simulate_wind_power(data['wind'], wind_kw)
    
    sub_info = pm_surya_ghar_subsidy(solar_kw)
    roi = get_detailed_roi(pv_power.sum()/1000, solar_kw, c_in, t_in, n_in, sub_info["subsidy_inr"], sc_in)
    env = co2_and_environment(pv_power.sum()/1000 * 1000) # Input in kWh
    
    st.session_state.results = {
        "data": data,
        "clim": clim,
        "pv_power": pv_power,
        "wind_power": wind_power,
        "sub_info": sub_info,
        "roi": roi,
        "env": env
    }
    st.session_state.last_solar = solar_kw
    st.session_state.last_wind = wind_kw

res = st.session_state.results

# --- 9. Main App ---
if nav == "Explorer":
    st.markdown(f"<div class='main-header'>📍 {st.session_state.loc['name']} Energy Potential</div>", unsafe_allow_html=True)
    
    # 8.1 Summary Metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Solar Capacity", f"{solar_kw} kW")
    m2.metric("Annual Solar Yield", f"{res['pv_power'].sum()/1000:.1f} MWh/y")
    m3.metric("Specific Yield", f"{res['pv_power'].sum()/solar_kw:.0f} kWh/kWp" if solar_kw > 0 else "0")
    m4.metric("Avg Daily Sun", f"{res['data']['ghi'].mean()*24/1000:.2f} kWh/m²")
    
    m5, m6, m7, m8 = st.columns(4)
    m5.metric("Net Metering Rate", f"₹{n_in}/kWh")
    m6.metric("Payback Period", f"{res['roi']['simple_payback_yr']:.1f} Yrs")
    m7.metric("CO₂ Avoided", f"{res['env']['co2_avoided_tonnes_yr']:.1f} t/yr")
    m8.metric("Trees Equivalent", f"{res['env']['trees_equivalent']} trees")

    # 8.2 Detailed Visuals
    t_sum, t_mon, t_prof, t_adv, t_env = st.tabs(["📊 Overview", "📅 Monthly Breakdown", "📈 24h Profiles", "🛠️ Installation Advice", "🌳 Environmental"])
    
    with t_sum:
        st.markdown("<div class='sub-header'>Solar Irradiance Heatmap</div>", unsafe_allow_html=True)
        fig_h = px.imshow(res['data']['ghi'].reshape(365, 24).T, 
                          color_continuous_scale="YlOrRd", 
                          labels=dict(x="Day of Year", y="Hour of Day", color="W/m²"),
                          template=tc['plotly_theme'])
        fig_h.update_layout(height=450, margin=dict(l=0,r=0,t=20,b=0))
        st.plotly_chart(fig_h, use_container_width=True, config={'displayModeBar': False})
        
        with st.expander("ℹ️ How to read this heatmap"):
            st.write("This map shows solar intensity for every hour of every day in a typical year. Darker red indicates peak sunshine (typically 11 AM - 2 PM). The vertical axis represents the 24 hours of a day, and the horizontal axis represents 365 days.")

    with t_mon:
        ghi_m = compute_monthly_means(res['data']['ghi'])
        pv_m = [res['pv_power'][idx].sum()/1000 for idx in monthly_indices()]
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(px.bar(x=months, y=ghi_m, title="Monthly Avg Irradiance (W/m²)", 
                                   color_discrete_sequence=['#F59E0B'], 
                                   labels={'x':'Month', 'y':'W/m²'},
                                   template=tc['plotly_theme']), use_container_width=True)
        with c2:
            st.plotly_chart(px.bar(x=months, y=pv_m, title="Monthly Solar Yield (MWh)", 
                                   color_discrete_sequence=['#3B82F6'], 
                                   labels={'x':'Month', 'y':'MWh'},
                                   template=tc['plotly_theme']), use_container_width=True)
            
        st.markdown("<div class='sub-header'>Monthly Yield Table</div>", unsafe_allow_html=True)
        mon_df = pd.DataFrame({"Month": months, "Irradiance (W/m²)": ghi_m, "Solar Yield (kWh)": [p*1000 for p in pv_m]})
        st.dataframe(mon_df.style.format({"Irradiance (W/m²)": "{:.1f}", "Solar Yield (kWh)": "{:,.0f}"}), use_container_width=True)
        
        st.divider()
        st.subheader("🗓️ Seasonal Maintenance Planner")
        best_mon = months[np.argmax(pv_m)]
        worst_mon = months[np.argmin(pv_m)]
        
        st.write(f"**Peak Generation Month:** {best_mon} (Maximize cleaning during this month!)")
        st.write(f"**Lowest Generation Month:** {worst_mon} (Ideal time for scheduled inverter maintenance)")
        
        st.info("💡 **Pro-Tip:** Cleaning your panels once every 15 days can increase yield by up to 10-15%, especially in dusty regions.")

    with t_prof:
        g24 = res['data']['ghi'].reshape(365, 24).mean(axis=0)
        t24 = res['data']['temp'].reshape(365, 24).mean(axis=0)
        p24 = res['pv_power'].reshape(365, 24).mean(axis=0)
        
        c1, c2 = st.columns(2)
        with c1:
            fig_g = go.Figure()
            fig_g.add_trace(go.Scatter(x=list(range(24)), y=g24, name="Irradiance", fill='tozeroy', line=dict(color='#F59E0B')))
            fig_g.update_layout(title="Typical 24h Solar Cycle", xaxis_title="Hour", yaxis_title="W/m²", template=tc['plotly_theme'])
            st.plotly_chart(fig_g, use_container_width=True)
        with c2:
            fig_t = go.Figure()
            fig_t.add_trace(go.Scatter(x=list(range(24)), y=t24, name="Temperature", line=dict(color='#EF4444')))
            fig_t.update_layout(title="Typical 24h Temp Cycle", xaxis_title="Hour", yaxis_title="°C", template=tc['plotly_theme'])
            st.plotly_chart(fig_t, use_container_width=True)
            
        st.plotly_chart(px.line(x=list(range(24)), y=p24, 
                                title="Typical 24h Power Generation (Watts)", 
                                labels={'x':'Hour','y':'Watts'}, 
                                color_discrete_sequence=['#10B981'],
                                template=tc['plotly_theme']), use_container_width=True)

    with t_adv:
        from energy_explore.advisor import generate_installation_advisory
        adv = generate_installation_advisory(res['data'], st.session_state.loc["lat"])
        
        st.markdown("<div class='sub-header'>Solar Installation Parameters</div>", unsafe_allow_html=True)
        a1, a2, a3 = st.columns(3)
        a1.metric("Optimal Tilt", f"{adv['solar']['optimal_tilt']}°")
        a2.metric("Optimal Azimuth", f"{adv['solar']['optimal_azimuth']}° (South)")
        a3.metric("Min Row Spacing", f"{adv['solar']['min_row_spacing_m']:.2f} m")
        
        st.info(f"💡 By using the optimal tilt of {adv['solar']['optimal_tilt']}°, you can gain **{adv['solar']['gain_vs_flat_pct']:.1f}%** more energy compared to a flat installation.")
        
        st.markdown("<div class='sub-header'>Wind Resource Assessment</div>", unsafe_allow_html=True)
        w1, w2, w3 = st.columns(3)
        w1.metric("Recommended Height", f"{adv['wind']['recommended_height_m']} m")
        w2.metric("Mean Speed @ Hub", f"{adv['wind']['height_data'][-1]['mean_speed_ms']:.1f} m/s")
        w3.metric("Capacity Factor", f"{adv['wind']['capacity_factor_pct']:.1f}%")
        
        st.write("**Power Density by Height:**")
        h_df = pd.DataFrame(adv['wind']['height_data'])
        fig_wind = px.line(h_df, x='height_m', y='power_density_wm2', 
                           template=tc['plotly_theme'], 
                           markers=True,
                           title="Wind Power Density Profile")
        st.plotly_chart(fig_wind, use_container_width=True)

    with t_env:

        st.markdown("<div class='sub-header'>Environmental Impact Metrics</div>", unsafe_allow_html=True)
        e1, e2, e3 = st.columns(3)
        e1.metric("Coal Saved", f"{res['env']['coal_saved_kg_yr']:.0f} kg/yr")
        e2.metric("Homes Powered", f"{res['env']['homes_powered']} homes")
        e3.metric("CO₂ Offset (25yr)", f"{res['env']['co2_avoided_tonnes_yr']*25:.1f} tonnes")
        
        st.info(f"💡 Your {solar_kw} kW system is equivalent to planting {res['env']['trees_equivalent']} mature trees every year in terms of carbon sequestration.")

elif nav == "Comparison":
    st.markdown("<div class='main-header'>⚖️ Location Comparison</div>", unsafe_allow_html=True)
    st.write("Compare solar potential and financial returns between two Indian cities.")
    
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("📍 Location 1")
        pin1 = st.text_input("PIN Code 1", value=st.session_state.pincode, key="pin1")
        nomi = pgeocode.Nominatim('in')
        geo1 = nomi.query_postal_code(pin1)
        if not pd.isna(geo1.latitude):
            loc1 = {"lat": round(geo1.latitude*4)/4, "lon": round(geo1.longitude*4)/4, "name": geo1.place_name, "state": geo1.state_name}
            data1, _ = get_weather(loc1["lat"], loc1["lon"], 200.0)
            pv1 = simulate_pv_power(data1['ghi'], data1['temp'], solar_kw)
            sub1 = pm_surya_ghar_subsidy(solar_kw)
            roi1 = get_detailed_roi(pv1.sum()/1000, solar_kw, c_in, t_in, n_in, sub1["subsidy_inr"], sc_in)
            
            st.metric("Annual Yield", f"{pv1.sum()/1000:.1f} MWh")
            st.metric("Payback", f"{roi1['simple_payback_yr']:.1f} Yrs")
            st.metric("Avg GHI", f"{data1['ghi'].mean()*24/1000:.2f} kWh/m²")
            
    with c2:
        st.subheader("📍 Location 2")
        pin2 = st.text_input("PIN Code 2", value="411001", key="pin2") # Pune as default
        geo2 = nomi.query_postal_code(pin2)
        if not pd.isna(geo2.latitude):
            loc2 = {"lat": round(geo2.latitude*4)/4, "lon": round(geo2.longitude*4)/4, "name": geo2.place_name, "state": geo2.state_name}
            data2, _ = get_weather(loc2["lat"], loc2["lon"], 200.0)
            pv2 = simulate_pv_power(data2['ghi'], data2['temp'], solar_kw)
            sub2 = pm_surya_ghar_subsidy(solar_kw)
            roi2 = get_detailed_roi(pv2.sum()/1000, solar_kw, c_in, t_in, n_in, sub2["subsidy_inr"], sc_in)
            
            st.metric("Annual Yield", f"{pv2.sum()/1000:.1f} MWh", delta=f"{(pv2.sum()-pv1.sum())/1000:.1f}")
            st.metric("Payback", f"{roi2['simple_payback_yr']:.1f} Yrs", delta=f"{roi2['simple_payback_yr']-roi1['simple_payback_yr']:.1f}", delta_color="inverse")
            st.metric("Avg GHI", f"{data2['ghi'].mean()*24/1000:.2f} kWh/m²", delta=f"{data2['ghi'].mean()*24/1000 - data1['ghi'].mean()*24/1000:.2f}")

    if not pd.isna(geo1.latitude) and not pd.isna(geo2.latitude):
        st.divider()
        st.subheader("Monthly Comparison (MWh)")
        pv1_m = [pv1[idx].sum()/1000 for idx in monthly_indices()]
        pv2_m = [pv2[idx].sum()/1000 for idx in monthly_indices()]
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        
        comp_df = pd.DataFrame({
            "Month": months,
            loc1["name"]: pv1_m,
            loc2["name"]: pv2_m
        })
        st.plotly_chart(px.line(comp_df, x="Month", y=[loc1["name"], loc2["name"]], 
                                markers=True, title="Monthly Yield Comparison",
                                template=tc['plotly_theme']), use_container_width=True)

elif nav == "System Sizer":
    st.markdown("<div class='main-header'>📏 Solar System Sizer</div>", unsafe_allow_html=True)
    
    t_quick, t_app, t_audit, t_compare = st.tabs(["⚡ Quick Sizer", "🏠 Appliance Builder", "🔍 Energy Audit", "⚖️ Source Comparison"])
    
    with t_quick:
        col1, col2 = st.columns([1, 1.5])
        with col1:
            st.subheader("Consumption Details")
            # Use custom units if set by appliance builder
            units = st.number_input("Monthly Electricity Consumption (kWh)", 50, 10000, st.session_state.custom_units)
            sun_type = st.selectbox("Your Region", list(REGION_SUN_HOURS.keys()))
            
            st.subheader("Panel Configuration")
            vendor = st.selectbox("Select Panel Model", list(VENDOR_PANELS.keys()))
            v_info = VENDOR_PANELS[vendor]
            
            sizing = size_solar_system(
                units, 
                peak_sun_hours=REGION_SUN_HOURS[sun_type], 
                state_name=st.session_state.loc["state"],
                panel_watt_peak=v_info["wattage"]
            )
            
            st.markdown(f"""
            <div class='info-card'>
            <b>Sizing Rationale:</b><br>
            Based on {REGION_SUN_HOURS[sun_type]} peak sun hours in your region and {v_info['brand']} {v_info['wattage']}W panels, a {sizing['solar_kw']} kW system is recommended.
            </div>
            """, unsafe_allow_html=True)
            
        with col2:
            st.subheader("Technical Configuration")
            k1, k2, k3 = st.columns(3)
            k1.metric("System Size", f"{sizing['solar_kw']} kW")
            k2.metric("Total Panels", f"{sizing['panel_count']} nos")
            k3.metric("Roof Area", f"{sizing['roof_area_m2']} m²")
            
            st.divider()
            st.subheader("Financial Estimate")
            c1, c2 = st.columns(2)
            c1.metric("Net Cost (After Subsidy)", f"₹{sizing['net_capex_inr']/1e5:.2f} Lakhs")
            c2.metric("Annual Savings", f"₹{sizing['annual_savings_inr']/1e3:.1f} K")
            st.success(sizing["subsidy_note"])
            
            with st.expander("🛠️ System Specs"):
                st.write(f"- **Inverter Capacity:** {sizing['inverter_kva']} kVA")
                st.write(f"- **Panel Rating:** {sizing['panel_wp']} Wp {v_info['type']}")
                st.write(f"- **Daily Generation:** ~{sizing['daily_gen_kwh']} kWh")
                st.write(f"- **LCOE:** ₹{sizing['lcoe_inr_per_kwh']}/kWh")

    with t_app:
        st.subheader("Interactive Appliance Builder")
        st.write("Build your household load by adding appliances and setting their daily usage.")
        
        # UI for adding appliances
        with st.expander("➕ Add New Appliance"):
            all_options = DEFAULT_APPLIANCES + ADDON_APPLIANCES
            opt_names = [a["name"] for a in all_options]
            selected_add = st.selectbox("Select Appliance", opt_names)
            if st.button("Add to My List"):
                to_add = next(a for a in all_options if a["name"] == selected_add)
                st.session_state.appliances.append(dict(to_add))
                st.rerun()

        # List of added appliances with editing
        st.write("### Your Appliance List")
        new_app_list = []
        for i, app in enumerate(st.session_state.appliances):
            c1, c2, c3, c4 = st.columns([2, 1, 1, 0.5])
            with c1: st.write(f"**{app['name']}**")
            with c2: 
                app["watts"] = st.number_input(f"Watts (W)", value=int(app["watts"]), key=f"w_{i}")
            with c3:
                app["hours"] = st.number_input(f"Hrs/Day", value=float(app["hours"]), key=f"h_{i}", step=0.5)
            with c4:
                if st.button("🗑️", key=f"del_{i}"):
                    st.session_state.appliances.pop(i)
                    st.rerun()
            new_app_list.append(app)
        st.session_state.appliances = new_app_list

        # Totals
        from energy_explore.sizer import compute_load
        load = compute_load(st.session_state.appliances)
        
        st.divider()
        m1, m2, m3 = st.columns(3)
        m1.metric("Daily Consumption", f"{load['daily_kwh']:.2f} kWh")
        m2.metric("Monthly Consumption", f"{load['monthly_kwh']:.1f} kWh")
        m3.metric("Peak Load", f"{load['peak_kw']:.2f} kW")
        
        if st.button("✨ Use this as my monthly usage"):
            st.session_state.custom_units = int(load['monthly_kwh'])
            st.success(f"Monthly units updated to {st.session_state.custom_units} kWh! Switch to Quick Sizer to see results.")
            st.rerun()

    with t_audit:
        st.subheader("Detailed Household Energy Audit")
        num_ac = st.number_input("Number of AC Units (1.5 Ton avg)", 0, 20, 1)
        num_beds = st.number_input("Number of Bedrooms", 1, 10, 2)
        home_type = st.selectbox("Home Type", ["apartment", "independent house", "villa"])
        
        audit = energy_audit(units, num_ac_units=num_ac, num_bedrooms=num_beds, home_type=home_type, grid_tariff_inr=t_in)
        
        c1, c2 = st.columns([1, 1])
        with c1:
            st.markdown(f"**Energy Efficiency Rating: <span style='color:{audit['energy_rating_color']}'>{audit['energy_rating']}</span>**", unsafe_allow_html=True)
            fig_audit = px.pie(
            names=list(audit["category_labels"].values()), 
            values=list(audit["breakdown_kwh"].values()), 
            hole=0.4,
            title="Monthly Usage Breakdown",
            color_discrete_sequence=px.colors.qualitative.Pastel,
            template=tc['plotly_theme']
        )
            st.plotly_chart(fig_audit, use_container_width=True)
            
        with c2:
            st.subheader("Priority Actions")
            act_df = pd.DataFrame(audit["priority_actions"])
            for _, row in act_df.iterrows():
                with st.expander(f"{row['priority']}: {row['action']}"):
                    st.write(f"**Potential Saving:** {row['saving']}")
                    st.write(f"**Estimated Cost:** {row['cost']}")

    with t_compare:
        st.subheader("Energy Source Comparison")
        comp = compare_energy_sources(units, peak_sun_hours=REGION_SUN_HOURS[sun_type], state_name=st.session_state.loc["state"])
        
        for opt in comp:
            with st.container():
                col_a, col_b, col_c = st.columns([1.5, 1, 2])
                with col_a:
                    st.markdown(f"### {opt['option']} {'⭐' if opt['recommended'] else ''}")
                    st.write(f"**Capacity:** {opt['capacity']}")
                with col_b:
                    st.write(f"**Payback:** {opt['payback_yr']} Yrs")
                    st.write(f"**Net Cost:** ₹{opt['net_capex_inr']/1e5:.2f} L")
                with col_c:
                    st.info(opt['note'])
                st.divider()

elif nav == "ROI Analysis":
    st.markdown("<div class='main-header'>💰 Financial & ROI Analysis</div>", unsafe_allow_html=True)
    
    st.subheader("Investment & Return Summary")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Net Investment", f"₹{res['roi']['net_capex_inr']/1e5:.2f} L")
    k2.metric("25-Yr Net Profit", f"₹{(sum(y['savings_inr'] for y in res['roi']['year_by_year']) - res['roi']['net_capex_inr'])/1e5:.2f} L")
    k3.metric("IRR (Internal Rate of Return)", f"{res['roi']['irr_pct']:.1f}%")
    k4.metric("LCOE (Cost per Unit)", f"₹{res['roi']['lcoe_inr_per_kwh']:.2f}/kWh")
    
    st.divider()
    
    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader("25-Year Cumulative Savings")
        yby = pd.DataFrame(res['roi']["year_by_year"])
        fig_cf = go.Figure()
        fig_cf.add_trace(go.Bar(x=yby["year"], y=yby["savings_inr"], name="Annual Savings", marker_color="#3B82F6"))
        fig_cf.add_trace(go.Scatter(x=yby["year"], y=yby["cumulative_savings"], name="Cumulative Savings", line=dict(color="#F59E0B", width=3)))
        fig_cf.update_layout(template=tc['plotly_theme'], height=450, xaxis_title="Year", yaxis_title="Rupees (₹)")
        st.plotly_chart(fig_cf, use_container_width=True)
    
    with c2:
        st.subheader("Financial Metrics")
        st.write(f"**Net Present Value (NPV):** ₹{res['roi']['npv_25yr_inr']/1e5:.2f} Lakhs")
        st.write(f"**Govt. Subsidy:** ₹{res['sub_info']['subsidy_inr']/1e3:.1f} K")
        st.write(f"**Self-Consumption:** {sc_in}%")
        st.write(f"**Grid Export:** {100-sc_in}%")
        
        st.markdown(f"""
        <div class='info-card'>
        <b>Pro Tip:</b><br>
        An IRR of {res['roi']['irr_pct']:.1f}% is significantly higher than most fixed deposits or mutual funds, making rooftop solar one of the safest and highest-yielding investments.
        </div>
        """, unsafe_allow_html=True)

    st.subheader("Detailed Year-by-Year Financials")
    st.dataframe(yby.style.format({
        "energy_kwh": "{:,.0f}",
        "savings_inr": "₹{:,.0f}",
        "cumulative_savings": "₹{:,.0f}"
    }), use_container_width=True)

    st.divider()
    st.subheader("🧾 Monthly Bill Estimator (Pre vs Post Solar)")
    st.write("See how your electricity bill changes after installing solar.")
    
    # Simple bill calculation based on units and tariff
    pre_solar_bill = units * t_in
    # Post solar bill: units - solar_generation (self consumed + exported at net meter rate)
    solar_gen_monthly = res['pv_power'].sum() / 12.0 # kWh/year to kWh/month
    post_solar_units = max(0, units - solar_gen_monthly * (sc_in/100.0))
    exported_units = solar_gen_monthly * (1 - sc_in/100.0)
    post_solar_bill = (post_solar_units * t_in) - (exported_units * n_in)
    
    b1, b2, b3 = st.columns(3)
    b1.metric("Pre-Solar Bill", f"₹{pre_solar_bill:,.0f}/mo")
    b2.metric("Post-Solar Bill", f"₹{max(0, post_solar_bill):,.0f}/mo", delta=f"{max(0, post_solar_bill) - pre_solar_bill:,.0f}", delta_color="inverse")
    b3.metric("Monthly Savings", f"₹{pre_solar_bill - max(0, post_solar_bill):,.0f}/mo")
    
    st.caption(f"Note: Based on {units} units/month consumption and {solar_kw} kW solar system.")

    st.divider()
    if st.button("📄 Generate & Download PDF Report", use_container_width=True):
        from energy_explore.advisor import generate_installation_advisory
        adv = generate_installation_advisory(res['data'], st.session_state.loc["lat"])
        
        # Prepare data for report (consolidate keys)
        report_data = dict(res['data'])
        report_data['pv_power'] = res['pv_power']
        report_data['wind_power'] = res['wind_power']
        
        pdf_bytes = generate_pdf_report(
            place_name=st.session_state.loc["name"],
            lat=st.session_state.loc["lat"],
            lon=st.session_state.loc["lon"],
            elev=200.0,
            clim=res['clim'],
            data=report_data,
            advisory=adv,
            roi=res['roi'],
            solar_kw=solar_kw,
            wind_kw=wind_kw,
            nasa_data_used=res['clim'].get('nasa_data_used', True)
        )
        st.download_button(
            label="💾 Download PDF",
            data=pdf_bytes,
            file_name=f"ENERLYTICS_Report_{st.session_state.loc['name']}.pdf",
            mime="application/pdf",
            use_container_width=True
        )

elif nav == "About":
    st.markdown("<div class='main-header'>📖 About ENERLYTICS</div>", unsafe_allow_html=True)
    tab1, tab2, tab3, tab4 = st.tabs(["🚀 Project", "🧪 Calculations", "📖 Guide", "👤 Developer"])
    
    with tab1:
        st.markdown("""
        ### ENERLYTICS: Energy Intelligence for a Sustainable Future
        **ENERLYTICS** is a professional-grade solar and wind energy advisory platform designed specifically for the Indian market. 
        It bridges the gap between complex climate science and practical, actionable energy solutions.
        
        #### Core Features:
        - **NASA-Powered Data**: Utilizes 30 years of satellite-derived meteorological data.
        - **Precision Modeling**: Implements the Perez Anisotropic Sky Model for solar yield.
        - **Financial Engineering**: Detailed ROI, NPV, and IRR calculations aligned with Indian subsidy schemes.
        - **Load Auditing**: Intelligent appliance-level load estimation and efficiency advisory.
        """)
        
    with tab2:
        st.subheader("Scientific Methodology")
        with st.expander("☀️ Solar Irradiance Modeling"):
            st.markdown("""
            1. **Stochastic Synthesis**: We use an Auto-Regressive AR(1) process to generate realistic hourly data from monthly NASA means.
            2. **DNI/DHI Splitting**: The Reindl model is used to separate Global Horizontal Irradiance into Direct and Diffuse components.
            3. **Transposition**: We implement the **Perez 1990 Anisotropic Sky Model**, which accounts for circumsolar and horizon brightening, providing 5-15% higher accuracy than standard isotropic models.
            """)
        with st.expander("💨 Wind Assessment"):
            st.markdown("""
            1. **Weibull Distribution**: Wind speeds are modeled using the Weibull probability density function, fitting k (shape) and c (scale) parameters to the site data.
            2. **Hellmann Power Law**: We extrapolate wind speeds from NASA's 10m reference height to hub heights up to 100m using site-specific roughness exponents.
            """)
        with st.expander("💰 Financial Logic"):
            st.markdown("""
            1. **ROI Analysis**: Includes panel degradation (0.5%/yr), tariff escalation (3%/yr), and O&M costs.
            2. **LCOE**: Levelized Cost of Energy accounts for the time-value of money over a 25-year lifecycle.
            3. **PM Surya Ghar**: Calculations are strictly aligned with the 2024-25 MNRE subsidy slabs (₹30k/kW up to 2kW, ₹78k cap).
            """)
            
    with tab3:
        st.subheader("How to Use the Platform")
        st.info("""
        1. **Explorer**: Start here to see your site's raw potential. Enter your PIN code and adjust capacity.
        2. **System Sizer**: Use this if you don't know what capacity you need. Input your bill or appliances.
        3. **ROI Analysis**: Check the deep financials. Adjust the 'Financial Overrides' in the sidebar for precision.
        4. **Export**: Use the 'Download' buttons (where available) to save your data.
        """)
        
    with tab4:
        st.markdown("""
        ## 👤 About the Developer

        **Himansu Kumar Sahu**

        Passionate about bridging the gap between high-fidelity climate science and practical energy solutions for the Indian subcontinent.

        [<img src="https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white" alt="LinkedIn"/>](http://www.linkedin.com/in/himansu-kumar-sahu-377916334)
        [<img src="https://img.shields.io/badge/GitHub-100000?style=for-the-badge&logo=github&logoColor=white" alt="GitHub"/>](https://github.com/himansu1211)
        [<img src="https://img.shields.io/badge/Gmail-D14836?style=for-the-badge&logo=gmail&logoColor=white" alt="Email"/>](mailto:himansuk1211@gmail.com)
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    st.write("Please run this app using: `streamlit run src/energy_explore/app.py`")
