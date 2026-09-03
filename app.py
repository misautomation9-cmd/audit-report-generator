import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import io

# ReportLab Imports
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

st.set_page_config(page_title="Enterprise Reporting Portal", layout="wide")

# --- Function to Generate Chart Image Stream ---
def generate_stock_chart():
    fig, ax = plt.subplots(figsize=(6, 2.5))
    items = ['CHQ COIL', 'HR COIL', 'HR PLATE', 'HT COIL', 'PM PLATE']
    opening = [567.19, 3576.35, 589.52, 614.05, 897.75]
    closing = [538.63, 5557.50, 680.33, 950.60, 902.02]
    
    x = range(len(items))
    ax.bar([i - 0.2 for i in x], opening, width=0.4, label='Opening (MT)', color='#4A90E2')
    ax.bar([i + 0.2 for i in x], closing, width=0.4, label='Closing (MT)', color='#50E3C2')
    ax.set_xticks(x)
    ax.set_xticklabels(items, rotation=15, fontsize=8)
    ax.set_ylabel("Metric Tons (MT)")
    ax.legend(fontsize=8)
    plt.tight_layout()
    
    img_buf = io.BytesIO()
    plt.savefig(img_buf, format='png', dpi=150)
    plt.close(fig)
    img_buf.seek(0)
    return img_buf

# --- Function to Build the PDF ---
def build_godown_pdf():
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()

    # Title & Header Styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=14,
        textColor=colors.HexColor('#1A2B4C'),
        spaceAfter=4
    )
    subtitle_style = ParagraphStyle(
        'DocSub',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.gray,
        spaceAfter=12
    )
    section_style = ParagraphStyle(
        'SecTitle',
        parent=styles['Heading2'],
        fontSize=11,
        textColor=colors.HexColor('#2C3E50'),
        spaceBefore=10,
        spaceAfter=6
    )

    # 1. Header Block
    story.append(Paragraph("DAILY GODOWN DISPATCH & STOCK MOVEMENTS REPORT", title_style))
    story.append(Paragraph("Consolidated report covering dispatches and itemized stock balances.", subtitle_style))
    story.append(Spacer(1, 8))

    # 2. Table: Salesperson Dispatch Summary
    story.append(Paragraph("1. Salesperson-Wise Dispatch Summary", section_style))
    sales_data = [
        ["Sales Person", "Sheet/Date", "Total Vehicles", "Parties Served", "Remarks"],
        ["AKASH JI", "GD 19-09-2026", "2", "STEEL TMT HUB INDIA", "NO ADJUSTMENT"],
        ["DEEPANKAR JI", "GD 20-09-2026", "5", "OFB TECH LTD, AGRASEN ISPAT", "Yesterday vehicle dispatch"],
        ["SONU JI", "GD 20-09-2026", "7", "RELIABLE STEEL MONGERS", "Pending for dispatch"]
    ]
    
    table_1 = Table(sales_data, colWidths=[90, 80, 70, 160, 120])
    table_1.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1A2B4C')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#D1D5DB')),
    ]))
    story.append(table_1)
    story.append(Spacer(1, 12))

    # 3. Table: Item Stock Breakdown
    story.append(Paragraph("2. Item-Wise Stock Breakdown (Opening vs Closing)", section_style))
    stock_data = [
        ["Particulars/Item", "Opening Stock (MT)", "Closing Stock (MT)", "Variance (MT)"],
        ["CHQ COIL", "567.19", "538.63", "-28.56"],
        ["HR COIL", "3,576.35", "5,557.50", "+1,981.15"],
        ["HR PLATE", "589.52", "680.33", "+90.81"],
        ["HT COIL", "614.05", "950.60", "+336.55"]
    ]
    table_2 = Table(stock_data, colWidths=[150, 120, 120, 130])
    table_2.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2C3E50')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#D1D5DB')),
    ]))
    story.append(table_2)
    story.append(Spacer(1, 12))

    # 4. Embedded Visual Chart
    story.append(Paragraph("3. Visual Analytics", section_style))
    chart_stream = generate_stock_chart()
    story.append(Image(chart_stream, width=520, height=210))

    # Render document
    doc.build(story)
    pdf_buffer.seek(0)
    return pdf_buffer.getvalue()

# --- Streamlit UI App ---
st.title("📦 Daily Godown Dispatch Portal")

uploaded_file = st.file_uploader("Upload Daily Stock Data", type=["xlsx", "csv"])

if uploaded_file or st.button("Generate Stock Report PDF"):
    with st.spinner("Generating PDF Report..."):
        pdf_bytes = build_godown_pdf()
        
    st.success("PDF Report successfully generated!")
    
    st.download_button(
        label="📥 Download Daily Godown Stock Report (PDF)",
        data=pdf_bytes,
        file_name="Daily_Godown_Stock_Report.pdf",
        mime="application/pdf"
    )
