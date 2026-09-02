import io
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def generate_pdf_report(excel_file):
    pdf_buffer = io.BytesIO()
    
    # Document setup with Landscape orientation for wide table space
    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=landscape(A4),
        rightMargin=20,
        leftMargin=20,
        topMargin=25,
        bottomMargin=25
    )
    story = []
    printable_width = landscape(A4)[0] - 40  # ~801 pt

    # Styles
    title_style = ParagraphStyle('DocTitle', fontName='Helvetica-Bold', fontSize=16, textColor=colors.HexColor('#1E293B'), spaceAfter=2)
    subtitle_style = ParagraphStyle('DocSubtitle', fontName='Helvetica', fontSize=9, textColor=colors.HexColor('#64748B'), spaceAfter=10)
    section_style = ParagraphStyle('SectionHeader', fontName='Helvetica-Bold', fontSize=11, textColor=colors.HexColor('#0F172A'), spaceBefore=10, spaceAfter=6)
    tbl_header_style = ParagraphStyle('TableHeader', fontName='Helvetica-Bold', fontSize=6.5, leading=8, textColor=colors.whitesmoke, alignment=1)
    tbl_cell_style = ParagraphStyle('TableCell', fontName='Helvetica', fontSize=6, leading=7.5, textColor=colors.HexColor('#334155'), alignment=0)
    tbl_total_style = ParagraphStyle('TableTotal', fontName='Helvetica-Bold', fontSize=6.5, leading=8, textColor=colors.HexColor('#0F172A'), alignment=0)

    def append_total_row(df):
        """Calculates and appends a TOTAL row for numeric columns."""
        df_total = df.copy()
        total_row = {}
        has_numeric = False

        for col in df_total.columns:
            col_str = str(col).lower()
            # Try converting numeric columns
            numeric_series = pd.to_numeric(df_total[col], errors='coerce')
            if numeric_series.notna().sum() > 0 and not any(k in col_str for k in ['date', 's.no', 'phone', 'driver', 'eway', 'so', 'po']):
                total_sum = numeric_series.sum()
                total_row[col] = total_sum
                has_numeric = True
            else:
                total_row[col] = ""
        
        if has_numeric:
            first_col = df_total.columns[0]
            total_row[first_col] = "TOTAL"
            df_total = pd.concat([df_total, pd.DataFrame([total_row])], ignore_index=True)
        return df_total

    def make_dynamic_table(df):
        """Builds ReportLab table with column wrapping and bold total row styling."""
        df_clean = df.copy()
        df_clean.columns = [str(c).strip() for c in df_clean.columns]
        df_clean = df_clean.loc[:, ~df_clean.columns.str.contains('^Unnamed')]
        
        df_clean = append_total_row(df_clean)

        num_cols = len(df_clean.columns)
        if num_cols == 0:
            return None

        col_width = printable_width / num_cols
        col_widths = [col_width] * num_cols

        data = [[Paragraph(str(col), tbl_header_style) for col in df_clean.columns]]
        
        last_row_idx = len(df_clean) - 1
        has_total = df_clean.iloc[-1][df_clean.columns[0]] == "TOTAL"

        for r_idx, row in df_clean.iterrows():
            row_data = []
            is_total_row = has_total and (r_idx == last_row_idx)
            current_style = tbl_total_style if is_total_row else tbl_cell_style
            
            for cell in row:
                if pd.isna(cell) or cell == "":
                    cell_text = ""
                elif isinstance(cell, (int, float)):
                    cell_text = f"{cell:,.2f}".rstrip('0').rstrip('.') if isinstance(cell, float) else f"{cell:,}"
                else:
                    cell_text = str(cell).strip()
                row_data.append(Paragraph(cell_text, current_style))
            data.append(row_data)

        t = Table(data, colWidths=col_widths, repeatRows=1)
        
        t_style = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#CBD5E1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -2 if has_total else -1), [colors.white, colors.HexColor('#F8FAFC')])
        ]
        
        if has_total:
            t_style.append(('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#E2E8F0')))
            t_style.append(('LINEABOVE', (0, -1), (-1, -1), 1.2, colors.HexColor('#1E293B')))
            
        t.setStyle(TableStyle(t_style))
        return t

    def build_date_comparison_section(xls):
        """Generates Date-Wise Comparisons across available sheets."""
        comp_elements = []
        comp_elements.append(Paragraph("DATE-WISE COMPARISON ANALYSIS", section_style))

        # 1. HR Date-wise Comparison (Wide horizontal date columns)
        if 'HR & Admin ' in xls.sheet_names:
            df_hr = pd.read_excel(xls, 'HR & Admin ')
            date_cols = [c for c in df_hr.columns if any(char.isdigit() for char in str(c))]
            if len(date_cols) >= 2:
                prev_d, latest_d = date_cols[-2], date_cols[-1]
                
                df_hr_comp = df_hr[['KPI', prev_d, latest_d]].dropna(subset=['KPI']).copy()
                df_hr_comp[prev_d] = pd.to_numeric(df_hr_comp[prev_d], errors='coerce').fillna(0)
                df_hr_comp[latest_d] = pd.to_numeric(df_hr_comp[latest_d], errors='coerce').fillna(0)
                df_hr_comp['Difference (Variance)'] = df_hr_comp[latest_d] - df_hr_comp[prev_d]
                
                df_hr_comp.columns = ['KPI / Metric', f'Previous ({prev_d})', f'Latest ({latest_d})', 'Variance (+/-)']
                
                comp_elements.append(Paragraph("<b>1. HR & Attendance Variance</b>", subtitle_style))
                tbl = make_dynamic_table(df_hr_comp)
                if tbl:
                    comp_elements.append(tbl)
                    comp_elements.append(Spacer(1, 10))

        # 2. Sales & Marketing Salesperson Date Comparison
        if 'Sales & Marketing ' in xls.sheet_names:
            df_sales = pd.read_excel(xls, 'Sales & Marketing ')
            df_sales.columns = df_sales.columns.str.strip()
            
            if 'Date' in df_sales.columns and 'Sales Person' in df_sales.columns:
                df_sales['Date_Parsed'] = pd.to_datetime(df_sales['Date'], format='%d/%m/%Y', errors='coerce')
                df_sales['Date_Parsed'] = df_sales['Date_Parsed'].fillna(pd.to_datetime(df_sales['Date'], errors='coerce')).ffill()
                
                dates = sorted(df_sales['Date_Parsed'].dropna().unique())
                if len(dates) >= 2:
                    p_date, l_date = dates[-2], dates[-1]
                    p_str, l_str = p_date.strftime('%d/%m/%Y'), l_date.strftime('%d/%m/%Y')

                    df_p = df_sales[df_sales['Date_Parsed'] == p_date]
                    df_l = df_sales[df_sales['Date_Parsed'] == l_date]

                    sp_p = df_p.groupby('Sales Person')['Order Quantity'].sum()
                    sp_l = df_l.groupby('Sales Person')['Order Quantity'].sum()

                    sp_comp = pd.DataFrame({f'Qty ({p_str})': sp_p, f'Qty ({l_str})': sp_l}).fillna(0)
                    sp_comp['Qty Variance (+/-)'] = sp_comp[f'Qty ({l_str})'] - sp_comp[f'Qty ({p_str})']
                    sp_comp = sp_comp.reset_index()

                    comp_elements.append(Paragraph("<b>2. Salesperson Order Quantity Variance</b>", subtitle_style))
                    tbl_sp = make_dynamic_table(sp_comp)
                    if tbl_sp:
                        comp_elements.append(tbl_sp)
                        comp_elements.append(Spacer(1, 10))

        return comp_elements

    xls = pd.ExcelFile(excel_file)

    # Document Header
    story.append(Paragraph("MANAGEMENT AUDIT & COMPARISON REPORT", title_style))
    story.append(Paragraph("Automated Sum Totals & Multi-Date Variance Analysis", subtitle_style))

    # Add Date Comparison Analysis Section at the top
    date_comp_nodes = build_date_comparison_section(xls)
    if len(date_comp_nodes) > 1:
        story.append(KeepTogether(date_comp_nodes))
        story.append(PageBreak())

    # Add Sheet Data with Total Rows
    for idx, sheet_name in enumerate(xls.sheet_names, start=1):
        df_sheet = pd.read_excel(xls, sheet_name)
        df_sheet = df_sheet.dropna(how='all').dropna(how='all', axis=1)
        if df_sheet.empty:
            continue

        clean_section_title = f"{idx}. {sheet_name.strip().title()} Summary"
        sheet_elements = [Paragraph(clean_section_title, section_style)]
        
        table = make_dynamic_table(df_sheet)
        if table:
            sheet_elements.append(table)
            sheet_elements.append(Spacer(1, 10))

        story.append(KeepTogether(sheet_elements))
        if idx < len(xls.sheet_names):
            story.append(PageBreak())

    doc.build(story)
    pdf_buffer.seek(0)
    return pdf_buffer

# Streamlit UI Setup
st.title("Audit Report & Date Comparison Generator")
uploaded_file = st.file_uploader("Upload Daily Excel Report (.xlsx)", type=["xlsx"])

if uploaded_file is not None:
    if st.button("Generate PDF with Sums & Date Comparison"):
        with st.spinner("Calculating totals & date variances..."):
            pdf_data = generate_pdf_report(uploaded_file)
            st.success("PDF generated successfully!")
            st.download_button(
                label="Download Consolidated PDF Report",
                data=pdf_data,
                file_name="Audit_Report_Totals_and_Comparison.pdf",
                mime="application/pdf"
            )
