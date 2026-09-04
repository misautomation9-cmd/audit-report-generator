import io
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import matplotlib.pyplot as plt

# ReportLab Imports
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Operations Audit: HR, Admin, Logistics & PO",
    page_icon="🚚",
    layout="wide"
)

st.title("🚚 AUDIT & OPERATIONS DASHBOARD: HR, ADMIN, LOGISTICS & PURCHASE ORDER")
st.caption("Upload daily Excel files to generate single-day reports or run side-by-side date comparisons.")

# --- HELPER FUNCTIONS ---

def clean_column_names(df):
    df.columns = [str(col).strip() for col in df.columns]
    return df

def parse_slash_separated_qty(val):
    if pd.isna(val):
        return 0.0
    val_str = str(val).strip()
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

def parse_numeric_clean(val):
    """Cleans numeric input strings removing currency symbols or commas."""
    if pd.isna(val):
        return 0.0
    val_str = str(val).replace("₹", "").replace(",", "").strip()
    try:
        return float(val_str)
    except ValueError:
        return 0.0

def parse_loading_time(val):
    if pd.isna(val):
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

# --- KPI CALCULATORS ---

def calculate_logistics_kpis(df):
    kpis = {}
    
    if "QTY" in df.columns:
        df["QTY_NUM"] = df["QTY"].apply(parse_slash_separated_qty)
    else:
        df["QTY_NUM"] = 0.0

    if "VEHICLE NO." in df.columns:
        kpis["Unique Vehicles Count"] = df["VEHICLE NO."].dropna().nunique()
        
    if "TRANSPORT" in df.columns:
        kpis["Unique Transports Count"] = df["TRANSPORT"].dropna().nunique()
        
    if "PARTY NAME (CUSTOMER)" in df.columns:
        kpis["Unique Parties Count"] = df["PARTY NAME (CUSTOMER)"].dropna().nunique()
        
    if "INVOICE NO." in df.columns:
        raw_invoices = df["INVOICE NO."].dropna().astype(str).tolist()
        split_invoices = set()
        for inv in raw_invoices:
            parts = [p.strip() for p in inv.split('/') if p.strip()]
            split_invoices.update(parts)
        kpis["Unique Invoices Count"] = len(split_invoices)
        
    if "QTY" in df.columns:
        kpis["Total Quantity (MT)"] = df["QTY_NUM"].sum()
        
    if "FREIGHT (IF)" in df.columns:
        total_freight = 0.0
        for _, row in df.iterrows():
            freight_str = str(row["FREIGHT (IF)"]).upper().strip()
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
    else:
        kpis["Total Freight (₹)"] = 0.0

    if "LOADING TIME" in df.columns:
        df["LOADING_NUM"] = df["LOADING TIME"].apply(parse_loading_time)
        total_loading = df["LOADING_NUM"].sum()
        kpis["Total Loading Time (Hrs)"] = total_loading
        
        veh_count = kpis.get("Unique Vehicles Count", 0)
        if veh_count > 0:
            kpis["Average Loading Time / Vehicle (Hrs)"] = total_loading / veh_count
        else:
            kpis["Average Loading Time / Vehicle (Hrs)"] = 0.0

    return kpis

def calculate_po_kpis(df):
    kpis = {}
    
    # Pre-clean numeric columns
    qty_col = next((c for c in df.columns if "QTY" in c.upper()), None)
    if qty_col:
        df["PO_QTY_NUM"] = df[qty_col].apply(parse_slash_separated_qty)
    else:
        df["PO_QTY_NUM"] = 0.0

    rate_col = next((c for c in df.columns if "RATE" in c.upper()), None)
    if rate_col:
        df["PO_RATE_NUM"] = df[rate_col].apply(parse_numeric_clean)
    else:
        df["PO_RATE_NUM"] = 0.0

    # Unique Counts
    po_col = next((c for c in df.columns if "PO" in c.upper() or "NO" in c.upper()), None)
    kpis["Unique PO Count"] = df[po_col].dropna().nunique() if po_col else 0

    party_col = next((c for c in df.columns if "PARTY" in c.upper()), None)
    kpis["Unique Party Name Count"] = df[party_col].dropna().nunique() if party_col else 0

    desc_col = next((c for c in df.columns if "DISCRIPTION" in c.upper() or "DESCRIPTION" in c.upper()), None)
    kpis["Unique Description Count"] = df[desc_col].dropna().nunique() if desc_col else 0

    size_col = next((c for c in df.columns if "SIZE" in c.upper()), None)
    kpis["Unique Size Count"] = df[size_col].dropna().nunique() if size_col else 0

    grade_col = next((c for c in df.columns if "GRADE" in c.upper()), None)
    kpis["Unique Grade Count"] = df[grade_col].dropna().nunique() if grade_col else 0

    # Aggregations
    kpis["Sum of Qty (MT)"] = df["PO_QTY_NUM"].sum()
    kpis["Sum of Purchase Rate (₹)"] = df["PO_RATE_NUM"].sum()
    kpis["Average Purchase Rate (₹)"] = df["PO_RATE_NUM"].mean() if len(df["PO_RATE_NUM"]) > 0 else 0.0

    return kpis

