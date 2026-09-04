import io
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ReportLab Imports for PDF Generation
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Godown & Operations Master Audit System",
    page_icon="🏭",
    layout="wide"
)

st.title("🏭 GODOWN & OPERATIONS MASTER AUDIT DASHBOARD")
st.caption("Upload daily Excel workbooks to analyze departmental KPIs, render visual analytics, and export standardized PDF audit reports.")

# --- EXPECTED SHEETS DEFINITION ---
EXPECTED_SHEETS = [
    "HR And Admin",
    "Logistics And Dispatch",
    "Purchase Order",
    "Purchase Plates",
    "Purchase Structure",
    "Sales And Marketing",
    "Accounts",
    "Sales Person Wise Dispatch",
    "Stock"
]

# --- HELPER FUNCTIONS FOR CALCULATIONS ---

def calculate_logistics_kpis(df):
    kpis = {}
    if "Vehicle No" in df.columns:
        kpis["Unique Vehicles Count"] = df["Vehicle No"].nunique()
    if "Transport" in df.columns:
        kpis["Unique Transports Count"] = df["Transport"].nunique()
    if "Party Name" in df.columns:
        kpis["Unique Parties Count"] = df["Party Name"].nunique()
    if "Invoice No" in df.columns:
        kpis["Unique Invoices Count"] = df["Invoice No"].astype(str).nunique()
    if "QNTY" in df.columns:
        kpis["Total Quantity (MT)"] = df["QNTY"].sum()
    
    # Custom Freight Calculation (PMT vs Fixed)
    if "FREIGHT" in df.columns:
        total_freight = 0.0
        for _, row in df.iterrows():
            freight_val = str(row["FREIGHT"]).strip()
            qty = row.get("QNTY", 1.0)
            if "PMT" in freight_val.upper():
                try:
                    rate = float(freight_val.upper().replace("/PMT", "").replace("PMT", "").strip())
                    total_freight += rate * float(qty)
                except ValueError:
                    pass
            else:
                try:
                    total_freight += float(freight_val)
                except ValueError:
                    pass
        kpis["Calculated Total Freight (₹)"] = total_freight

    if "Loading Hours" in df.columns:
        kpis["Total Loading Hours"] = df["Loading Hours"].sum()
        if "Vehicle No" in df.columns and kpis["Unique Vehicles Count"] > 0:
            kpis["Average Loading Time / Vehicle"] = kpis["Total Loading Hours"] / kpis["Unique Vehicles Count"]

    return kpis

def generate_pdf_report(excel_data, filename="Daily_Audit_Report.pdf"):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(name="TitleStyle", fontName="Helvetica-Bold", fontSize=16, leading=20, alignment=1, textColor=colors.HexColor("#1A252F"))
    heading_style = ParagraphStyle(name="HeadingStyle", fontName="Helvetica-Bold", fontSize=12, leading=16, textColor=colors.HexColor("#2C3E50"))
    body_style = ParagraphStyle(name="BodyStyle", fontName="Helvetica", fontSize=8, leading=10)

    story.append(Paragraph("DAILY GODOWN DISPATCH, STOCK & OPERATIONAL AUDIT REPORT", title_style))
    story.append(Spacer(1, 15))

    for sheet_name in EXPECTED_SHEETS:
        if sheet_name in excel_data:
            df = excel_data[sheet_name]
            story.append(Paragraph(f"Module: {sheet_name}", heading_style))
            story.append(Spacer(1, 5))

            # Convert Dataframe to Table format (limiting to first 10 rows for PDF summary readability)
            display_df = df.head(10).astype(str)
            table_data = [display_df.columns.tolist()] + display_df.values.tolist()
            
            pdf_table = Table(table_data)
            pdf_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F2F4F4')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1A252F')),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 7),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#B0BEC5')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ]))
            story.append(pdf_table)
            story.append(Spacer(1, 12))

    doc.build(story)
    buffer.seek(0)
    return buffer

