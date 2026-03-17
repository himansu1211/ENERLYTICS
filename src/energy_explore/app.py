"""
ENERLYTICS - Professional Solar & Wind Advisory for India.
"""
import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import pgeocode
import requests
import os
from datetime import datetime

# Import project modules
from energy_explore.pipeline import fetch_nasa_power_climatology
from energy_explore.core import generate_cell, monthly_indices, compute_monthly_means, simulate_pv_power, simulate_wind_power
from energy_explore.validation import validation_metrics
from energy_explore.advisor import generate_installation_advisory, HELLMANN_EXPONENTS, VENDOR_PANELS
from energy_explore.financial import (
    pm_surya_ghar_subsidy, calculate_roi, simulate_battery_dispatch, 
    co2_and_environment, get_state_tariff, DISCOM_TARIFFS
)
from energy_explore.sizer import (
    size_solar_system, energy_audit, compute_load, compare_energy_sources,
    DEFAULT_APPLIANCES, ADDON_APPLIANCES, REGION_SUN_HOURS
)
from energy_explore.report import generate_pdf_report, generate_epw_string
from energy_explore.perez import perez_poa_total

# --- Page Config ---
st.set_page_config(
    page_title="ENERLYTICS",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Logo / Header ---
st.markdown("""
    <div style="display: flex; align-items: center; justify-content: center; padding: 10px; margin-bottom: 20px; border-bottom: 2px solid #F59E0B;">
        <h1 style="color: #0F172A; margin: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; letter-spacing: 2px;">
            <span style="color: #F59E0B;">ENER</span>LYTICS
        </h1>
        <span style="font-size: 2rem; margin-left: 10px;">☀️</span>
    </div>
""", unsafe_allow_html=True)

# --- State Initialisation ---
if 'generated' not in st.session_state:
    st.session_state.generated = False
if 'lat' not in st.session_state:
    st.session_state.lat = 28.61 # New Delhi
if 'lon' not in st.session_state:
    st.session_state.lon = 77.23
if 'place_name' not in st.session_state:
    st.session_state.place_name = "New Delhi"
if 'state_name' not in st.session_state:
    st.session_state.state_name = "Delhi"
if 'elev' not in st.session_state:
    st.session_state.elev = 216.0

# --- Sidebar ---
with st.sidebar:
    st.title("☀️ ENERLYTICS")
    nav = st.radio("Navigation", ["Explorer", "System Sizer", "Financial Calculator", "Products", "About"])
    
    st.divider()
    st.header("📍 1. Location")
    pincode = st.text_input("Enter 6-digit PIN Code", value="110001", max_chars=6)
    
    if pincode and len(pincode) == 6:
        nomi = pgeocode.Nominatim('in')
        res = nomi.query_postal_code(pincode)
        if not pd.isna(res.latitude):
            st.session_state.lat = round(res.latitude * 4) / 4
            st.session_state.lon = round(res.longitude * 4) / 4
            st.session_state.place_name = res.place_name
            st.session_state.state_name = res.state_name
            st.success(f"Found: {res.place_name}, {res.state_name}")
        else:
            st.error("Invalid PIN code.")
            
    st.markdown(f"**Grid point:** {st.session_state.lat}°N, {st.session_state.lon}°E")
    st.session_state.elev = st.number_input("Elevation (m)", value=st.session_state.elev)
    
    st.divider()
    st.header("⚡ 2. Energy System")
    solar_kw = st.number_input("Solar Capacity (kW)", value=5.0, min_value=0.0, step=1.0)
    wind_kw = st.number_input("Wind Capacity (kW)", value=0.0, min_value=0.0, step=1.0)
    mod_len = st.number_input("Module length (m)", value=2.0, min_value=0.5, max_value=4.0)
    use_perez = st.checkbox("Use Perez 1990 Model", value=True)
    if use_perez:
        st.info("Perez 1990 anisotropic sky model (+5-15% accuracy vs isotropic)")
        
    st.divider()
    with st.expander("💰 3. Financial Inputs"):
        state_info = get_state_tariff(st.session_state.state_name)
        cost_kw = st.number_input("System cost (₹/kW)", value=55000)
        tariff = st.number_input("Grid tariff (₹/kWh)", value=state_info["tariff"], step=0.1)
        net_meter = st.number_input("Net metering rate (₹/kWh)", value=state_info["net_meter"], step=0.1)
        self_con = st.slider("Self consumption (%)", 50, 100, 80)
        apply_subsidy = st.checkbox("Apply PM Surya Ghar Subsidy", value=True)
        is_special = st.checkbox("Is special category state", value=False)
        battery_kwh = st.number_input("Battery storage (kWh)", value=0.0)
        loan_frac = st.slider("Loan fraction (%)", 0, 100, 70)
        loan_rate = st.number_input("Loan interest rate (%)", value=7.0)

    if st.button("Generate Synthetic Year + Analyse", use_container_width=True, type="primary"):
        st.session_state.generated = True

# --- Main App Logic ---
if nav == "Explorer":
    if not st.session_state.generated:
        st.title("ENERLYTICS")
        st.info("👈 Enter a PIN code and click 'Generate' in the sidebar to begin.")
    else:
        # 1. Fetch Data
        with st.spinner("Fetching climatology..."):
            clim = fetch_nasa_power_climatology(st.session_state.lat, st.session_state.lon)
            
        # 2. Synthesis
        with st.spinner("Synthesising hourly weather series..."):
            row = {
                "grid_id": f"{st.session_state.lat:.2f}_{st.session_state.lon:.2f}",
                "lat": st.session_state.lat, "lon": st.session_state.lon, 
                "elevation": st.session_state.elev, **clim
            }
            data = generate_cell(row)
            
            # Add power simulations
            data['pv_power'] = simulate_pv_power(data['ghi'], data['temp'], capacity_kw=solar_kw)
            data['wind_power'] = simulate_wind_power(data['wind'], capacity_kw=wind_kw)
            
            # Advisory
            adv = generate_installation_advisory(data, st.session_state.lat, use_perez, mod_len)
            
            # Financials
            subsidy_val = pm_surya_ghar_subsidy(solar_kw, is_special)["subsidy_inr"] if apply_subsidy else 0
            roi = calculate_roi(
                data['pv_power'].sum() / 1000.0, solar_kw, cost_kw, 
                tariff, net_meter, subsidy_val, self_consumption_pct=self_con
            )
            
            # Battery
            bess = simulate_battery_dispatch(data['pv_power'], battery_kwh=battery_kwh)
            
            # Metrics
            metrics = validation_metrics(data, clim)

        # 3. Tabs
        t1, t2, t3, t4, t5, t6, t7, t8 = st.tabs(["📊 Annual Summary", "📅 Monthly Breakdown", "🔧 Installation Advisory", "💰 Financial Analysis", "✅ Data Quality", "📄 Export", "🆚 Comparison Mode", "🗺️ Location Intelligence"])
        
        with t1:
            st.success(f"📍 **{st.session_state.place_name}** ({st.session_state.lat}°N, {st.session_state.lon}°E) | Elevation: {st.session_state.elev}m")
            if not clim["nasa_data_used"]:
                st.warning("⚠️ Using Regional Fallback Data (NASA API unavailable)")
            
            # Metric Cards
            m1, m2, m3, m4, m5, m6 = st.columns(6)
            insolation = data['ghi'].mean() * 24 / 1000.0
            m1.metric("Insolation", f"{insolation:.2f}", "kWh/m²/d")
            m2.metric("Avg Temp", f"{data['temp'].mean():.1f}°C")
            m3.metric("Peak UV", "High")
            m4.metric("Avg Wind", f"{data['wind'].mean():.1f}", "m/s")
            m5.metric("Solar Yield", f"{data['pv_power'].sum()/1000:.1f}", "MWh/yr")
            m6.metric("Wind Yield", f"{data['wind_power'].sum()/1000:.1f}", "MWh/yr")
            
            # Heatmap
            st.subheader("☀️ Full-Year GHI Heatmap")
            ghi_heat = data['ghi'].reshape(365, 24).T
            fig_h = px.imshow(ghi_heat, color_continuous_scale="YlOrRd", labels=dict(x="Day", y="Hour", color="W/m²"))
            fig_h.update_layout(template="simple_white", height=400)
            st.plotly_chart(fig_h, use_container_width=True)
            
            # Hourly Profile
            st.subheader("📈 Sample Week Profile (Jan 1-7)")
            fig_p = go.Figure()
            fig_p.add_trace(go.Scatter(y=data['pv_power'][:168], name="Solar Power (kW)", line=dict(color="#F59E0B")))
            fig_p.add_trace(go.Scatter(y=data['wind_power'][:168], name="Wind Power (kW)", line=dict(color="#3B82F6")))
            fig_p.add_trace(go.Scatter(y=data['temp'][:168], name="Temp (°C)", line=dict(color="#EF4444", dash="dash"), yaxis="y2"))
            fig_p.update_layout(
                yaxis2=dict(overlaying="y", side="right", title="Temp (°C)"),
                template="simple_white", hovermode="x unified", height=400
            )
            st.plotly_chart(fig_p, use_container_width=True)

        with t2:
            st.header("📅 Monthly Breakdown")
            col1, col2 = st.columns(2)
            ghi_m = compute_monthly_means(data['ghi'])
            temp_m = compute_monthly_means(data['temp'])
            indices = monthly_indices()
            
            with col1:
                st.plotly_chart(px.bar(x=list(range(1,13)), y=ghi_m, title="Monthly GHI (W/m²)", labels={'x':'Month', 'y':'W/m²'}, color_discrete_sequence=['#F59E0B']), use_container_width=True)
            with col2:
                st.plotly_chart(px.line(x=list(range(1,13)), y=temp_m, title="Monthly Temp (°C)", labels={'x':'Month', 'y':'°C'}, color_discrete_sequence=['#EF4444']), use_container_width=True)

            st.subheader("🗓️ Seasonal Planner & Bill Estimator")
            plan1, plan2 = st.columns(2)
            with plan1:
                st.info("**Best Month:** May (Peak Sun)\n\n**Worst Month:** July (Monsoon Clouding)\n\n**Maintenance Note:** Schedule panel cleaning in Oct-Nov post-monsoon for peak winter yield.")
            with plan2:
                current_bill = st.number_input("Current monthly bill (₹)", value=2500)
                savings = roi['annual_savings_inr_yr1'] / 12.0
                st.success(f"Estimated Post-Solar Bill: **₹{max(0, current_bill - savings):.0f}**\n\nMonthly Savings: ₹{savings:.0f}")

            st.subheader("Monthly Table")
            m_df = pd.DataFrame({
                "Month": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
                "GHI (W/m²)": ghi_m,
                "Temp (°C)": temp_m,
                "Wind (m/s)": [data['wind'][idx].mean() for idx in indices],
                "Solar (MWh)": [data['pv_power'][idx].sum()/1000 for idx in indices],
                "Wind (MWh)": [data['wind_power'][idx].sum()/1000 for idx in indices]
            })
            st.dataframe(m_df.style.format(precision=1), use_container_width=True)

        with t3:
            if solar_kw > 0:
                st.header("☀️ Solar Panel Installation")
                s = adv["solar"]
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Optimal Tilt", f"{s['optimal_tilt']:.1f}°")
                k2.metric("Facing Direction", "South (180°)")
                k3.metric("Annual POA", f"{s['annual_poa_kwh']:.0f}", "kWh/m²")
                k4.metric("Gain vs Flat", f"+{s['gain_vs_flat_pct']:.1f}%")
                
                if use_perez:
                    st.success(f"✅ Perez 1990 Model Active | Perez vs Isotropic: +{s['perez_gain_vs_isotropic_pct']:.1f}%")
                
                cc1, cc2 = st.columns(2)
                with cc1:
                    st.write("**Physical Specifications**")
                    st.table({
                        "Tilt": f"{s['optimal_tilt']:.1f}°",
                        "Azimuth": "180° (South)",
                        "Min Row Spacing": f"{s['min_row_spacing_m']:.2f} m",
                        "Row Pitch": f"{s['row_pitch_m']:.2f} m",
                        "GCR": f"{s['gcr']:.2f}"
                    })
                with cc2:
                    st.info(f"At {st.session_state.lat}°N latitude, solar panels perform best when facing South to catch the sun as it arcs through the southern sky throughout the year.")

                st.subheader("🏢 Vendor Comparison")
                st.write("Compare your site potential against top-tier Indian panel manufacturers.")
                v_df = pd.DataFrame([
                    {"Vendor": k, "Wattage": v["wattage"], "Efficiency": f"{v['eff']}%", "Bifacial": "✅" if v["bifacial"] else "❌", "Temp Coeff": v["temp_coeff"]}
                    for k, v in VENDOR_PANELS.items()
                ])
                st.table(v_df)
                st.info("Bifacial panels can provide 5-15% additional yield depending on albedo (ground reflectivity).")
            
            if wind_kw > 0:
                st.header("💨 Wind Turbine Installation")
                w = adv["wind"]
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Recommended Hub Height", f"{w['recommended_height_m']}m")
                k2.metric("Mean Speed", f"{w['height_data'][-1]['mean_speed_ms']:.1f} m/s")
                k3.metric("Consistency (k)", f"{w['k']:.2f}")
                k4.metric("Dominant Direction", "West (Typical)")

        with t4:
            st.header("💰 Financial Analysis")
            if apply_subsidy:
                st.success(f"PM Surya Ghar Muft Bijli Yojana ✅ | Subsidy: ₹{roi['net_capex_inr']-roi['gross_capex_inr']:,.0f}")
            
            k1, k2, k3, k4, k5 = st.columns(5)
            k1.metric("Simple Payback", f"{roi['simple_payback_yr']:.1f} Yrs")
            k2.metric("LCOE", f"₹{roi['lcoe_inr_per_kwh']:.2f}/kWh")
            k3.metric("25yr NPV", f"₹{roi['npv_25yr_inr']/1e5:.2f} L")
            k4.metric("IRR", f"{roi['irr_pct']:.1f}%")
            k5.metric("CO2 Saved", f"{roi['co2_avoided_tonnes_yr']:.1f}", "tonnes/yr")
            
            st.subheader("Cash Flow Forecast")
            yby = pd.DataFrame(roi["year_by_year"])
            fig_cf = go.Figure()
            fig_cf.add_trace(go.Scatter(x=yby["year"], y=yby["cumulative_savings"]/1e5, name="Cumulative Savings", fill='tozeroy'))
            fig_cf.add_hline(y=roi["net_capex_inr"]/1e5, line_dash="dash", line_color="red", annotation_text="Investment")
            fig_cf.update_layout(yaxis_title="₹ Lakhs", template="simple_white")
            st.plotly_chart(fig_cf, use_container_width=True)

        with t5:
            st.header("✅ Data Quality")
            k1, k2, k3 = st.columns(3)
            k1.metric("Solar RMSE", f"{metrics['ghi_monthly_rmse']:.1f} W/m²")
            k2.metric("Temp RMSE", f"{metrics['temp_monthly_rmse']:.1f}°C")
            k3.metric("Wind RMSE", f"{metrics['wind_monthly_rmse']:.1f} m/s")
            
            st.subheader("Monthly Bias (MBE)")
            st.bar_chart(metrics["ghi_monthly_mbe"], color="#F59E0B")
            
            st.subheader("Statistical Diagnostics")
            diag = pd.DataFrame({
                "Variable": ["GHI", "Temp", "Wind"],
                "RMSE": [metrics["ghi_monthly_rmse"], metrics["temp_monthly_rmse"], metrics["wind_monthly_rmse"]],
                "Lag-1 Autocorr": [metrics["ghi_lag1_autocorr"], metrics["temp_lag1_autocorr"], metrics["wind_lag1_autocorr"]],
                "Skewness": [metrics["ghi_skewness"], metrics["temp_skewness"], metrics["wind_skewness"]]
            })
            st.table(diag)

        with t6:
            st.header("📄 Export Results")
            pdf_data = generate_pdf_report(
                st.session_state.place_name, st.session_state.lat, st.session_state.lon,
                st.session_state.elev, clim, data, adv, roi, solar_kw, wind_kw, clim["nasa_data_used"]
            )
            st.download_button("⬇ Download PDF Report", data=pdf_data, file_name=f"enerlytics_{pincode}.pdf", mime="application/pdf")
            
            epw_str = generate_epw_string(data, st.session_state.lat, st.session_state.lon, st.session_state.elev, st.session_state.place_name, clim)
            st.download_button("⬇ Download EnergyPlus Weather (EPW)", data=epw_str, file_name=f"{pincode}.epw", mime="text/plain")

        with t7:
            st.header("🆚 Comparison Mode")
            st.write("Compare current location with another PIN code.")
            comp_pin = st.text_input("Enter second PIN code to compare", max_chars=6, key="comp_pin")
            
            if comp_pin and len(comp_pin) == 6:
                nomi = pgeocode.Nominatim('in')
                res2 = nomi.query_postal_code(comp_pin)
                if res2.latitude is not None and not np.isnan(res2.latitude):
                    with st.spinner(f"Fetching data for {res2.place_name}..."):
                        clim2 = fetch_nasa_power_climatology(res2.latitude, res2.longitude)
                        row2 = {"grid_id": "comp", "lat": res2.latitude, "lon": res2.longitude, "elevation": 200, **clim2}
                        data2 = generate_cell(row2)
                        data2['pv_power'] = simulate_pv_power(data2['ghi'], data2['temp'], capacity_kw=solar_kw)
                        
                        c1, c2, c3 = st.columns([1, 1, 0.5])
                        with c1:
                            st.metric(f"📍 {st.session_state.place_name}", f"{data['ghi'].mean()*24/1000:.2f} kWh/m²")
                        with c2:
                            st.metric(f"📍 {res2.place_name}", f"{data2['ghi'].mean()*24/1000:.2f} kWh/m²")
                        with c3:
                            diff = (data2['ghi'].mean() - data['ghi'].mean()) / data['ghi'].mean() * 100
                            st.metric("Delta", f"{diff:+.1f}%", delta_color="normal")
                        
                        # Comparison Chart
                        fig_comp = go.Figure()
                        fig_comp.add_trace(go.Bar(name=st.session_state.place_name, x=list(range(1,13)), y=compute_monthly_means(data['ghi'])))
                        fig_comp.add_trace(go.Bar(name=res2.place_name, x=list(range(1,13)), y=compute_monthly_means(data2['ghi'])))
                        fig_comp.update_layout(title="Monthly GHI Comparison (W/m²)", barmode='group')
                        st.plotly_chart(fig_comp, use_container_width=True)
                else:
                    st.error("Invalid second PIN code.")

        with t8:
            st.header("🗺️ Location Intelligence")
            st.write("Regional solar potential across India. High GHI regions are shown in amber/red.")
            
            # India-wide solar potential (reference cities)
            map_data = pd.DataFrame({
                'City': ['Delhi', 'Mumbai', 'Pune', 'Ahmedabad', 'Jodhpur', 'Bengaluru', 'Chennai', 'Kolkata', 'Guwahati', 'Leh', 
                         'Indore', 'Bhopal', 'Nagpur', 'Hyderabad', 'Kochi', 'Madurai', 'Vizag', 'Patna', 'Ranchi', 'Raipur', 
                         'Chandigarh', 'Amritsar', 'Dehradun', 'Srinagar', 'Shimla', 'Jaipur', 'Udaipur', 'Surat', 'Rajkot', 'Nashik'],
                'Lat': [28.6, 19.1, 18.5, 23.0, 26.3, 12.9, 13.0, 22.5, 26.1, 34.1, 
                        22.7, 23.2, 21.1, 17.4, 9.9, 9.9, 17.7, 25.6, 23.4, 21.2, 
                        30.7, 31.6, 30.3, 34.1, 31.1, 26.9, 24.6, 21.2, 22.3, 20.0],
                'Lon': [77.2, 72.8, 73.8, 72.6, 73.0, 77.6, 80.2, 88.3, 91.7, 77.5, 
                        75.9, 77.4, 79.1, 78.5, 76.3, 78.1, 83.3, 85.1, 85.3, 81.6, 
                        76.8, 74.9, 78.0, 74.8, 77.2, 75.8, 73.7, 72.8, 70.8, 73.8],
                'GHI_kWh': [5.2, 5.0, 5.1, 5.8, 6.2, 5.4, 5.5, 4.8, 4.2, 5.5, 
                            5.4, 5.3, 5.2, 5.4, 4.9, 5.6, 5.3, 4.9, 5.1, 5.2, 
                            5.0, 4.9, 4.7, 4.4, 4.5, 5.6, 5.7, 5.6, 5.8, 5.2]
            })
            
            # Add current location
            curr_loc = pd.DataFrame({
                'City': [st.session_state.place_name],
                'Lat': [st.session_state.lat],
                'Lon': [st.session_state.lon],
                'GHI_kWh': [data['ghi'].mean()*24/1000]
            })
            map_data = pd.concat([map_data, curr_loc], ignore_index=True)
            
            fig_map = px.scatter_mapbox(
                map_data, lat="Lat", lon="Lon", color="GHI_kWh", size="GHI_kWh",
                hover_name="City", hover_data=["GHI_kWh"],
                color_continuous_scale="YlOrRd", zoom=3.5, height=600,
                mapbox_style="carto-positron"
            )
            st.plotly_chart(fig_map, use_container_width=True)
            st.info("The map shows annual average GHI (kWh/m²/day). Jodhpur and Ahmedabad are among the highest potential regions in India.")

elif nav == "System Sizer":
    st.title("📏 Solar System Sizer")
    st.write("Enter your monthly bill or build your load from appliances — we calculate the exact system you need.")
    
    # Mode Toggle
    sizer_mode = st.radio("Sizing Mode", ["Quick Input", "Appliance Load Builder"], horizontal=True)
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Quick Input")
        if sizer_mode == "Quick Input":
            monthly_units = st.slider("Monthly units (kWh)", 50, 2000, 300)
        else:
            # Appliance Load Builder logic
            st.info("Build your load below. Monthly units will be calculated automatically.")
            
            # Default appliance profile
            if "appliances" not in st.session_state:
                st.session_state.appliances = [dict(a) for a in DEFAULT_APPLIANCES]
            
            # Edit Appliances
            for idx, app in enumerate(st.session_state.appliances):
                cols = st.columns([2, 1, 1, 0.5])
                with cols[0]:
                    st.write(f"**{app['name']}** ({app['watts']}W)")
                with cols[1]:
                    new_hrs = st.number_input(f"Hrs/Day", value=float(app['hours']), key=f"hrs_{idx}", min_value=0.0, max_value=24.0, step=0.5)
                    st.session_state.appliances[idx]['hours'] = new_hrs
                
                kwh_mo = (app['watts'] * new_hrs * 30) / 1000.0
                with cols[2]:
                    st.write(f"{kwh_mo:.1f} kWh/mo")
                with cols[3]:
                    if st.button("❌", key=f"del_{idx}"):
                        st.session_state.appliances.pop(idx)
                        st.rerun()
            
            # Add appliance
            with st.expander("➕ Add Appliance"):
                addon_names = [a["name"] for a in ADDON_APPLIANCES]
                new_app_name = st.selectbox("Select appliance", addon_names)
                if st.button("Add"):
                    new_app = next(a for a in ADDON_APPLIANCES if a["name"] == new_app_name)
                    st.session_state.appliances.append(dict(new_app))
                    st.rerun()
            
            load_data = compute_load(st.session_state.appliances)
            monthly_units = load_data["monthly_kwh"]
            st.success(f"Calculated Monthly Load: **{monthly_units:.1f} kWh**")

        sun_hours_key = st.selectbox("Location type", list(REGION_SUN_HOURS.keys()))
        sun_hours = REGION_SUN_HOURS[sun_hours_key]
        self_cons = st.slider("Self-consumption %", 50, 100, 80)
        sys_eff = st.slider("System efficiency %", 50, 100, 80)
        
    # Calculate sizing using sizer.py engine
    sizing = size_solar_system(
        monthly_kwh=monthly_units, 
        peak_sun_hours=sun_hours, 
        self_consumption_pct=self_cons, 
        system_efficiency_pct=sys_eff,
        state_name=st.session_state.state_name
    )
    
    with col2:
        st.subheader("Recommended system")
        k1, k2, k3 = st.columns(3)
        k1.metric("Solar panels", f"{sizing['solar_kw']} kW")
        k2.metric("Inverter", f"{sizing['inverter_kva']} kVA")
        k3.metric("Battery (opt.)", f"{sizing['battery_kwh']} kWh")
        
        k4, k5, k6 = st.columns(3)
        k4.metric("Panel count", f"{sizing['panels']} nos")
        k5.metric("Roof area", f"{sizing['roof_area_m2']} m²")
        k6.metric("Daily gen.", f"{sizing['daily_gen_kwh']} kWh")
        
        st.divider()
        st.subheader("Cost estimate (2025 India)")
        c1, c2 = st.columns(2)
        c1.metric("Gross CAPEX", f"₹{sizing['gross_capex_inr']/1e5:.2f} L")
        c2.metric("After subsidy", f"₹{sizing['net_capex_inr']/1e5:.2f} L")
        st.caption(sizing["subsidy_note"])
        
        c3, c4 = st.columns(2)
        c3.metric("Annual savings", f"₹{sizing['annual_savings_inr']/1e3:.1f} K/yr")
        c4.metric("Payback", f"{sizing['simple_payback_yr']} years")
        
        if st.button("🚀 Analyze this system in Explorer", use_container_width=True):
            st.session_state.solar_kw = sizing['solar_kw']
            st.session_state.nav = "Explorer"
            st.rerun()

    st.divider()
    st.subheader("💡 Energy Audit Mode")
    st.write("What's wasting your electricity? Estimate your load profile by category.")
    
    # Use sizer.py energy_audit engine
    audit_res = energy_audit(
        monthly_kwh=monthly_units,
        num_ac_units=1,
        num_bedrooms=2,
        has_geyser=True,
        has_ev=False,
        home_type="apartment",
        grid_tariff_inr=sizing["tariff_inr_kwh"]
    )
    
    audit_col1, audit_col2 = st.columns(2)
    with audit_col1:
        fig_audit = px.pie(
            names=list(audit_res["category_labels"].values()), 
            values=list(audit_res["breakdown_kwh"].values()), 
            title=f"Monthly Consumption Breakdown: {audit_res['energy_rating']}",
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        st.plotly_chart(fig_audit, use_container_width=True)
        
    with audit_col2:
        st.write("**Priority Efficiency Actions**")
        for action in audit_res["priority_actions"][:3]: # Show top 3
            with st.expander(f"📌 {action['action']}"):
                st.write(f"**Saving:** {action['saving']}")
                st.write(f"**Cost:** {action['cost']}")
                st.write(f"**Priority:** {action['priority']}")
        
        st.success(f"Total Efficiency Potential: **{audit_res['total_savings_potential_pct']}%** reduction possible.")

    st.divider()
    st.subheader("🆚 Energy Source Comparison")
    st.write("Compare solar vs wind vs hybrid options for your load.")
    
    # Assume default 3.5 m/s if no wind data yet
    comp_options = compare_energy_sources(
        monthly_kwh=monthly_units,
        peak_sun_hours=sun_hours,
        state_name=st.session_state.state_name
    )
    
    cols = st.columns(len(comp_options))
    for idx, opt in enumerate(comp_options):
        with cols[idx]:
            st.markdown(f"""
            <div style="padding:15px; border-radius:10px; border:2px solid {opt['color'] if opt['recommended'] else '#ddd'}; height:100%">
                <h4 style="margin-top:0">{opt['option']} {'✅' if opt['recommended'] else ''}</h4>
                <p><b>Capacity:</b> {opt['capacity']}</p>
                <p><b>Net Cost:</b> ₹{opt['net_capex_inr']/1e5:.2f} L</p>
                <p><b>Payback:</b> {opt['payback_yr']} yrs</p>
                <p style="font-size:0.8em; color:#666">{opt['note']}</p>
            </div>
            """, unsafe_allow_html=True)

    st.divider()
    st.subheader("What size means in practice")
    s1, s2, s3, s4 = st.columns(4)
    with s1:
        st.info(f"**{sizing['size_label']}**\n\n{sizing['solar_kw']} kW\n\n{sizing['use_case']}")
    with s2:
        st.info("**Medium home**\n\n3–6 kW\n\n300–600 kWh/mo - 3BHK\n\n+ 1 AC, washing machine")
    with s3:
        st.info("**Large home / villa**\n\n6–10 kW\n\n600–1000 kWh/mo\n\nbungalow - 2+ ACs, EV charging")
    with s4:
        st.info("**Commercial / factory**\n\n10–500 kW\n\n1000+ kWh/mo - C&I\n\nground-mount, 3-phase")

elif nav == "Financial Calculator":\   st.title("💰 Standalone Solar Financial Calculator")\n    \n    col1, col2 = st.columns(2)\n    with col1:\n        calc_cap = st.slider("System Capacity (kW)", 1, 100, 5)\n        calc_state = st.selectbox("Select State", list(DISCOM_TARIFFS.keys()))\n        state_info = get_state_tariff(calc_state)\n        calc_cost = st.number_input("Cost per kW (₹/kW)", value=55000)\n        calc_tariff = st.number_input("Tariff (₹/kWh)", value=state_info["tariff"], step=0.1)\n        calc_net_meter = st.number_input("Net Metering (₹/kWh)", value=state_info["net_meter"], step=0.1)\n        calc_subsidy_on = st.checkbox("Apply PM Surya Ghar Subsidy", value=True)\n        \n    with col2:\n        # Default insolation 5.0 kWh/m2/day = 1825 kWh/kWp/year\n        default_insolation = 5.0\n        # If we have run a simulation, use that insolation\n        if st.session_state.generated:\n            current_insolation = data['ghi'].mean() * 24 / 1000.0\n            st.info(f"Using actual simulated insolation: {current_insolation:.2f} kWh/m²/day")\n        else:\n            current_insolation = default_insolation\n            st.info(f"Using default India insolation: {current_insolation:.2f} kWh/m²/day")\n            \n        annual_yield_kwh = calc_cap * current_insolation * 365\n        calc_subsidy = pm_surya_ghar_subsidy(calc_cap)["subsidy_inr"] if calc_subsidy_on else 0\n        \n        if st.button("Calculate Financials", use_container_width=True, type="primary"):\n            calc_roi = calculate_roi(annual_yield_kwh, calc_cap, calc_cost, calc_tariff, calc_net_meter, calc_subsidy)\n            \n            k1, k2, k3 = st.columns(3)\n            k1.metric("Payback Period", f"{calc_roi['simple_payback_yr']:.1f} Yrs")\n            k2.metric("25yr NPV", f"₹{calc_roi['npv_25yr_inr']/1e5:.2f} L")\n            k3.metric("IRR", f"{calc_roi['irr_pct']:.1f}%")\n            \n            st.success(f"Estimated Annual Savings: ₹{calc_roi['annual_savings_inr_yr1']:,.0f}")\n            st.write(f"Net Investment after Subsidy: ₹{calc_roi['net_capex_inr']:,.0f}")\n\nelif nav == "Products":\n    st.title("🛒 Products")\n    \n    col1, col2 = st.columns([1, 2])\n    \n    with col1:\n        st.markdown("## Coming Soon!")\n        st.markdown("""\n        **ENERLYTICS Premium Products:**\n        \n        - 🔋 **Smart Energy Monitors**\n        - ☀️ **Pre-engineered Solar Kits**\n        - 📱 **Mobile App Integration**\n        - 💼 **Enterprise Energy Audit**\n        \n        *Sign up for early access!*\n        """)\n        \n        st.info("👈 Enter your email to get notified")\n        email = st.text_input("Email")\n        if st.button("Notify Me", use_container_width=True):\n            st.success("Thanks! You'll be first to know.")\n            \n    with col2:\n        st.image("https://via.placeholder.com/600x400/f59e0b/ffffff?text=ENERLYTICS+Products+Coming+Soon", use_column_width=True)\n        st.caption("Visualisation of upcoming hardware + software integrations")

elif nav == "About":
    st.title("📖 About ENERLYTICS")
    
    tab_info, tab_calc, tab_guide, tab_dev = st.tabs([
        "🚀 Project Overview", 
        "🧪 Scientific Calculations", 
        "📖 User Guide", 
        "👤 About the Developer"
    ])
    
    with tab_info:
        st.markdown("""
        **ENERLYTICS** is a professional-grade solar and wind energy advisory platform specifically engineered for the Indian market.
        
        ### 🚀 Advanced Features
        - **System Sizer**: Interactive calculator with **Quick Input** and **Appliance Load Builder** modes.
        - **Comparison Mode**: Side-by-side analysis of two different PIN codes.
        - **Bill Estimator**: Real-time post-solar electricity bill forecasting.
        - **Seasonal Planner**: Intelligent maintenance scheduling based on monsoon cycles.
        """)
        
    with tab_calc:
        st.subheader("Scientific Methodology")
        
        with st.expander("☀️ Solar Irradiance Modeling"):
            st.markdown(r"""
            - **Synthesis**: We use a stochastic **AR(1)** (Autoregressive Integrated Moving Average) process to synthesize hourly GHI from monthly NASA means, maintaining realistic daily variance.
            - **Separation**: The **Reindl Model** (a 3-interval piecewise function) is used to split Global Horizontal Irradiance (GHI) into Direct Normal (DNI) and Diffuse Horizontal (DHI) components based on the clearness index ($K_t$).
            - **Transposition**: The **Perez 1990 Anisotropic Sky Model** is our primary engine for calculating Plane of Array (POA) irradiance. It accounts for:
                - **Circumsolar brightening** (the bright area around the solar disk).
                - **Horizon brightening** (brightening near the horizon in clear skies).
                - This model is 5-15% more accurate than standard isotropic models for tropical climates like India.
            """)
            
        with st.expander("💨 Wind Resource Assessment"):
            st.markdown(r"""
            - **Weibull Distribution**: We fit the hourly wind speed series to a Weibull probability density function to determine the **k (shape)** and **c (scale)** parameters, which are critical for turbine selection.
            - **Hellmann Power Law**: To evaluate potential at different hub heights (30m to 100m), we use the Hellmann exponent ($\alpha$):
                $$v_h = v_{ref} \cdot (h / h_{ref})^\alpha$$
                Default exponents are adjusted based on terrain (e.g., 0.143 for open flat, 0.25 for suburban).
            """)
            
        with st.expander("💰 Financial Engineering"):
            st.markdown("""
            - **LCOE (Levelized Cost of Energy)**: Calculated by discounting all lifetime costs (CAPEX + OPEX) and dividing by the total discounted energy generated over 25 years.
            - **IRR (Internal Rate of Return)**: Computed using the Newton-Raphson method on the project's net cash flows, accounting for 0.5% annual degradation and 3% tariff escalation.
            - **Subsidy Logic**: Directly implements the FY2024-25 MNRE slabs:
                - 1 kW: ₹30,000
                - 2 kW: ₹60,000
                - 3 kW+: Capped at ₹78,000
            """)

    with tab_guide:
        st.subheader("How to Use ENERLYTICS")
        st.markdown("""
        1. **Location**: Enter your 6-digit Indian PIN code in the sidebar. The system will auto-snap to the nearest 0.25° grid point.
        2. **System Design**: Input your planned Solar and Wind capacity. Toggle the **Perez Model** for higher accuracy.
        3. **Financials**: Open the 'Financial Inputs' expander to adjust grid tariffs and net-metering rates based on your specific DISCOM (defaults are auto-filled by state).
        4. **Analyze**: Click **Generate Synthetic Year + Analyse**.
        5. **Review Tabs**:
            - **Annual Summary**: High-level yields and heatmaps.
            - **Monthly Breakdown**: Seasonal variation tables.
            - **Installation Advisory**: Optimal tilt angles and row spacing.
            - **Financial Analysis**: Payback periods and cash-flow charts.
            - **Data Quality**: Statistical validation against NASA benchmarks.
            - **Comparison Mode**: Side-by-side analysis of two different PIN codes.
            - **Location Intelligence**: Interactive India-wide GHI potential map.
        6. **Export**: Go to the **Export** tab to download a professional **PDF Report** or an **EPW File** for architectural software.
        """)

    with tab_dev:
        col1, col2 = st.columns([1, 3])
        with col1:
            st.image("https://img.icons8.com/clouds/200/user.png") # Placeholder or author image
        with col2:
            st.header("Himanshu Kumar Sahu")
            st.markdown("""
            Passionate about bridging the gap between high-fidelity climate science and practical energy solutions for the Indian subcontinent.
            
            - **Expertise**: Python, NumPy, Streamlit, Renewable Energy Physics.
            - **Mission**: To democratize bankable energy data for every rooftop in India.
            
            [<img src="https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white" alt="LinkedIn"/>](http://www.linkedin.com/in/himansu-kumar-sahu-377916334)
            [<img src="https://img.shields.io/badge/GitHub-100000?style=for-the-badge&logo=github&logoColor=white" alt="GitHub"/>](https://github.com/himansu1211)
            [<img src="https://img.shields.io/badge/Gmail-D14836?style=for-the-badge&logo=gmail&logoColor=white" alt="Email"/>](mailto:himansuk1211@gmail.com)
            """, unsafe_allow_html=True)

def main():
    """Streamlit entry point."""
    import sys
    import os
    from streamlit.web import cli as stcli
    
    # Path to this file
    this_file = os.path.abspath(__file__)
    sys.argv = ["streamlit", "run", this_file]
    sys.exit(stcli.main())

if __name__ == "__main__":
    main()
