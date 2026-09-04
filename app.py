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
st.caption("Upload daily Excel workbooks to analyze departmental KPIs, perform multi-day comparisons, and export audit reports.")

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

# --- HELPER FUNCTIONS FOR CALCULATIONS & METRICS ---

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
    
    # Freight Calculation (PMT vs Fixed)
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
        if "Vehicle No" in df.columns and kpis.get("Unique Vehicles Count", 0) > 0:
            kpis["Average Loading Time / Vehicle"] = kpis["Total Loading Hours"] / kpis["Unique Vehicles Count"]

    return kpis

def display_kpis_safely(kpis):
    if kpis:
        max_cols_per_row = 4
        kpi_items = list(kpis.items())
        for i in range(0, len(kpi_items), max_cols_per_row):
            batch = kpi_items[i:i + max_cols_per_row]
            cols = st.columns(len(batch))
            for idx, (k, v) in enumerate(batch):
                val_str = f"{v:,.2f}" if isinstance(v, float) else str(v)
                cols[idx].metric(label=k, value=val_str)

def generate_pdf_report(excel_data_dict, filename="Daily_Audit_Report.pdf"):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(name="TitleStyle", fontName="Helvetica-Bold", fontSize=16, leading=20, alignment=1, textColor=colors.HexColor("#1A252F"))
    heading_style = ParagraphStyle(name="HeadingStyle", fontName="Helvetica-Bold", fontSize=12, leading=16, textColor=colors.HexColor("#2C3E50"))

    story.append(Paragraph("DAILY GODOWN DISPATCH, STOCK & OPERATIONAL AUDIT REPORT", title_style))
    story.append(Spacer(1, 15))

    # Handles single dictionary of sheets or comparison dictionary of files
    for file_label, excel_data in excel_data_dict.items():
        story.append(Paragraph(f"Data Source: {file_label}", title_style))
        story.append(Spacer(1, 10))

        for sheet_name in EXPECTED_SHEETS:
            if sheet_name in excel_data:
                df = excel_data[sheet_name]
                story.append(Paragraph(f"Module: {sheet_name}", heading_style))
                story.append(Spacer(1, 5))

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
st.sidebar.header("📂 Operational Data Controls")

# NEW: REPORT MODE SELECTION
report_mode = st.sidebar.radio(
    "Select Reporting Mode",
    ["Single Day View", "Multiple Day Comparison"]
)

excel_data_today = None
excel_data_yesterday = None

if report_mode == "Single Day View":
    uploaded_today = st.sidebar.file_uploader("Upload Today's Master Excel Workbook", type=["xlsx", "xls"], key="single_today")
    if uploaded_today is not None:
        excel_data_today = pd.read_excel(uploaded_today, sheet_name=None)
        st.sidebar.success(f"Workbook '{uploaded_today.name}' Loaded!")
        
        pdf_buf = generate_pdf_report({"Today": excel_data_today})
        st.sidebar.download_button(
            label="📥 Download Audit PDF Report",
            data=pdf_buf,
            file_name="Daily_Audit_Report.pdf",
            mime="application/pdf"
        )

else:
    uploaded_yesterday = st.sidebar.file_uploader("Upload Yesterday's Excel Workbook", type=["xlsx", "xls"], key="multi_yest")
    uploaded_today = st.sidebar.file_uploader("Upload Today's Master Excel Workbook", type=["xlsx", "xls"], key="multi_today")
    
    if uploaded_yesterday is not None and uploaded_today is not None:
        excel_data_yesterday = pd.read_excel(uploaded_yesterday, sheet_name=None)
        excel_data_today = pd.read_excel(uploaded_today, sheet_name=None)
        st.sidebar.success("Both Yesterday and Today Workbooks Loaded!")
        
        pdf_buf = generate_pdf_report({
            f"Yesterday ({uploaded_yesterday.name})": excel_data_yesterday,
            f"Today ({uploaded_today.name})": excel_data_today
        })
        st.sidebar.download_button(
            label="📥 Download Comparative PDF Report",
            data=pdf_buf,
            file_name="Comparative_Audit_Report.pdf",
            mime="application/pdf"
        )

# --- MAIN WORKSPACE RENDER ---

