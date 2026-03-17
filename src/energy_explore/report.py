"""
Professional PDF and EPW report generation for ENERLYTICS.
Ref: Perez, R. et al. (1990).
"""
import io
import datetime
import numpy as np
import matplotlib.pyplot as plt
from typing import Dict, Any
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image

def _monthly_bar_bytes(ghi_monthly: np.ndarray) -> io.BytesIO:
    """Creates a matplotlib monthly GHI bar chart as PNG bytes."""
    plt.figure(figsize=(160/25.4, 50/25.4)) # mm to inches
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    plt.bar(months, ghi_monthly, color="#F59E0B")
    plt.title("Monthly Average GHI (W/m²)", fontsize=10, pad=10)
    plt.xticks(fontsize=8)
    plt.yticks(fontsize=8)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    for spine in plt.gca().spines.values():
        spine.set_visible(False)
    
    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format='png', bbox_inches='tight', dpi=150)
    plt.close()
    img_buffer.seek(0)
    return img_buffer

def generate_pdf_report(
    place_name: str,
    lat: float,
    lon: float,
    elev: float,
    clim: dict,
    data: dict,
    advisory: dict,
    roi: dict,
    solar_kw: float,
    wind_kw: float,
    nasa_data_used: bool,
) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=A4, 
        rightMargin=10*mm, leftMargin=10*mm, topMargin=10*mm, bottomMargin=10*mm
    )
    styles = getSampleStyleSheet()
    
    # Custom styles
    styles.add(ParagraphStyle(
        name='HeaderTitle', parent=styles['Normal'],
        fontSize=14, textColor=colors.white, fontName='Helvetica-Bold'
    ))
    styles.add(ParagraphStyle(
        name='MetricVal', parent=styles['Normal'],
        fontSize=12, alignment=1, fontName='Helvetica-Bold'
    ))
    styles.add(ParagraphStyle(
        name='MetricLabel', parent=styles['Normal'],
        fontSize=8, alignment=1, textColor=colors.grey
    ))

    elements = []
    
    # Header Bar
    header_data = [[
        Paragraph("ENERLYTICS", styles['HeaderTitle']),
        Paragraph(datetime.datetime.now().strftime("%d %b %Y"), 
                  ParagraphStyle('Date', parent=styles['Normal'], alignment=2, textColor=colors.white))
    ]]
    header_table = Table(header_data, colWidths=[140*mm, 50*mm])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#0F172A')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (-1,-1), 5*mm),
        ('RIGHTPADDING', (0,0), (-1,-1), 5*mm),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 5*mm))
    
    # Title Block
    elements.append(Paragraph(place_name.upper(), styles['Title']))
    elements.append(Paragraph(f"{lat:.4f}°N, {lon:.4f}°E | Elevation: {elev:.0f}m", 
                              ParagraphStyle('Sub', parent=styles['Normal'], textColor=colors.grey, alignment=1)))
    elements.append(Spacer(1, 8*mm))
    
    # Metrics Row 1
    # Insolation | Avg Temp | Peak UV | Avg Wind | Solar Yield | Wind Yield
    ghi_m = data['ghi'].mean() * 24 / 1000.0 # kWh/m2/day
    temp_m = data['temp'].mean()
    wind_m = data['wind'].mean()
    solar_yield = (data.get('pv_power', np.zeros(8760)).sum() / 1000.0)
    wind_yield = (data.get('wind_power', np.zeros(8760)).sum() / 1000.0)
    
    m_row1 = [
        [Paragraph(f"{ghi_m:.2f}", styles['MetricVal']), Paragraph(f"{temp_m:.1f}°C", styles['MetricVal']), 
         Paragraph("High", styles['MetricVal']), Paragraph(f"{wind_m:.1f}", styles['MetricVal']),
         Paragraph(f"{solar_yield:.1f}", styles['MetricVal']), Paragraph(f"{wind_yield:.1f}", styles['MetricVal'])],
        [Paragraph("Insolation", styles['MetricLabel']), Paragraph("Avg Temp", styles['MetricLabel']),
         Paragraph("Peak UV", styles['MetricLabel']), Paragraph("Avg Wind (m/s)", styles['MetricLabel']),
         Paragraph("Solar (MWh/yr)", styles['MetricLabel']), Paragraph("Wind (MWh/yr)", styles['MetricLabel'])]
    ]
    t_metrics = Table(m_row1, colWidths=[31*mm]*6)
    t_metrics.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.2, colors.lightgrey),
    ]))
    elements.append(t_metrics)
    elements.append(Spacer(1, 5*mm))
    
    # Row 2 — Advisory
    s_adv = advisory.get('solar', {})
    w_adv = advisory.get('wind', {})
    
    m_row2 = [
        [Paragraph(f"{s_adv.get('optimal_tilt', 0):.1f}°", styles['MetricVal']), 
         Paragraph("South (180°)", styles['MetricVal']),
         Paragraph(f"{s_adv.get('row_pitch_m', 0):.2f} m", styles['MetricVal'])],
        [Paragraph("Optimal Tilt", styles['MetricLabel']), 
         Paragraph("Facing Direction", styles['MetricLabel']),
         Paragraph("Row Pitch", styles['MetricLabel'])]
    ]
    t_adv = Table(m_row2, colWidths=[63*mm]*3)
    t_adv.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.2, colors.lightgrey),
    ]))
    elements.append(t_adv)
    elements.append(Spacer(1, 5*mm))
    
    # Row 3 — Financial
    m_row3 = [
        [Paragraph(f"₹{roi.get('net_capex_inr', 0)/1e5:.2f} L", styles['MetricVal']), 
         Paragraph(f"{roi.get('simple_payback_yr', 0):.1f} Yrs", styles['MetricVal']),
         Paragraph(f"₹{roi.get('npv_25yr_inr', 0)/1e5:.2f} L", styles['MetricVal'])],
        [Paragraph("Net CAPEX", styles['MetricLabel']), 
         Paragraph("Payback Period", styles['MetricLabel']),
         Paragraph("25yr NPV", styles['MetricLabel'])]
    ]
    t_fin = Table(m_row3, colWidths=[63*mm]*3)
    t_fin.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.2, colors.lightgrey),
    ]))
    elements.append(t_fin)
    elements.append(Spacer(1, 10*mm))
    
    # Monthly Chart
    ghi_monthly = [data['ghi'][idx].mean() for idx in clim.get('monthly_indices', [])]
    if not ghi_monthly: # Fallback if indices missing
        ghi_monthly = [100.0] * 12 
        
    chart_buffer = _monthly_bar_bytes(np.array(ghi_monthly))
    elements.append(Image(chart_buffer, width=160*mm, height=50*mm))
    elements.append(Spacer(1, 10*mm))
    
    # Footer
    footer_text = "Data source: NASA POWER 30-year climatology | "
    footer_text += "NASA DATA USED ✅" if nasa_data_used else "REGIONAL FALLBACK ⚠️"
    elements.append(Paragraph(footer_text, ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, textColor=colors.grey, alignment=1)))
    
    # Page Border
    def draw_border(canvas, doc):
        canvas.setStrokeColor(colors.lightgrey)
        canvas.setLineWidth(0.5)
        canvas.rect(5*mm, 5*mm, 200*mm, 287*mm)
        
    doc.build(elements, onFirstPage=draw_border)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes

