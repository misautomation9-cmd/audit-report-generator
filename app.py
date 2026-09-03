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
# 1. PARSING & DATA PROCESSING ENGINE
# ==========================================

def parse_qty(v):
    """Splits slash-separated quantities (e.g. '17.86/33.55') and returns sum."""
    if pd.isna(v) or not str(v).strip():
        return 0.0
    parts = re.split(r'[/+]', str(v).strip())
    total_qty = 0.0
    for part in parts:
        clean_num = re.sub(r'[^0-9\.]', '', part.strip())
        if clean_num:
            try:
                total_qty += float(clean_num)
            except ValueError:
                pass
    return total_qty

def parse_invoice_count(val):
    """Counts individual invoices in slash-separated string (e.g. '3651/3650' -> 2)."""
    if pd.isna(val) or not str(val).strip() or str(val).strip() == '-':
        return 0
    parts = [p.strip() for p in str(val).strip().split('/') if p.strip()]
    return len(parts)

def parse_loading_time_to_hours(val):
    """Converts strings like '18 HRS', '1.5 HRS', '20 MIN.' to float hours."""
    if pd.isna(val) or not str(val).strip():
        return 0.0
    val_str = str(val).upper().strip()
    
    hrs_match = re.search(r'([\d\.]+)\s*(?:HRS|HR|HOURS|HOUR)', val_str)
    if hrs_match:
        try:
            return float(hrs_match.group(1))
        except ValueError:
            pass
            
    min_match = re.search(r'([\d\.]+)\s*(?:MIN|MINS|MINUTES|MINUTE)', val_str)
    if min_match:
        try:
            return float(min_match.group(1)) / 60.0
        except ValueError:
            pass
            
    try:
        clean_num = re.sub(r'[^0-9\.]', '', val_str)
        return float(clean_num) if clean_num else 0.0
    except ValueError:
        return 0.0

def parse_freight_amount(val, qty_val=0.0):
    """Calculates total freight cost: Rate * Quantity if PMT, or direct fixed amount."""
    if pd.isna(val) or not str(val).strip() or str(val).strip() == '-':
        return 0.0
    
    val_str = str(val).upper().strip()
    is_pmt = any(k in val_str for k in ['PMT', 'TON', 'PER MT', '/MT'])
    clean_num = re.sub(r'[^0-9\.]', '', val_str.split('/')[0])
    try:
        rate_or_fixed = float(clean_num)
        return rate_or_fixed * float(qty_val) if is_pmt else rate_or_fixed
    except ValueError:
        return 0.0

def parse_godown_sections(df, sheet_name):
    """Parses 2-section layout from daily godown reporting sheets."""
    # Section 1: Dispatches & Salesperson Details
    disp_df = df.iloc[:, 0:6].copy()
    disp_df.columns = ['Date', 'SR_No', 'Vehicle_No', 'Party_Name', 'Sales_Person', 'Adjustment_Stock']
    
    disp_df['Date'] = disp_df['Date'].astype(str).str.strip().replace({'nan': np.nan, 'None': np.nan}).ffill().fillna(sheet_name)
    disp_df['Party_Name'] = disp_df['Party_Name'].astype(str).str.strip()
    disp_df = disp_df[~disp_df['Party_Name'].isin(['nan', 'None', '', 'Particulars'])]
    disp_df['Sales_Person'] = disp_df['Sales_Person'].astype(str).str.strip().replace({'nan': 'Unassigned', 'None': 'Unassigned'})
    disp_df['Vehicle_No'] = disp_df['Vehicle_No'].astype(str).str.strip()
    disp_df['Adjustment_Stock'] = disp_df['Adjustment_Stock'].replace({'nan': np.nan, 'None': np.nan, '': np.nan}).ffill().fillna('-')
    disp_df['Sheet'] = sheet_name

    # Section 2: Stock Balances & Production
    stock_df = df.iloc[:, 6:12].copy()
    stock_df.columns = ['Opening_Particulars', 'Opening_MT', 'Closing_Particulars', 'Closing_MT', 'Production_Yesterday', 'Dispatch_Stock']
    
    stock_summary = {
        'Sheet': sheet_name,
        'Opening_Stock_MT': pd.to_numeric(stock_df.iloc[0]['Opening_MT'], errors='coerce') or 0.0,
        'Closing_Stock_MT': pd.to_numeric(stock_df.iloc[0]['Closing_MT'], errors='coerce') or 0.0,
        'Production_Yesterday_MT': pd.to_numeric(stock_df.iloc[0]['Production_Yesterday'], errors='coerce') or 0.0,
        'Dispatch_Stock_MT': pd.to_numeric(stock_df.iloc[0]['Dispatch_Stock'], errors='coerce') or 0.0
    }
    
    item_df = stock_df.iloc[1:12].copy()
    item_df['Particulars'] = item_df['Opening_Particulars'].astype(str).str.strip()
    item_df = item_df[~item_df['Particulars'].isin(['nan', 'None', '', 'Particulars'])]
    item_df['Opening_MT'] = pd.to_numeric(item_df['Opening_MT'], errors='coerce').fillna(0.0)
    item_df['Closing_MT'] = pd.to_numeric(item_df['Closing_MT'], errors='coerce').fillna(0.0)
    item_df['Variance_MT'] = item_df['Closing_MT'] - item_df['Opening_MT']
    item_df['Sheet'] = sheet_name

    return disp_df, stock_summary, item_df[['Sheet', 'Particulars', 'Opening_MT', 'Closing_MT', 'Variance_MT']]