def display_kpis_safely(kpis):
    if kpis:
        max_cols_per_row = 4
        kpi_items = list(kpis.items())
        for i in range(0, len(kpi_items), max_cols_per_row):
            batch = kpi_items[i:i + max_cols_per_row]
            cols = st.columns(len(batch))
            for idx, (k, v) in enumerate(batch):
                val_str = f"{v:,.2f}" if isinstance(v, float) else str(v)
                cols[idx].metric(label=k, value=val_str)

# --- PDF GENERATOR ---

def generate_pdf_report(excel_data_dict, chart_images=None, kpi_data=None, kpi_data_po=None, df_comp=None, df_comp_po=None):
    """Generates PDF report including data tables, single/comparison KPIs, and embedded graphs."""
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
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(name="DocTitle", fontName="Helvetica-Bold", fontSize=15, leading=18, alignment=1, textColor=colors.HexColor('#1A252F'))
    subtitle_style = ParagraphStyle(name="DocSubTitle", fontName="Helvetica-Bold", fontSize=12, leading=15, textColor=colors.HexColor('#2E4053'))
    heading_style = ParagraphStyle(name="SectionHeading", fontName="Helvetica-Bold", fontSize=10, leading=13, textColor=colors.HexColor('#16A085'))
    
    cell_hdr_style = ParagraphStyle(name="CellHeader", fontName="Helvetica-Bold", fontSize=6, leading=7, textColor=colors.white, alignment=1)
    cell_body_style = ParagraphStyle(name="CellBody", fontName="Helvetica", fontSize=6, leading=7, textColor=colors.HexColor('#2C3E50'), alignment=0)

    kpi_title_style = ParagraphStyle(name="KPITitle", fontName="Helvetica-Bold", fontSize=7, leading=8, textColor=colors.HexColor('#566573'), alignment=1)
    kpi_val_style = ParagraphStyle(name="KPIVal", fontName="Helvetica-Bold", fontSize=12, leading=14, textColor=colors.HexColor('#1A252F'), alignment=1)

    comp_hdr_style = ParagraphStyle(name="CompHeader", fontName="Helvetica-Bold", fontSize=7, leading=8, textColor=colors.white, alignment=1)
    comp_body_style = ParagraphStyle(name="CompBody", fontName="Helvetica", fontSize=7, leading=8, textColor=colors.HexColor('#2C3E50'), alignment=0)
    comp_num_style = ParagraphStyle(name="CompNum", fontName="Helvetica", fontSize=7, leading=8, textColor=colors.HexColor('#2C3E50'), alignment=1)

    story.append(Paragraph("OPERATIONS & AUDIT COMPREHENSIVE REPORT", title_style))
    story.append(Spacer(1, 10))

    # 1. ADD COMPARISON VARIANCE TABLES (IF MULTI-DAY VIEW)
    if df_comp is not None and not df_comp.empty:
        story.append(Paragraph("Logistics KPI Variance Summary", subtitle_style))
        story.append(Spacer(1, 6))

        comp_table_data = [[
            Paragraph("Metric Name", comp_hdr_style),
            Paragraph("Yesterday", comp_hdr_style),
            Paragraph("Today", comp_hdr_style),
            Paragraph("Variance (Difference)", comp_hdr_style)
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
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1F4E78')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#BDC3C7')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(comp_table)
        story.append(Spacer(1, 12))

    if df_comp_po is not None and not df_comp_po.empty:
        story.append(Paragraph("Purchase Order KPI Variance Summary", subtitle_style))
        story.append(Spacer(1, 6))

        po_comp_table_data = [[
            Paragraph("Metric Name", comp_hdr_style),
            Paragraph("Yesterday", comp_hdr_style),
            Paragraph("Today", comp_hdr_style),
            Paragraph("Variance (Difference)", comp_hdr_style)
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
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E4053')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#BDC3C7')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(po_comp_table)
        story.append(Spacer(1, 12))

    # 2. ADD SINGLE-DAY KPI CARDS (IF SINGLE-DAY VIEW)
    if kpi_data and df_comp is None:
        story.append(Paragraph("Key Logistics Performance Indicators", subtitle_style))
        story.append(Spacer(1, 6))

        kpi_list = list(kpi_data.items())
        row1_kpis = kpi_list[:4]
        row2_kpis = kpi_list[4:8]

        kpi_table_data = [
            [Paragraph(k, kpi_title_style) for k, _ in row1_kpis],
            [Paragraph(f"{v:,.2f}" if isinstance(v, float) else str(v), kpi_val_style) for _, v in row1_kpis]
        ]

        if row2_kpis:
            kpi_table_data.append([Paragraph(k, kpi_title_style) for k, _ in row2_kpis])
            kpi_table_data.append([Paragraph(f"{v:,.2f}" if isinstance(v, float) else str(v), kpi_val_style) for _, v in row2_kpis])

        num_kpi_cols = len(row1_kpis)
        kpi_card_table = Table(kpi_table_data, colWidths=[812 / num_kpi_cols] * num_kpi_cols)
        kpi_card_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8F9F9')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E7E9')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(kpi_card_table)
        story.append(Spacer(1, 12))

    if kpi_data_po and df_comp_po is None:
        story.append(Paragraph("Purchase Order Performance Indicators", subtitle_style))
        story.append(Spacer(1, 6))

        po_kpi_list = list(kpi_data_po.items())
        p_row1 = po_kpi_list[:4]
        p_row2 = po_kpi_list[4:]

        po_kpi_table_data = [
            [Paragraph(k, kpi_title_style) for k, _ in p_row1],
            [Paragraph(f"{v:,.2f}" if isinstance(v, float) else str(v), kpi_val_style) for _, v in p_row1]
        ]

        if p_row2:
            po_kpi_table_data.append([Paragraph(k, kpi_title_style) for k, _ in p_row2])
            po_kpi_table_data.append([Paragraph(f"{v:,.2f}" if isinstance(v, float) else str(v), kpi_val_style) for _, v in p_row2])

        num_po_cols = len(p_row1)
        po_kpi_card_table = Table(po_kpi_table_data, colWidths=[812 / num_po_cols] * num_po_cols)
        po_kpi_card_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F4F6F6')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#D5D8DC')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(po_kpi_card_table)
        story.append(Spacer(1, 12))

    # 3. EMBED VISUAL CHARTS
    if chart_images:
        story.append(Paragraph("Visual Performance Charts", subtitle_style))
        story.append(Spacer(1, 8))
        
        img_elements = []
        for img_bytes in chart_images:
            img_buf = io.BytesIO(img_bytes)
            img_elements.append(RLImage(img_buf, width=380, height=190))
        
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
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]))
        story.append(chart_table)
        story.append(Spacer(1, 10))

    # 4. ADD DATA TABLES
    for file_label, excel_data in excel_data_dict.items():
        story.append(Paragraph(f"Data Set Source: {file_label}", subtitle_style))
        story.append(Spacer(1, 8))

        for sheet_name in ["HR AND ADMIN", "LOGISTICS AND DISPATCH", "PURCHASE ORDER"]:
            matched_key = next((k for k in excel_data.keys() if sheet_name in k.upper()), None)
            if matched_key:
                df = excel_data[matched_key]
                story.append(Paragraph(f"Module: {sheet_name}", heading_style))
                story.append(Spacer(1, 4))

                clean_df = df.head(15).fillna("-")
                headers = [Paragraph(str(col), cell_hdr_style) for col in clean_df.columns]
                table_data = [headers]

                for _, row in clean_df.iterrows():
                    row_data = [Paragraph(str(val), cell_body_style) for val in row.values]
                    table_data.append(row_data)

                num_cols = len(clean_df.columns)
                col_width = 812 / num_cols

                pdf_table = Table(table_data, colWidths=[col_width] * num_cols)
                pdf_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2C3E50')),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#BDC3C7')),
                    ('TOPPADDING', (0, 0), (-1, -1), 3),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                    ('LEFTPADDING', (0, 0), (-1, -1), 2),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                ]))
                story.append(pdf_table)
                story.append(Spacer(1, 10))

    doc.build(story)
    buffer.seek(0)
    return buffer