# --- SIDEBAR & NAVIGATION ---
st.sidebar.header("📁 Operational Data Controls")
uploaded_file = st.sidebar.file_uploader("Upload Daily Master Excel Workbook", type=["xlsx", "xls"])

if uploaded_file is not None:
    excel_data = pd.read_excel(uploaded_file, sheet_name=None)
    st.sidebar.success(f"Workbook '{uploaded_file.name}' Loaded!")

    # PDF Download Button
    pdf_buffer = generate_pdf_report(excel_data)
    st.sidebar.download_button(
        label="📥 Download Audit PDF Report",
        data=pdf_buffer,
        file_name="Daily_Audit_Report.pdf",
        mime="application/pdf"
    )

    # Main Tabs for Reports
    tabs = st.tabs(EXPECTED_SHEETS)

    # 1. HR AND ADMIN
    with tabs[0]:
        st.header("HR And Admin Report")
        if "HR And Admin" in excel_data:
            df_hr = excel_data["HR And Admin"]
            st.dataframe(df_hr, use_container_width=True)
        else:
            st.warning("Sheet 'HR And Admin' not found.")

    # 2. LOGISTICS AND DISPATCH
    with tabs[1]:
        st.header("Logistics And Dispatch Analytics")
        if "Logistics And Dispatch" in excel_data:
            df_log = excel_data["Logistics And Dispatch"]
            
            kpis = calculate_logistics_kpis(df_log)
            cols = st.columns(len(kpis))
            for idx, (k, v) in enumerate(kpis.items()):
                val_str = f"{v:,.2f}" if isinstance(v, float) else str(v)
                cols[idx].metric(label=k, value=val_str)

            st.markdown("---")
            st.dataframe(df_log, use_container_width=True)

            if "Vehicle No" in df_log.columns and "QNTY" in df_log.columns:
                fig = px.bar(df_log, x="Vehicle No", y="QNTY", title="Dispatch Quantity Tonnage per Vehicle", color="Transport")
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Sheet 'Logistics And Dispatch' not found.")

    # 3. PURCHASE ORDER
    with tabs[2]:
        st.header("Purchase Order Summary")
        if "Purchase Order" in excel_data:
            df_po = excel_data["Purchase Order"]
            
            m1, m2, m3, m4, m5 = st.columns(5)
            if "PO" in df_po.columns: m1.metric("Unique POs", df_po["PO"].nunique())
            if "Party Name" in df_po.columns: m2.metric("Unique Parties", df_po["Party Name"].nunique())
            if "Pcs" in df_po.columns: m3.metric("Total Pieces", df_po["Pcs"].sum())
            if "Qty" in df_po.columns: m4.metric("Total PO Qty", f"{df_po['Qty'].sum():,.2f}")
            if "Rate" in df_po.columns: m5.metric("Avg Purchase Rate", f"₹{df_po['Rate'].mean():,.2f}")

            st.dataframe(df_po, use_container_width=True)
        else:
            st.warning("Sheet 'Purchase Order' not found.")

    # 4. PURCHASE PLATES (PENDING)
    with tabs[3]:
        st.header("Purchase Pending Plates Report")
        if "Purchase Plates" in excel_data:
            df_pp = excel_data["Purchase Plates"]
            
            c1, c2, c3, c4 = st.columns(4)
            if "PO" in df_pp.columns: c1.metric("Unique Pending POs", df_pp["PO"].nunique())
            if "Party" in df_pp.columns: c2.metric("Unique Suppliers", df_pp["Party"].nunique())
            if "Recd Qty" in df_pp.columns: c3.metric("Received Qty", f"{df_pp['Recd Qty'].sum():,.2f}")
            if "Pending" in df_pp.columns: c4.metric("Pending Qty", f"{df_pp['Pending'].sum():,.2f}")

            st.dataframe(df_pp, use_container_width=True)
        else:
            st.warning("Sheet 'Purchase Plates' not found.")

    # 5. PURCHASE STRUCTURE (PENDING)
    with tabs[4]:
        st.header("Purchase Pending Structure Report")
        if "Purchase Structure" in excel_data:
            df_ps = excel_data["Purchase Structure"]
            st.dataframe(df_ps, use_container_width=True)
        else:
            st.warning("Sheet 'Purchase Structure' not found.")

    # 6. SALES AND MARKETING
    with tabs[5]:
        st.header("Sales & Marketing Performance Report")
        if "Sales And Marketing" in excel_data:
            df_sales = excel_data["Sales And Marketing"]
            st.dataframe(df_sales, use_container_width=True)

            if "Sales Person" in df_sales.columns and "Order Value" in df_sales.columns:
                fig_sales = px.pie(df_sales, names="Sales Person", values="Order Value", title="Order Value Contribution by Sales Person")
                st.plotly_chart(fig_sales, use_container_width=True)
        else:
            st.warning("Sheet 'Sales And Marketing' not found.")

    # 7. ACCOUNTS
    with tabs[6]:
        st.header("Accounts & Financial Audit Summary")
        if "Accounts" in excel_data:
            df_acc = excel_data["Accounts"]
            st.dataframe(df_acc, use_container_width=True)
        else:
            st.warning("Sheet 'Accounts' not found.")

    # 8. SALES PERSON WISE DISPATCH
    with tabs[7]:
        st.header("Salesperson-Wise Dispatch Comparison")
        if "Sales Person Wise Dispatch" in excel_data:
            df_sp_disp = excel_data["Sales Person Wise Dispatch"]
            st.dataframe(df_sp_disp, use_container_width=True)

            if "Sales Person" in df_sp_disp.columns and "Total Vehicles" in df_sp_disp.columns:
                fig_sp = px.bar(df_sp_disp, x="Sales Person", y="Total Vehicles", color="Sales Person", text="Total Vehicles", title="Total Vehicles Handled per Salesperson")
                st.plotly_chart(fig_sp, use_container_width=True)
        else:
            st.warning("Sheet 'Sales Person Wise Dispatch' not found.")

    # 9. STOCK
    with tabs[8]:
        st.header("Stock Balance & Movement Analysis")
        if "Stock" in excel_data:
            df_stock = excel_data["Stock"]
            
            # Calculate Variance
            if "Opening Stock (MT)" in df_stock.columns and "Closing Stock (MT)" in df_stock.columns:
                df_stock["Variance (MT)"] = df_stock["Closing Stock (MT)"] - df_stock["Opening Stock (MT)"]
            
            st.dataframe(df_stock, use_container_width=True)

            # Stock Graph
            if "Particulars" in df_stock.columns or "Particulars/Item" in df_stock.columns:
                item_col = "Particulars" if "Particulars" in df_stock.columns else "Particulars/Item"
                
                fig_stock = go.Figure(data=[
                    go.Bar(name='Opening Stock (MT)', x=df_stock[item_col], y=df_stock['Opening Stock (MT)'], marker_color='#3366CC'),
                    go.Bar(name='Closing Stock (MT)', x=df_stock[item_col], y=df_stock['Closing Stock (MT)'], marker_color='#109618')
                ])
                if "Yesterday Production (MT)" in df_stock.columns:
                    fig_stock.add_trace(go.Bar(name='Yesterday Production (MT)', x=df_stock[item_col], y=df_stock['Yesterday Production (MT)'], marker_color='#FF9900'))
                if "Dispatch Stock (MT)" in df_stock.columns:
                    fig_stock.add_trace(go.Bar(name='Dispatch Stock (MT)', x=df_stock[item_col], y=df_stock['Dispatch Stock (MT)'], marker_color='#DC3912'))

                fig_stock.update_layout(barmode='group', title="Item-Wise Stock Breakdown & Movement (MT)", yaxis_title="Metric Tons (MT)")
                st.plotly_chart(fig_stock, use_container_width=True)
        else:
            st.warning("Sheet 'Stock' not found.")

else:
    st.info("Upload your daily Excel file in the sidebar to view metrics, interactive charts, and export the PDF report.")
