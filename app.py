import io
import re
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether, PageBreak
)
from reportlab.lib.styles import ParagraphStyle

def generate_pdf_report(excel_file):
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=landscape(A4),
        rightMargin=20, leftMargin=20, topMargin=25, bottomMargin=25
    )
    story = []
    printable_width = landscape(A4)[0] - 40  # ~801 pt printable width

    # Typography Styles
    title_style = ParagraphStyle('DocTitle', fontName='Helvetica-Bold', fontSize=16, textColor=colors.HexColor('#1E293B'), spaceAfter=2)
    subtitle_style = ParagraphStyle('DocSubtitle', fontName='Helvetica', fontSize=9, textColor=colors.HexColor('#64748B'), spaceAfter=10)
    section_style = ParagraphStyle('SectionHeader', fontName='Helvetica-Bold', fontSize=11, textColor=colors.HexColor('#0F172A'), spaceBefore=10, spaceAfter=6)
    sub_section_style = ParagraphStyle('SubSectionHeader', fontName='Helvetica-Bold', fontSize=9.5, textColor=colors.HexColor('#2563EB'), spaceBefore=6, spaceAfter=4)
    tbl_header_style = ParagraphStyle('TableHeader', fontName='Helvetica-Bold', fontSize=6.5, leading=8, textColor=colors.whitesmoke, alignment=1)
    tbl_cell_style = ParagraphStyle('TableCell', fontName='Helvetica', fontSize=6, leading=7.5, textColor=colors.HexColor('#334155'), alignment=0)
    tbl_total_style = ParagraphStyle('TableTotal', fontName='Helvetica-Bold', fontSize=6.5, leading=8, textColor=colors.HexColor('#0F172A'), alignment=0)

    def compute_kpi_summary(df, date_str):
        """Calculates key performance indicators including Loading Hours for a single tab."""
        if df is None or df.empty:
            return {}

        df_c = df.copy()
        df_c.columns = [str(c).strip() for c in df_c.columns]
        col_map = {c.lower(): c for c in df_c.columns}
        
        # 1. Total Dispatched Quantity
        qnty_col = next((col_map[c] for c in col_map if any(k in c for k in ['qnty', 'quantity', 'qty', 'weight', 'tonnage'])), None)
        total_qty = 0.0
        if qnty_col:
            def parse_qty(v):
                if pd.isna(v): return 0.0
                v_str = str(v).split('/')[0].strip()
                try: return float(v_str)
                except: return 0.0
            total_qty = df_c[qnty_col].apply(parse_qty).sum()

        # 2. Loading Hours / Duration Calculation
        time_col = next((col_map[c] for c in col_map if any(k in c for k in ['time', 'duration', 'loading', 'hours', 'hr'])), None)
        total_loading_hours = 0.0
        avg_loading_hours = 0.0
        if time_col:
            def parse_hours(v):
                if pd.isna(v): return 0.0
                try: return float(v)
                except: return 0.0
            hours_series = df_c[time_col].apply(parse_hours)
            total_loading_hours = hours_series.sum()
            avg_loading_hours = hours_series.mean() if len(hours_series) > 0 else 0.0

        # 3. Party Count
        party_col = next((col_map[c] for c in col_map if any(k in c for k in ['party', 'customer', 'name', 'client'])), None)
        unique_parties = df_c[party_col].nunique() if party_col else len(df_c)

        # 4. Pending Status Breakdown
        yesterday_pending, material_pending = 0, 0
        for _, row in df_c.iterrows():
            row_str = " ".join([str(val).lower() for val in row.values if pd.notna(val)])
            if 'yesterday pending' in row_str or 'yp' in row_str:
                yesterday_pending += 1
            elif 'material pending' in row_str or 'unbilled' in row_str or 'hold' in row_str:
                material_pending += 1

        return {
            "date": date_str,
            "total_qty": total_qty,
            "total_loading_hours": total_loading_hours,
            "avg_loading_hours": avg_loading_hours,
            "party_count": unique_parties,
            "yesterday_pending": yesterday_pending,
            "material_pending": material_pending,
            "total_dispatches": len(df_c)
        }

    def generate_chart_img(kpi1, kpi2, dept_name):
        """Generates a comparison bar chart including Loading Hours."""
        fig, ax = plt.subplots(figsize=(7.5, 3.0), dpi=150)
        
        metrics = ['Dispatched Qty\n(MT)', 'Loading Hours\n(Hrs)', 'Parties\nServiced', 'Yesterday\nPending', 'Material\nPending']
        d1_vals = [kpi1['total_qty'], kpi1['total_loading_hours'], kpi1['party_count'], kpi1['yesterday_pending'], kpi1['material_pending']]
        d2_vals = [kpi2['total_qty'], kpi2['total_loading_hours'], kpi2['party_count'], kpi2['yesterday_pending'], kpi2['material_pending']]

        x = range(len(metrics))
        width = 0.35

        rects1 = ax.bar([i - width/2 for i in x], d1_vals, width, label=kpi1['date'], color='#2563EB')
        rects2 = ax.bar([i + width/2 for i in x], d2_vals, width, label=kpi2['date'], color='#0D9488')

        ax.set_title(f'Operational Audit & Loading Hours Comparison - {dept_name}', fontsize=10, fontweight='bold', pad=10)
        ax.set_xticks(x)
        ax.set_xticklabels(metrics, fontsize=7.5)
        ax.legend(fontsize=8)
        ax.grid(axis='y', linestyle='--', alpha=0.5)

        for rect in rects1 + rects2:
            h = rect.get_height()
            ax.annotate(f'{h:,.1f}' if isinstance(h, float) else f'{int(h)}',
                        xy=(rect.get_x() + rect.get_width() / 2, h),
                        xytext=(0, 3), textcoords="offset points",
                        ha='center', va='bottom', fontsize=7, fontweight='bold')

        plt.tight_layout()
        img_buf = io.BytesIO()
        plt.savefig(img_buf, format='png')
        plt.close(fig)
        img_buf.seek(0)
        return img_buf

    def append_total_row(df):
        """Appends a TOTAL row for numeric data while ignoring non-numeric IDs."""
        if df is None or df.empty:
            return df

        df_total = df.copy()
        total_row = {}
        has_numeric = False
        ignore_keys = ['date', 's.no', 'phone', 'code', 'id', 'sr no', 'driver', 'invoice', 'eway', 'bill', 'no', 'number']

        for col in df_total.columns:
            col_str = str(col).lower()
            def parse_num(v):
                if pd.isna(v): return None
                v_s = str(v).split('/')[0].strip()
                try: return float(v_s)
                except: return None

            numeric_series = df_total[col].apply(parse_num)
            if numeric_series.notna().sum() > 0 and not any(k in col_str for k in ignore_keys):
                total_row[col] = numeric_series.sum()
                has_numeric = True
            else:
                total_row[col] = ""
        
        if has_numeric:
            total_row[df_total.columns[0]] = "TOTAL"
            df_total = pd.concat([df_total, pd.DataFrame([total_row])], ignore_index=True)
        return df_total

    def make_dynamic_table(df):
        """Constructs landscape tables with bold TOTAL footers."""
        if df is None or df.empty:
            return None

        df_clean = append_total_row(df.dropna(how='all').dropna(how='all', axis=1))
        num_cols = len(df_clean.columns)
        if num_cols == 0:
            return None

        col_width = printable_width / num_cols
        data = [[Paragraph(str(col), tbl_header_style) for col in df_clean.columns]]
        
        last_row_idx = len(df_clean) - 1
        has_total = (df_clean.iloc[last_row_idx][df_clean.columns[0]] == "TOTAL")

        for r_idx, row in df_clean.iterrows():
            row_data = []
            current_style = tbl_total_style if (has_total and r_idx == last_row_idx) else tbl_cell_style
            for cell in row:
                if pd.isna(cell) or cell == "":
                    text = ""
                elif isinstance(cell, (int, float)):
                    text = f"{cell:,.2f}".rstrip('0').rstrip('.') if isinstance(cell, float) else f"{cell:,}"
                else:
                    text = str(cell).strip()
                row_data.append(Paragraph(text, current_style))
            data.append(row_data)

        t = Table(data, colWidths=[col_width] * num_cols, repeatRows=1)
        t_style = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#CBD5E1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -2 if has_total else -1), [colors.white, colors.HexColor('#F8FAFC')])
        ]
        if has_total:
            t_style.extend([
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#E2E8F0')),
                ('LINEABOVE', (0, -1), (-1, -1), 1.2, colors.HexColor('#1E293B'))
            ])
        t.setStyle(TableStyle(t_style))
        return t

    xls = pd.ExcelFile(excel_file)
    story.append(Paragraph("DYNAMIC DATE-WISE AUDIT & OPERATIONAL COMPARISON REPORT", title_style))
    story.append(Paragraph("Dispatch Volume, Loading Hours & Pending Order Variance Analysis", subtitle_style))

    dept_groups = {}
    pattern = r"^(.*?)[-\s](\d{1,2}[/\.-]\d{1,2}[/\.-]\d{2,4})$"
    date_list = []

    for sheet in xls.sheet_names:
        match = re.match(pattern, sheet.strip())
        if match:
            dept_name = match.group(1).strip()
            date_val = match.group(2).strip()
            dept_groups.setdefault(dept_name, []).append((date_val, sheet))
            date_list.append(date_val)
        else:
            dept_groups.setdefault(sheet.strip(), []).append(("Raw Data", sheet))

    unique_dates = sorted(list(set(date_list)))
    if len(unique_dates) >= 2:
        dynamic_filename = f"Dispatch_Comparison_{unique_dates[0]}_vs_{unique_dates[-1]}.pdf"
    elif len(unique_dates) == 1:
        dynamic_filename = f"Dispatch_Audit_{unique_dates[0]}.pdf"
    else:
        dynamic_filename = "Operational_Audit_Comparison.pdf"

    for dept_idx, (dept, tabs) in enumerate(dept_groups.items(), start=1):
        dept_elements = [Paragraph(f"{dept_idx}. Department / Module: {dept}", section_style)]
        
        if len(tabs) >= 2:
            first_date, tab1 = tabs[0]
            second_date, tab2 = tabs[1]
            df1 = pd.read_excel(xls, tab1)
            df2 = pd.read_excel(xls, tab2)

            if not df1.empty and not df2.empty:
                kpi1 = compute_kpi_summary(df1, first_date)
                kpi2 = compute_kpi_summary(df2, second_date)

                qty_diff = kpi2['total_qty'] - kpi1['total_qty']
                qty_status = f"HIGHER (+{qty_diff:,.2f} MT)" if qty_diff > 0 else (f"LOWER ({qty_diff:,.2f} MT)" if qty_diff < 0 else "NO CHANGE")

                hrs_diff = kpi2['total_loading_hours'] - kpi1['total_loading_hours']
                hrs_status = f"+{hrs_diff:,.2f} Hrs" if hrs_diff >= 0 else f"{hrs_diff:,.2f} Hrs"

                summary_data = [
                    [Paragraph("<b>Operational Metric</b>", tbl_header_style), Paragraph(f"<b>{first_date}</b>", tbl_header_style), Paragraph(f"<b>{second_date}</b>", tbl_header_style), Paragraph("<b>Operational Variance / Status</b>", tbl_header_style)],
                    [Paragraph("<b>Dispatched Quantity Tonnage</b>", tbl_cell_style), Paragraph(f"{kpi1['total_qty']:,.2f} MT", tbl_cell_style), Paragraph(f"{kpi2['total_qty']:,.2f} MT", tbl_cell_style), Paragraph(f"<b>{qty_status}</b>", tbl_cell_style)],
                    [Paragraph("<b>Total Loading Duration Hours</b>", tbl_cell_style), Paragraph(f"{kpi1['total_loading_hours']:,.2f} Hrs", tbl_cell_style), Paragraph(f"{kpi2['total_loading_hours']:,.2f} Hrs", tbl_cell_style), Paragraph(f"<b>{hrs_status}</b>", tbl_cell_style)],
                    [Paragraph("<b>Average Loading Time / Vehicle</b>", tbl_cell_style), Paragraph(f"{kpi1['avg_loading_hours']:,.2f} Hrs", tbl_cell_style), Paragraph(f"{kpi2['avg_loading_hours']:,.2f} Hrs", tbl_cell_style), Paragraph(f"{kpi2['avg_loading_hours'] - kpi1['avg_loading_hours']:+.2f} Hrs", tbl_cell_style)],
                    [Paragraph("<b>Number of Parties Serviced</b>", tbl_cell_style), Paragraph(f"{kpi1['party_count']}", tbl_cell_style), Paragraph(f"{kpi2['party_count']}", tbl_cell_style), Paragraph(f"{kpi2['party_count'] - kpi1['party_count']:+} Parties", tbl_cell_style)],
                    [Paragraph("<b>Yesterday Pending Orders</b>", tbl_cell_style), Paragraph(f"{kpi1['yesterday_pending']}", tbl_cell_style), Paragraph(f"{kpi2['yesterday_pending']}", tbl_cell_style), Paragraph(f"{kpi2['yesterday_pending'] - kpi1['yesterday_pending']:+} Orders", tbl_cell_style)],
                    [Paragraph("<b>Material / Billing Pending</b>", tbl_cell_style), Paragraph(f"{kpi1['material_pending']}", tbl_cell_style), Paragraph(f"{kpi2['material_pending']}", tbl_cell_style), Paragraph(f"{kpi2['material_pending'] - kpi1['material_pending']:+} Orders", tbl_cell_style)],
                    [Paragraph("<b>Total Recorded Dispatches</b>", tbl_cell_style), Paragraph(f"{kpi1['total_dispatches']}", tbl_cell_style), Paragraph(f"{kpi2['total_dispatches']}", tbl_cell_style), Paragraph(f"{kpi2['total_dispatches'] - kpi1['total_dispatches']:+} Dispatches", tbl_cell_style)]
                ]

                kpi_table = Table(summary_data, colWidths=[200, 150, 150, 250])
                kpi_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
                    ('TOPPADDING', (0, 0), (-1, -1), 3),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')])
                ]))

                chart_img = generate_chart_img(kpi1, kpi2, dept)

                dept_elements.extend([
                    Paragraph(f"<b>Operational Audit Comparison: {first_date} vs {second_date}</b>", sub_section_style),
                    kpi_table,
                    Spacer(1, 6),
                    Image(chart_img, width=520, height=205),
                    Spacer(1, 8)
                ])

        for date_str, sheet_name in tabs:
            df_raw = pd.read_excel(xls, sheet_name)
            raw_table = make_dynamic_table(df_raw)
            if raw_table:
                dept_elements.extend([
                    Paragraph(f"<b>Tab Log: {date_str if date_str != 'Raw Data' else sheet_name}</b>", sub_section_style),
                    raw_table,
                    Spacer(1, 8)
                ])

        story.append(KeepTogether(dept_elements))
        if dept_idx < len(dept_groups):
            story.append(PageBreak())

    doc.build(story)
    pdf_buffer.seek(0)
    return pdf_buffer, dynamic_filename

st.title("Dynamic Operational Audit & Variance Generator")
uploaded_file = st.file_uploader("Upload Multi-Tab Excel Workbook (.xlsx)", type=["xlsx"])

if uploaded_file is not None and st.button("Generate Operational Audit PDF"):
    with st.spinner("Processing dispatched quantities, loading hours, and pending statuses..."):
        pdf_data, download_filename = generate_pdf_report(uploaded_file)
        st.success("PDF generated successfully!")
        st.download_button("Download Comparison PDF Report", data=pdf_data, file_name=download_filename, mime="application/pdf")
