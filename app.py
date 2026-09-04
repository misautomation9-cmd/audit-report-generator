import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Daily Godown Dispatch & Audit Dashboard",
    page_icon="📊",
    layout="wide"
)

# --- TITLE & SUBTITLE ---
st.title("DAILY GODOWN DISPATCH & STOCK MOVEMENTS REPORT")
st.caption("Consolidated report covering dispatches, delayed yesterday vehicle dispatches, and itemized stock balances.")

# --- SIDEBAR CONTROLS ---
st.sidebar.header("Filter Options")
report_type = st.sidebar.radio(
    "Select View Mode",
    ["Daily Godown Stock Report", "Dynamic Date-Wise Audit Comparison"]
)

if report_type == "Daily Godown Stock Report":
    # -------------------------------------------------------------------------
    # 1. SALESPERSON-WISE DISPATCH SUMMARY
    # -------------------------------------------------------------------------
    st.header("1. Salesperson-Wise Dispatch Summary")
    
    sales_summary_data = [
        {"Sales Person": "AKASH JI", "Sheet/Date": "GD 19-09-2026", "Total Vehicles": 2, "Parties Served": "STEEL TMT HUB INDIA, NILESH SHAH (RAJDEEP STEEL PRODUCTS/SHIP TO RAIPUR)", "Adjustment/Remarks": "NO ADJUSTMENT"},
        {"Sales Person": "AKASH JI", "Sheet/Date": "GD 20-09-2026", "Total Vehicles": 5, "Parties Served": "JMD TRADING COMPANY, OM INDUSTRIES TILDA, SG MART, RADIANT METAL ALLOYS, VRIDHI CONSTRUCTION", "Adjustment/Remarks": "No adjustment"},
        {"Sales Person": "DEEPANKAR JI", "Sheet/Date": "GD 19-09-2026", "Total Vehicles": 4, "Parties Served": "LOHA LIVE PLATFORM, HARI AGRAWAL (RAMETI ENTERPRISES), BANKE TRADECOM SERVICE, VANKAL CABLES", "Adjustment/Remarks": "NO ADJUSTMENT"},
        {"Sales Person": "DEEPANKAR JI", "Sheet/Date": "GD 20-09-2026", "Total Vehicles": 5, "Parties Served": "OFB TECH LIMITED MAHARASHTRA, DP BANSAL COMMERCIAL COMPANY, ANAND STEEL SAGAR, AGRASEN ISPAT, SHREEJI STEEL SURAT", "Adjustment/Remarks": "yesterday vehicle dispatch 20.08.2026, No adjustment"},
        {"Sales Person": "DIPESH JI", "Sheet/Date": "GD 19-09-2026", "Total Vehicles": 2, "Parties Served": "ISPAT SALES (A UNIT OF AGS ISPAT), VISHWAGEETA ISPAT", "Adjustment/Remarks": "NO ADJUSTMENT"},
        {"Sales Person": "DIPESH JI", "Sheet/Date": "GD 20-09-2026", "Total Vehicles": 4, "Parties Served": "ARYA ENERGY LTD ANUPPUR, VISHWAGEETA ISPAT, ASHIRWAD IRON & POWER PVT LTD", "Adjustment/Remarks": "No adjustment"},
        {"Sales Person": "SONU JI", "Sheet/Date": "GD 19-09-2026", "Total Vehicles": 10, "Parties Served": "ESSEL PROJECTS BHILAI, HI-TECH METALLICS, LAXMIKRIPA STEEL POWER, RR INDUSTRIES, BOLD STEEL SUPPLIER, ARUNSTEEL, AGRAWAL STEEL, JESANI SALES", "Adjustment/Remarks": "NO ADJUSTMENT"},
        {"Sales Person": "SONU JI", "Sheet/Date": "GD 20-09-2026", "Total Vehicles": 7, "Parties Served": "RELIABLE STEEL MONGERS, DIAMOND FURNITURE, ARUN STEEL, SOURABH ROLLING MILL, ESSEL PROJECTS, KUNAL OZA", "Adjustment/Remarks": "yesterday vehicle dispatch 20.08.2026, No adjustment, Pending for dispatch"},
        {"Sales Person": "VINITA JI", "Sheet/Date": "GD 19-09-2026", "Total Vehicles": 2, "Parties Served": "SARDA TRADERS, JAHIR AGRO INDUSTRIES", "Adjustment/Remarks": "NO ADJUSTMENT"}
    ]
    df_sales = pd.DataFrame(sales_summary_data)
    st.dataframe(df_sales, use_container_width=True)

    # -------------------------------------------------------------------------
    # 2. DELAYED YESTERDAY VEHICLES DISPATCHED TODAY
    # -------------------------------------------------------------------------
    st.header("2. Delayed Yesterday Vehicles Dispatched Today")
    
    delayed_data = [
        {"Sheet/Date": "GD 20-09-2026", "SR No": 1, "Vehicle No": "NL01AH3668", "Party Name": "OFB TECH LIMITED MAHARASHTRA", "Sales Person": "DEEPANKAR JI", "Dispatch Remark": "yesterday vehicle dispatch 20.08.2026"},
        {"Sheet/Date": "GD 20-09-2026", "SR No": 2, "Vehicle No": "CG07CA9013", "Party Name": "DP BANSAL COMMERCIAL COMPANY", "Sales Person": "DEEPANKAR JI", "Dispatch Remark": "yesterday vehicle dispatch 20.08.2026"},
        {"Sheet/Date": "GD 20-09-2026", "SR No": 3, "Vehicle No": "RJ48GB1023", "Party Name": "RELIABLE STEEL MONGERS PVT LTD", "Sales Person": "SONU JI", "Dispatch Remark": "yesterday vehicle dispatch 20.08.2026"}
    ]
    df_delayed = pd.DataFrame(delayed_data)
    st.dataframe(df_delayed, use_container_width=True)

    # -------------------------------------------------------------------------
    # 3. GODOWN OVERALL STOCK & PRODUCTION SUMMARY
    # -------------------------------------------------------------------------
    st.header("3. Godown Overall Stock & Production Summary (MT)")
    
    overall_stock_data = [
        {"Sheet / Date": "GD 19-09-2026", "Opening Stock (MT)": 3189.14, "Closing Stock (MT)": 4543.22, "Yesterday Production (MT)": 106.21, "Dispatch Stock (MT)": 255.81},
        {"Sheet / Date": "GD 20-09-2026", "Opening Stock (MT)": 4543.22, "Closing Stock (MT)": 5535.35, "Yesterday Production (MT)": 214.20, "Dispatch Stock (MT)": 328.45}
    ]
    df_overall = pd.DataFrame(overall_stock_data)
    st.dataframe(df_overall, use_container_width=True)

    # -------------------------------------------------------------------------
    # 4. ITEM-WISE STOCK BREAKDOWN
    # -------------------------------------------------------------------------
    st.header("4. Item-Wise Stock Breakdown (Opening vs Closing)")
    
    item_stock_data = [
        {"Particulars/Item": "CHQ COIL", "Opening Stock (MT)": 567.19, "Closing Stock (MT)": 538.63, "Variance (MT)": -28.56},
        {"Particulars/Item": "CHQ PLATE", "Opening Stock (MT)": 237.97, "Closing Stock (MT)": 222.06, "Variance (MT)": -15.91},
        {"Particulars/Item": "HR COIL", "Opening Stock (MT)": 3576.35, "Closing Stock (MT)": 5557.50, "Variance (MT)": 1981.15},
        {"Particulars/Item": "HR PLATE", "Opening Stock (MT)": 589.52, "Closing Stock (MT)": 680.33, "Variance (MT)": 90.81},
        {"Particulars/Item": "HR SHEET", "Opening Stock (MT)": 577.88, "Closing Stock (MT)": 555.03, "Variance (MT)": -22.85},
        {"Particulars/Item": "HT COIL", "Opening Stock (MT)": 614.05, "Closing Stock (MT)": 950.60, "Variance (MT)": 336.55},
        {"Particulars/Item": "HT PLATE", "Opening Stock (MT)": 561.92, "Closing Stock (MT)": 561.93, "Variance (MT)": 0.01},
        {"Particulars/Item": "OT PLATE", "Opening Stock (MT)": 10.60, "Closing Stock (MT)": 10.60, "Variance (MT)": 0.00},
        {"Particulars/Item": "PM PLATE", "Opening Stock (MT)": 897.75, "Closing Stock (MT)": 902.02, "Variance (MT)": 4.27},
        {"Particulars/Item": "SCRAP", "Opening Stock (MT)": 30.48, "Closing Stock (MT)": 31.22, "Variance (MT)": 0.74},
        {"Particulars/Item": "STRUCTURE", "Opening Stock (MT)": 68.64, "Closing Stock (MT)": 68.64, "Variance (MT)": 0.00}
    ]
    df_items = pd.DataFrame(item_stock_data)
    st.dataframe(df_items, use_container_width=True)

    # -------------------------------------------------------------------------
    # 5. VISUAL ANALYTICS
    # -------------------------------------------------------------------------
    st.header("5. Visual Analytics")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("A. Salesperson-Wise Parties Served")
        parties_data = {
            "Sales Person": ["SONU JI", "DEEPANKAR JI", "AKASH JI", "DIPESH JI", "VINITA JI"],
            "Parties Served": [14, 9, 7, 4, 2]
        }
        df_parties = pd.DataFrame(parties_data)
        fig_parties = px.bar(
            df_parties, 
            x="Sales Person", 
            y="Parties Served", 
            text="Parties Served",
            color_discrete_sequence=["#636EFA"]
        )
        fig_parties.update_traces(textposition="outside")
        fig_parties.update_layout(yaxis_range=[0, 16], yaxis_title="Number of Parties Served")
        st.plotly_chart(fig_parties, use_container_width=True)

    with col2:
        st.subheader("B. Item Stock Opening vs Closing Comparison")
        fig_stock = go.Figure(data=[
            go.Bar(name='Opening Stock (MT)', x=df_items['Particulars/Item'], y=df_items['Opening Stock (MT)'], marker_color='#3366CC'),
            go.Bar(name='Closing Stock (MT)', x=df_items['Particulars/Item'], y=df_items['Closing Stock (MT)'], marker_color='#109618')
        ])
        fig_stock.update_layout(barmode='group', yaxis_title="Metric Tons (MT)")
        st.plotly_chart(fig_stock, use_container_width=True)

