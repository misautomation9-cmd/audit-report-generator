import io
import re
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import streamlit as st

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, PageBreak, Image
)
from reportlab.lib.styles import ParagraphStyle

# ==========================================
# 1. PARSING & KPI EXTRACTION ENGINE
# ==========================================

def parse_reporting_sections(df, sheet_name):
    """
    Parses the 2-section layout from daily godown reporting sheets:
    Handles merged cells in 'Adjustment_Stock' via forward-fill.
    """
    # --- SECTION 1: Dispatches & Salesperson Details ---
    disp_df = df.iloc[:, 0:6].copy()
    disp_df.columns = ['Date', 'SR_No', 'Vehicle_No', 'Party_Name', 'Sales_Person', 'Adjustment_Stock']
    
    # Clean dates and propagate sheet date
    disp_df['Date'] = disp_df['Date'].astype(str).str.strip().replace({'nan': np.nan, 'None': np.nan}).ffill().fillna(sheet_name)
    
    # Filter out empty or header rows
    disp_df['Party_Name'] = disp_df['Party_Name'].astype(str).str.strip()
    disp_df = disp_df[~disp_df['Party_Name'].isin(['nan', 'None', '', 'Particulars'])]
    disp_df['Sales_Person'] = disp_df['Sales_Person'].astype(str).str.strip().replace({'nan': 'Unassigned', 'None': 'Unassigned'})
    disp_df['Vehicle_No'] = disp_df['Vehicle_No'].astype(str).str.strip()
    
    # Handle Merged Cells in Adjustment_Stock (Forward Fill)
    disp_df['Adjustment_Stock'] = disp_df['Adjustment_Stock'].replace({'nan': np.nan, 'None': np.nan, '': np.nan})
    disp_df['Adjustment_Stock'] = disp_df['Adjustment_Stock'].ffill().fillna('-')
    disp_df['Sheet'] = sheet_name

    # --- SECTION 2: Stock Balances & Production ---
    stock_df = df.iloc[:, 6:12].copy()
    stock_df.columns = ['Opening_Particulars', 'Opening_MT', 'Closing_Particulars', 'Closing_MT', 'Production_Yesterday', 'Dispatch_Stock']
    
    # Overall summary from Row 0
    stock_summary = {
        'Sheet': sheet_name,
        'Opening_Stock_MT': pd.to_numeric(stock_df.iloc[0]['Opening_MT'], errors='coerce') or 0.0,
        'Closing_Stock_MT': pd.to_numeric(stock_df.iloc[0]['Closing_MT'], errors='coerce') or 0.0,
        'Production_Yesterday_MT': pd.to_numeric(stock_df.iloc[0]['Production_Yesterday'], errors='coerce') or 0.0,
        'Dispatch_Stock_MT': pd.to_numeric(stock_df.iloc[0]['Dispatch_Stock'], errors='coerce') or 0.0
    }
    
    # Itemized Breakdown (Rows 1 to 11)
    item_df = stock_df.iloc[1:12].copy()
    item_df['Particulars'] = item_df['Opening_Particulars'].astype(str).str.strip()
    item_df = item_df[~item_df['Particulars'].isin(['nan', 'None', '', 'Particulars'])]
    item_df['Opening_MT'] = pd.to_numeric(item_df['Opening_MT'], errors='coerce').fillna(0.0)
    item_df['Closing_MT'] = pd.to_numeric(item_df['Closing_MT'], errors='coerce').fillna(0.0)
    item_df['Variance_MT'] = item_df['Closing_MT'] - item_df['Opening_MT']
    item_df['Sheet'] = sheet_name

    return disp_df, stock_summary, item_df[['Sheet', 'Particulars', 'Opening_MT', 'Closing_MT', 'Variance_MT']]


