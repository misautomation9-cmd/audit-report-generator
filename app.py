import io
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ReportLab Imports for Advanced PDF Generation
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Operations Audit: HR, Admin & Logistics",
    page_icon="🚚",
    layout="wide"
)

st.title("🚚 AUDIT & OPERATIONS DASHBOARD: HR, ADMIN & LOGISTICS")
st.caption("Upload daily Excel files to generate single-day reports or run side-by-side date comparisons.")

# --- HELPER FUNCTIONS ---

def clean_column_names(df):
    """Normalizes column names by removing extra spaces and forcing standard casing."""
    df.columns = [str(col).strip() for col in df.columns]
    return df

def parse_slash_separated_qty(val):
    """Splits values separated by '/' (e.g., '10/20.5/5' or '15') and returns their sum."""
    if pd.isna(val):
        return 0.0
    val_str = str(val).strip()
    if '/' in val_str:
        parts = val_str.split('/')
        total = 0.0
        for p in parts:
            try:
                total += float(p.strip())
            except ValueError:
                pass
        return total
    else:
        try:
            return float(val_str)
        except ValueError:
            return 0.0

def calculate_logistics_kpis(df):
    kpis = {}
    
    if "QTY" in df.columns:
        df["QTY_NUM"] = df["QTY"].apply(parse_slash_separated_qty)
    else:
        df["QTY_NUM"] = 0.0

    if "VEHICLE NO." in df.columns:
        kpis["Unique Vehicles Count"] = df["VEHICLE NO."].dropna().nunique()
        
    if "TRANSPORT" in df.columns:
        kpis["Unique Transports Count"] = df["TRANSPORT"].dropna().nunique()
        
    if "PARTY NAME (CUSTOMER)" in df.columns:
        kpis["Unique Parties Count"] = df["PARTY NAME (CUSTOMER)"].dropna().nunique()
        
    if "INVOICE NO." in df.columns:
        raw_invoices = df["INVOICE NO."].dropna().astype(str).tolist()
        split_invoices = set()
        for inv in raw_invoices:
            parts = [p.strip() for p in inv.split('/') if p.strip()]
            split_invoices.update(parts)
        kpis["Unique Invoices Count"] = len(split_invoices)
        
    if "QTY" in df.columns:
        kpis["Total Quantity (MT)"] = df["QTY_NUM"].sum()
        
    if "FREIGHT (IF)" in df.columns:
        total_freight = 0.0
        for _, row in df.iterrows():
            freight_str = str(row["FREIGHT (IF)"]).upper().strip()
            qty = float(row.get("QTY_NUM", 0.0))
            
            if "PMT" in freight_str:
                clean_num = ''.join(c for c in freight_str.replace("PMT", "").replace("/", "") if c.isdigit() or c == '.')
                try:
                    total_freight += float(clean_num) * qty
                except ValueError:
                    pass
            else:
                try:
                    total_freight += float(freight_str)
                except ValueError:
                    pass
        kpis["Total Freight (₹)"] = total_freight

    if "LOADING TIME" in df.columns:
        df["LOADING_NUM"] = pd.to_numeric(df["LOADING TIME"].astype(str).str.replace("HRS", "", case=False).str.strip(), errors='coerce').fillna(0)
        total_loading = df["LOADING_NUM"].sum()
        kpis["Total Loading Time (Hrs)"] = total_loading
        
        veh_count = kpis.get("Unique Vehicles Count", 0)
        if veh_count > 0:
            kpis["Average Loading Time / Vehicle (Hrs)"] = total_loading / veh_count

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