else:
    # -------------------------------------------------------------------------
    # DYNAMIC DATE-WISE AUDIT & OPERATIONAL COMPARISON REPORT
    # -------------------------------------------------------------------------
    st.header("Operational Audit Comparison: 31-08-2026 vs 01-09-2026")
    
    audit_metrics = [
        {"Operational/ Cost Metric": "Total Invoices Generated", "31-08-2026": "14 Invoices", "01-09-2026": "22 Invoices", "Operational Variance": "+8 Invoices"},
        {"Operational/ Cost Metric": "Dispatched Quantity Tonnage", "31-08-2026": "217.86 MT", "01-09-2026": "196.41 MT", "Operational Variance": "-21.45 MT"},
        {"Operational/ Cost Metric": "Calculated Total Freight Cost", "31-08-2026": "0.00", "01-09-2026": "11,299.50", "Operational Variance": "+11,299.50"},
        {"Operational/ Cost Metric": "Total Loading Duration Hours", "31-08-2026": "88.33 Hrs", "01-09-2026": "76.42 Hrs", "Operational Variance": "-11.92 Hrs"},
        {"Operational/ Cost Metric": "Average Loading Time / Vehicle", "31-08-2026": "5.89 Hrs", "01-09-2026": "3.06 Hrs", "Operational Variance": "-2.83 Hrs"},
        {"Operational/ Cost Metric": "Number of Parties Serviced", "31-08-2026": "15", "01-09-2026": "25", "Operational Variance": "+10 Parties"},
        {"Operational/ Cost Metric": "Yesterday Pending Orders", "31-08-2026": "2", "01-09-2026": "3", "Operational Variance": "+1 Orders"},
        {"Operational/ Cost Metric": "Material/Billing Pending", "31-08-2026": "0", "01-09-2026": "0", "Operational Variance": "+0 Orders"}
    ]
    st.dataframe(pd.DataFrame(audit_metrics), use_container_width=True)

    st.subheader("Operational Audit & Freight Variance Comparison Chart")
    
    chart_metrics_df = pd.DataFrame([
        {"Metric": "Dispatched Qty (MT)", "31-08-2026": 217.9, "01-09-2026": 196.4},
        {"Metric": "Total Invoices Generated", "31-08-2026": 14.0, "01-09-2026": 22.0},
        {"Metric": "Loading Hours (Hrs)", "31-08-2026": 88.3, "01-09-2026": 76.4},
        {"Metric": "Total Freight (₹)", "31-08-2026": 0.0, "01-09-2026": 11299.5},
        {"Metric": "Parties Serviced", "31-08-2026": 15.0, "01-09-2026": 25.0}
    ])
    
    fig_audit = go.Figure(data=[
        go.Bar(name='31-08-2026', x=chart_metrics_df['Metric'], y=chart_metrics_df['31-08-2026'], text=chart_metrics_df['31-08-2026'], textposition='auto'),
        go.Bar(name='01-09-2026', x=chart_metrics_df['Metric'], y=chart_metrics_df['01-09-2026'], text=chart_metrics_df['01-09-2026'], textposition='auto')
    ])
    fig_audit.update_layout(barmode='group')
    st.plotly_chart(fig_audit, use_container_width=True)