def compute_operational_kpis(df, date_str):
    """Computes KPIs for standard dispatch audit tables."""
    if df is None or df.empty:
        return {}

    df_c = df.copy()
    df_c.columns = [str(c).strip() for c in df_c.columns]
    col_map = {c.lower(): c for c in df_c.columns}
    
    qnty_col = next((col_map[c] for c in col_map if any(k in c for k in ['qnty', 'quantity', 'qty', 'weight', 'tonnage'])), None)
    qty_series = df_c[qnty_col].apply(parse_qty) if qnty_col else pd.Series([0.0] * len(df_c))
    total_qty = qty_series.sum()

    inv_col = next((col_map[c] for c in col_map if any(k in c for k in ['invoice', 'inv no', 'inv. no'])), None)
    total_invoices = df_c[inv_col].apply(parse_invoice_count).sum() if inv_col else 0

    time_col = next((col_map[c] for c in col_map if any(k in c for k in ['loading time', 'time', 'duration', 'loading'])), None)
    hours_series = df_c[time_col].apply(parse_loading_time_to_hours) if time_col else pd.Series([0.0] * len(df_c))
    total_loading_hours = hours_series.sum()
    avg_loading_hours = hours_series.mean() if len(hours_series) > 0 else 0.0

    freight_col = next((col_map[c] for c in col_map if 'freight' in c), None)
    total_freight_amt = sum([parse_freight_amount(df_c[freight_col].iloc[i], qty_series.iloc[i]) for i in range(len(df_c))]) if freight_col else 0.0

    party_col = next((col_map[c] for c in col_map if any(k in c for k in ['party', 'customer', 'name'])), None)
    unique_parties = df_c[party_col].nunique() if party_col else len(df_c)

    yesterday_pending, material_pending = 0, 0
    for _, row in df_c.iterrows():
        row_str = " ".join([str(val).lower() for val in row.values if pd.notna(val)])
        if 'yesterday pending' in row_str or 'yp' in row_str:
            yesterday_pending += 1
        elif any(k in row_str for k in ['material pending', 'unbilled', 'hold']):
            material_pending += 1

    return {
        "date": date_str,
        "total_qty": total_qty,
        "total_invoices": total_invoices,
        "total_loading_hours": total_loading_hours,
        "avg_loading_hours": avg_loading_hours,
        "total_freight": total_freight_amt,
        "party_count": unique_parties,
        "yesterday_pending": yesterday_pending,
        "material_pending": material_pending,
        "total_dispatches": len(df_c)
    }

# ==========================================
# 2. CHARTS GENERATION ENGINE
# ==========================================

def generate_stock_comparison_chart(df_item_stock):
    if df_item_stock.empty:
        return None
    agg_item = df_item_stock.groupby('Particulars').agg({'Opening_MT': 'sum', 'Closing_MT': 'sum'}).reset_index()

    fig, ax = plt.subplots(figsize=(10, 3.8), dpi=150)
    x = np.arange(len(agg_item['Particulars']))
    width = 0.35

    rects1 = ax.bar(x - width/2, agg_item['Opening_MT'], width, label='Opening Stock (MT)', color='#3B82F6')
    rects2 = ax.bar(x + width/2, agg_item['Closing_MT'], width, label='Closing Stock (MT)', color='#10B981')

    max_val = max(agg_item['Opening_MT'].max(), agg_item['Closing_MT'].max()) if not agg_item.empty else 100
    ax.set_ylim(0, max_val * 1.18)

    ax.bar_label(rects1, padding=3, fmt='%.1f', fontsize=6.5, fontweight='bold')
    ax.bar_label(rects2, padding=3, fmt='%.1f', fontsize=6.5, fontweight='bold')

    ax.set_ylabel('Metric Tons (MT)', fontsize=8, fontweight='bold')
    ax.set_title('Item-Wise Opening vs Closing Stock Balance', fontsize=10, fontweight='bold', pad=8)
    ax.set_xticks(x)
    ax.set_xticklabels(agg_item['Particulars'], rotation=30, ha='right', fontsize=7.5)
    ax.legend(frameon=True, facecolor='#F8FAFC')
    ax.grid(axis='y', linestyle='--', alpha=0.5)

    plt.tight_layout()
    img_buf = io.BytesIO()
    plt.savefig(img_buf, format='png', bbox_inches='tight')
    plt.close(fig)
    img_buf.seek(0)
    return img_buf

