import io
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def generate_pdf_report(excel_file):
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    story = []
    
    # Page setup parameters
    page_width = A4[0] - 72  # Printable width (523 points)

    # Custom Typography Styles
    title_style = ParagraphStyle(
        'DocTitle',
        fontName='Helvetica-Bold',
        fontSize=18,
        textColor=colors.HexColor('#1E293B'),
        spaceAfter=4,
        alignment=0
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        fontName='Helvetica',
        fontSize=11,
        textColor=colors.HexColor('#64748B'),
        spaceAfter=15,
        alignment=0
    )
    section_style = ParagraphStyle(
        'SectionHeader',
        fontName='Helvetica-Bold',
        fontSize=12,
        textColor=colors.HexColor('#0F172A'),
        spaceBefore=12,
        spaceAfter=8
    )
    tbl_header_style = ParagraphStyle(
        'TableHeader',
        fontName='Helvetica-Bold',
        fontSize=8,
        textColor=colors.whitesmoke,
        alignment=1
    )
    tbl_cell_style = ParagraphStyle(
        'TableCell',
        fontName='Helvetica',
        fontSize=7,
        textColor=colors.HexColor('#334155'),
        alignment=0
    )

    def make_dynamic_table(df):
        """Creates a dynamically sized ReportLab table fitting any number of columns."""
        # Clean column names
        df.columns = df.columns.astype(str).str.strip()
        num_cols = len(df.columns)
        
        if num_cols == 0:
            return None

        # Dynamically calculate equal column widths based on available page width
        col_width = page_width / num_cols
        col_widths = [col_width] * num_cols

        data = [[Paragraph(str(col), tbl_header_style) for col in df.columns]]
        for _, row in df.iterrows():
            row_data = []
            for cell in row:
                cell_text = str(cell) if pd.notna(cell) else ""
                row_data.append(Paragraph(cell_text, tbl_cell_style))
            data.append(row_data)

        t = Table(data, colWidths=col_widths)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')])
        ]))
        return t

    def create_sheet_chart(df, sheet_name):
        """Dynamically identifies numeric & categorical columns to render clean bar charts."""
        df.columns = df.columns.astype(str).str.strip()
        
        # Identify possible categorical and numeric columns
        cat_cols = [c for c in df.columns if any(k in c.lower() for k in ['date', 'name', 'person', 'party', 'item', 'kpi', 'description', 'po'])]
        num_cols = [c for c in df.columns if any(k in c.lower() for k in ['val', 'amount', 'price', 'value', 'qty', 'total', 'order'])]

        cat_col = cat_cols[0] if cat_cols else df.columns[0]
        num_col = num_cols[0] if num_cols else None

        if not num_col:
            return None

        # Clean numeric and categorical data
        df_plot = df.copy()
        df_plot[num_col] = pd.to_numeric(df_plot[num_col], errors='coerce').fillna(0)
        df_plot[cat_col] = df_plot[cat_col].astype(str).str.strip()

        # Filter out zero entries
        df_plot = df_plot[df_plot[num_col] > 0]
        if df_plot.empty:
            return None

        # Group data by category to avoid duplicate/overlapping bar outlines
        grouped = df_plot.groupby(cat_col, as_index=False)[num_col].sum()

        fig, ax = plt.subplots(figsize=(6.5, 2.4), dpi=150)
        bars = ax.bar(grouped[cat_col], grouped[num_col], color='#2563EB', edgecolor='#1D4ED8', width=0.4)

        ax.set_title(f"{num_col} by {cat_col} ({sheet_name})", fontsize=9, fontweight='bold', pad=14)
        ax.ticklabel_format(style='plain', axis='y')

        # Auto-format large values into Lakhs if applicable
        max_val = grouped[num_col].max()
        if max_val >= 1e5:
            ax.get_yaxis().set_major_formatter(plt.FuncFormatter(lambda x, loc: f"{x/1e5:,.1f} L"))

        plt.xticks(rotation=20, ha='right', fontsize=7)
        plt.yticks(fontsize=7)
        plt.tight_layout()

        img_buf = io.BytesIO()
        plt.savefig(img_buf, format='png', bbox_inches='tight')
        plt.close(fig)
        img_buf.seek(0)
        return Image(img_buf, width=6.5*inch, height=2.4*inch)

    xls = pd.ExcelFile(excel_file)

    # Document Title Block
    story.append(Paragraph("IRONMART MANAGEMENT AUDIT REPORT", title_style))
    story.append(Paragraph("Automated Multi-Sheet Consolidated Review", subtitle_style))

    # Dynamically Iterate Over ALL Sheets in the Excel Workbook
    for idx, sheet_name in enumerate(xls.sheet_names, start=1):
        df_sheet = pd.read_excel(xls, sheet_name)
        
        if df_sheet.empty:
            continue

        # Add Section Header
        clean_section_title = f"{idx}. {sheet_name.replace('_', ' ').title()} Summary"
        story.append(Paragraph(clean_section_title, section_style))

        # Build Dynamic Table
        table = make_dynamic_table(df_sheet)
        if table:
            story.append(table)
            story.append(Spacer(1, 10))

        # Build Dynamic Chart if applicable
        chart_img = create_sheet_chart(df_sheet, sheet_name)
        if chart_img:
            story.append(chart_img)
            story.append(Spacer(1, 15))

    doc.build(story)
    pdf_buffer.seek(0)
    return pdf_buffer

# Streamlit UI Interface
st.title("Excel to PDF Audit Report Generator")
uploaded_file = st.file_uploader("Upload Excel File (.xlsx)", type=["xlsx"])

if uploaded_file is not None:
    if st.button("Generate PDF Report"):
        with st.spinner("Processing all sheets and columns into PDF..."):
            pdf_data = generate_pdf_report(uploaded_file)
            st.success("Report generated successfully!")
            st.download_button(
                label="Download PDF Report",
                data=pdf_data,
                file_name="Audit_Report_Output.pdf",
                mime="application/pdf"
            )