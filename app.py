import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Dynamic Godown & Operations Daily Audit",
    page_icon="📦",
    layout="wide"
)

st.title("DAILY GODOWN DISPATCH, STOCK & OPERATIONAL AUDIT SYSTEM")
st.caption("Upload your daily multi-sheet Excel file to generate daily reports and run date-wise comparisons.")

# --- SIDEBAR: FILE UPLOADER & MODE ---
st.sidebar.header("📁 Data Upload & Mode")

mode = st.sidebar.radio(
    "Select Operating Mode",
    ["Daily Single Report View", "Date-Wise Audit Comparison"]
)

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

if mode == "Daily Single Report View":
    uploaded_file = st.sidebar.file_uploader("Upload Today's Daily Excel File", type=["xlsx", "xls"])
    
    if uploaded_file is not None:
        try:
            excel_data = pd.read_excel(uploaded_file, sheet_name=None)
            st.sidebar.success(f"File '{uploaded_file.name}' loaded successfully!")
            
            # Overview Metrics Header
            st.header(f"📊 Audit Dashboard — File: {uploaded_file.name}")
            
            # Tabbed interface for all 9 sheets
            tabs = st.tabs(EXPECTED_SHEETS)
            
            for index, sheet_name in enumerate(EXPECTED_SHEETS):
                with tabs[index]:
                    st.subheader(f"Sheet: {sheet_name}")
                    if sheet_name in excel_data:
                        df = excel_data[sheet_name]
                        
                        # High-level summary metrics if numeric columns exist
                        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
                        if numeric_cols:
                            m_cols = st.columns(min(len(numeric_cols), 4))
                            for idx, col in enumerate(numeric_cols[:4]):
                                m_cols[idx % 4].metric(label=f"Total {col}", value=f"{df[col].sum():,.2f}")
                        
                        st.dataframe(df, use_container_width=True)
                        
                        # Quick Visualization for Specific Sheets
                        if sheet_name == "Sales Person Wise Dispatch" and "Sales Person" in df.columns:
                            target_col = "Total Vehicles" if "Total Vehicles" in df.columns else df.columns[1]
                            fig = px.bar(df, x="Sales Person", y=target_col, text=target_col, title="Vehicles Dispatched per Salesperson")
                            st.plotly_chart(fig, use_container_width=True)
                            
                        elif sheet_name == "Stock" and "Particulars/Item" in df.columns:
                            if "Opening Stock (MT)" in df.columns and "Closing Stock (MT)" in df.columns:
                                fig = go.Figure(data=[
                                    go.Bar(name='Opening Stock (MT)', x=df['Particulars/Item'], y=df['Opening Stock (MT)']),
                                    go.Bar(name='Closing Stock (MT)', x=df['Particulars/Item'], y=df['Closing Stock (MT)'])
                                ])
                                fig.update_layout(barmode='group', title="Item-Wise Stock Balance (Opening vs Closing)")
                                st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.warning(f"Sheet '{sheet_name}' was not found in the uploaded workbook.")
                        
        except Exception as e:
            st.error(f"Error reading Excel file: {e}")
    else:
        st.info("Please upload a daily Excel file to populate the report tabs.")

elif mode == "Date-Wise Audit Comparison":
    st.sidebar.subheader("Select Two Files to Compare")
    file_1 = st.sidebar.file_uploader("Upload Earlier Date Report (File 1)", type=["xlsx", "xls"], key="f1")
    file_2 = st.sidebar.file_uploader("Upload Later Date Report (File 2)", type=["xlsx", "xls"], key="f2")
    
    if file_1 and file_2:
        try:
            data_1 = pd.read_excel(file_1, sheet_name=None)
            data_2 = pd.read_excel(file_2, sheet_name=None)
            
            selected_sheet = st.selectbox("Select Sheet to Compare", EXPECTED_SHEETS)
            
            if selected_sheet in data_1 and selected_sheet in data_2:
                df1 = data_1[selected_sheet]
                df2 = data_2[selected_sheet]
                
                col_left, col_right = st.columns(2)
                with col_left:
                    st.markdown(f"### 📅 File 1: {file_1.name}")
                    st.dataframe(df1, use_container_width=True)
                with col_right:
                    st.markdown(f"### 📅 File 2: {file_2.name}")
                    st.dataframe(df2, use_container_width=True)
                
                # Comparative Summary if numeric data exists
                num_cols1 = df1.select_dtypes(include=['number']).columns
                num_cols2 = df2.select_dtypes(include=['number']).columns
                common_num_cols = list(set(num_cols1).intersection(set(num_cols2)))
                
                if common_num_cols:
                    st.markdown("---")
                    st.subheader(f"📈 Operational Variance Summary — {selected_sheet}")
                    comp_metrics = []
                    for col in common_num_cols:
                        val1 = df1[col].sum()
                        val2 = df2[col].sum()
                        diff = val2 - val1
                        comp_metrics.append({
                            "Metric": col,
                            f"File 1 ({file_1.name})": round(val1, 2),
                            f"File 2 ({file_2.name})": round(val2, 2),
                            "Variance": round(diff, 2)
                        })
                    
                    df_comp = pd.DataFrame(comp_metrics)
                    st.dataframe(df_comp, use_container_width=True)
                    
                    fig = go.Figure(data=[
                        go.Bar(name=file_1.name, x=df_comp['Metric'], y=df_comp[f"File 1 ({file_1.name})"]),
                        go.Bar(name=file_2.name, x=df_comp['Metric'], y=df_comp[f"File 2 ({file_2.name})"])
                    ])
                    fig.update_layout(barmode='group', title=f"Metric Comparison: {selected_sheet}")
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning(f"The sheet '{selected_sheet}' must exist in both uploaded files to perform comparison.")
                
        except Exception as e:
            st.error(f"Error during file comparison: {e}")
    else:
        st.info("Upload both Excel files in the sidebar to run a side-by-side comparative analysis.")