def generate_sales_parties_chart(df_dispatches):
    if df_dispatches.empty:
        return None
    sales_party_agg = df_dispatches.groupby('Sales_Person')['Party_Name'].nunique().reset_index()
    sales_party_agg.columns = ['Sales_Person', 'Parties_Count']
    sales_party_agg = sales_party_agg.sort_values(by='Parties_Count', ascending=False)

    fig, ax = plt.subplots(figsize=(10, 3.5), dpi=150)
    rects = ax.bar(sales_party_agg['Sales_Person'], sales_party_agg['Parties_Count'], color='#6366F1', width=0.4)

    max_c = sales_party_agg['Parties_Count'].max() if not sales_party_agg.empty else 5
    ax.set_ylim(0, max_c * 1.2)

    ax.bar_label(rects, padding=3, fontsize=7.5, fontweight='bold')
    ax.set_ylabel('Number of Parties Served', fontsize=8, fontweight='bold')
    ax.set_title('Salesperson-Wise Served Parties Count', fontsize=10, fontweight='bold', pad=8)
    ax.set_xticklabels(sales_party_agg['Sales_Person'], rotation=20, ha='right', fontsize=7.5)
    ax.grid(axis='y', linestyle='--', alpha=0.5)

    plt.tight_layout()
    img_buf = io.BytesIO()
    plt.savefig(img_buf, format='png', bbox_inches='tight')
    plt.close(fig)
    img_buf.seek(0)
    return img_buf

def generate_audit_comparison_chart(kpi1, kpi2, dept_name):
    fig, ax = plt.subplots(figsize=(10, 3.5), dpi=150)
    metrics = ['Dispatched Qty\n(MT)', 'Total Invoices\nGenerated', 'Loading Hours\n(Hrs)', 'Total Freight\n(₹)', 'Parties\nServiced']
    d1_vals = [kpi1['total_qty'], kpi1['total_invoices'], kpi1['total_loading_hours'], kpi1['total_freight'], kpi1['party_count']]
    d2_vals = [kpi2['total_qty'], kpi2['total_invoices'], kpi2['total_loading_hours'], kpi2['total_freight'], kpi2['party_count']]

    x = range(len(metrics))
    width = 0.35

    rects1 = ax.bar([i - width/2 for i in x], d1_vals, width, label=kpi1['date'], color='#2563EB')
    rects2 = ax.bar([i + width/2 for i in x], d2_vals, width, label=kpi2['date'], color='#0D9488')

    ax.set_title(f'Operational Audit & Freight Variance Comparison - {dept_name}', fontsize=10, fontweight='bold', pad=8)
    ax.set_xticks(x)
    ax.set_xticklabels(metrics, fontsize=7.5)
    ax.legend(fontsize=8)
    ax.grid(axis='y', linestyle='--', alpha=0.5)

    for rect in rects1 + rects2:
        h = rect.get_height()
        ax.annotate(f'{h:,.1f}' if isinstance(h, float) else f'{int(h)}',
                    xy=(rect.get_x() + rect.get_width() / 2, h),
                    xytext=(0, 3), textcoords="offset points",
                    ha='center', va='bottom', fontsize=6.5, fontweight='bold')

    plt.tight_layout()
    img_buf = io.BytesIO()
    plt.savefig(img_buf, format='png', bbox_inches='tight')
    plt.close(fig)
    img_buf.seek(0)
    return img_buf

# ==========================================
# 3. CONSOLIDATED PDF BUILDER
# ==========================================

