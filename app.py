import streamlit as st
import pandas as pd

st.set_page_config(page_title="Enterprise Reporting Portal", layout="wide")

# --- Navigation Setup ---
query_params = st.query_params
default_report = query_params.get("report", "Godown Stock Report")

report_map = {
    "godown": "Godown Stock Report",
    "dispatch": "Dispatch Comparison Report"
}
reverse_map = {v: k for k, v in report_map.items()}

st.sidebar.title("Navigation")
selected_report = st.sidebar.radio(
    "Select Report:",
    options=["Godown Stock Report", "Dispatch Comparison Report"],
    index=0 if report_map.get(default_report, default_report) == "Godown Stock Report" else 1
)

st.query_params["report"] = reverse_map.get(selected_report, "godown")

# --- Report 1: Godown Stock Report ---
def render_godown_stock_report():
    st.title("📦 Daily Godown Dispatch & Stock Movements Report")
    
    # 1. File Uploader
    uploaded_file = st.sidebar.file_uploader("Upload Godown Data (Excel/CSV)", type=["xlsx", "xls", "csv"], key="godown_file")
    
    if uploaded_file is not None:
        try:
            # Load Data
            df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
            st.success("File uploaded successfully!")
            
            # Display Data / Summary
            st.subheader("Data Overview")
            st.dataframe(df.head())
            
            # 2. Download Generated PDF / Report Data
            # Note: Replace 'df.to_csv()' with your custom PDF generation logic/bytes
            csv_data = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Generated Report",
                data=csv_data,
                file_name="Godown_Stock_Report.csv",
                mime="text/csv"
            )
        except Exception as e:
            st.error(f"Error processing file: {e}")
    else:
        st.info("Please upload an Excel or CSV file in the sidebar to generate the report.")

# --- Report 2: Dispatch Comparison Report ---
def render_dispatch_comparison_report():
    st.title("📊 Date-Wise Audit & Operational Comparison Report")
    
    # 1. File Uploader (Allows multiple files for comparison)
    uploaded_files = st.sidebar.file_uploader("Upload Dispatch Files to Compare", type=["xlsx", "xls", "csv"], accept_multiple_files=True, key="dispatch_files")
    
    if uploaded_files:
        try:
            st.success(f"{len(uploaded_files)} file(s) uploaded successfully!")
            
            # Display Metrics or Process Files
            col1, col2, col3 = st.columns(3)
            col1.metric("Invoices Generated", "22", delta="+8")
            col2.metric("Dispatched Tonnage", "196.41 MT", delta="-21.45 MT")
            col3.metric("Freight Cost", "₹11,299.50", delta="+11,299.50")
            
            # 2. Download Button
            # Pass your generated PDF bytes here
            st.download_button(
                label="📥 Download Comparison Report (PDF)",
                data=b"Sample PDF Content",  # Replace with generated PDF binary bytes
                file_name="Dispatch_Comparison_Report.pdf",
                mime="application/pdf"
            )
        except Exception as e:
            st.error(f"Error processing files: {e}")
    else:
        st.info("Please upload dispatch files in the sidebar to run the comparison.")

# --- Page Router ---
if selected_report == "Godown Stock Report":
    render_godown_stock_report()
elif selected_report == "Dispatch Comparison Report":
    render_dispatch_comparison_report()