if report_mode == "Single Day View":
    if excel_data_today is not None:
        tabs = st.tabs(EXPECTED_SHEETS)

        # 1. HR AND ADMIN
        with tabs[0]:
            st.header("HR And Admin Report")
            if "HR And Admin" in excel_data_today:
                st.dataframe(excel_data_today["HR And Admin"], use_container_width=True)

        # 2. LOGISTICS AND DISPATCH
        with tabs[1]:
            st.header("Logistics And Dispatch Analytics")
            if "Logistics And Dispatch" in excel_data_today:
                df = excel_data_today["Logistics And Dispatch"]
                display_kpis_safely(calculate_logistics_kpis(df))
                st.markdown("---")
                st.dataframe(df, use_container_width=True)
                if "Vehicle No" in df.columns and "QNTY" in df.columns:
                    fig = px.bar(df, x="Vehicle No", y="QNTY", title="Dispatch Quantity Tonnage per Vehicle", color="Transport" if "Transport" in df.columns else None)
                    st.plotly_chart(fig, use_container_width=True)

        # 3. PURCHASE ORDER
        with tabs[2]:
            st.header("Purchase Order Summary")
            if "Purchase Order" in excel_data_today:
                df = excel_data_today["Purchase Order"]
                kpis = {}
                if "PO" in df.columns: kpis["Unique POs"] = df["PO"].nunique()
                if "Party Name" in df.columns: kpis["Unique Parties"] = df["Party Name"].nunique()
                if "Pcs" in df.columns: kpis["Total Pieces"] = df["Pcs"].sum()
                if "Qty" in df.columns: kpis["Total PO Qty"] = df["Qty"].sum()
                if "Rate" in df.columns: kpis["Avg Purchase Rate (₹)"] = df["Rate"].mean()
                display_kpis_safely(kpis)
                st.dataframe(df, use_container_width=True)

        # 4. PURCHASE PLATES
        with tabs[3]:
            st.header("Purchase Pending Plates Report")
            if "Purchase Plates" in excel_data_today:
                df = excel_data_today["Purchase Plates"]
                kpis = {}
                if "PO" in df.columns: kpis["Unique Pending POs"] = df["PO"].nunique()
                if "Party" in df.columns: kpis["Unique Suppliers"] = df["Party"].nunique()
                if "Recd Qty" in df.columns: kpis["Received Qty"] = df["Recd Qty"].sum()
                if "Pending" in df.columns: kpis["Pending Qty"] = df["Pending"].sum()
                display_kpis_safely(kpis)
                st.dataframe(df, use_container_width=True)

        # 5. PURCHASE STRUCTURE
        with tabs[4]:
            st.header("Purchase Pending Structure Report")
            if "Purchase Structure" in excel_data_today:
                st.dataframe(excel_data_today["Purchase Structure"], use_container_width=True)

        # 6. SALES AND MARKETING
        with tabs[5]:
            st.header("Sales & Marketing Performance Report")
            if "Sales And Marketing" in excel_data_today:
                df = excel_data_today["Sales And Marketing"]
                st.dataframe(df, use_container_width=True)
                if "Sales Person" in df.columns and "Order Value" in df.columns:
                    fig = px.pie(df, names="Sales Person", values="Order Value", title="Order Value Contribution by Sales Person")
                    st.plotly_chart(fig, use_container_width=True)

        # 7. ACCOUNTS
        with tabs[6]:
            st.header("Accounts & Financial Audit Summary")
            if "Accounts" in excel_data_today:
                st.dataframe(excel_data_today["Accounts"], use_container_width=True)

        # 8. SALES PERSON WISE DISPATCH
        with tabs[7]:
            st.header("Salesperson-Wise Dispatch Summary")
            if "Sales Person Wise Dispatch" in excel_data_today:
                df = excel_data_today["Sales Person Wise Dispatch"]
                st.dataframe(df, use_container_width=True)
                if "Sales Person" in df.columns and "Total Vehicles" in df.columns:
                    fig = px.bar(df, x="Sales Person", y="Total Vehicles", color="Sales Person", text="Total Vehicles", title="Total Vehicles Handled per Salesperson")
                    st.plotly_chart(fig, use_container_width=True)

        # 9. STOCK
        with tabs[8]:
            st.header("Stock Balance & Movement Analysis")
            if "Stock" in excel_data_today:
                df = excel_data_today["Stock"]
                if "Opening Stock (MT)" in df.columns and "Closing Stock (MT)" in df.columns:
                    df["Variance (MT)"] = df["Closing Stock (MT)"] - df["Opening Stock (MT)"]
                st.dataframe(df, use_container_width=True)
                
                item_col = "Particulars" if "Particulars" in df.columns else ("Particulars/Item" if "Particulars/Item" in df.columns else None)
                if item_col:
                    fig = go.Figure(data=[
                        go.Bar(name='Opening Stock (MT)', x=df[item_col], y=df['Opening Stock (MT)'], marker_color='#3366CC'),
                        go.Bar(name='Closing Stock (MT)', x=df[item_col], y=df['Closing Stock (MT)'], marker_color='#109618')
                    ])
                    if "Yesterday Production (MT)" in df.columns:
                        fig.add_trace(go.Bar(name='Yesterday Production (MT)', x=df[item_col], y=df['Yesterday Production (MT)'], marker_color='#FF9900'))
                    if "Dispatch Stock (MT)" in df.columns:
                        fig.add_trace(go.Bar(name='Dispatch Stock (MT)', x=df[item_col], y=df['Dispatch Stock (MT)'], marker_color='#DC3912'))
                    fig.update_layout(barmode='group', title="Item-Wise Stock Breakdown & Movement (MT)")
                    st.plotly_chart(fig, use_container_width=True)

    else:
        st.info("Upload Today's Excel file in the sidebar to start processing single-day reports.")