def append_total_row_to_df(df):
    if df is None or df.empty:
        return df

    df_total = df.copy()
    df_c_cols = [str(c).strip().lower() for c in df_total.columns]
    
    qnty_col = next((df_total.columns[i] for i, c in enumerate(df_c_cols) if any(k in c for k in ['qnty', 'quantity', 'qty', 'weight'])), None)
    qty_series = df_total[qnty_col].apply(parse_qty) if qnty_col else pd.Series([0.0] * len(df_total))

    total_row = {}
    has_numeric = False
    ignore_keys = ['date', 's.no', 'phone', 'code', 'id', 'sr no', 'driver', 'eway', 'bill', 'no']

    for col in df_total.columns:
        col_str = str(col).lower()
        if any(k in col_str for k in ['invoice', 'inv no', 'inv. no']):
            inv_sum = df_total[col].apply(parse_invoice_count).sum()
            total_row[col] = f"{inv_sum} INVOICES"
            has_numeric = True
        elif 'freight' in col_str:
            freight_sum = sum([parse_freight_amount(df_total[col].iloc[i], qty_series.iloc[i]) for i in range(len(df_total))])
            total_row[col] = f"₹{freight_sum:,.2f}"
            has_numeric = True
        elif any(k in col_str for k in ['loading time', 'time', 'duration']):
            time_sum = df_total[col].apply(parse_loading_time_to_hours).sum()
            total_row[col] = f"{time_sum:,.2f} HRS"
            has_numeric = True
        elif any(k in col_str for k in ['qnty', 'quantity', 'qty', 'weight']):
            total_row[col] = f"{qty_series.sum():,.2f}"
            has_numeric = True
        else:
            def parse_generic_num(v):
                if pd.isna(v): return None
                try: return float(re.sub(r'[^0-9\.]', '', str(v)))
                except: return None

            numeric_series = df_total[col].apply(parse_generic_num)
            if numeric_series.notna().sum() > 0 and not any(k in col_str for k in ignore_keys):
                total_row[col] = numeric_series.sum()
                has_numeric = True
            else:
                total_row[col] = ""
    
    if has_numeric:
        total_row[df_total.columns[0]] = "TOTAL"
        df_total = pd.concat([df_total, pd.DataFrame([total_row])], ignore_index=True)
    return df_total

