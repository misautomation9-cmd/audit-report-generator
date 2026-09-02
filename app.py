import io
import re
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether, PageBreak
)
from reportlab.lib.styles import ParagraphStyle

def generate_pdf_report(excel_file):
    pdf_buffer = io.BytesIO()
    
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

    # Typography Styles
    title_style = ParagraphStyle('DocTitle', fontName='Helvetica-Bold', fontSize=16, textColor=colors.HexColor('#1E293B'), spaceAfter=2)
    subtitle_style = ParagraphStyle('DocSubtitle', fontName='Helvetica', fontSize=9, textColor=colors.HexColor('#64748B'), spaceAfter=10)
    section_style = ParagraphStyle('SectionHeader', fontName='Helvetica-Bold', fontSize=11, textColor=colors.HexColor('#0F172A'), spaceBefore=10, spaceAfter=6)
    sub_section_style = ParagraphStyle('SubSectionHeader', fontName='Helvetica-Bold', fontSize=9.5, textColor=colors.HexColor('#2563EB'), spaceBefore=6, spaceAfter=4)
    tbl_header_style = ParagraphStyle('TableHeader', fontName='Helvetica-Bold', fontSize=6.5, leading=8, textColor=colors.whitesmoke, alignment=1)
    tbl_cell_style = ParagraphStyle('TableCell', fontName='Helvetica', fontSize=6, leading=7.5, textColor=colors.HexColor('#334155'), alignment=0)
    tbl_total_style = ParagraphStyle('TableTotal', fontName='Helvetica-Bold', fontSize=6.5, leading=8, textColor=colors.HexColor('#0F172A'), alignment=0)

    def append_total_row(df):
        """Calculates and appends a TOTAL row at the bottom for numeric columns."""
        df_total = df.copy()
        total_row = {}
        has_numeric = False

        for col in df_total.columns:
            col_str = str(col).lower()
            numeric_series = pd.to_numeric(df_total[col], errors='coerce')
            
            # Skip non-aggregatable numeric fields like IDs or codes
            if numeric_series.notna().sum() > 0 and not any(k in col_str for k in ['date', 's.no', 'phone', 'code', 'id', 'sr no']):
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
        """Builds an auto-fitted ReportLab table with bold TOTAL formatting."""
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

    def create_comparison_chart(comp_df, first_date, second_date, dept_name):
        """Generates dynamic side-by-side bar chart for numerical comparison."""
        cat_col = comp_df.columns[0]
        numeric_cols = [c for c in comp_df.columns if c not in [cat_col] and 'Variance' not in c]

        if len(numeric_cols) < 2:
            return None

        col1, col2 = numeric_cols[0], numeric_cols[1]
        plot_df = comp_df.head(10).copy()  # Limit to top 10 items for visual clarity

        fig, ax = plt.subplots(figsize=(8.5, 2.4), dpi=150)
        x = range(len(plot_df))
        width = 0.35

        ax.bar([i - width/2 for i in x], plot_df[col1], width, label=first_date, color='#3B82F6')
        ax.bar([i + width/2 for i in x], plot_df[col2], width, label=second_date, color='#10B981')

        ax.set_title(f"{dept_name}: Comparison Between {first_date} and {second_date}", fontsize=8, fontweight='bold', pad=8)
        ax.set_xticks(list(x))
        ax.set_xticklabels(plot_df[cat_col].astype(str).str[:15], rotation=15, ha='right', fontsize=6.5)
        ax.tick_params(axis='y', labelsize=6.5)
        ax.legend(fontsize=7)
        ax.grid(axis='y', linestyle='--', alpha=0.5)
        plt.tight_layout()

        img_buf = io.BytesIO()
        plt.savefig(img_buf, format='png', bbox_inches='tight')
        plt.close(fig)
        img_buf.seek(0)
        return Image(img_buf, width=8.5*inch, height=2.4*inch)

    xls = pd.ExcelFile(excel_file)
    
    # Document Header
    story.append(Paragraph("DYNAMIC DATE-WISE AUDIT & COMPARISON REPORT", title_style))
    story.append(Paragraph("Multi-Tab Variance & Summarization Engine", subtitle_style))

    # Parse sheet names (e.g., 'HR-01/09/2026' or 'HR-01-09-2026')
    dept_groups = {}
    pattern = r"^(.*?)[-\s](\d{1,2}[/\.-]\d{1,2}[/\.-]\d{2,4})$"

    for sheet in xls.sheet_names:
        match = re.match(pattern, sheet.strip())
        if match:
            dept = match.group(1).strip()
            date_str = match.group(2).strip()
            dept_groups.setdefault(dept, []).append((date_str, sheet))
        else:
            dept_groups.setdefault(sheet.strip(), []).append(("Raw Data", sheet))

    # Process each department group
    for dept_idx, (dept, tabs) in enumerate(dept_groups.items(), start=1):
        dept_elements = [Paragraph(f"{dept_idx}. Department / Module: {dept}", section_style)]
        
        # If two date tabs exist, perform dynamic comparison
        if len(tabs) >= 2:
            first_date, tab1 = tabs[0]
            second_date, tab2 = tabs[1]

            df1 = pd.read_excel(xls, tab1).dropna(how='all').dropna(how='all', axis=1)
            df2 = pd.read_excel(xls, tab2).dropna(how='all').dropna(how='all', axis=1)

            df1.columns = [str(c).strip() for c in df1.columns]
            df2.columns = [str(c).strip() for c in df2.columns]

            # Primary Key Column (first string/text column)
            cat_cols = [c for c in df1.columns if any(k in c.lower() for k in ['name', 'kpi', 'person', 'party', 'item', 'description', 'particulars'])]
            key_col = cat_cols[0] if cat_cols else df1.columns[0]

            # Merge data on key column
            merged = pd.merge(df1, df2, on=key_col, suffixes=(f' ({first_date})', f' ({second_date})'))
            
            comp_data = {key_col: merged[key_col]}
            numeric_cols = [c for c in df1.columns if c != key_col and pd.to_numeric(df1[c], errors='coerce').notna().sum() > 0]

            for num_col in numeric_cols:
                c1 = f"{num_col} ({first_date})"
                c2 = f"{num_col} ({second_date})"
                if c1 in merged.columns and c2 in merged.columns:
                    val1 = pd.to_numeric(merged[c1], errors='coerce').fillna(0)
                    val2 = pd.to_numeric(merged[c2], errors='coerce').fillna(0)
                    comp_data[c1] = val1
                    comp_data[c2] = val2
                    comp_data[f"{num_col} Variance (+/-)"] = val2 - val1

            comp_df = pd.DataFrame(comp_data)

            dept_elements.append(Paragraph(f"<b>Date-Wise Comparison: {first_date} vs {second_date}</b>", sub_section_style))
            
            comp_table = make_dynamic_table(comp_df)
            if comp_table:
                dept_elements.append(comp_table)
                dept_elements.append(Spacer(1, 8))

            chart_img = create_comparison_chart(comp_df, first_date, second_date, dept)
            if chart_img:
                dept_elements.append(chart_img)
                dept_elements.append(Spacer(1, 10))

        # Output individual daily tab tables
        for date_str, sheet_name in tabs:
            df_raw = pd.read_excel(xls, sheet_name).dropna(how='all').dropna(how='all', axis=1)
            if not df_raw.empty:
                label = f"Data Log: {sheet_name}" if date_str == "Raw Data" else f"Tab Log: {date_str}"
                dept_elements.append(Paragraph(f"<b>{label}</b>", sub_section_style))
                raw_table = make_dynamic_table(df_raw)
                if raw_table:
                    dept_elements.append(raw_table)
                    dept_elements.append(Spacer(1, 8))

        story.append(KeepTogether(dept_elements))
        if dept_idx < len(dept_groups):
            story.append(PageBreak())

    doc.build(story)
    pdf_buffer.seek(0)
    return pdf_buffer

# Streamlit Interface Setup
st.title("Dynamic Date-Wise Audit & Variance Generator")
uploaded_file = st.file_uploader("Upload Multi-Tab Excel Workbook (.xlsx)", type=["xlsx"])

if uploaded_file is not None:
    if st.button("Generate Audit Comparison PDF"):
        with st.spinner("Processing dynamic date comparisons, graphs, and totals..."):
            pdf_data = generate_pdf_report(uploaded_file)
            st.success("PDF generated successfully!")
            st.download_button(
                label="Download Comparison PDF Report",
                data=pdf_data,
                file_name="Dynamic_Audit_Date_Comparison.pdf",
                mime="application/pdf"
            )
