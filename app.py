import io
import sys
import logging
import traceback
from datetime import datetime

import streamlit as st
import pandas as pd
import numpy as np

import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import matplotlib.pyplot as plt

# ReportLab Core Imports
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image as RLImage,
    KeepTogether,
    PageBreak,
    HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY

# --- LOGGING CONFIGURATION ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("OperationsAuditApp")

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Operations Audit: HR, Admin, Logistics, PO & Purchase Pending Plates",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- GLOBAL STYLES & CONSTANTS ---
THEME_HEADER_COLOR = "#1F4E78"
THEME_ACCENT_COLOR = "#00CC96"
THEME_WARN_COLOR = "#E74C3C"
THEME_BG_LIGHT = "#F8F9F9"

st.markdown(
    """
    <style>
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    .stMetric {
        background-color: #f8f9fa;
        padding: 10px;
        border-radius: 5px;
        border: 1px solid #e9ecef;
    }
    .metric-card-title {
        font-size: 0.85rem;
        color: #6c757d;
        font-weight: 600;
    }
    .metric-card-value {
        font-size: 1.4rem;
        color: #212529;
        font-weight: bold;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("🚚 AUDIT & OPERATIONS DASHBOARD")
st.caption("Upload daily Excel files to generate single-day reports, track pending plates, or run side-by-side date comparisons.")

# --- UTILITY & CLEANING FUNCTIONS ---

def clean_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Strips whitespace from column names and normalizes string headers."""
    if df is None or df.empty:
        return pd.DataFrame()
    df_copy = df.copy()
    df_copy.columns = [str(col).strip() for col in df_copy.columns]
    return df_copy

def parse_slash_separated_qty(val) -> float:
    """Parses numeric fields that may contain slash-separated entries (e.g., '10/20/30')."""
    if pd.isna(val) or val is None:
        return 0.0
    val_str = str(val).strip()
    if '/' in val_str:
        parts = val_str.split('/')
        total = 0.0
        for p in parts:
            p_clean = p.strip().replace(",", "")
            try:
                total += float(p_clean)
            except ValueError:
                pass
        return total
    else:
        try:
            return float(val_str.replace(",", ""))
        except ValueError:
            return 0.0

def parse_numeric_clean(val) -> float:
    """Cleans numeric input strings by removing currency symbols, commas, or extra text."""
    if pd.isna(val) or val is None:
        return 0.0
    val_str = str(val).replace("₹", "").replace(",", "").strip()
    try:
        return float(val_str)
    except ValueError:
        return 0.0

def parse_loading_time(val) -> float:
    """Normalizes loading time values including special string conditions like 'OTO'."""
    if pd.isna(val) or val is None:
        return 0.0
    val_str = str(val).upper().replace("HRS", "").replace("MIN.", "").strip()
    if val_str == "OTO":
        return 0.0
    if "OTO/" in val_str:
        val_str = val_str.split("OTO/")[1].strip()
    if '/' in val_str:
        parts = val_str.split('/')
        total = 0.0
        for p in parts:
            try:
                total += float(p.strip())
            except ValueError:
                pass
        return total
    else:
        try:
            return float(val_str)
        except ValueError:
            return 0.0

def safe_get_column(df: pd.DataFrame, keywords: list) -> str:
    """Searches a dataframe for a column matching any of the provided keywords."""
    if df is None or df.empty:
        return None
    for kw in keywords:
        for col in df.columns:
            if kw.upper() in col.upper():
                return col
    return None

# --- PENDING PLATES DATA COMPUTATIONS ---

def process_pending_plates_df(df: pd.DataFrame) -> pd.DataFrame:
    """Pre-processes Purchase Pending Plates dataframe with clean numeric columns."""
    if df is None or df.empty:
        return pd.DataFrame()
        
    df_clean = df.copy()
    
    col_po_qty = safe_get_column(df_clean, ["PO QTY", "PO_QTY", "QTY (MT)", "PO QTY (MT)"])
    col_recd = safe_get_column(df_clean, ["RECD.QTY", "RECD QTY", "RECEIVED", "RECD"])
    col_pend = safe_get_column(df_clean, ["PENDING", "PENDING QTY", "PEND QTY"])
    
    df_clean["CLEAN_PO_QTY"] = df_clean[col_po_qty].apply(parse_slash_separated_qty) if col_po_qty else 0.0
    df_clean["CLEAN_RECD_QTY"] = df_clean[col_recd].apply(parse_slash_separated_qty) if col_recd else 0.0
    df_clean["CLEAN_PENDING"] = df_clean[col_pend].apply(parse_slash_separated_qty) if col_pend else 0.0
    
    return df_clean

def get_grouped_pending_summary(df: pd.DataFrame, group_col_keyword: str) -> pd.DataFrame:
    """Generates grouped summaries for PO QTY, RECD QTY, and PENDING based on target column keyword."""
    df_clean = process_pending_plates_df(df)
    if df_clean.empty:
        return pd.DataFrame()

    target_col = safe_get_column(df_clean, [group_col_keyword])
    
    if target_col:
        grp = df_clean.groupby(target_col, as_index=False)[["CLEAN_PO_QTY", "CLEAN_RECD_QTY", "CLEAN_PENDING"]].sum()
        grp.columns = [target_col, "PO QTY (MT)", "RECD QTY", "PENDING"]
        grp = grp.sort_values(by="PENDING", ascending=False).reset_index(drop=True)
        return grp
    return pd.DataFrame()

# --- LOGISTICS KPI CALCULATIONS ---

def calculate_logistics_kpis(df: pd.DataFrame) -> dict:
    """Computes comprehensive logistics metrics and indicators."""
    kpis = {
        "Unique Vehicles Count": 0,
        "Unique Transports Count": 0,
        "Unique Parties Count": 0,
        "Unique Invoices Count": 0,
        "Total Quantity (MT)": 0.0,
        "Total Freight (₹)": 0.0,
        "Total Loading Time (Hrs)": 0.0,
        "Average Loading Time / Vehicle (Hrs)": 0.0
    }
    if df is None or df.empty:
        return kpis

    df_work = df.copy()
    
    col_qty = safe_get_column(df_work, ["QTY", "QUANTITY", "MT"])
    if col_qty:
        df_work["QTY_NUM"] = df_work[col_qty].apply(parse_slash_separated_qty)
    else:
        df_work["QTY_NUM"] = 0.0

    col_veh = safe_get_column(df_work, ["VEHICLE NO.", "VEHICLE", "TRUCK NO"])
    if col_veh:
        kpis["Unique Vehicles Count"] = int(df_work[col_veh].dropna().nunique())

    col_trans = safe_get_column(df_work, ["TRANSPORT", "TRANSPORTER"])
    if col_trans:
        kpis["Unique Transports Count"] = int(df_work[col_trans].dropna().nunique())

    col_party = safe_get_column(df_work, ["PARTY NAME (CUSTOMER)", "PARTY NAME", "CUSTOMER"])
    if col_party:
        kpis["Unique Parties Count"] = int(df_work[col_party].dropna().nunique())

    col_inv = safe_get_column(df_work, ["INVOICE NO.", "INVOICE", "INV NO"])
    if col_inv:
        raw_invoices = df_work[col_inv].dropna().astype(str).tolist()
        split_invoices = set()
        for inv in raw_invoices:
            parts = [p.strip() for p in inv.split('/') if p.strip()]
            split_invoices.update(parts)
        kpis["Unique Invoices Count"] = len(split_invoices)

    kpis["Total Quantity (MT)"] = float(df_work["QTY_NUM"].sum())

    col_freight = safe_get_column(df_work, ["FREIGHT (IF)", "FREIGHT", "AMNT"])
    if col_freight:
        total_freight = 0.0
        for _, row in df_work.iterrows():
            freight_str = str(row[col_freight]).upper().strip()
            qty = float(row.get("QTY_NUM", 0.0))
            if freight_str in ["NAN", "NONE", "-", ""]:
                continue
            elif "PMT" in freight_str:
                clean_num = ''.join(c for c in freight_str.replace("PMT", "").replace("/", "") if c.isdigit() or c == '.')
                try:
                    total_freight += float(clean_num) * qty
                except ValueError:
                    pass
            else:
                try:
                    total_freight += float(freight_str)
                except ValueError:
                    pass
        kpis["Total Freight (₹)"] = total_freight

    col_load = safe_get_column(df_work, ["LOADING TIME", "LOADING", "TIME"])
    if col_load:
        df_work["LOADING_NUM"] = df_work[col_load].apply(parse_loading_time)
        total_loading = float(df_work["LOADING_NUM"].sum())
        kpis["Total Loading Time (Hrs)"] = total_loading
        veh_count = kpis.get("Unique Vehicles Count", 0)
        kpis["Average Loading Time / Vehicle (Hrs)"] = total_loading / veh_count if veh_count > 0 else 0.0

    return kpis

# --- PURCHASE ORDER KPI CALCULATIONS ---

def calculate_po_kpis(df: pd.DataFrame) -> dict:
    """Computes key metrics for Purchase Order operations."""
    kpis = {
        "Unique PO Count": 0,
        "Unique Party Name Count": 0,
        "Unique Description Count": 0,
        "Unique Size Count": 0,
        "Unique Grade Count": 0,
        "Sum of Qty (MT)": 0.0,
        "Sum of Purchase Rate (₹)": 0.0,
        "Average Purchase Rate (₹)": 0.0
    }
    if df is None or df.empty:
        return kpis

    df_work = df.copy()

    col_qty = safe_get_column(df_work, ["PO QTY", "QTY", "QUANTITY"])
    df_work["PO_QTY_NUM"] = df_work[col_qty].apply(parse_slash_separated_qty) if col_qty else 0.0

    col_rate = safe_get_column(df_work, ["RATE", "PURCHASE RATE", "PRICE"])
    df_work["PO_RATE_NUM"] = df_work[col_rate].apply(parse_numeric_clean) if col_rate else 0.0

    col_po = safe_get_column(df_work, ["PO NO", "PO NO.", "PO", "ORDER NO"])
    if col_po:
        kpis["Unique PO Count"] = int(df_work[col_po].dropna().nunique())

    col_party = safe_get_column(df_work, ["PARTY NAME", "PARTY", "VENDOR"])
    if col_party:
        kpis["Unique Party Name Count"] = int(df_work[col_party].dropna().nunique())

    col_desc = safe_get_column(df_work, ["DISCRIPTION", "DESCRIPTION", "ITEM"])
    if col_desc:
        kpis["Unique Description Count"] = int(df_work[col_desc].dropna().nunique())

    col_size = safe_get_column(df_work, ["SIZE (MM)", "SIZE", "DIMENSION"])
    if col_size:
        kpis["Unique Size Count"] = int(df_work[col_size].dropna().nunique())

    col_grade = safe_get_column(df_work, ["GRADE", "SPECIFICATION"])
    if col_grade:
        kpis["Unique Grade Count"] = int(df_work[col_grade].dropna().nunique())

    kpis["Sum of Qty (MT)"] = float(df_work["PO_QTY_NUM"].sum())
    kpis["Sum of Purchase Rate (₹)"] = float(df_work["PO_RATE_NUM"].sum())
    kpis["Average Purchase Rate (₹)"] = float(df_work["PO_RATE_NUM"].mean()) if len(df_work["PO_RATE_NUM"]) > 0 else 0.0

    return kpis

def display_kpis_safely(kpis: dict):
    """Renders structured KPI metric cards inside Streamlit layout."""
    if not kpis:
        st.info("No KPI data available to display.")
        return
        
    max_cols_per_row = 4
    kpi_items = list(kpis.items())
    for i in range(0, len(kpi_items), max_cols_per_row):
        batch = kpi_items[i:i + max_cols_per_row]
        cols = st.columns(len(batch))
        for idx, (k, v) in enumerate(batch):
            val_str = f"{v:,.2f}" if isinstance(v, float) else str(v)
            cols[idx].metric(label=k, value=val_str)

# --- MATPLOTLIB CHART GENERATOR FOR PDF EMBEDDING ---

def generate_pdf_chart_bytes(df_log=None, df_po=None, df_comp=None, df_comp_po=None, df_ppp=None) -> list:
    """Generates high-resolution Matplotlib chart figures converted to PNG byte arrays for PDF embedding."""
    chart_bytes_list = []

    # 1. Logistics Comparison Chart
    if df_comp is not None and not df_comp.empty:
        try:
            fig_c, ax_c = plt.subplots(figsize=(8, 3.8))
            metrics = df_comp['Metric Name'].tolist()
            x = np.arange(len(metrics))
            width = 0.35
            bars1 = ax_c.bar(x - width/2, df_comp['Yesterday'], width, label='Yesterday', color='#8E44AD')
            bars2 = ax_c.bar(x + width/2, df_comp['Today'], width, label='Today', color='#2ECC71')
            ax_c.bar_label(bars1, fmt='%.2f', padding=2, fontsize=5)
            ax_c.bar_label(bars2, fmt='%.2f', padding=2, fontsize=5)
            ax_c.set_title("Logistics KPI Comparison Variance", fontsize=9, fontweight='bold', pad=10)
            ax_c.set_xticks(x)
            ax_c.set_xticklabels(metrics, rotation=20, ha='right', fontsize=6)
            ax_c.legend(fontsize=7)
            ax_c.grid(axis='y', linestyle='--', alpha=0.3)
            plt.tight_layout()
            
            buf_c = io.BytesIO()
            plt.savefig(buf_c, format='png', dpi=150)
            buf_c.seek(0)
            chart_bytes_list.append(buf_c.getvalue())
            plt.close(fig_c)
        except Exception as e:
            logger.error(f"Error generating Logistics Comparison Chart: {e}")

    # 2. Purchase Order Comparison Chart
    if df_comp_po is not None and not df_comp_po.empty:
        try:
            fig_poc, ax_poc = plt.subplots(figsize=(8, 3.8))
            po_metrics = df_comp_po['Metric Name'].tolist()
            x_po = np.arange(len(po_metrics))
            width = 0.35
            p_bars1 = ax_poc.bar(x_po - width/2, df_comp_po['Yesterday'], width, label='Yesterday', color='#3498DB')
            p_bars2 = ax_poc.bar(x_po + width/2, df_comp_po['Today'], width, label='Today', color='#1ABC9C')
            ax_poc.bar_label(p_bars1, fmt='%.2f', padding=2, fontsize=5)
            ax_poc.bar_label(p_bars2, fmt='%.2f', padding=2, fontsize=5)
            ax_poc.set_title("Purchase Order KPI Comparison Variance", fontsize=9, fontweight='bold', pad=10)
            ax_poc.set_xticks(x_po)
            ax_poc.set_xticklabels(po_metrics, rotation=20, ha='right', fontsize=6)
            ax_poc.legend(fontsize=7)
            ax_poc.grid(axis='y', linestyle='--', alpha=0.3)
            plt.tight_layout()
            
            buf_poc = io.BytesIO()
            plt.savefig(buf_poc, format='png', dpi=150)
            buf_poc.seek(0)
            chart_bytes_list.append(buf_poc.getvalue())
            plt.close(fig_poc)
        except Exception as e:
            logger.error(f"Error generating Purchase Order Comparison Chart: {e}")

    # 3. Purchase Pending Plates Summary Chart (Party Wise)
    if df_ppp is not None and not df_ppp.empty:
        try:
            grp_party = get_grouped_pending_summary(df_ppp, "PARTY NAME")
            if not grp_party.empty:
                fig_p, ax_p = plt.subplots(figsize=(8, 3.8))
                top_grp = grp_party.head(8)
                x = np.arange(len(top_grp))
                w = 0.25
                p_col = top_grp.columns[0]
                
                ax_p.bar(x - w, top_grp["PO QTY (MT)"], w, label='PO QTY', color='#3498DB')
                ax_p.bar(x, top_grp["RECD QTY"], w, label='RECD QTY', color='#2ECC71')
                ax_p.bar(x + w, top_grp["PENDING"], w, label='PENDING', color='#E74C3C')
                
                ax_p.set_title("Party Wise Pending Plates Summary (Top Accounts)", fontsize=9, fontweight='bold', pad=10)
                ax_p.set_xticks(x)
                ax_p.set_xticklabels(top_grp[p_col].astype(str), rotation=25, ha='right', fontsize=6)
                ax_p.legend(fontsize=7)
                ax_p.grid(axis='y', linestyle='--', alpha=0.3)
                plt.tight_layout()
                
                buf_p = io.BytesIO()
                plt.savefig(buf_p, format='png', dpi=150)
                buf_p.seek(0)
                chart_bytes_list.append(buf_p.getvalue())
                plt.close(fig_p)
        except Exception as e:
            logger.error(f"Error generating Pending Plates Party Chart: {e}")

    # 4. Logistics Party Quantity Distribution Chart
    if df_log is not None and not df_log.empty:
        col_party = safe_get_column(df_log, ["PARTY NAME (CUSTOMER)", "PARTY NAME", "CUSTOMER"])
        col_qty = safe_get_column(df_log, ["QTY", "QUANTITY"])
        if col_party and col_qty:
            try:
                df_log_temp = df_log.copy()
                df_log_temp["QTY_NUM"] = df_log_temp[col_qty].apply(parse_slash_separated_qty)
                party_qty = df_log_temp.groupby(col_party)["QTY_NUM"].sum().reset_index()
                party_qty = party_qty[party_qty["QTY_NUM"] > 0].sort_values(by="QTY_NUM", ascending=False).head(10)

                if not party_qty.empty:
                    fig_l, ax_l = plt.subplots(figsize=(8, 3.8))
                    bars_l = ax_l.bar(party_qty[col_party], party_qty["QTY_NUM"], color='#2980B9')
                    ax_l.bar_label(bars_l, fmt='%.2f', padding=3, fontsize=6)
                    ax_l.set_title("Top 10 Customers by Dispatched Quantity (MT)", fontsize=9, fontweight='bold', pad=10)
                    plt.xticks(rotation=25, ha='right', fontsize=6)
                    ax_l.grid(axis='y', linestyle='--', alpha=0.3)
                    plt.tight_layout()
                    
                    buf_l = io.BytesIO()
                    plt.savefig(buf_l, format='png', dpi=150)
                    buf_l.seek(0)
                    chart_bytes_list.append(buf_l.getvalue())
                    plt.close(fig_l)
            except Exception as e:
                logger.error(f"Error generating Logistics Party Chart: {e}")

    return chart_bytes_list

# --- REPORTLAB PDF COMPILATION ENGINE ---

def generate_pdf_report(excel_data_dict: dict, chart_images: list = None, kpi_data: dict = None, kpi_data_po: dict = None, df_comp: pd.DataFrame = None, df_comp_po: pd.DataFrame = None) -> io.BytesIO:
    """Compiles single-day or comparative operations audits into a landscape A4 PDF document."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=landscape(A4), 
        rightMargin=15, 
        leftMargin=15, 
        topMargin=15, 
        bottomMargin=15
    )
    story = []
    
    # Custom Palette
    COLOR_PRIMARY = colors.HexColor('#1F4E78')
    COLOR_SECONDARY = colors.HexColor('#2E4053')
    COLOR_ACCENT = colors.HexColor('#16A085')
    COLOR_TEXT_DARK = colors.HexColor('#2C3E50')
    COLOR_BG_CARD = colors.HexColor('#F8F9F9')
    COLOR_GRID = colors.HexColor('#BDC3C7')

    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        name="DocTitle",
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=18,
        alignment=TA_CENTER,
        textColor=COLOR_PRIMARY
    )
    subtitle_style = ParagraphStyle(
        name="DocSubTitle",
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=COLOR_SECONDARY,
        spaceBefore=6,
        spaceAfter=4
    )
    heading_style = ParagraphStyle(
        name="SectionHeading",
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        textColor=COLOR_ACCENT,
        spaceBefore=4,
        spaceAfter=4
    )
    meta_style = ParagraphStyle(
        name="MetaText",
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        alignment=TA_RIGHT,
        textColor=colors.HexColor('#7F8C8D')
    )
    
    cell_hdr_style = ParagraphStyle(name="CellHeader", fontName="Helvetica-Bold", fontSize=6, leading=7, textColor=colors.white, alignment=TA_CENTER)
    cell_body_style = ParagraphStyle(name="CellBody", fontName="Helvetica", fontSize=6, leading=7, textColor=COLOR_TEXT_DARK, alignment=TA_LEFT)

    kpi_title_style = ParagraphStyle(name="KPITitle", fontName="Helvetica-Bold", fontSize=7, leading=8, textColor=colors.HexColor('#566573'), alignment=TA_CENTER)
    kpi_val_style = ParagraphStyle(name="KPIVal", fontName="Helvetica-Bold", fontSize=11, leading=13, textColor=COLOR_PRIMARY, alignment=TA_CENTER)

    comp_hdr_style = ParagraphStyle(name="CompHeader", fontName="Helvetica-Bold", fontSize=7, leading=8, textColor=colors.white, alignment=TA_CENTER)
    comp_body_style = ParagraphStyle(name="CompBody", fontName="Helvetica", fontSize=7, leading=8, textColor=COLOR_TEXT_DARK, alignment=TA_LEFT)
    comp_num_style = ParagraphStyle(name="CompNum", fontName="Helvetica", fontSize=7, leading=8, textColor=COLOR_TEXT_DARK, alignment=TA_CENTER)

    # Document Header
    story.append(Paragraph("OPERATIONS & AUDIT COMPREHENSIVE REPORT", title_style))
    gen_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    story.append(Paragraph(f"Generated on: {gen_time} | Operational Audit Unit", meta_style))
    story.append(HRFlowable(width="100%", thickness=1, color=COLOR_PRIMARY, spaceBefore=4, spaceAfter=8))

    # SECTION 1: COMPARISON TABLES (IF MULTI-DAY)
    if df_comp is not None and not df_comp.empty:
        story.append(Paragraph("Logistics KPI Variance Summary", subtitle_style))
        comp_table_data = [[
            Paragraph("Metric Name", comp_hdr_style), Paragraph("Yesterday", comp_hdr_style),
            Paragraph("Today", comp_hdr_style), Paragraph("Variance (Difference)", comp_hdr_style)
        ]]
        for _, row in df_comp.iterrows():
            comp_table_data.append([
                Paragraph(str(row["Metric Name"]), comp_body_style),
                Paragraph(f"{row['Yesterday']:,.2f}".rstrip('0').rstrip('.'), comp_num_style),
                Paragraph(f"{row['Today']:,.2f}".rstrip('0').rstrip('.'), comp_num_style),
                Paragraph(f"{row['Variance (Difference)']:,.2f}".rstrip('0').rstrip('.'), comp_num_style)
            ])
        comp_table = Table(comp_table_data, colWidths=[250, 180, 180, 202])
        comp_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), COLOR_PRIMARY),
            ('GRID', (0, 0), (-1, -1), 0.5, COLOR_GRID),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(comp_table)
        story.append(Spacer(1, 8))

    if df_comp_po is not None and not df_comp_po.empty:
        story.append(Paragraph("Purchase Order KPI Variance Summary", subtitle_style))
        po_comp_table_data = [[
            Paragraph("Metric Name", comp_hdr_style), Paragraph("Yesterday", comp_hdr_style),
            Paragraph("Today", comp_hdr_style), Paragraph("Variance (Difference)", comp_hdr_style)
        ]]
        for _, row in df_comp_po.iterrows():
            po_comp_table_data.append([
                Paragraph(str(row["Metric Name"]), comp_body_style),
                Paragraph(f"{row['Yesterday']:,.2f}".rstrip('0').rstrip('.'), comp_num_style),
                Paragraph(f"{row['Today']:,.2f}".rstrip('0').rstrip('.'), comp_num_style),
                Paragraph(f"{row['Variance (Difference)']:,.2f}".rstrip('0').rstrip('.'), comp_num_style)
            ])
        po_comp_table = Table(po_comp_table_data, colWidths=[250, 180, 180, 202])
        po_comp_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), COLOR_SECONDARY),
            ('GRID', (0, 0), (-1, -1), 0.5, COLOR_GRID),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(po_comp_table)
        story.append(Spacer(1, 8))

    # SECTION 2: SINGLE-DAY KPI CARDS
    if kpi_data and df_comp is None:
        story.append(Paragraph("Key Logistics Performance Indicators", subtitle_style))
        kpi_list = list(kpi_data.items())
        r1, r2 = kpi_list[:4], kpi_list[4:8]
        kpi_tbl_data = [
            [Paragraph(k, kpi_title_style) for k, _ in r1],
            [Paragraph(f"{v:,.2f}" if isinstance(v, float) else str(v), kpi_val_style) for _, v in r1]
        ]
        if r2:
            kpi_tbl_data.append([Paragraph(k, kpi_title_style) for k, _ in r2])
            kpi_tbl_data.append([Paragraph(f"{v:,.2f}" if isinstance(v, float) else str(v), kpi_val_style) for _, v in r2])
        
        kpi_card_table = Table(kpi_tbl_data, colWidths=[812 / len(r1)] * len(r1))
        kpi_card_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), COLOR_BG_CARD),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E7E9')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(kpi_card_table)
        story.append(Spacer(1, 8))

    if kpi_data_po and df_comp_po is None:
        story.append(Paragraph("Purchase Order Performance Indicators", subtitle_style))
        po_kpi_list = list(kpi_data_po.items())
        pr1, pr2 = po_kpi_list[:4], po_kpi_list[4:]
        po_kpi_tbl_data = [
            [Paragraph(k, kpi_title_style) for k, _ in pr1],
            [Paragraph(f"{v:,.2f}" if isinstance(v, float) else str(v), kpi_val_style) for _, v in pr1]
        ]
        if pr2:
            po_kpi_tbl_data.append([Paragraph(k, kpi_title_style) for k, _ in pr2])
            po_kpi_tbl_data.append([Paragraph(f"{v:,.2f}" if isinstance(v, float) else str(v), kpi_val_style) for _, v in pr2])
        
        po_kpi_card_table = Table(po_kpi_tbl_data, colWidths=[812 / len(pr1)] * len(pr1))
        po_kpi_card_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F4F6F6')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#D5D8DC')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(po_kpi_card_table)
        story.append(Spacer(1, 8))

    # SECTION 3: EMBEDDED VISUAL CHARTS
    if chart_images:
        story.append(Paragraph("Visual Operational Trends", subtitle_style))
        img_elements = [RLImage(io.BytesIO(img_bytes), width=385, height=180) for img_bytes in chart_images]
        chart_rows = []
        for i in range(0, len(img_elements), 2):
            pair = img_elements[i:i+2]
            if len(pair) == 1:
                pair.append("")
            chart_rows.append(pair)
        
        chart_table = Table(chart_rows, colWidths=[395, 395])
        chart_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(chart_table)
        story.append(Spacer(1, 8))

    # SECTION 4: MODULE DATA TABLES & PURCHASE PENDING PLATES GROUPINGS
    for file_label, excel_data in excel_data_dict.items():
        story.append(Paragraph(f"Data Set Source: {file_label}", subtitle_style))
        
        target_sheets = ["HR AND ADMIN", "LOGISTICS AND DISPATCH", "PURCHASE ORDER", "PURCHASE PENDING PLATES"]
        for sheet_name in target_sheets:
            matched_key = next((k for k in excel_data.keys() if sheet_name in k.upper()), None)
            if matched_key:
                df = excel_data[matched_key]
                story.append(Paragraph(f"Module: {sheet_name}", heading_style))

                # Special summary rendering for Purchase Pending Plates in PDF
                if "PENDING" in sheet_name:
                    for kw in ["PARTY NAME", "PO NO", "THICK", "DISCRIPTION"]:
                        grp_df = get_grouped_pending_summary(df, kw)
                        if not grp_df.empty:
                            story.append(Paragraph(f"Summary Grouping: {kw} Wise", ParagraphStyle(name="GrpLbl", fontName="Helvetica-Bold", fontSize=8, textColor=colors.HexColor('#2980B9'))))
                            grp_headers = [Paragraph(str(c), cell_hdr_style) for c in grp_df.columns]
                            grp_rows = [grp_headers]
                            for _, r in grp_df.head(10).iterrows():
                                grp_rows.append([Paragraph(str(r[c]), cell_body_style) for c in grp_df.columns])
                            
                            grp_tbl = Table(grp_rows, colWidths=[812 / len(grp_df.columns)] * len(grp_df.columns))
                            grp_tbl.setStyle(TableStyle([
                                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495E')),
                                ('GRID', (0, 0), (-1, -1), 0.3, COLOR_GRID),
                                ('TOPPADDING', (0, 0), (-1, -1), 2),
                                ('BOTTOMPADDING', (0, 0), (-1, -1), 2)
                            ]))
                            story.append(grp_tbl)
                            story.append(Spacer(1, 4))

                # Raw sheet sample printout
                clean_df = df.head(12).fillna("-")
                headers = [Paragraph(str(col), cell_hdr_style) for col in clean_df.columns]
                table_data = [headers]

                for _, row in clean_df.iterrows():
                    row_data = [Paragraph(str(val), cell_body_style) for val in row.values]
                    table_data.append(row_data)

                num_cols = max(len(clean_df.columns), 1)
                col_width = 812 / num_cols

                pdf_table = Table(table_data, colWidths=[col_width] * num_cols)
                pdf_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), COLOR_SECONDARY),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('GRID', (0, 0), (-1, -1), 0.3, COLOR_GRID),
                    ('TOPPADDING', (0, 0), (-1, -1), 2),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ]))
                story.append(pdf_table)
                story.append(Spacer(1, 8))

    doc.build(story)
    buffer.seek(0)
    return buffer

# --- SIDEBAR INTERFACE CONTROLS ---

st.sidebar.header("📁 Data Controls & Uploads")

report_mode = st.sidebar.radio(
    "Select Report Type", 
    ["Single Day View", "Multiple Day Comparison"],
    help="Choose Single Day View for individual file analysis or Multiple Day Comparison to analyze yesterday vs today variance."
)

excel_today = None
excel_yesterday = None

if report_mode == "Single Day View":
    file_today = st.sidebar.file_uploader("Upload Master Excel Workbook", type=["xlsx", "xls"], key="single_today")
    if file_today:
        try:
            raw_dict = pd.read_excel(file_today, sheet_name=None)
            excel_today = {str(k).upper().strip(): clean_column_names(v) for k, v in raw_dict.items()}
            st.sidebar.success(f"Loaded File: {file_today.name}")
        except Exception as e:
            st.sidebar.error(f"Error reading workbook: {e}")

else:
    file_yesterday = st.sidebar.file_uploader("Upload Yesterday's Excel Workbook", type=["xlsx", "xls"], key="m_yest")
    file_today = st.sidebar.file_uploader("Upload Today's Excel Workbook", type=["xlsx", "xls"], key="m_today")
    
    if file_yesterday and file_today:
        try:
            raw_yest = pd.read_excel(file_yesterday, sheet_name=None)
            raw_tod = pd.read_excel(file_today, sheet_name=None)
            excel_yesterday = {str(k).upper().strip(): clean_column_names(v) for k, v in raw_yest.items()}
            excel_today = {str(k).upper().strip(): clean_column_names(v) for k, v in raw_tod.items()}
            st.sidebar.success("Both Workbooks Successfully Loaded!")
        except Exception as e:
            st.sidebar.error(f"Error reading comparative workbooks: {e}")

# --- MAIN DASHBOARD WORKSPACE ---

if report_mode == "Single Day View":
    if excel_today:
        single_day_figs = []
        kpis_today = {}
        kpis_po_today = {}
        df_log_prep = None
        df_po_prep = None
        df_ppp_prep = None

        log_key_today = next((k for k in excel_today.keys() if "LOGISTICS" in k or "DISPATCH" in k), None)
        if log_key_today:
            df_log_prep = excel_today[log_key_today]
            kpis_today = calculate_logistics_kpis(df_log_prep)
            col_party = safe_get_column(df_log_prep, ["PARTY NAME (CUSTOMER)", "PARTY NAME"])
            if col_party and "QTY_NUM" in df_log_prep.columns:
                fig1 = px.bar(
                    df_log_prep, 
                    x=col_party, 
                    y="QTY_NUM", 
                    text_auto='.2f', 
                    title="Total Dispatched Quantity (MT) per Customer Party"
                )
                fig1.update_layout(xaxis_tickangle=-45, template="plotly_white")
                single_day_figs.append(fig1)

        po_key_today = next((k for k in excel_today.keys() if "PURCHASE ORDER" in k or "PO" in k), None)
        if po_key_today:
            df_po_prep = excel_today[po_key_today]
            kpis_po_today = calculate_po_kpis(df_po_prep)

        ppp_key_today = next((k for k in excel_today.keys() if "PENDING" in k), None)
        if ppp_key_today:
            df_ppp_prep = excel_today[ppp_key_today]

        pdf_chart_bytes = generate_pdf_chart_bytes(df_log=df_log_prep, df_po=df_po_prep, df_ppp=df_ppp_prep)

        tab_hr, tab_log, tab_po, tab_ppp = st.tabs([
            "HR AND ADMIN", 
            "LOGISTICS AND DISPATCH", 
            "PURCHASE ORDER", 
            "PURCHASE PENDING PLATES"
        ])
        
        with tab_hr:
            st.header("🏢 HR AND ADMIN")
            hr_key = next((k for k in excel_today.keys() if "HR" in k or "ADMIN" in k), None)
            if hr_key:
                st.dataframe(excel_today[hr_key], use_container_width=True)
            else:
                st.warning("Sheet 'HR AND ADMIN' not found in uploaded file.")

        with tab_log:
            st.header("🚚 LOGISTICS AND DISPATCH")
            if df_log_prep is not None:
                st.subheader("📊 Key Logistics Metrics")
                display_kpis_safely(kpis_today)
                st.markdown("---")
                st.subheader("📋 Dispatch Records")
                st.dataframe(df_log_prep, use_container_width=True)
                if len(single_day_figs) > 0:
                    st.plotly_chart(single_day_figs[0], use_container_width=True)
            else:
                st.warning("Sheet 'LOGISTICS AND DISPATCH' not found in uploaded file.")

        with tab_po:
            st.header("🛒 PURCHASE ORDER")
            if df_po_prep is not None:
                st.subheader("📊 Purchase Order Overview")
                display_kpis_safely(kpis_po_today)
                st.markdown("---")
                st.subheader("📋 Order Records")
                st.dataframe(df_po_prep, use_container_width=True)
            else:
                st.warning("Sheet 'PURCHASE ORDER' not found in uploaded file.")

        with tab_ppp:
            st.header("📌 PURCHASE PENDING PLATES SUMMARY")
            if df_ppp_prep is not None:
                st.subheader("📊 Grouped Metrics Analysis")
                
                g_col1, g_col2 = st.columns(2)
                with g_col1:
                    st.markdown("### 1. Party Name Wise Summary")
                    df_party = get_grouped_pending_summary(df_ppp_prep, "PARTY NAME")
                    st.dataframe(df_party, use_container_width=True)
                    if not df_party.empty:
                        fig_party = px.bar(
                            df_party, 
                            x=df_party.columns[0], 
                            y=["PO QTY (MT)", "RECD QTY", "PENDING"], 
                            barmode="group", 
                            title="Party Name Wise Pending Quantities",
                            color_discrete_sequence=["#3498DB", "#2ECC71", "#E74C3C"]
                        )
                        fig_party.update_layout(xaxis_tickangle=-30, template="plotly_white")
                        st.plotly_chart(fig_party, use_container_width=True)

                    st.markdown("### 3. Thickness Wise Summary")
                    df_thick = get_grouped_pending_summary(df_ppp_prep, "THICK")
                    st.dataframe(df_thick, use_container_width=True)
                    if not df_thick.empty:
                        fig_thick = px.bar(
                            df_thick, 
                            x=df_thick.columns[0], 
                            y=["PO QTY (MT)", "RECD QTY", "PENDING"], 
                            barmode="group", 
                            title="Thickness Wise Pending Quantities",
                            color_discrete_sequence=["#3498DB", "#2ECC71", "#E74C3C"]
                        )
                        fig_thick.update_layout(template="plotly_white")
                        st.plotly_chart(fig_thick, use_container_width=True)

                with g_col2:
                    st.markdown("### 2. PO Wise Summary")
                    df_po_no = get_grouped_pending_summary(df_ppp_prep, "PO NO")
                    st.dataframe(df_po_no, use_container_width=True)
                    if not df_po_no.empty:
                        fig_po_no = px.bar(
                            df_po_no, 
                            x=df_po_no.columns[0], 
                            y=["PO QTY (MT)", "RECD QTY", "PENDING"], 
                            barmode="group", 
                            title="PO NO Wise Pending Quantities",
                            color_discrete_sequence=["#3498DB", "#2ECC71", "#E74C3C"]
                        )
                        fig_po_no.update_layout(xaxis_tickangle=-30, template="plotly_white")
                        st.plotly_chart(fig_po_no, use_container_width=True)

                    st.markdown("### 4. Description Wise Summary")
                    df_desc = get_grouped_pending_summary(df_ppp_prep, "DISCRIPTION")
                    st.dataframe(df_desc, use_container_width=True)
                    if not df_desc.empty:
                        fig_desc = px.bar(
                            df_desc, 
                            x=df_desc.columns[0], 
                            y=["PO QTY (MT)", "RECD QTY", "PENDING"], 
                            barmode="group", 
                            title="Description Wise Pending Quantities",
                            color_discrete_sequence=["#3498DB", "#2ECC71", "#E74C3C"]
                        )
                        fig_desc.update_layout(xaxis_tickangle=-30, template="plotly_white")
                        st.plotly_chart(fig_desc, use_container_width=True)

                st.markdown("---")
                st.subheader("📋 Complete Purchase Pending Plates Table")
                st.dataframe(df_ppp_prep, use_container_width=True)
            else:
                st.warning("Sheet 'PURCHASE PENDING PLATES' not found in uploaded file.")

        pdf_buf = generate_pdf_report(
            {"Today": excel_today}, 
            chart_images=pdf_chart_bytes, 
            kpi_data=kpis_today, 
            kpi_data_po=kpis_po_today
        )
        st.sidebar.markdown("---")
        st.sidebar.download_button(
            "📥 Download Comprehensive PDF Report", 
            pdf_buf, 
            "Daily_Audit_Report.pdf", 
            "application/pdf"
        )

    else:
        st.info("💡 Please upload an Excel workbook in the sidebar to generate the audit workspace.")

# --- MULTIPLE DAY COMPARISON VIEW ---
else:
    if excel_yesterday and excel_today:
        tab_hr, tab_log, tab_po, tab_ppp = st.tabs([
            "HR AND ADMIN COMPARISON", 
            "LOGISTICS COMPARISON", 
            "PURCHASE ORDER COMPARISON", 
            "PENDING PLATES COMPARISON"
        ])
        df_comp = pd.DataFrame()
        df_comp_po = pd.DataFrame()

        with tab_hr:
            st.header("🏢 HR AND ADMIN — Side-by-Side Comparison")
            c1, c2 = st.columns(2)
            hr_y_key = next((k for k in excel_yesterday.keys() if "HR" in k or "ADMIN" in k), None)
            hr_t_key = next((k for k in excel_today.keys() if "HR" in k or "ADMIN" in k), None)
            
            with c1:
                st.subheader("📅 Yesterday's HR Data")
                if hr_y_key:
                    st.dataframe(excel_yesterday[hr_y_key], use_container_width=True)
            with c2:
                st.subheader("📅 Today's HR Data")
                if hr_t_key:
                    st.dataframe(excel_today[hr_t_key], use_container_width=True)

        with tab_log:
            st.header("🚚 LOGISTICS AND DISPATCH — Variance Analysis")
            log_y_key = next((k for k in excel_yesterday.keys() if "LOGISTICS" in k or "DISPATCH" in k), None)
            log_t_key = next((k for k in excel_today.keys() if "LOGISTICS" in k or "DISPATCH" in k), None)
            
            if log_y_key and log_t_key:
                df_log_y, df_log_t = excel_yesterday[log_y_key], excel_today[log_t_key]
                kpis_y, kpis_t = calculate_logistics_kpis(df_log_y), calculate_logistics_kpis(df_log_t)
                
                comp_rows = [{
                    "Metric Name": k, 
                    "Yesterday": round(kpis_y.get(k, 0.0), 2), 
                    "Today": round(kpis_t.get(k, 0.0), 2), 
                    "Variance (Difference)": round(kpis_t.get(k, 0.0) - kpis_y.get(k, 0.0), 2)
                } for k in kpis_t.keys()]
                
                df_comp = pd.DataFrame(comp_rows)
                st.dataframe(df_comp, use_container_width=True)
                
                fig_comp_log = px.bar(
                    df_comp, 
                    x="Metric Name", 
                    y=["Yesterday", "Today"], 
                    barmode="group",
                    title="Logistics Metrics Variance",
                    color_discrete_sequence=["#8E44AD", "#2ECC71"]
                )
                fig_comp_log.update_layout(xaxis_tickangle=-25, template="plotly_white")
                st.plotly_chart(fig_comp_log, use_container_width=True)

        with tab_po:
            st.header("🛒 PURCHASE ORDER — Variance Analysis")
            po_y_key = next((k for k in excel_yesterday.keys() if "PURCHASE ORDER" in k or "PO" in k), None)
            po_t_key = next((k for k in excel_today.keys() if "PURCHASE ORDER" in k or "PO" in k), None)
            
            if po_y_key and po_t_key:
                k_po_y, k_po_t = calculate_po_kpis(excel_yesterday[po_y_key]), calculate_po_kpis(excel_today[po_t_key])
                po_rows = [{
                    "Metric Name": k, 
                    "Yesterday": round(k_po_y.get(k, 0.0), 2), 
                    "Today": round(k_po_t.get(k, 0.0), 2), 
                    "Variance (Difference)": round(k_po_t.get(k, 0.0) - k_po_y.get(k, 0.0), 2)
                } for k in k_po_t.keys()]
                
                df_comp_po = pd.DataFrame(po_rows)
                st.dataframe(df_comp_po, use_container_width=True)
                
                fig_comp_po = px.bar(
                    df_comp_po, 
                    x="Metric Name", 
                    y=["Yesterday", "Today"], 
                    barmode="group",
                    title="Purchase Order Metrics Variance",
                    color_discrete_sequence=["#3498DB", "#1ABC9C"]
                )
                fig_comp_po.update_layout(xaxis_tickangle=-25, template="plotly_white")
                st.plotly_chart(fig_comp_po, use_container_width=True)

        with tab_ppp:
            st.header("📌 PURCHASE PENDING PLATES — Side-by-Side Comparison")
            ppp_y_key = next((k for k in excel_yesterday.keys() if "PENDING" in k), None)
            ppp_t_key = next((k for k in excel_today.keys() if "PENDING" in k), None)
            
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("📅 Yesterday's Pending Plates")
                if ppp_y_key:
                    st.dataframe(excel_yesterday[ppp_y_key], use_container_width=True)
            with c2:
                st.subheader("📅 Today's Pending Plates")
                if ppp_t_key:
                    st.dataframe(excel_today[ppp_t_key], use_container_width=True)

        comp_pdf_bytes = generate_pdf_chart_bytes(
            df_log=excel_today.get(log_t_key if 'log_t_key' in locals() and log_t_key else "LOGISTICS AND DISPATCH"),
            df_po=excel_today.get(po_t_key if 'po_t_key' in locals() and po_t_key else "PURCHASE ORDER"),
            df_comp=df_comp,
            df_comp_po=df_comp_po,
            df_ppp=excel_today.get(ppp_t_key if 'ppp_t_key' in locals() and ppp_t_key else "PURCHASE PENDING PLATES")
        )

        pdf_buf = generate_pdf_report(
            {f"Yesterday ({file_yesterday.name})": excel_yesterday, f"Today ({file_today.name})": excel_today}, 
            chart_images=comp_pdf_bytes, 
            df_comp=df_comp, 
            df_comp_po=df_comp_po
        )
        st.sidebar.markdown("---")
        st.sidebar.download_button(
            "📥 Download Comparative PDF Report", 
            pdf_buf, 
            "Comparative_Audit_Report.pdf", 
            "application/pdf"
        )
    else:
        st.info("💡 Please upload both Yesterday's and Today's Excel workbooks to generate comparative analysis.")