def compute_kpi_summary(df, date_str):
    """Generates structured KPI dictionary for comparative displays."""
    if df is None or df.empty:
        return {}

    disp_df, stock_summary, item_df = parse_reporting_sections(df, date_str)

    sales_person_summary = disp_df.groupby('Sales_Person').agg(
        total_dispatches=('Vehicle_No', 'count'),
        parties=('Party_Name', 'nunique')
    ).to_dict('index')

    return {
        "date": date_str,
        "total_dispatches": len(disp_df),
        "party_count": disp_df['Party_Name'].nunique(),
        "opening_stock_mt": stock_summary['Opening_Stock_MT'],
        "closing_stock_mt": stock_summary['Closing_Stock_MT'],
        "yesterday_production_mt": stock_summary['Production_Yesterday_MT'],
        "dispatch_stock_mt": stock_summary['Dispatch_Stock_MT'],
        "sales_summary": sales_person_summary,
        "item_breakdown": item_df
    }

# ==========================================
# 2. CHART GENERATION ENGINE
# ==========================================

def generate_stock_comparison_chart(df_item_stock):
    """Generates a grouped bar chart comparing item-wise Opening vs. Closing stock with data labels."""
    if df_item_stock.empty:
        return None

    agg_item = df_item_stock.groupby('Particulars').agg({
        'Opening_MT': 'sum',
        'Closing_MT': 'sum'
    }).reset_index()

    fig, ax = plt.subplots(figsize=(10, 4.2), dpi=150)
    
    x = np.arange(len(agg_item['Particulars']))
    width = 0.35

    rects1 = ax.bar(x - width/2, agg_item['Opening_MT'], width, label='Opening Stock (MT)', color='#3B82F6')
    rects2 = ax.bar(x + width/2, agg_item['Closing_MT'], width, label='Closing Stock (MT)', color='#10B981')

    # Add Data Labels with top margin spacing
    max_val = max(agg_item['Opening_MT'].max(), agg_item['Closing_MT'].max())
    ax.set_ylim(0, max_val * 1.18)

    ax.bar_label(rects1, padding=3, fmt='%.1f', fontsize=6.5, fontweight='bold', rotation=0)
    ax.bar_label(rects2, padding=3, fmt='%.1f', fontsize=6.5, fontweight='bold', rotation=0)

    ax.set_ylabel('Metric Tons (MT)', fontsize=9, fontweight='bold', color='#1E293B')
    ax.set_title('Item-Wise Opening vs Closing Stock Balance', fontsize=11, fontweight='bold', color='#0F172A', pad=10)
    ax.set_xticks(x)
    ax.set_xticklabels(agg_item['Particulars'], rotation=35, ha='right', fontsize=8)
    ax.legend(frameon=True, facecolor='#F8FAFC', edgecolor='none')
    ax.grid(axis='y', linestyle='--', alpha=0.5)

    plt.tight_layout()
    img_buf = io.BytesIO()
    plt.savefig(img_buf, format='png', bbox_inches='tight')
    plt.close(fig)
    img_buf.seek(0)
    return img_buf


def generate_sales_parties_chart(df_dispatches):
    """Generates a bar chart showing unique parties served by each salesperson with data labels."""
    if df_dispatches.empty:
        return None

    sales_party_agg = df_dispatches.groupby('Sales_Person')['Party_Name'].nunique().reset_index()
    sales_party_agg.columns = ['Sales_Person', 'Parties_Count']
    sales_party_agg = sales_party_agg.sort_values(by='Parties_Count', ascending=False)

    fig, ax = plt.subplots(figsize=(10, 3.8), dpi=150)
    
    rects = ax.bar(sales_party_agg['Sales_Person'], sales_party_agg['Parties_Count'], color='#6366F1', width=0.4)

    # Set dynamic y limit for spacing
    max_c = sales_party_agg['Parties_Count'].max() if not sales_party_agg.empty else 5
    ax.set_ylim(0, max_c * 1.2)

    # Add Data Labels
    ax.bar_label(rects, padding=3, fontsize=8, fontweight='bold')

    ax.set_ylabel('Number of Parties Served', fontsize=9, fontweight='bold', color='#1E293B')
    ax.set_title('Salesperson-Wise Served Parties Count', fontsize=11, fontweight='bold', color='#0F172A', pad=10)
    ax.set_xticklabels(sales_party_agg['Sales_Person'], rotation=25, ha='right', fontsize=8)
    ax.grid(axis='y', linestyle='--', alpha=0.5)

    plt.tight_layout()
    img_buf = io.BytesIO()
    plt.savefig(img_buf, format='png', bbox_inches='tight')
    plt.close(fig)
    img_buf.seek(0)
    return img_buf