def generate_unified_pdf(excel_file):
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=landscape(A4),
        rightMargin=20, leftMargin=20, topMargin=25, bottomMargin=25
    )
    story = []
    printable_width = landscape(A4)[0] - 40

    # Typography Styles
    title_style = ParagraphStyle('DocTitle', fontName='Helvetica-Bold', fontSize=15, textColor=colors.HexColor('#0F172A'), spaceAfter=2)
    subtitle_style = ParagraphStyle('DocSubTitle', fontName='Helvetica', fontSize=8.5, textColor=colors.HexColor('#64748B'), spaceAfter=10)
    section_style = ParagraphStyle('SectionHeader', fontName='Helvetica-Bold', fontSize=10.5, textColor=colors.HexColor('#1E293B'), spaceBefore=10, spaceAfter=5)
    sub_section_style = ParagraphStyle('SubSectionHeader', fontName='Helvetica-Bold', fontSize=9, textColor=colors.HexColor('#2563EB'), spaceBefore=6, spaceAfter=4)

    tbl_header_style = ParagraphStyle('TableHeader', fontName='Helvetica-Bold', fontSize=7, leading=8, textColor=colors.whitesmoke, alignment=1)
    tbl_cell_style = ParagraphStyle('TableCell', fontName='Helvetica', fontSize=6.5, leading=7.5, textColor=colors.HexColor('#334155'), alignment=0)
    tbl_cell_center = ParagraphStyle('TableCellCenter', fontName='Helvetica', fontSize=6.5, leading=7.5, textColor=colors.HexColor('#334155'), alignment=1)
    tbl_total_style = ParagraphStyle('TableTotal', fontName='Helvetica-Bold', fontSize=6.5, leading=8, textColor=colors.HexColor('#0F172A'), alignment=0)

    xls = pd.ExcelFile(excel_file)
    
    # Classify sheets by layout structure
    godown_sheets = []
    audit_dept_groups = {}
    pattern = r"^(.*?)[-\s](\d{1,2}[/\.-]\d{1,2}[/\.-]\d{2,4})$"

    for sheet in xls.sheet_names:
        df_test = pd.read_excel(xls, sheet_name=sheet)
        if df_test.shape[1] >= 12 and any(df_test.iloc[:, 0].astype(str).str.contains('GD|Godown|Sheet', case=False, na=False)):
            godown_sheets.append(sheet)
        else:
            match = re.match(pattern, sheet.strip())
            if match:
                dept_name = match.group(1).strip()
                date_val = match.group(2).strip()
                audit_dept_groups.setdefault(dept_name, []).append((date_val, sheet))
            else:
                audit_dept_groups.setdefault(sheet.strip(), []).append(("Raw Data", sheet))

    # ==========================================
    # PART A: GODOWN STOCK & DISPATCH REPORT
    # ==========================================
    if godown_sheets:
        story.append(Paragraph("DAILY GODOWN DISPATCH & STOCK MOVEMENTS REPORT", title_style))
        story.append(Paragraph("Consolidated report covering dispatches, delayed yesterday vehicle dispatches, and itemized stock balances.", subtitle_style))

        all_dispatches, all_summaries, all_items = [], [], []

        for sheet_name in godown_sheets:
            df_raw = pd.read_excel(xls, sheet_name=sheet_name)
            disp_df, stock_summary, item_df = parse_godown_sections(df_raw, sheet_name)
            all_dispatches.append(disp_df)
            all_summaries.append(stock_summary)
            all_items.append(item_df)

        df_dispatches = pd.concat(all_dispatches, ignore_index=True)
        df_stock_summary = pd.DataFrame(all_summaries)
        df_item_stock = pd.concat(all_items, ignore_index=True)

        # 1. Salesperson Summary Table
        story.append(Paragraph("1. Salesperson-Wise Dispatch Summary", section_style))
        sales_agg = df_dispatches.groupby(['Sales_Person', 'Sheet']).agg(
            Total_Dispatches=('Vehicle_No', 'count'),
            Parties=('Party_Name', lambda x: ', '.join([str(p) for p in x.dropna().unique() if str(p).strip()])),
            Adjustment_Notes=('Adjustment_Stock', lambda x: ', '.join([str(v).strip() for v in x.unique() if str(v).strip() not in ['-', 'nan', 'None']]) or 'None')
        ).reset_index()

        sales_table_data = [[
            Paragraph("Sales Person", tbl_header_style), Paragraph("Sheet / Date", tbl_header_style),
            Paragraph("Total Vehicles", tbl_header_style), Paragraph("Parties Served", tbl_header_style),
            Paragraph("Adjustment / Remarks", tbl_header_style)
        ]]

        for _, r in sales_agg.iterrows():
            sales_table_data.append([
                Paragraph(r['Sales_Person'], tbl_cell_style), Paragraph(str(r['Sheet']), tbl_cell_center),
                Paragraph(str(r['Total_Dispatches']), tbl_cell_center), Paragraph(r['Parties'], tbl_cell_style),
                Paragraph(r['Adjustment_Notes'], tbl_cell_style)
            ])

        t_sales = Table(sales_table_data, colWidths=[110, 75, 65, 260, 210])
        t_sales.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#CBD5E1')),
            ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
        ]))
        story.append(t_sales)
        story.append(Spacer(1, 8))

        # 2. Yesterday Dispatches Table
        story.append(Paragraph("2. Delayed Yesterday Vehicles Dispatched Today", section_style))
        yesterday_mask = df_dispatches['Adjustment_Stock'].astype(str).str.contains('yesterday|vehicle|\d{2}\.\d{2}\.\d{4}', case=False, na=False)
        df_yesterday_dispatches = df_dispatches[yesterday_mask].copy()

        yest_table_data = [[
            Paragraph("Sheet / Date", tbl_header_style), Paragraph("SR No", tbl_header_style),
            Paragraph("Vehicle No", tbl_header_style), Paragraph("Party Name", tbl_header_style),
            Paragraph("Sales Person", tbl_header_style), Paragraph("Dispatch Remark", tbl_header_style)
        ]]

        if not df_yesterday_dispatches.empty:
            for _, r in df_yesterday_dispatches.iterrows():
                yest_table_data.append([
                    Paragraph(str(r['Sheet']), tbl_cell_center), Paragraph(str(r['SR_No']), tbl_cell_center),
                    Paragraph(r['Vehicle_No'], tbl_cell_center), Paragraph(r['Party_Name'], tbl_cell_style),
                    Paragraph(r['Sales_Person'], tbl_cell_style), Paragraph(r['Adjustment_Stock'], tbl_cell_style)
                ])
        else:
            yest_table_data.append([
                Paragraph("No delayed yesterday dispatches recorded.", tbl_cell_style),
                Paragraph("-", tbl_cell_center), Paragraph("-", tbl_cell_center),
                Paragraph("-", tbl_cell_style), Paragraph("-", tbl_cell_style), Paragraph("-", tbl_cell_style)
            ])

        t_yest = Table(yest_table_data, colWidths=[75, 45, 85, 240, 105, 170])
        t_yest.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#991B1B')),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#CBD5E1')),
            ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
        ]))
        story.append(t_yest)
        story.append(Spacer(1, 8))

        # 3. Overall Stock Summary Table
        story.append(Paragraph("3. Godown Overall Stock & Production Summary (MT)", section_style))
        stock_table_data = [[
            Paragraph("Sheet / Date", tbl_header_style), Paragraph("Opening Stock (MT)", tbl_header_style),
            Paragraph("Closing Stock (MT)", tbl_header_style), Paragraph("Yesterday Production (MT)", tbl_header_style),
            Paragraph("Dispatch Stock (MT)", tbl_header_style)
        ]]

        for _, r in df_stock_summary.iterrows():
            stock_table_data.append([
                Paragraph(str(r['Sheet']), tbl_cell_style), Paragraph(f"{r['Opening_Stock_MT']:,.2f}", tbl_cell_center),
                Paragraph(f"{r['Closing_Stock_MT']:,.2f}", tbl_cell_center), Paragraph(f"{r['Production_Yesterday_MT']:,.2f}", tbl_cell_center),
                Paragraph(f"{r['Dispatch_Stock_MT']:,.2f}", tbl_cell_center)
            ])

        t_stock = Table(stock_table_data, colWidths=[150, 140, 140, 145, 145])
        t_stock.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0D9488')),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#CBD5E1')),
            ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
        ]))
        story.append(t_stock)
        story.append(Spacer(1, 8))

        # 4. Itemized Stock Table
        story.append(Paragraph("4. Item-Wise Stock Breakdown (Opening vs Closing)", section_style))
        item_stock_agg = df_item_stock.groupby('Particulars').agg({'Opening_MT': 'sum', 'Closing_MT': 'sum', 'Variance_MT': 'sum'}).reset_index()

        item_table_data = [[
            Paragraph("Particulars / Item", tbl_header_style), Paragraph("Opening Stock (MT)", tbl_header_style),
            Paragraph("Closing Stock (MT)", tbl_header_style), Paragraph("Variance (MT)", tbl_header_style)
        ]]

        for _, r in item_stock_agg.iterrows():
            item_table_data.append([
                Paragraph(r['Particulars'], tbl_cell_style), Paragraph(f"{r['Opening_MT']:,.2f}", tbl_cell_center),
                Paragraph(f"{r['Closing_MT']:,.2f}", tbl_cell_center), Paragraph(f"{r['Variance_MT']:,.2f}", tbl_cell_center)
            ])

        t_item = Table(item_table_data, colWidths=[210, 170, 170, 170])
        t_item.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#374151')),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#CBD5E1')),
            ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
        ]))
        story.append(t_item)
        story.append(Spacer(1, 8))

        # 5. Visual Analytics Charts
        story.append(Paragraph("5. Visual Analytics", section_style))
        sales_chart_buf = generate_sales_parties_chart(df_dispatches)
        if sales_chart_buf:
            story.append(Paragraph("A. Salesperson-Wise Parties Served", sub_section_style))
            story.append(Image(sales_chart_buf, width=720, height=185))
            story.append(Spacer(1, 6))

        stock_chart_buf = generate_stock_comparison_chart(df_item_stock)
        if stock_chart_buf:
            story.append(Paragraph("B. Item Stock Opening vs Closing Comparison", sub_section_style))
            story.append(Image(stock_chart_buf, width=720, height=195))

        if audit_dept_groups:
            story.append(PageBreak())

    # ==========================================
    # PART B: OPERATIONAL AUDIT & FREIGHT REPORT
    # ==========================================
    if audit_dept_groups:
        story.append(Paragraph("DYNAMIC DATE-WISE AUDIT & OPERATIONAL COMPARISON REPORT", title_style))
        story.append(Paragraph("Dispatch Volume, Freight Costs, Loading Time & Pending Variance Analysis", subtitle_style))

        for dept_idx, (dept, tabs) in enumerate(audit_dept_groups.items(), start=1):
            dept_elements = [Paragraph(f"{dept_idx}. Department / Module: {dept}", section_style)]
            
            if len(tabs) >= 2:
                first_date, tab1 = tabs[0]
                second_date, tab2 = tabs[1]
                df1 = pd.read_excel(xls, tab1)
                df2 = pd.read_excel(xls, tab2)

                if not df1.empty and not df2.empty:
                    kpi1 = compute_operational_kpis(df1, first_date)
                    kpi2 = compute_operational_kpis(df2, second_date)

                    summary_data = [
                        [Paragraph("<b>Operational / Cost Metric</b>", tbl_header_style), Paragraph(f"<b>{first_date}</b>", tbl_header_style), Paragraph(f"<b>{second_date}</b>", tbl_header_style), Paragraph("<b>Operational Variance</b>", tbl_header_style)],
                        [Paragraph("<b>Total Invoices Generated</b>", tbl_cell_style), Paragraph(f"{kpi1['total_invoices']} Invoices", tbl_cell_style), Paragraph(f"{kpi2['total_invoices']} Invoices", tbl_cell_style), Paragraph(f"<b>{kpi2['total_invoices'] - kpi1['total_invoices']:+} Invoices</b>", tbl_cell_style)],
                        [Paragraph("<b>Dispatched Quantity Tonnage</b>", tbl_cell_style), Paragraph(f"{kpi1['total_qty']:,.2f} MT", tbl_cell_style), Paragraph(f"{kpi2['total_qty']:,.2f} MT", tbl_cell_style), Paragraph(f"<b>{kpi2['total_qty'] - kpi1['total_qty']:+,.2f} MT</b>", tbl_cell_style)],
                        [Paragraph("<b>Calculated Total Freight Cost</b>", tbl_cell_style), Paragraph(f"₹{kpi1['total_freight']:,.2f}", tbl_cell_style), Paragraph(f"₹{kpi2['total_freight']:,.2f}", tbl_cell_style), Paragraph(f"<b>₹{kpi2['total_freight'] - kpi1['total_freight']:+,.2f}</b>", tbl_cell_style)],
                        [Paragraph("<b>Total Loading Duration Hours</b>", tbl_cell_style), Paragraph(f"{kpi1['total_loading_hours']:,.2f} Hrs", tbl_cell_style), Paragraph(f"{kpi2['total_loading_hours']:,.2f} Hrs", tbl_cell_style), Paragraph(f"<b>{kpi2['total_loading_hours'] - kpi1['total_loading_hours']:+,.2f} Hrs</b>", tbl_cell_style)],
                        [Paragraph("<b>Average Loading Time / Vehicle</b>", tbl_cell_style), Paragraph(f"{kpi1['avg_loading_hours']:,.2f} Hrs", tbl_cell_style), Paragraph(f"{kpi2['avg_loading_hours']:,.2f} Hrs", tbl_cell_style), Paragraph(f"{kpi2['avg_loading_hours'] - kpi1['avg_loading_hours']:+.2f} Hrs", tbl_cell_style)],
                        [Paragraph("<b>Number of Parties Serviced</b>", tbl_cell_style), Paragraph(f"{kpi1['party_count']}", tbl_cell_style), Paragraph(f"{kpi2['party_count']}", tbl_cell_style), Paragraph(f"{kpi2['party_count'] - kpi1['party_count']:+} Parties", tbl_cell_style)],
                        [Paragraph("<b>Yesterday Pending Orders</b>", tbl_cell_style), Paragraph(f"{kpi1['yesterday_pending']}", tbl_cell_style), Paragraph(f"{kpi2['yesterday_pending']}", tbl_cell_style), Paragraph(f"{kpi2['yesterday_pending'] - kpi1['yesterday_pending']:+} Orders", tbl_cell_style)],
                        [Paragraph("<b>Material / Billing Pending</b>", tbl_cell_style), Paragraph(f"{kpi1['material_pending']}", tbl_cell_style), Paragraph(f"{kpi2['material_pending']}", tbl_cell_style), Paragraph(f"{kpi2['material_pending'] - kpi1['material_pending']:+} Orders", tbl_cell_style)]
                    ]

                    kpi_table = Table(summary_data, colWidths=[200, 150, 150, 220])
                    kpi_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
                        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#CBD5E1')),
                        ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')])
                    ]))

                    chart_img = generate_audit_comparison_chart(kpi1, kpi2, dept)

                    dept_elements.extend([
                        Paragraph(f"<b>Operational Audit Comparison: {first_date} vs {second_date}</b>", sub_section_style),
                        kpi_table, Spacer(1, 6),
                        Image(chart_img, width=540, height=200), Spacer(1, 8)
                    ])

            for date_str, sheet_name in tabs:
                df_raw = pd.read_excel(xls, sheet_name)
                df_clean = append_total_row_to_df(df_raw.dropna(how='all').dropna(how='all', axis=1))
                if not df_clean.empty and len(df_clean.columns) > 0:
                    col_w = printable_width / len(df_clean.columns)
                    table_data = [[Paragraph(str(col), tbl_header_style) for col in df_clean.columns]]
                    last_row_idx = len(df_clean) - 1
                    has_total = (df_clean.iloc[last_row_idx][df_clean.columns[0]] == "TOTAL")

                    for r_idx, row in df_clean.iterrows():
                        row_data = []
                        curr_style = tbl_total_style if (has_total and r_idx == last_row_idx) else tbl_cell_style
                        for cell in row:
                            if pd.isna(cell) or cell == "":
                                text = ""
                            elif isinstance(cell, (int, float)):
                                text = f"{cell:,.2f}".rstrip('0').rstrip('.') if isinstance(cell, float) else f"{cell:,}"
                            else:
                                text = str(cell).strip()
                            row_data.append(Paragraph(text, curr_style))
                        table_data.append(row_data)

                    t_raw = Table(table_data, colWidths=[col_w] * len(df_clean.columns), repeatRows=1)
                    t_style = [
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                        ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#CBD5E1')),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -2 if has_total else -1), [colors.white, colors.HexColor('#F8FAFC')])
                    ]
                    if has_total:
                        t_style.extend([
                            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#E2E8F0')),
                            ('LINEABOVE', (0, -1), (-1, -1), 1.2, colors.HexColor('#1E293B'))
                        ])
                    t_raw.setStyle(TableStyle(t_style))

                    dept_elements.extend([
                        Paragraph(f"<b>Tab Log: {date_str if date_str != 'Raw Data' else sheet_name}</b>", sub_section_style),
                        t_raw, Spacer(1, 8)
                    ])

            story.append(KeepTogether(dept_elements))
            if dept_idx < len(audit_dept_groups):
                story.append(PageBreak())

    doc.build(story)
    pdf_buffer.seek(0)
    return pdf_buffer, "Unified_Godown_And_Dispatch_Audit_Report.pdf"