def generate_pdf_report(excel_data_dict, chart_images=None):
    """Generates clean, auto-wrapping landscape PDF report including visual charts."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=landscape(A4), 
        rightMargin=15, 
        leftMargin=15, 
        topMargin=15, 
        bottomMargin=15
    )
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(name="DocTitle", fontName="Helvetica-Bold", fontSize=15, leading=18, alignment=1, textColor=colors.HexColor('#1A252F'))
    subtitle_style = ParagraphStyle(name="DocSubTitle", fontName="Helvetica-Bold", fontSize=12, leading=15, textColor=colors.HexColor('#2E4053'))
    heading_style = ParagraphStyle(name="SectionHeading", fontName="Helvetica-Bold", fontSize=10, leading=13, textColor=colors.HexColor('#16A085'))
    
    cell_hdr_style = ParagraphStyle(name="CellHeader", fontName="Helvetica-Bold", fontSize=6, leading=7, textColor=colors.white, alignment=1)
    cell_body_style = ParagraphStyle(name="CellBody", fontName="Helvetica", fontSize=6, leading=7, textColor=colors.HexColor('#2C3E50'), alignment=0)

    story.append(Paragraph("OPERATIONS & AUDIT COMPREHENSIVE REPORT", title_style))
    story.append(Spacer(1, 10))

    # 1. ADD DATA TABLES WITH TEXT WRAPPING
    for file_label, excel_data in excel_data_dict.items():
        story.append(Paragraph(f"Data Set Source: {file_label}", subtitle_style))
        story.append(Spacer(1, 8))

        for sheet_name in ["HR AND ADMIN", "LOGISTICS AND DISPATCH"]:
            if sheet_name in excel_data:
                df = excel_data[sheet_name]
                story.append(Paragraph(f"Module: {sheet_name}", heading_style))
                story.append(Spacer(1, 4))

                clean_df = df.head(15).fillna("-")
                
                # Format headers and cells into Paragraphs for auto-wrap
                headers = [Paragraph(str(col), cell_hdr_style) for col in clean_df.columns]
                table_data = [headers]

                for _, row in clean_df.iterrows():
                    row_data = [Paragraph(str(val), cell_body_style) for val in row.values]
                    table_data.append(row_data)

                # Page width available = 842 (A4 Landscape width) - 30 (margins) = 812 pt
                num_cols = len(clean_df.columns)
                col_width = 812 / num_cols

                pdf_table = Table(table_data, colWidths=[col_width] * num_cols)
                pdf_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2C3E50')),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#BDC3C7')),
                    ('TOPPADDING', (0, 0), (-1, -1), 3),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                    ('LEFTPADDING', (0, 0), (-1, -1), 2),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                ]))
                story.append(pdf_table)
                story.append(Spacer(1, 10))

    # 2. EMBED Plotly GRAPHS INTO PDF
    if chart_images:
        story.append(Spacer(1, 5))
        story.append(Paragraph("Visual Performance Charts", subtitle_style))
        story.append(Spacer(1, 8))
        
        # Grid layout for charts in PDF
        img_elements = []
        for img_bytes in chart_images:
            img_buf = io.BytesIO(img_bytes)
            # 380pt width x 200pt height fits 2 charts per row on Landscape A4
            img_elements.append(RLImage(img_buf, width=380, height=200))
        
        # Group images side-by-side in pairs
        chart_rows = []
        for i in range(0, len(img_elements), 2):
            pair = img_elements[i:i+2]
            if len(pair) == 1:
                pair.append("") # Spacer filler if odd number of charts
            chart_rows.append(pair)
        
        chart_table = Table(chart_rows, colWidths=[395, 395])
        chart_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]))
        story.append(chart_table)

    doc.build(story)
    buffer.seek(0)
    return buffer

# --- SIDEBAR CONTROLS ---
st.sidebar.header("📁 Data Controls")

report_mode = st.sidebar.radio(
    "Select Report Type",
    ["Single Day View", "Multiple Day Comparison"]
)

excel_today = None
excel_yesterday = None

if report_mode == "Single Day View":
    file_today = st.sidebar.file_uploader("Upload Master Excel Workbook", type=["xlsx", "xls"], key="single_today")
    if file_today:
        raw_dict = pd.read_excel(file_today, sheet_name=None)
        excel_today = {str(k).upper().strip(): clean_column_names(v) for k, v in raw_dict.items()}
        st.sidebar.success(f"Loaded: {file_today.name}")

else:
    file_yesterday = st.sidebar.file_uploader("Upload Yesterday's Excel Workbook", type=["xlsx", "xls"], key="m_yest")
    file_today = st.sidebar.file_uploader("Upload Today's Excel Workbook", type=["xlsx", "xls"], key="m_today")
    
    if file_yesterday and file_today:
        raw_yest = pd.read_excel(file_yesterday, sheet_name=None)
        raw_tod = pd.read_excel(file_today, sheet_name=None)
        
        excel_yesterday = {str(k).upper().strip(): clean_column_names(v) for k, v in raw_yest.items()}
        excel_today = {str(k).upper().strip(): clean_column_names(v) for k, v in raw_tod.items()}
        st.sidebar.success("Both Workbooks Loaded Successfully!")

# --- MAIN WORKSPACE ---

if report_mode == "Single Day View":
    if excel_today:
        tab_hr, tab_log = st.tabs(["HR AND ADMIN", "LOGISTICS AND DISPATCH"])
        
        fig1, fig2, fig3 = None, None, None
        
        # 1. HR AND ADMIN SHEET
        with tab_hr:
            st.header("HR AND ADMIN")
            if "HR AND ADMIN" in excel_today:
                df_hr = excel_today["HR AND ADMIN"]
                if len(df_hr.columns) >= 3:
                    st.info(f"Dynamic 3rd Column Detected: **{df_hr.columns[2]}**")
                st.dataframe(df_hr, use_container_width=True)
            else:
                st.warning("Sheet 'HR AND ADMIN' not found in uploaded file.")
                
        # 2. LOGISTICS AND DISPATCH SHEET
        with tab_log:
            st.header("LOGISTICS AND DISPATCH")
            if "LOGISTICS AND DISPATCH" in excel_today:
                df_log = excel_today["LOGISTICS AND DISPATCH"]
                
                st.subheader("📌 Key Logistics Performance Indicators")
                kpis = calculate_logistics_kpis(df_log)
                display_kpis_safely(kpis)
                
                st.markdown("---")
                st.dataframe(df_log, use_container_width=True)
                
                st.markdown("---")
                st.subheader("📊 Visual Analytics")
                g1, g2, g3 = st.columns(3)
                
                with g1:
                    if "PARTY NAME (CUSTOMER)" in df_log.columns and "QTY" in df_log.columns:
                        fig1 = px.bar(
                            df_log, 
                            x="PARTY NAME (CUSTOMER)", 
                            y="QTY_NUM", 
                            title="Total Quantity (MT) per Party Name",
                            labels={"QTY_NUM": "Quantity (MT)"},
                            color="PARTY NAME (CUSTOMER)"
                        )
                        st.plotly_chart(fig1, use_container_width=True)
                
                with g2:
                    if "PARTY NAME (CUSTOMER)" in df_log.columns and "LOADING TIME" in df_log.columns:
                        fig2 = px.bar(
                            df_log, 
                            x="PARTY NAME (CUSTOMER)", 
                            y="LOADING_NUM", 
                            title="Total Loading Time (Hrs) per Party Name",
                            labels={"LOADING_NUM": "Loading Hours"},
                            color_discrete_sequence=["#FF9900"]
                        )
                        st.plotly_chart(fig2, use_container_width=True)

                with g3:
                    if "PARTY NAME (CUSTOMER)" in df_log.columns and "INVOICE NO." in df_log.columns:
                        inv_df = df_log.groupby("PARTY NAME (CUSTOMER)")["INVOICE NO."].nunique().reset_index()
                        inv_df.columns = ["PARTY NAME (CUSTOMER)", "Invoice Count"]
                        fig3 = px.pie(
                            inv_df, 
                            names="PARTY NAME (CUSTOMER)", 
                            values="Invoice Count", 
                            title="No. of Unique Invoices per Customer"
                        )
                        st.plotly_chart(fig3, use_container_width=True)
            else:
                st.warning("Sheet 'LOGISTICS AND DISPATCH' not found in uploaded file.")

        # SIDEBAR PDF DOWNLOAD WITH CHARTS
        chart_bytes = []
        for fig in [fig1, fig2, fig3]:
            if fig is not None:
                try:
                    img_data = fig.to_image(format="png", width=700, height=400)
                    chart_bytes.append(img_data)
                except Exception as e:
                    st.sidebar.warning("Install `kaleido` (`pip install kaleido`) to include charts in PDF export.")
                    break

        pdf_buf = generate_pdf_report({"Today": excel_today}, chart_images=chart_bytes)
        st.sidebar.download_button("📥 Download PDF Report (With Graphs)", pdf_buf, "Daily_Audit_Report.pdf", "application/pdf")

    else:
        st.info("Please upload an Excel file to generate the single-day report.")

# MULTIPLE DAY COMPARISON VIEW
else:
    if excel_yesterday and excel_today:
        tab_hr, tab_log = st.tabs(["HR AND ADMIN COMPARISON", "LOGISTICS COMPARISON"])
        fig_comp = None
        
        with tab_hr:
            st.header("HR AND ADMIN — Side-by-Side Comparison")
            df_hr_y = excel_yesterday.get("HR AND ADMIN")
            df_hr_t = excel_today.get("HR AND ADMIN")
            
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("📅 Yesterday")
                if df_hr_y is not None:
                    st.dataframe(df_hr_y, use_container_width=True)
            with c2:
                st.subheader("📅 Today")
                if df_hr_t is not None:
                    st.dataframe(df_hr_t, use_container_width=True)
                    
        with tab_log:
            st.header("LOGISTICS AND DISPATCH — Side-by-Side & Variance Comparison")
            df_log_y = excel_yesterday.get("LOGISTICS AND DISPATCH")
            df_log_t = excel_today.get("LOGISTICS AND DISPATCH")
            
            if df_log_y is not None and df_log_t is not None:
                kpis_y = calculate_logistics_kpis(df_log_y)
                kpis_t = calculate_logistics_kpis(df_log_t)
                
                st.subheader("📈 KPI Variance Summary")
                comp_rows = []
                all_keys = set(kpis_y.keys()).union(set(kpis_t.keys()))
                
                for k in all_keys:
                    val_y = kpis_y.get(k, 0.0)
                    val_t = kpis_t.get(k, 0.0)
                    diff = val_t - val_y
                    comp_rows.append({
                        "Metric Name": k,
                        "Yesterday": round(val_y, 2),
                        "Today": round(val_t, 2),
                        "Variance (Difference)": round(diff, 2)
                    })
                
                df_comp = pd.DataFrame(comp_rows)
                st.dataframe(df_comp, use_container_width=True)
                
                fig_comp = go.Figure(data=[
                    go.Bar(name='Yesterday', x=df_comp['Metric Name'], y=df_comp['Yesterday'], marker_color='#AB63FA'),
                    go.Bar(name='Today', x=df_comp['Metric Name'], y=df_comp['Today'], marker_color='#00CC96')
                ])
                fig_comp.update_layout(barmode='group', title="Logistics KPI Comparison")
                st.plotly_chart(fig_comp, use_container_width=True)
                
                c1, c2 = st.columns(2)
                with c1:
                    st.subheader("📅 Yesterday's Raw Data")
                    st.dataframe(df_log_y, use_container_width=True)
                with c2:
                    st.subheader("📅 Today's Raw Data")
                    st.dataframe(df_log_t, use_container_width=True)

        chart_bytes = []
        if fig_comp is not None:
            try:
                img_data = fig_comp.to_image(format="png", width=700, height=400)
                chart_bytes.append(img_data)
            except Exception:
                pass

        pdf_buf = generate_pdf_report({
            f"Yesterday ({file_yesterday.name})": excel_yesterday,
            f"Today ({file_today.name})": excel_today
        }, chart_images=chart_bytes)
        st.sidebar.download_button("📥 Download Comparative PDF Report", pdf_buf, "Comparative_Audit_Report.pdf", "application/pdf")
    else:
        st.info("Please upload both Yesterday's and Today's Excel files to view comparison metrics.")