def generate_pdf_chart_bytes(df_log=None, df_po=None, df_comp=None, df_comp_po=None):
    """Generates graph images using Matplotlib for PDF embedding."""
    chart_bytes_list = []

    # 1. Logistics Comparison Bar Chart (If df_comp is provided)
    if df_comp is not None and not df_comp.empty:
        fig_c, ax_c = plt.subplots(figsize=(8, 3.8))
        
        metrics = df_comp['Metric Name'].tolist()
        yesterday_vals = df_comp['Yesterday'].tolist()
        today_vals = df_comp['Today'].tolist()
        
        x = np.arange(len(metrics))
        width = 0.35
        
        bars1 = ax_c.bar(x - width/2, yesterday_vals, width, label='Yesterday', color='#AB63FA')
        bars2 = ax_c.bar(x + width/2, today_vals, width, label='Today', color='#00CC96')
        
        ax_c.bar_label(bars1, fmt='%.2f', padding=2, fontsize=5)
        ax_c.bar_label(bars2, fmt='%.2f', padding=2, fontsize=5)
        
        ax_c.set_title("Logistics KPI Comparison", fontsize=9, fontweight='bold')
        ax_c.set_xticks(x)
        ax_c.set_xticklabels(metrics, rotation=25, ha='right', fontsize=6)
        ax_c.legend(fontsize=7)
        plt.tight_layout()
        
        buf_c = io.BytesIO()
        plt.savefig(buf_c, format='png', dpi=150)
        buf_c.seek(0)
        chart_bytes_list.append(buf_c.getvalue())
        plt.close(fig_c)

    # 2. Purchase Order Comparison Bar Chart (If df_comp_po is provided)
    if df_comp_po is not None and not df_comp_po.empty:
        fig_poc, ax_poc = plt.subplots(figsize=(8, 3.8))
        
        po_metrics = df_comp_po['Metric Name'].tolist()
        po_yest_vals = df_comp_po['Yesterday'].tolist()
        po_tod_vals = df_comp_po['Today'].tolist()
        
        x_po = np.arange(len(po_metrics))
        width = 0.35
        
        p_bars1 = ax_poc.bar(x_po - width/2, po_yest_vals, width, label='Yesterday', color='#3498DB')
        p_bars2 = ax_poc.bar(x_po + width/2, po_tod_vals, width, label='Today', color='#2ECC71')
        
        ax_poc.bar_label(p_bars1, fmt='%.2f', padding=2, fontsize=5)
        ax_poc.bar_label(p_bars2, fmt='%.2f', padding=2, fontsize=5)
        
        ax_poc.set_title("Purchase Order KPI Comparison", fontsize=9, fontweight='bold')
        ax_poc.set_xticks(x_po)
        ax_poc.set_xticklabels(po_metrics, rotation=25, ha='right', fontsize=6)
        ax_poc.legend(fontsize=7)
        plt.tight_layout()
        
        buf_poc = io.BytesIO()
        plt.savefig(buf_poc, format='png', dpi=150)
        buf_poc.seek(0)
        chart_bytes_list.append(buf_poc.getvalue())
        plt.close(fig_poc)
    
    # 3. Logistics Charts
    if df_log is not None and "PARTY NAME (CUSTOMER)" in df_log.columns:
        if "QTY_NUM" in df_log.columns:
            fig1, ax1 = plt.subplots(figsize=(7, 3.5))
            party_qty = df_log.groupby("PARTY NAME (CUSTOMER)")["QTY_NUM"].sum().reset_index()
            party_qty = party_qty[party_qty["QTY_NUM"] > 0]
            
            bars1 = ax1.bar(party_qty["PARTY NAME (CUSTOMER)"], party_qty["QTY_NUM"], color='#1f77b4')
            ax1.bar_label(bars1, fmt='%.2f', padding=3, fontsize=7)
            ax1.set_title("Total Quantity (MT) per Party Name", fontsize=9, fontweight='bold')
            ax1.set_ylabel("Quantity (MT)", fontsize=8)
            plt.xticks(rotation=45, ha='right', fontsize=6)
            plt.tight_layout()
            
            buf1 = io.BytesIO()
            plt.savefig(buf1, format='png', dpi=150)
            buf1.seek(0)
            chart_bytes_list.append(buf1.getvalue())
            plt.close(fig1)

        if "LOADING_NUM" in df_log.columns:
            fig2, ax2 = plt.subplots(figsize=(7, 3.5))
            party_load = df_log.groupby("PARTY NAME (CUSTOMER)")["LOADING_NUM"].sum().reset_index()
            party_load = party_load[party_load["LOADING_NUM"] > 0]
            
            bars2 = ax2.bar(party_load["PARTY NAME (CUSTOMER)"], party_load["LOADING_NUM"], color='#ff7f0e')
            ax2.bar_label(bars2, fmt='%.1f', padding=3, fontsize=7)
            ax2.set_title("Total Loading Time (Hrs) per Party Name", fontsize=9, fontweight='bold')
            ax2.set_ylabel("Loading Hours", fontsize=8)
            plt.xticks(rotation=45, ha='right', fontsize=6)
            plt.tight_layout()
            
            buf2 = io.BytesIO()
            plt.savefig(buf2, format='png', dpi=150)
            buf2.seek(0)
            chart_bytes_list.append(buf2.getvalue())
            plt.close(fig2)

    # 4. Purchase Order Charts
    if df_po is not None and not df_po.empty:
        p_col = next((c for c in df_po.columns if "PARTY" in c.upper()), None)
        q_col = "PO_QTY_NUM"
        d_col = next((c for c in df_po.columns if "DISCRIPTION" in c.upper() or "DESCRIPTION" in c.upper()), None)
        t_col = next((c for c in df_po.columns if "THIKNESS" in c.upper() or "THICKNESS" in c.upper()), None)
        r_col = "PO_RATE_NUM"
        g_col = next((c for c in df_po.columns if "GRADE" in c.upper()), None)

        # Graph 1: Party Name vs Qty
        if p_col and q_col in df_po.columns:
            fig, ax = plt.subplots(figsize=(7, 3.5))
            grp = df_po.groupby(p_col)[q_col].sum().reset_index()
            bars = ax.bar(grp[p_col].astype(str), grp[q_col], color='#2980B9')
            ax.bar_label(bars, fmt='%.1f', padding=2, fontsize=6)
            ax.set_title("PO: Party Name vs Total Quantity (MT)", fontsize=9, fontweight='bold')
            plt.xticks(rotation=30, ha='right', fontsize=6)
            plt.tight_layout()
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=150)
            buf.seek(0)
            chart_bytes_list.append(buf.getvalue())
            plt.close(fig)

        # Graph 2: Description vs Qty
        if d_col and q_col in df_po.columns:
            fig, ax = plt.subplots(figsize=(7, 3.5))
            grp = df_po.groupby(d_col)[q_col].sum().reset_index()
            bars = ax.bar(grp[d_col].astype(str), grp[q_col], color='#27AE60')
            ax.bar_label(bars, fmt='%.1f', padding=2, fontsize=6)
            ax.set_title("PO: Description vs Total Quantity (MT)", fontsize=9, fontweight='bold')
            plt.xticks(rotation=30, ha='right', fontsize=6)
            plt.tight_layout()
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=150)
            buf.seek(0)
            chart_bytes_list.append(buf.getvalue())
            plt.close(fig)

        # Graph 3: Thickness vs Rate
        if t_col and r_col in df_po.columns:
            fig, ax = plt.subplots(figsize=(7, 3.5))
            grp = df_po.groupby(t_col)[r_col].mean().reset_index()
            bars = ax.bar(grp[t_col].astype(str), grp[r_col], color='#E67E22')
            ax.bar_label(bars, fmt='%.1f', padding=2, fontsize=6)
            ax.set_title("PO: Thickness vs Purchase Rate (₹)", fontsize=9, fontweight='bold')
            plt.xticks(rotation=30, ha='right', fontsize=6)
            plt.tight_layout()
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=150)
            buf.seek(0)
            chart_bytes_list.append(buf.getvalue())
            plt.close(fig)

        # Graph 4: Grade vs Rate
        if g_col and r_col in df_po.columns:
            fig, ax = plt.subplots(figsize=(7, 3.5))
            grp = df_po.groupby(g_col)[r_col].mean().reset_index()
            bars = ax.bar(grp[g_col].astype(str), grp[r_col], color='#8E44AD')
            ax.bar_label(bars, fmt='%.1f', padding=2, fontsize=6)
            ax.set_title("PO: Grade vs Purchase Rate (₹)", fontsize=9, fontweight='bold')
            plt.xticks(rotation=30, ha='right', fontsize=6)
            plt.tight_layout()
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=150)
            buf.seek(0)
            chart_bytes_list.append(buf.getvalue())
            plt.close(fig)

    return chart_bytes_list