# ==========================================
# 3. REPORTLAB PDF DOCUMENT BUILDER
# ==========================================

def generate_pdf_report(excel_file):
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=landscape(A4),
        rightMargin=20, leftMargin=20, topMargin=25, bottomMargin=25
    )
    story = []

    # Typography & Color Palette
    title_style = ParagraphStyle('DocTitle', fontName='Helvetica-Bold', fontSize=15, textColor=colors.HexColor('#0F172A'), spaceAfter=4)
    subtitle_style = ParagraphStyle('DocSubTitle', fontName='Helvetica', fontSize=9, textColor=colors.HexColor('#64748B'), spaceAfter=12)
    section_style = ParagraphStyle('SectionHeader', fontName='Helvetica-Bold', fontSize=11, textColor=colors.HexColor('#1E293B'), spaceBefore=12, spaceAfter=6)
    
    tbl_header_style = ParagraphStyle('TableHeader', fontName='Helvetica-Bold', fontSize=7.5, textColor=colors.whitesmoke, alignment=1)
    tbl_cell_style = ParagraphStyle('TableCell', fontName='Helvetica', fontSize=7, textColor=colors.HexColor('#334155'), alignment=0)
    tbl_cell_center = ParagraphStyle('TableCellCenter', fontName='Helvetica', fontSize=7, textColor=colors.HexColor('#334155'), alignment=1)

    # Document Header
    story.append(Paragraph("DAILY GODOWN DISPATCH & STOCK MOVEMENTS REPORT", title_style))
    story.append(Paragraph("Consolidated report covering dispatches, delayed yesterday vehicle dispatches, and itemized stock balances.", subtitle_style))

    # Data Processing
    xls = pd.ExcelFile(excel_file)
    all_dispatches, all_summaries, all_items = [], [], []

    for sheet_name in xls.sheet_names:
        df_raw = pd.read_excel(xls, sheet_name=sheet_name)
        disp_df, stock_summary, item_df = parse_reporting_sections(df_raw, sheet_name)
        all_dispatches.append(disp_df)
        all_summaries.append(stock_summary)
        all_items.append(item_df)

    df_dispatches = pd.concat(all_dispatches, ignore_index=True)
    df_stock_summary = pd.DataFrame(all_summaries)
    df_item_stock = pd.concat(all_items, ignore_index=True)

    # --- SECTION 1: Salesperson Dispatch Summary ---
    story.append(Paragraph("1. Salesperson-Wise Dispatch Summary", section_style))
    
    sales_agg = df_dispatches.groupby(['Sales_Person', 'Sheet']).agg(
        Total_Dispatches=('Vehicle_No', 'count'),
        Parties=('Party_Name', lambda x: ', '.join([str(p) for p in x.dropna().unique() if str(p).strip()])),
        Adjustment_Notes=('Adjustment_Stock', lambda x: ', '.join([str(v).strip() for v in x.unique() if str(v).strip() not in ['-', 'nan', 'None']]) or 'None')
    ).reset_index()

    sales_table_data = [[
        Paragraph("Sales Person", tbl_header_style),
        Paragraph("Sheet / Date", tbl_header_style),
        Paragraph("Total Vehicles", tbl_header_style),
        Paragraph("Parties Served", tbl_header_style),
        Paragraph("Adjustment / Remarks", tbl_header_style)
    ]]

    for _, r in sales_agg.iterrows():
        sales_table_data.append([
            Paragraph(r['Sales_Person'], tbl_cell_style),
            Paragraph(str(r['Sheet']), tbl_cell_center),
            Paragraph(str(r['Total_Dispatches']), tbl_cell_center),
            Paragraph(r['Parties'], tbl_cell_style),
            Paragraph(r['Adjustment_Notes'], tbl_cell_style)
        ])

    t_sales = Table(sales_table_data, colWidths=[120, 80, 70, 270, 220])
    t_sales.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
    ]))
    story.append(t_sales)
    story.append(Spacer(1, 10))

    # --- SECTION 2: Dedicated Table for Yesterday Vehicles Dispatched Today ---
    story.append(Paragraph("2. Delayed Yesterday Vehicles Dispatched Today", section_style))
    
    # Target keyword search across forward-filled Adjustment_Stock
    yesterday_mask = df_dispatches['Adjustment_Stock'].astype(str).str.contains('yesterday|vehicle|\d{2}\.\d{2}\.\d{4}', case=False, na=False)
    df_yesterday_dispatches = df_dispatches[yesterday_mask].copy()

    yest_table_data = [[
        Paragraph("Sheet / Date", tbl_header_style),
        Paragraph("SR No", tbl_header_style),
        Paragraph("Vehicle No", tbl_header_style),
        Paragraph("Party Name", tbl_header_style),
        Paragraph("Sales Person", tbl_header_style),
        Paragraph("Dispatch Remark", tbl_header_style)
    ]]

    if not df_yesterday_dispatches.empty:
        for _, r in df_yesterday_dispatches.iterrows():
            yest_table_data.append([
                Paragraph(str(r['Sheet']), tbl_cell_center),
                Paragraph(str(r['SR_No']), tbl_cell_center),
                Paragraph(r['Vehicle_No'], tbl_cell_center),
                Paragraph(r['Party_Name'], tbl_cell_style),
                Paragraph(r['Sales_Person'], tbl_cell_style),
                Paragraph(r['Adjustment_Stock'], tbl_cell_style)
            ])
    else:
        yest_table_data.append([
            Paragraph("No delayed yesterday dispatches recorded.", tbl_cell_style),
            Paragraph("-", tbl_cell_center), Paragraph("-", tbl_cell_center),
            Paragraph("-", tbl_cell_style), Paragraph("-", tbl_cell_style), Paragraph("-", tbl_cell_style)
        ])

    t_yest = Table(yest_table_data, colWidths=[80, 50, 90, 250, 110, 180])
    t_yest.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#991B1B')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
    ]))
    story.append(t_yest)
    story.append(Spacer(1, 10))

    # --- SECTION 3: Godown Overall Stock & Production Summary ---
    story.append(Paragraph("3. Godown Overall Stock & Production Summary (MT)", section_style))

    stock_table_data = [[
        Paragraph("Sheet / Date", tbl_header_style),
        Paragraph("Opening Stock (MT)", tbl_header_style),
        Paragraph("Closing Stock (MT)", tbl_header_style),
        Paragraph("Yesterday Production (MT)", tbl_header_style),
        Paragraph("Dispatch Stock (MT)", tbl_header_style)
    ]]

    for _, r in df_stock_summary.iterrows():
        stock_table_data.append([
            Paragraph(str(r['Sheet']), tbl_cell_style),
            Paragraph(f"{r['Opening_Stock_MT']:,.2f}", tbl_cell_center),
            Paragraph(f"{r['Closing_Stock_MT']:,.2f}", tbl_cell_center),
            Paragraph(f"{r['Production_Yesterday_MT']:,.2f}", tbl_cell_center),
            Paragraph(f"{r['Dispatch_Stock_MT']:,.2f}", tbl_cell_center)
        ])

    t_stock = Table(stock_table_data, colWidths=[160, 150, 150, 150, 150])
    t_stock.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0D9488')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
    ]))
    story.append(t_stock)
    story.append(Spacer(1, 10))

    # --- SECTION 4: Itemized Stock Breakdown Table ---
    story.append(Paragraph("4. Item-Wise Stock Breakdown (Opening vs Closing)", section_style))

    item_stock_agg = df_item_stock.groupby('Particulars').agg({
        'Opening_MT': 'sum',
        'Closing_MT': 'sum',
        'Variance_MT': 'sum'
    }).reset_index()

    item_table_data = [[
        Paragraph("Particulars / Item", tbl_header_style),
        Paragraph("Opening Stock (MT)", tbl_header_style),
        Paragraph("Closing Stock (MT)", tbl_header_style),
        Paragraph("Variance (MT)", tbl_header_style)
    ]]

    for _, r in item_stock_agg.iterrows():
        item_table_data.append([
            Paragraph(r['Particulars'], tbl_cell_style),
            Paragraph(f"{r['Opening_MT']:,.2f}", tbl_cell_center),
            Paragraph(f"{r['Closing_MT']:,.2f}", tbl_cell_center),
            Paragraph(f"{r['Variance_MT']:,.2f}", tbl_cell_center)
        ])

    t_item = Table(item_table_data, colWidths=[220, 180, 180, 180])
    t_item.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#374151')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
    ]))
    story.append(t_item)
    story.append(Spacer(1, 10))

    # --- SECTION 5: Visual Analytics Charts ---
    story.append(Paragraph("5. Visual Analytics", section_style))

    sales_chart_buf = generate_sales_parties_chart(df_dispatches)
    if sales_chart_buf:
        story.append(Paragraph("A. Salesperson-Wise Parties Served", section_style))
        story.append(Image(sales_chart_buf, width=760, height=195))
        story.append(Spacer(1, 10))

    stock_chart_buf = generate_stock_comparison_chart(df_item_stock)
    if stock_chart_buf:
        story.append(Paragraph("B. Item Stock Opening vs Closing Comparison", section_style))
        story.append(Image(stock_chart_buf, width=760, height=205))

    doc.build(story)
    pdf_buffer.seek(0)
    return pdf_buffer, "Daily_Godown_Stock_Report.pdf"