# COMPARATIVE MULTI-DAY MODE
else:
    if excel_data_yesterday is not None and excel_data_today is not None:
        tabs = st.tabs(EXPECTED_SHEETS)

        for idx, sheet_name in enumerate(EXPECTED_SHEETS):
            with tabs[idx]:
                st.header(f"Comparative Analysis: {sheet_name}")

                df_yest = excel_data_yesterday.get(sheet_name)
                df_today = excel_data_today.get(sheet_name)

                if df_yest is not None and df_today is not None:
                    col1, col2 = st.columns(2)
                    with col1:
                        st.subheader("📅 Yesterday's Report")
                        st.dataframe(df_yest, use_container_width=True)
                    with col2:
                        st.subheader("📅 Today's Report")
                        st.dataframe(df_today, use_container_width=True)

                    st.markdown("---")
                    st.subheader(f"📊 Quantitative Variance Summary — {sheet_name}")

                    # Automatically extract and compare numeric metrics
                    num_cols_yest = df_yest.select_dtypes(include=['number']).columns
                    num_cols_today = df_today.select_dtypes(include=['number']).columns
                    common_num_cols = list(set(num_cols_yest).intersection(set(num_cols_today)))

                    if common_num_cols:
                        comp_metrics = []
                        for col in common_num_cols:
                            val_y = df_yest[col].sum()
                            val_t = df_today[col].sum()
                            diff = val_t - val_y
                            comp_metrics.append({
                                "Metric Name": col,
                                "Yesterday Total": round(val_y, 2),
                                "Today Total": round(val_t, 2),
                                "Variance (Difference)": round(diff, 2)
                            })
                        
                        df_comp = pd.DataFrame(comp_metrics)
                        st.dataframe(df_comp, use_container_width=True)

                        # Comparative Chart
                        fig_comp = go.Figure(data=[
                            go.Bar(name='Yesterday', x=df_comp['Metric Name'], y=df_comp['Yesterday Total'], marker_color='#AB63FA'),
                            go.Bar(name='Today', x=df_comp['Metric Name'], y=df_comp['Today Total'], marker_color='#00CC96')
                        ])
                        fig_comp.update_layout(barmode='group', title=f"Metric Comparison ({sheet_name})")
                        st.plotly_chart(fig_comp, use_container_width=True)
                    else:
                        st.info("No common numeric columns found to calculate automated variances.")
                else:
                    st.warning(f"Sheet '{sheet_name}' is missing in one or both uploaded workbooks.")
    else:
        st.info("Upload both Yesterday's and Today's Excel workbooks in the sidebar to run the multi-day comparison analysis.")