# --- SIDEBAR CONTROLS ---
st.sidebar.header("📁 Data Controls")

report_mode = st.sidebar.radio(
    "Select Report Type",
    ["Single Day View", "Multiple Day Comparison"]
)

excel_today = None
excel_yesterday = None

if report_mode == "Single Day View":
    file_today = st.sidebar.file_uploader("Upload Master Excel Workbook", type=["xlsx", "xls"], key="single_today")
    if file_today:
        raw_dict = pd.read_excel(file_today, sheet_name=None)
        excel_today = {str(k).upper().strip(): clean_column_names(v) for k, v in raw_dict.items()}
        st.sidebar.success(f"Loaded: {file_today.name}")

else:
    file_yesterday = st.sidebar.file_uploader("Upload Yesterday's Excel Workbook", type=["xlsx", "xls"], key="m_yest")
    file_today = st.sidebar.file_uploader("Upload Today's Excel Workbook", type=["xlsx", "xls"], key="m_today")
    
    if file_yesterday and file_today:
        raw_yest = pd.read_excel(file_yesterday, sheet_name=None)
        raw_tod = pd.read_excel(file_today, sheet_name=None)
        
        excel_yesterday = {str(k).upper().strip(): clean_column_names(v) for k, v in raw_yest.items()}
        excel_today = {str(k).upper().strip(): clean_column_names(v) for k, v in raw_tod.items()}
        st.sidebar.success("Both Workbooks Loaded Successfully!")

