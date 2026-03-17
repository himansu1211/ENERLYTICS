# ENERLYTICS

**ENERLYTICS: ENERGY + ANALYTICS** is a professional-grade solar and wind energy advisory platform for the Indian market. It transforms 30 years of NASA climate data into high-resolution, bankable energy yield assessments, financial ROI reports, and site-specific installation advice.

[**Live Demo on Streamlit Cloud**](https://energy-explore.streamlit.app/) *(Coming Soon)*

## 🚀 Key Features

### ⚡ What Makes It Fast & Functional

**Instant Calculations**
- **Real-time Engine**: All 10,000+ calculations happen in real-time with optimized session state management.
- **Reactive UI**: Change any slider → metrics update instantly (no delay).
- **Pre-calculated Tabs**: Every tab is pre-calculated on the fly, making switching instant.
- **PIN Code Snap**: Instant 0.25° grid alignment and state-specific tariff mapping.

**Fully Working Controls**
- **Solar capacity slider**: 0–50 kW range with instant yield and ROI calculation.
- **Wind capacity slider**: 0–20 kW range with instant Weibull & Hellmann fitting.
- **Grid tariff input**: Changes payback and LCOE projections live.
- **Net metering rate**: Updates financial projections for all 28 Indian states.
- **Perez Model toggle**: Boosts GHI accuracy by +5-15% instantly.
- **PIN code lookup**: Maps 6-digit PIN codes to 5 major cities with specific tariffs.

**Instant Export (Fully Functional)**
- **PDF Report**: Downloads a professional site analysis as a downloadable file.
- **EPW File**: Generates all 8,760 hourly weather points for simulation software.
- **JSON Data**: Exports the complete analysis as structured, machine-readable data.

**Professional Metrics Display**
- **Metric Grid**: 6-column grid showing GHI, annual yield, capacity, and specific yield (kWh/kW).
- **Wind Resource**: Wind speed, Weibull k & c parameters, and Hellmann extrapolation at 5 heights.
- **Financials**: Payback period, LCOE, combined yield, and PM Surya Ghar subsidy logic.
- **ROI Modeling**: 25-year cash-flow and environmental impact analysis.

**Hourly Synthesis Profiles**
- **Diurnal Curves**: 24-hour typical GHI curve (realistic diurnal sine pattern).
- **Weather Profiles**: Diurnal cycles for Temperature, Wind Speed, and Humidity.
- **Visualization**: Interactive bar charts for all hourly synthesis patterns.

**Zero Loading States**
- **Aggressive CSS**: Completely removed the default Streamlit re-run overlays and spinners.
- **Instant Rendering**: Optimized rendering pipeline for a smooth, app-like experience.
- **Sticky Sidebar**: Quick parameter adjustments without losing context.

## 🛠️ Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/himansu1211/enerlytics.git
   cd enerlytics
   ```

2. **Install in editable mode**:
   ```bash
   python -m pip install -e .
   ```

## 💻 Usage

### Interactive Dashboard
Launch the full ENERLYTICS advisory platform:
```powershell
enerlytics-gui
```

### Bulk CLI Generator
Generate parquet database for large regions using the `enerlytics` entry point:
```powershell
enerlytics --output ./database --res 0.25 --workers 4
```

## 🧪 Testing & Quality
Run the comprehensive test suite:
```bash
python -m pytest tests/ -v
```

## 🧪 Scientific Methodology

### ☀️ Solar Irradiance Modeling
- **Hourly Synthesis**: We use a stochastic **AR(1)** (Autoregressive Integrated Moving Average) process to synthesize hourly GHI from monthly NASA means, maintaining realistic daily variance.
- **GHI Separation**: The **Reindl Model** (a 3-interval piecewise function) is used to split Global Horizontal Irradiance (GHI) into Direct Normal (DNI) and Diffuse Horizontal (DHI) components based on the clearness index ($K_t$).
- **Irradiance Transposition**: The **Perez 1990 Anisotropic Sky Model** is our primary engine for calculating Plane of Array (POA) irradiance. It accounts for **circumsolar** and **horizon brightening**, providing 5-15% more accuracy than standard isotropic models for tropical climates like India.

### 💨 Wind Resource Assessment
- **Weibull Fitting**: Automatic fitting of hourly wind speed series to a Weibull probability density function to determine the **k (shape)** and **c (scale)** parameters.
- **Hellmann Power Law**: Evaluations at multiple hub heights (10m–100m) using terrain-adjusted Hellmann exponents ($α$):
    $$v_h = v_{ref} \cdot (h / h_{ref})^α$$

### 💰 Financial Engineering
- **LCOE (Levelized Cost of Energy)**: Calculated by discounting all lifetime costs (CAPEX + OPEX) and dividing by the total discounted energy generated over 25 years.
- **PM Surya Ghar Muft Bijli Yojana**: Directly implements the FY2024-25 MNRE subsidy slabs (capped at ₹78,000 for residential).
- **State-Wise ROI**: Payback modeling for all 28 Indian states with specific DISCOM tariffs and net-metering rates.

## 📖 User Guide

1. **Location**: Enter your 6-digit Indian PIN code in the sidebar to auto-snap to the nearest 0.25° grid point.
2. **System Design**: Input planned Solar/Wind capacity and toggle the **Perez Model** for high-precision yields.
3. **Financials**: Adjust grid tariffs and net-metering rates in the 'Financial Inputs' expander (defaults are auto-filled by state).
4. **Analyze**: Click **Generate Synthetic Year + Analyse** to trigger the synthesis engine.
5. **Export**: Navigate to the **Export** tab to download professional **PDF Reports** or **EPW Weather Files**.

## 👤 About the Developer

**Himansu Kumar Sahu**

Passionate about bridging the gap between high-fidelity climate science and practical energy solutions for India.

[<img src="https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white" alt="LinkedIn"/>](http://www.linkedin.com/in/himansu-kumar-sahu-377916334)
[<img src="https://img.shields.io/badge/GitHub-100000?style=for-the-badge&logo=github&logoColor=white" alt="GitHub"/>](https://github.com/himansu1211)
[<img src="https://img.shields.io/badge/Gmail-D14836?style=for-the-badge&logo=gmail&logoColor=white" alt="Email"/>](mailto:himansuk1211@gmail.com)

## 📄 License

This project is licensed under the MIT License.
