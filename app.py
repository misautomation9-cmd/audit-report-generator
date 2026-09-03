import io
import re
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, PageBreak
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
        """Calculates specific key performance indicators for a single date tab."""
        if df is None or df.empty:
            return {}

        df_c = df.copy()
        df_c.columns = [str(c).strip() for c in df_c.columns]
        col_map = {c.lower(): c for c in df_c.columns}
        
        # 1. Total Dispatched Quantity
        qnty_col = next((col_map[c] for c in col_map if any(k in c for k in ['qnty', 'quantity', 'qty', 'weight', 'tonnage'])), None)
        total_qty = pd.to_numeric(df_c[qnty_col], errors='coerce').sum() if qnty_col else 0.0

        # 2. Loading Time Calculation
        time_col = next((col_map[c] for c in col_map if any(k in c for k in ['time', 'duration', 'loading', 'hours'])), None)
        avg_loading_time = pd.to_numeric(df_c[time_col], errors='coerce').mean() if time_col else 0.0

        # 3. Party Count
        party_col = next((col_map[c] for c in col_map if any(k in c for k in ['party', 'customer', 'name', 'client'])), None)
        unique_parties = df_c[party_col].nunique() if party_col else len(df_c)

        # 4. Pending Status Breakdown
        status_col = next((col_map[c] for c in col_map if any(k in c for k in ['status', 'remark', 'billing', 'state'])), None)
        yesterday_pending, material_pending = 0, 0

        if status_col:
            statuses = df_c[status_col].astype(str).str.lower()
            yesterday_pending = statuses.str.contains('yesterday|pending|yp', na=False).sum()
            material_pending = statuses.str.contains('material|unbilled|hold', na=False).sum()

        return {
            "date": date_str,
            "total_qty": total_qty,
            "avg_loading_time": avg_loading_time,
            "party_count": unique_parties,
            "yesterday_pending": yesterday_pending,
            "material_pending": material_pending,
            "total_dispatches": len(df_c)
        }

    def append_total_row(df):
        """Appends a TOTAL row for numeric data while ignoring document IDs and phone numbers."""
        if df is None or df.empty:
            return df

        df_total = df.copy()
        total_row = {}
        has_numeric = False
        ignore_keys = ['date', 's.no', 'phone', 'code', 'id', 'sr no', 'driver', 'invoice', 'eway', 'bill', 'no', 'number']

        for col in df_total.columns:
            col_str = str(col).lower()
            numeric_series = pd.to_numeric(df_total[col], errors='coerce')
            
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
        """Constructs auto-scaled landscape tables with bold TOTAL footers."""
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
    story.append(Paragraph("Dispatch Volume, Loading Efficiency & Operational Pending Status Engine", subtitle_style))

    # Pattern recognition for grouping date tabs (e.g. DISPATCH-31-08-2026)
    dept_groups = {}
    pattern = r"^(.*?)[-\s](\d{1,2}[/\.-]\d{1,2}[/\.-]\d{2,4})$"

    for sheet in xls.sheet_names:
        match = re.match(pattern, sheet.strip())
        if match:
            dept_groups.setdefault(match.group(1).strip(), []).append((match.group(2).strip(), sheet))
        else:
            dept_groups.setdefault(sheet.strip(), []).append(("Raw Data", sheet))

    # Process each department group
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

                summary_data = [
                    [Paragraph("<b>Operational Metric</b>", tbl_header_style), Paragraph(f"<b>{first_date}</b>", tbl_header_style), Paragraph(f"<b>{second_date}</b>", tbl_header_style), Paragraph("<b>Operational Variance / Status</b>", tbl_header_style)],
                    [Paragraph("<b>Dispatched Quantity Tonnage</b>", tbl_cell_style), Paragraph(f"{kpi1['total_qty']:,.2f} MT", tbl_cell_style), Paragraph(f"{kpi2['total_qty']:,.2f} MT", tbl_cell_style), Paragraph(f"<b>{qty_status}</b>", tbl_cell_style)],
                    [Paragraph("<b>Number of Parties Serviced</b>", tbl_cell_style), Paragraph(f"{kpi1['party_count']}", tbl_cell_style), Paragraph(f"{kpi2['party_count']}", tbl_cell_style), Paragraph(f"{kpi2['party_count'] - kpi1['party_count']:+} Parties", tbl_cell_style)],
                    [Paragraph("<b>Yesterday Pending Orders</b>", tbl_cell_style), Paragraph(f"{kpi1['yesterday_pending']}", tbl_cell_style), Paragraph(f"{kpi2['yesterday_pending']}", tbl_cell_style), Paragraph(f"{kpi2['yesterday_pending'] - kpi1['yesterday_pending']:+} Orders", tbl_cell_style)],
                    [Paragraph("<b>Material / Billing Pending</b>", tbl_cell_style), Paragraph(f"{kpi1['material_pending']}", tbl_cell_style), Paragraph(f"{kpi2['material_pending']}", tbl_cell_style), Paragraph(f"{kpi2['material_pending'] - kpi1['material_pending']:+} Orders", tbl_cell_style)],
                    [Paragraph("<b>Total Recorded Dispatches</b>", tbl_cell_style), Paragraph(f"{kpi1['total_dispatches']}", tbl_cell_style), Paragraph(f"{kpi2['total_dispatches']}", tbl_cell_style), Paragraph(f"{kpi2['total_dispatches'] - kpi1['total_dispatches']:+} Dispatches", tbl_cell_style)]
                ]

                kpi_table = Table(summary_data, colWidths=[200, 150, 150, 250])
                kpi_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')])
                ]))

                dept_elements.extend([
                    Paragraph(f"<b>Operational Audit Comparison: {first_date} vs {second_date}</b>", sub_section_style),
                    kpi_table,
                    Spacer(1, 10)
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
    return pdf_buffer

st.title("Dynamic Operational Audit & Variance Generator")
uploaded_file = st.file_uploader("Upload Multi-Tab Excel Workbook (.xlsx)", type=["xlsx"])

if uploaded_file is not None and st.button("Generate Operational Audit PDF"):
    with st.spinner("Processing dispatched quantities, loading times, and pending material statuses..."):
        pdf_data = generate_pdf_report(uploaded_file)
        st.success("PDF generated successfully!")
        st.download_button("Download Comparison PDF Report", data=pdf_data, file_name="Operational_Audit_Comparison.pdf", mime="application/pdf")