# --- MAIN WORKSPACE ---

if report_mode == "Single Day View":
    if excel_today:
        single_day_figs = []
        pdf_chart_bytes = []
        kpis_today = {}
        kpis_po_today = {}
        df_log_prep = None
        df_po_prep = None

        if "LOGISTICS AND DISPATCH" in excel_today:
            df_log_prep = excel_today["LOGISTICS AND DISPATCH"]
            kpis_today = calculate_logistics_kpis(df_log_prep)
            
            if "PARTY NAME (CUSTOMER)" in df_log_prep.columns and "QTY" in df_log_prep.columns:
                fig1 = px.bar(
                    df_log_prep, 
                    x="PARTY NAME (CUSTOMER)", 
                    y="QTY_NUM", 
                    text_auto='.2f',
                    title="Total Quantity (MT) per Party Name",
                    labels={"QTY_NUM": "Quantity (MT)"},
                    color="PARTY NAME (CUSTOMER)"
                )
                fig1.update_traces(textposition='outside')
                single_day_figs.append(fig1)

            if "PARTY NAME (CUSTOMER)" in df_log_prep.columns and "LOADING TIME" in df_log_prep.columns:
                fig2 = px.bar(
                    df_log_prep, 
                    x="PARTY NAME (CUSTOMER)", 
                    y="LOADING_NUM", 
                    text_auto='.1f',
                    title="Total Loading Time (Hrs) per Party Name",
                    labels={"LOADING_NUM": "Loading Hours"},
                    color_discrete_sequence=["#FF9900"]
                )
                fig2.update_traces(textposition='outside')
                single_day_figs.append(fig2)

        po_key_today = next((k for k in excel_today.keys() if "PURCHASE ORDER" in k or "PO" in k), None)
        if po_key_today:
            df_po_prep = excel_today[po_key_today]
            kpis_po_today = calculate_po_kpis(df_po_prep)

        pdf_chart_bytes = generate_pdf_chart_bytes(df_log=df_log_prep, df_po=df_po_prep)

        tab_hr, tab_log, tab_po = st.tabs(["HR AND ADMIN", "LOGISTICS AND DISPATCH", "PURCHASE ORDER"])
        
        with tab_hr:
            st.header("HR AND ADMIN")
            if "HR AND ADMIN" in excel_today:
                df_hr = excel_today["HR AND ADMIN"]
                st.dataframe(df_hr, use_container_width=True)
            else:
                st.warning("Sheet 'HR AND ADMIN' not found in uploaded file.")
                
        with tab_log:
            st.header("LOGISTICS AND DISPATCH")
            if "LOGISTICS AND DISPATCH" in excel_today:
                df_log = excel_today["LOGISTICS AND DISPATCH"]
                st.subheader("📌 Key Logistics Performance Indicators")
                display_kpis_safely(kpis_today)
                st.markdown("---")
                st.dataframe(df_log, use_container_width=True)
                st.markdown("---")
                st.subheader("📊 Visual Analytics")
                if len(single_day_figs) > 0:
                    g1, g2 = st.columns(2)
                    with g1:
                        if len(single_day_figs) > 0:
                            st.plotly_chart(single_day_figs[0], use_container_width=True)
                    with g2:
                        if len(single_day_figs) > 1:
                            st.plotly_chart(single_day_figs[1], use_container_width=True)
            else:
                st.warning("Sheet 'LOGISTICS AND DISPATCH' not found in uploaded file.")

        with tab_po:
            st.header("PURCHASE ORDER")
            if df_po_prep is not None:
                st.subheader("📌 Purchase Order Performance Indicators")
                display_kpis_safely(kpis_po_today)
                st.markdown("---")
                st.dataframe(df_po_prep, use_container_width=True)
                st.markdown("---")
                st.subheader("📊 Visual Analytics")

                p_col = next((c for c in df_po_prep.columns if "PARTY" in c.upper()), None)
                d_col = next((c for c in df_po_prep.columns if "DISCRIPTION" in c.upper() or "DESCRIPTION" in c.upper()), None)
                t_col = next((c for c in df_po_prep.columns if "THIKNESS" in c.upper() or "THICKNESS" in c.upper()), None)
                g_col = next((c for c in df_po_prep.columns if "GRADE" in c.upper()), None)

                col1, col2 = st.columns(2)
                with col1:
                    if p_col:
                        fig_p1 = px.bar(df_po_prep, x=p_col, y="PO_QTY_NUM", text_auto='.2f', title="Party Name vs Total Quantity (MT)")
                        st.plotly_chart(fig_p1, use_container_width=True)
                    if t_col:
                        fig_p3 = px.bar(df_po_prep, x=t_col, y="PO_RATE_NUM", text_auto='.2f', title="Thickness vs Purchase Rate (₹)")
                        st.plotly_chart(fig_p3, use_container_width=True)
                with col2:
                    if d_col:
                        fig_p2 = px.bar(df_po_prep, x=d_col, y="PO_QTY_NUM", text_auto='.2f', title="Description vs Total Quantity (MT)")
                        st.plotly_chart(fig_p2, use_container_width=True)
                    if g_col:
                        fig_p4 = px.bar(df_po_prep, x=g_col, y="PO_RATE_NUM", text_auto='.2f', title="Grade vs Purchase Rate (₹)")
                        st.plotly_chart(fig_p4, use_container_width=True)
            else:
                st.warning("Sheet 'PURCHASE ORDER' not found in uploaded file.")

        pdf_buf = generate_pdf_report({"Today": excel_today}, chart_images=pdf_chart_bytes, kpi_data=kpis_today, kpi_data_po=kpis_po_today)
        st.sidebar.download_button("📥 Download PDF Report (With KPIs & Graphs)", pdf_buf, "Daily_Audit_Report.pdf", "application/pdf")

    else:
        st.info("Please upload an Excel file to generate the single-day report.")

