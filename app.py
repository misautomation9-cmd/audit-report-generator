import streamlit as st

# Set page configuration
st.set_page_config(page_title="Enterprise Reporting Portal", layout="wide")

# Function to render Report 1
def render_godown_stock_report():
    st.title("📦 Daily Godown Dispatch & Stock Movements Report")
    st.write("Consolidated report covering dispatches, delayed vehicles, and stock balances.")
    
    # Example Metric Summary
    col1, col2, col3 = st.columns(3)
    col1.metric("Opening Stock", "4,543.22 MT")
    col2.metric("Closing Stock", "5,535.35 MT")
    col3.metric("Production", "214.20 MT")
    
    # Add your DataFrames / Visualizations here
    st.subheader("Item-Wise Stock Breakdown")
    # st.dataframe(stock_df)

# Function to render Report 2
def render_dispatch_comparison_report():
    st.title("📊 Date-Wise Audit & Operational Comparison Report")
    st.write("Dispatch Volume, Freight Costs, Loading Time & Pending Variance Analysis.")
    
    # Example Metric Summary
    col1, col2, col3 = st.columns(3)
    col1.metric("Invoices Generated", "22", delta="+8")
    col2.metric("Dispatched Tonnage", "196.41 MT", delta="-21.45 MT")
    col3.metric("Freight Cost", "₹11,299.50", delta="+11,299.50")

    # Add your DataFrames / Visualizations here
    st.subheader("Operational Audit Comparison")
    # st.dataframe(dispatch_df)

# --- Dynamic Link & Routing Logic ---

# 1. Read 'report' key from URL query parameters (e.g., ?report=dispatch)
query_params = st.query_params
default_report = query_params.get("report", "Godown Stock Report")

# Map parameter options to readable names
report_map = {
    "godown": "Godown Stock Report",
    "dispatch": "Dispatch Comparison Report"
}

# Reverse lookup for parameter synchronization
reverse_map = {v: k for k, v in report_map.items()}

# Set default selection based on URL if present
selected_option = report_map.get(default_report, default_report)

# 2. Sidebar Navigation Selection
st.sidebar.title("Navigation")
selected_report = st.sidebar.radio(
    "Select Report:",
    options=["Godown Stock Report", "Dispatch Comparison Report"],
    index=0 if selected_option == "Godown Stock Report" else 1
)

# Sync URL parameters with user selection
st.query_params["report"] = reverse_map.get(selected_report, "godown")

# 3. Dynamic Display Logic
if selected_report == "Godown Stock Report":
    render_godown_stock_report()
elif selected_report == "Dispatch Comparison Report":
    render_dispatch_comparison_report()