# ==========================================
# 4. STREAMLIT USER INTERFACE
# ==========================================

st.set_page_config(page_title="Enterprise Reporting & Audit System", layout="wide")
st.title("📦 Unified Enterprise Reporting Portal")
st.write("Generates PDF reports covering Godown Stock Movements, Salesperson Dispatches, Freight Costs, and Operational Audits.")

uploaded_file = st.file_uploader("Upload Multi-Tab Excel Reporting Workbook (.xlsx)", type=["xlsx"])

if uploaded_file is not None:
    xls = pd.ExcelFile(uploaded_file)
    sheet_names = xls.sheet_names

    tab1, tab2 = st.tabs(["📊 Interactive KPI Portal", "📄 Consolidated PDF Generator"])

    with tab1:
        st.subheader("Tab Inspector & Operational Overview")
        selected_sheet = st.selectbox("Select Excel Sheet to Analyze:", sheet_names)
        df_selected = pd.read_excel(xls, sheet_name=selected_sheet)

        if df_selected.shape[1] >= 12 and any(df_selected.iloc[:, 0].astype(str).str.contains('GD|Godown|Sheet', case=False, na=False)):
            disp_df, stock_summary, item_df = parse_godown_sections(df_selected, selected_sheet)
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Dispatches", len(disp_df))
            col2.metric("Opening Stock (MT)", f"{stock_summary['Opening_Stock_MT']:,.2f}")
            col3.metric("Closing Stock (MT)", f"{stock_summary['Closing_Stock_MT']:,.2f}")
            col4.metric("Yesterday Production (MT)", f"{stock_summary['Production_Yesterday_MT']:,.2f}")

            st.markdown("---")
            st.write("**Item-Wise Stock Breakdown:**")
            st.dataframe(item_df, use_container_width=True)
        else:
            kpi_data = compute_operational_kpis(df_selected, selected_sheet)
            if kpi_data:
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Dispatched Tonnage (MT)", f"{kpi_data['total_qty']:,.2f}")
                col2.metric("Invoices Generated", kpi_data['total_invoices'])
                col3.metric("Loading Time (Hrs)", f"{kpi_data['total_loading_hours']:,.2f}")
                col4.metric("Calculated Freight (₹)", f"₹{kpi_data['total_freight']:,.2f}")

            st.markdown("---")
            st.write("**Raw Data Logs:**")
            st.dataframe(df_selected, use_container_width=True)

    with tab2:
        st.subheader("Generate Executive Consolidated PDF")
        st.write("Generates a landscape PDF with styled tables, automatic sub-totals, and embedded charts.")

        if st.button("Generate Consolidated PDF Report"):
            with st.spinner("Processing stock balances, freight, loading hours, and charts..."):
                pdf_bytes, filename = generate_unified_pdf(uploaded_file)
                st.success("PDF generated successfully!")
                st.download_button(
                    label="📥 Download Unified PDF Report",
                    data=pdf_bytes,
                    file_name=filename,
                    mime="application/pdf"
                )