# MULTIPLE DAY COMPARISON VIEW
else:
    if excel_yesterday and excel_today:
        tab_hr, tab_log, tab_po = st.tabs(["HR AND ADMIN COMPARISON", "LOGISTICS COMPARISON", "PURCHASE ORDER COMPARISON"])
        df_comp = pd.DataFrame()
        df_comp_po = pd.DataFrame()
        
        with tab_hr:
            st.header("HR AND ADMIN — Side-by-Side Comparison")
            df_hr_y = excel_yesterday.get("HR AND ADMIN")
            df_hr_t = excel_today.get("HR AND ADMIN")
            
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("📅 Yesterday")
                if df_hr_y is not None:
                    st.dataframe(df_hr_y, use_container_width=True)
            with c2:
                st.subheader("📅 Today")
                if df_hr_t is not None:
                    st.dataframe(df_hr_t, use_container_width=True)
                    
        with tab_log:
            st.header("LOGISTICS AND DISPATCH — Side-by-Side & Variance Comparison")
            df_log_y = excel_yesterday.get("LOGISTICS AND DISPATCH")
            df_log_t = excel_today.get("LOGISTICS AND DISPATCH")
            
            if df_log_y is not None and df_log_t is not None:
                kpis_y = calculate_logistics_kpis(df_log_y)
                kpis_t = calculate_logistics_kpis(df_log_t)
                
                st.subheader("📈 KPI Variance Summary")
                comp_rows = []
                
                metric_order = [
                    "Average Loading Time / Vehicle (Hrs)",
                    "Total Loading Time (Hrs)",
                    "Unique Transports Count",
                    "Unique Vehicles Count",
                    "Unique Parties Count",
                    "Total Quantity (MT)",
                    "Unique Invoices Count",
                    "Total Freight (₹)"
                ]
                
                all_keys = [m for m in metric_order if m in kpis_y or m in kpis_t]
                for k in set(list(kpis_y.keys()) + list(kpis_t.keys())):
                    if k not in all_keys:
                        all_keys.append(k)
                
                for k in all_keys:
                    val_y = kpis_y.get(k, 0.0)
                    val_t = kpis_t.get(k, 0.0)
                    diff = val_t - val_y
                    comp_rows.append({
                        "Metric Name": k,
                        "Yesterday": round(val_y, 2),
                        "Today": round(val_t, 2),
                        "Variance (Difference)": round(diff, 2)
                    })
                
                df_comp = pd.DataFrame(comp_rows)
                st.dataframe(df_comp, use_container_width=True)
                
                yest_labels = [f"{val:,.2f}".rstrip('0').rstrip('.') if isinstance(val, float) else str(val) for val in df_comp['Yesterday']]
                tod_labels = [f"{val:,.2f}".rstrip('0').rstrip('.') if isinstance(val, float) else str(val) for val in df_comp['Today']]

                fig_comp = go.Figure(data=[
                    go.Bar(
                        name='Yesterday', 
                        x=df_comp['Metric Name'], 
                        y=df_comp['Yesterday'], 
                        text=yest_labels, 
                        textposition='outside', 
                        marker_color='#AB63FA'
                    ),
                    go.Bar(
                        name='Today', 
                        x=df_comp['Metric Name'], 
                        y=df_comp['Today'], 
                        text=tod_labels, 
                        textposition='outside', 
                        marker_color='#00CC96'
                    )
                ])
                
                fig_comp.update_layout(
                    title="Logistics KPI Comparison",
                    barmode='group',
                    xaxis_tickangle=-30,
                    margin=dict(t=50, b=100, l=40, r=40),
                    legend=dict(x=0.85, y=0.95),
                    template="plotly_white"
                )
                
                st.plotly_chart(fig_comp, use_container_width=True)
                
                c1, c2 = st.columns(2)
                with c1:
                    st.subheader("📅 Yesterday's Raw Data")
                    st.dataframe(df_log_y, use_container_width=True)
                with c2:
                    st.subheader("📅 Today's Raw Data")
                    st.dataframe(df_log_t, use_container_width=True)

        with tab_po:
            st.header("PURCHASE ORDER — Side-by-Side & Variance Comparison")
            po_y_key = next((k for k in excel_yesterday.keys() if "PURCHASE ORDER" in k or "PO" in k), None)
            po_t_key = next((k for k in excel_today.keys() if "PURCHASE ORDER" in k or "PO" in k), None)

            if po_y_key and po_t_key:
                df_po_y, df_po_t = excel_yesterday[po_y_key], excel_today[po_t_key]
                k_po_y, k_po_t = calculate_po_kpis(df_po_y), calculate_po_kpis(df_po_t)

                st.subheader("📈 Purchase Order KPI Variance Summary")
                po_rows = []
                for k in k_po_t.keys():
                    val_y, val_t = k_po_y.get(k, 0.0), k_po_t.get(k, 0.0)
                    po_rows.append({
                        "Metric Name": k,
                        "Yesterday": round(val_y, 2),
                        "Today": round(val_t, 2),
                        "Variance (Difference)": round(val_t - val_y, 2)
                    })

                df_comp_po = pd.DataFrame(po_rows)
                st.dataframe(df_comp_po, use_container_width=True)

                fig_po_comp = go.Figure(data=[
                    go.Bar(name='Yesterday', x=df_comp_po['Metric Name'], y=df_comp_po['Yesterday'], text=df_comp_po['Yesterday'], textposition='outside', marker_color='#3498DB'),
                    go.Bar(name='Today', x=df_comp_po['Metric Name'], y=df_comp_po['Today'], text=df_comp_po['Today'], textposition='outside', marker_color='#2ECC71')
                ])
                fig_po_comp.update_layout(title="Purchase Order KPI Comparison", barmode='group', xaxis_tickangle=-30, template="plotly_white")
                st.plotly_chart(fig_po_comp, use_container_width=True)

                c1, c2 = st.columns(2)
                with c1:
                    st.subheader("📅 Yesterday's PO Data")
                    st.dataframe(df_po_y, use_container_width=True)
                with c2:
                    st.subheader("📅 Today's PO Data")
                    st.dataframe(df_po_t, use_container_width=True)

        comp_pdf_bytes = generate_pdf_chart_bytes(
            df_log=excel_today.get("LOGISTICS AND DISPATCH"),
            df_po=excel_today.get(po_t_key if 'po_t_key' in locals() and po_t_key else "PURCHASE ORDER"),
            df_comp=df_comp,
            df_comp_po=df_comp_po
        )

        pdf_buf = generate_pdf_report(
            {
                f"Yesterday ({file_yesterday.name})": excel_yesterday,
                f"Today ({file_today.name})": excel_today
            }, 
            chart_images=comp_pdf_bytes, 
            df_comp=df_comp,
            df_comp_po=df_comp_po
        )
        st.sidebar.download_button("📥 Download Comparative PDF Report", pdf_buf, "Comparative_Audit_Report.pdf", "application/pdf")
    else:
        st.info("Please upload both Yesterday's and Today's Excel files to view comparison metrics.")
