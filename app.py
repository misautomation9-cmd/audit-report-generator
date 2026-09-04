import io
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import HRFlowable, Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
import streamlit as st

st.set_page_config(
    page_title="Godown Stock PDF Generator", page_icon="📄", layout="centered"
)

st.title("📦 Daily Stock & Dispatch PDF Generator")
st.write(
    "Upload your daily Excel workbook to generate and download the consolidated PDF report."
)

uploaded_file = st.file_uploader("Upload Excel File (.xlsx)", type=["xlsx"])


def build_pdf_report(
    sales_df, delayed_df, summary_df, stock_df, chart1_bytes, chart2_bytes
):
  buffer = io.BytesIO()
  doc = SimpleDocTemplate(
      buffer,
      pagesize=A4,
      rightMargin=25,
      leftMargin=25,
      topMargin=25,
      bottomMargin=25,
  )
  elements = []

  styles = getSampleStyleSheet()
  title_style = ParagraphStyle(
      'DocTitle',
      parent=styles['Heading1'],
      fontSize=14,
      leading=18,
      alignment=1,
      textColor=colors.HexColor('#0F172A'),
  )
  sub_style = ParagraphStyle(
      'DocSub',
      parent=styles['Normal'],
      fontSize=9,
      leading=12,
      alignment=1,
      textColor=colors.HexColor('#475569'),
  )
  sec_style = ParagraphStyle(
      'SecHeader',
      parent=styles['Heading2'],
      fontSize=11,
      leading=15,
      textColor=colors.HexColor('#1E293B'),
  )
  cell_style = ParagraphStyle('CellText', parent=styles['Normal'], fontSize=8, leading=10)
  header_cell_style = ParagraphStyle(
      'HeaderCellText',
      parent=styles['Normal'],
      fontSize=8,
      leading=10,
      textColor=colors.white,
      fontName='Helvetica-Bold',
  )

  # Title Header
  elements.append(
      Paragraph(
          'DAILY GODOWN DISPATCH & STOCK MOVEMENTS REPORT', title_style
      )
  )
  elements.append(
      Paragraph(
          'Consolidated report covering dispatches, delayed yesterday vehicle'
          ' dispatches, and itemized stock balances.',
          sub_style,
      )
  )
  elements.append(Spacer(1, 10))
  elements.append(
      HRFlowable(
          width='100%',
          thickness=1,
          color=colors.HexColor('#CBD5E1'),
          spaceAfter=12,
      )
  )

  # Helper function to generate styled ReportLab Tables
  def make_table(df, col_widths=None):
    table_data = [[
        Paragraph(str(col), header_cell_style) for col in df.columns
    ]]
    for _, row in df.iterrows():
      table_data.append(
          [Paragraph(str(val), cell_style) for val in row.values]
      )

    t = Table(table_data, colWidths=col_widths)
    t.setStyle(
        TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#334155')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
        ])
    )
    return t

  # 1. Salesperson Summary
  elements.append(
      Paragraph('1. Salesperson-Wise Dispatch Summary', sec_style)
  )
  elements.append(Spacer(1, 5))
  elements.append(make_table(sales_df, [90, 80, 70, 180, 120]))
  elements.append(Spacer(1, 12))

  # 2. Delayed Vehicles
  elements.append(
      Paragraph('2. Delayed Yesterday Vehicles Dispatched Today', sec_style)
  )
  elements.append(Spacer(1, 5))
  elements.append(make_table(delayed_df, [80, 40, 80, 160, 90, 90]))
  elements.append(Spacer(1, 12))

  # 3. Overall Stock Summary
  elements.append(
      Paragraph('3. Godown Overall Stock & Production Summary (MT)', sec_style)
  )
  elements.append(Spacer(1, 5))
  elements.append(make_table(summary_df, [120, 105, 105, 105, 105]))
  elements.append(Spacer(1, 12))

  # 4. Item Stock Breakdown
  elements.append(
      Paragraph('4. Item-Wise Stock Breakdown (Opening vs Closing)', sec_style)
  )
  elements.append(Spacer(1, 5))
  elements.append(make_table(stock_df, [200, 115, 115, 110]))
  elements.append(Spacer(1, 15))

  # 5. Visual Analytics (Charts)
  elements.append(Paragraph('5. Visual Analytics', sec_style))
  elements.append(Spacer(1, 8))

  img1 = Image(chart1_bytes, width=540, height=180)
  img2 = Image(chart2_bytes, width=540, height=200)

  elements.append(img1)
  elements.append(Spacer(1, 10))
  elements.append(img2)

  doc.build(elements)
  buffer.seek(0)
  return buffer


if uploaded_file:
  try:
    # Read sheets directly from Excel file
    xls = pd.ExcelFile(uploaded_file)
    df_sales = pd.read_excel(xls, 'Salesperson_Summary')
    df_delayed = pd.read_excel(xls, 'Delayed_Vehicles')
    df_summary = pd.read_excel(xls, 'Overall_Summary')
    df_stock = pd.read_excel(xls, 'Stock_Breakdown')

    # Generate Chart 1 (Salesperson Parties)
    fig1, ax1 = plt.subplots(figsize=(10, 3.5))
    ax1.bar(
        df_sales['Sales Person'],
        df_sales['Parties Count'],
        color='#6C63FF',
        width=0.4,
    )
    ax1.set_ylabel('Number of Parties Served', fontweight='bold')
    ax1.set_title(
        'Salesperson-Wise Served Parties Count', fontweight='bold', pad=12
    )
    ax1.grid(axis='y', linestyle='--', alpha=0.5)
    plt.tight_layout()
    chart1_io = io.BytesIO()
    plt.savefig(chart1_io, format='png', dpi=200)
    plt.close()

    # Generate Chart 2 (Opening vs Closing Stock)
    x = np.arange(len(df_stock['Particulars/Item']))
    width = 0.35
    fig2, ax2 = plt.subplots(figsize=(12, 4.5))
    ax2.bar(
        x - width / 2,
        df_stock['Opening Stock (MT)'],
        width,
        label='Opening Stock (MT)',
        color='#3B82F6',
    )
    ax2.bar(
        x + width / 2,
        df_stock['Closing Stock (MT)'],
        width,
        label='Closing Stock (MT)',
        color='#10B981',
    )
    ax2.set_ylabel('Metric Tons (MT)', fontweight='bold')
    ax2.set_title(
        'Item-Wise Opening vs Closing Stock Balance', fontweight='bold', pad=12
    )
    ax2.set_xticks(x)
    ax2.set_xticklabels(
        df_stock['Particulars/Item'], rotation=25, ha='right'
    )
    ax2.legend()
    ax2.grid(axis='y', linestyle='--', alpha=0.5)
    plt.tight_layout()
    chart2_io = io.BytesIO()
    plt.savefig(chart2_io, format='png', dpi=200)
    plt.close()

    # Build PDF and create Streamlit Download Button
    pdf_data = build_pdf_report(
        df_sales, df_delayed, df_summary, df_stock, chart1_io, chart2_io
    )

    st.success('PDF generated successfully!')
    st.download_button(
        label='📥 Download Godown Report PDF',
        data=pdf_data,
        file_name='Daily_Godown_Stock_Report.pdf',
        mime='application/pdf',
    )

  except Exception as e:
    st.error(f'Error processing Excel structure: {e}')
