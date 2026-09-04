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
    page_title="Multi-Department Operational Report Generator",
    page_icon="📄",
    layout="centered",
)

st.title("📦 Daily Stock & Dispatch PDF Generator")
st.write(
    "Upload your daily operational Excel workbook containing the 9 target"
    " sheets to directly generate and download the consolidated PDF report."
)

uploaded_file = st.file_uploader("Upload Excel File (.xlsx)", type=["xlsx"])


def build_pdf_report(sheets_data, chart1_bytes, chart2_bytes):
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
  cell_style = ParagraphStyle(
      'CellText', parent=styles['Normal'], fontSize=7.5, leading=9.5
  )
  header_cell_style = ParagraphStyle(
      'HeaderCellText',
      parent=styles['Normal'],
      fontSize=7.5,
      leading=9.5,
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
          'Consolidated report covering dispatches, delayed vehicle dispatches,'
          ' and multi-department operational balances.',
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

  # Helper function to generate clean tables dynamically from any dataframe
  def make_table(df):
    if df.empty:
      return Paragraph('No data recorded for this section.', cell_style)

    table_data = [[
        Paragraph(str(col), header_cell_style) for col in df.columns
    ]]
    for _, row in df.iterrows():
      table_data.append([
          Paragraph(str(val) if pd.notna(val) else '', cell_style)
          for val in row.values
      ])

    t = Table(table_data, repeatRows=1)
    t.setStyle(
        TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#334155')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            (
                'ROWBACKGROUNDS',
                (0, 1),
                (-1, -1),
                [colors.white, colors.HexColor('#F8FAFC')],
            ),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
        ])
    )
    return t

  # Section Mapping
  section_order = [
      ('Sales Person Wise Dispatch', '1. Sales Person Wise Dispatch Summary'),
      (
          'Logistics And Dispatch',
          '2. Delayed Yesterday Vehicles Dispatched Today',
      ),
      ('Stock', '3. Godown Overall Stock & Production Summary (MT)'),
      ('Purchase Order', '4. Purchase Orders Summary'),
      ('Purchase Plates', '5. Purchase Plates Summary'),
      ('Purchase Structure', '6. Purchase Structure Breakdown'),
      ('Sales And Marketing', '7. Sales & Marketing Overview'),
      ('HR ANd Admin', '8. HR & Administration Operational Summary'),
      ('Accounts', '9. Accounts & Financial Summary'),
  ]

  for sheet_key, section_title in section_order:
    if sheet_key in sheets_data:
      elements.append(Paragraph(section_title, sec_style))
      elements.append(Spacer(1, 4))
      elements.append(make_table(sheets_data[sheet_key]))
      elements.append(Spacer(1, 10))

  # Render Visual Charts
  if chart1_bytes or chart2_bytes:
    elements.append(Paragraph('10. Visual Analytics', sec_style))
    elements.append(Spacer(1, 6))

    if chart1_bytes:
      elements.append(Image(chart1_bytes, width=540, height=180))
      elements.append(Spacer(1, 8))

    if chart2_bytes:
      elements.append(Image(chart2_bytes, width=540, height=200))

  doc.build(elements)
  buffer.seek(0)
  return buffer


if uploaded_file:
  try:
    xls = pd.ExcelFile(uploaded_file)
    found_sheets = xls.sheet_names

    # Load sheets into dictionary
    sheets_data = {sheet: pd.read_excel(xls, sheet) for sheet in found_sheets}

    # Chart 1: Salesperson Parties Served
    chart1_io = None
    if 'Sales Person Wise Dispatch' in sheets_data:
      df_sp = sheets_data['Sales Person Wise Dispatch']
      sp_cols = df_sp.columns
      sp_col = [c for c in sp_cols if 'person' in c.lower() or 'sales' in c.lower()]
      party_col = [c for c in sp_cols if 'party' in c.lower() or 'parties' in c.lower()]

      if sp_col and party_col:
        counts = df_sp.groupby(sp_col[0])[party_col[0]].count()
        fig1, ax1 = plt.subplots(figsize=(10, 3.5))
        ax1.bar(counts.index, counts.values, color='#6C63FF', width=0.4)
        ax1.set_ylabel('Parties Served', fontweight='bold')
        ax1.set_title(
            'Salesperson-Wise Served Parties Count', fontweight='bold', pad=12
        )
        ax1.grid(axis='y', linestyle='--', alpha=0.5)
        plt.tight_layout()
        chart1_io = io.BytesIO()
        plt.savefig(chart1_io, format='png', dpi=200)
        plt.close()

    # Chart 2: Item Opening vs Closing Stock
    chart2_io = None
    if 'Stock' in sheets_data:
      df_st = sheets_data['Stock']
      st_cols = df_st.columns
      item_col = [c for c in st_cols if 'item' in c.lower() or 'particular' in c.lower()]
      open_col = [c for c in st_cols if 'open' in c.lower()]
      close_col = [c for c in st_cols if 'close' in c.lower()]

      if item_col and open_col and close_col:
        items = df_st[item_col[0]].astype(str)
        opening = pd.to_numeric(df_st[open_col[0]], errors='coerce').fillna(0)
        closing = pd.to_numeric(df_st[close_col[0]], errors='coerce').fillna(0)

        x = np.arange(len(items))
        width = 0.35

        fig2, ax2 = plt.subplots(figsize=(12, 4.5))
        ax2.bar(
            x - width / 2,
            opening,
            width,
            label='Opening Stock (MT)',
            color='#3B82F6',
        )
        ax2.bar(
            x + width / 2,
            closing,
            width,
            label='Closing Stock (MT)',
            color='#10B981',
        )
        ax2.set_ylabel('Metric Tons (MT)', fontweight='bold')
        ax2.set_title(
            'Item-Wise Opening vs Closing Stock Balance',
            fontweight='bold',
            pad=12,
        )
        ax2.set_xticks(x)
        ax2.set_xticklabels(items, rotation=25, ha='right')
        ax2.legend()
        ax2.grid(axis='y', linestyle='--', alpha=0.5)
        plt.tight_layout()
        chart2_io = io.BytesIO()
        plt.savefig(chart2_io, format='png', dpi=200)
        plt.close()

    # Generate PDF
    pdf_buffer = build_pdf_report(sheets_data, chart1_io, chart2_io)

    st.success('All sheets mapped and PDF generated successfully!')
    st.download_button(
        label='📥 Download Godown Report PDF',
        data=pdf_buffer,
        file_name='Daily_Godown_Stock_Report.pdf',
        mime='application/pdf',
    )

  except Exception as e:
    st.error(f'Error reading workbook: {e}')