# ==========================================
# 4. STREAMLIT APPLICATION INTERFACE
# ==========================================

st.set_page_config(page_title="Godown Reporting & Analytics", layout="wide")
st.title("Daily Godown Dispatch & Stock Comparison Generator")

uploaded_file = st.file_uploader("Upload Daily Reporting Excel Workbook (.xlsx)", type=["xlsx"])

if uploaded_file is not None:
    xls = pd.ExcelFile(uploaded_file)
    sheet_names = xls.sheet_names

    tab1, tab2 = st.tabs(["📊 KPI Dashboard & Sheet Comparison", "📄 PDF Report Generator"])

    # --- TAB 1: INTERACTIVE DASHBOARD ---
    with tab1:
        st.subheader("Sheet-by-Sheet KPI Overview")
        selected_sheet = st.selectbox("Select Sheet to Inspect:", sheet_names)
        
        df_selected = pd.read_excel(xls, sheet_name=selected_sheet)
        kpi_data = compute_kpi_summary(df_selected, selected_sheet)

        if kpi_data:
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Dispatches", kpi_data["total_dispatches"])
            col2.metric("Opening Stock (MT)", f"{kpi_data['opening_stock_mt']:,.2f}")
            col3.metric("Closing Stock (MT)", f"{kpi_data['closing_stock_mt']:,.2f}")
            col4.metric("Yesterday Production (MT)", f"{kpi_data['yesterday_production_mt']:,.2f}")

            st.markdown("---")
            st.write("**Item Breakdown (MT):**")
            st.dataframe(kpi_data["item_breakdown"], use_container_width=True)

    # --- TAB 2: PDF GENERATION ---
    with tab2:
        st.subheader("Generate & Download Executive PDF")
        st.write("Extracts all tabs, computes salesperson dispatches, stock balances, and embeds analytical visualizations into a consolidated landscape PDF.")
        
        if st.button("Generate Complete PDF Report"):
            with st.spinner("Processing dispatches, tabulating stock levels, and rendering PDF..."):
                pdf_data, filename = generate_pdf_report(uploaded_file)
                st.success("PDF generated successfully!")
                st.download_button(
                    label="Download Consolidated PDF",
                    data=pdf_data,
                    file_name=filename,
                    mime="application/pdf"
                )