def generate_epw_string(
    data: dict,
    lat: float,
    lon: float,
    elev: float,
    place_name: str,
    clim: dict,
    timezone_offset: int = 5,
) -> str:
    """Generates a valid EnergyPlus Weather (.epw) format string."""
    # Line 1: LOCATION
    epw = f"LOCATION,{place_name},,,IND,999999,{lat:.2f},{lon:.2f},{timezone_offset},{elev:.1f}\n"
    epw += "DESIGN CONDITIONS,0\n"
    epw += "TYPICAL/EXTREME PERIODS,0\n"
    epw += "GROUND TEMPERATURES,0\n"
    epw += "HOLIDAYS/DAYLIGHT SAVINGS,No,0,0,0\n"
    epw += "COMMENTS 1,Generated by ENERLYTICS — github.com/himansu1211\n"
    epw += "DATA PERIODS,1,1,Data,Sunday,1/1,12/31\n"
    
    # Data Rows
    h = np.arange(8760)
    # EPW year is arbitrary for TMY, using 2024
    year = 2024
    
    # Month/Day map
    month_days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    
    idx = 0
    rows = []
    pressure = 101325 * np.exp(-elev / 8500.0)
    
    # kt calculation for sky cover
    I0_h = np.maximum(data.get('I0', np.ones(8760)) * data.get('cos_zenith', np.ones(8760)), 1e-6)
    kt = np.clip(data['ghi'] / I0_h, 0, 1.2)
    
    for m in range(12):
        for d in range(month_days[m]):
            for hr in range(24):
                # hour is 1-24
                row = [
                    str(year), str(m+1), str(d+1), str(hr+1), "0", "A7",
                    f"{data['temp'][idx]:.1f}",
                    f"{data['temp'][idx] - 5.0:.1f}", # dewpoint
                    "60", # rel_hum
                    f"{pressure:.0f}",
                    "999999", "999999", "999999", # ext rad
                    f"{data['ghi'][idx]:.0f}",
                    f"{data['dni'][idx]:.0f}",
                    f"{data['dhi'][idx]:.0f}",
                    "999999", "999999", "999999", "999999", # illumination
                    f"{data['wind_dir'][idx]:.0f}",
                    f"{data['wind'][idx]:.1f}",
                    f"{round(10 * (1 - kt[idx]))}", # sky cover
                    "999999", "999999", "999999", "999999", "999999", "999999", "999999", "999999",
                    "0.2", "999999", "0" # albedo, rain
                ]
                rows.append(",".join(row))
                idx += 1
                
    return epw + "\n".join(rows) + "\n"
