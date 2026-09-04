import io
import re
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import streamlit as st

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, PageBreak, Image
)
from reportlab.lib.styles import ParagraphStyle

# ==========================================
# 1. HELPER PARSERS & CLEANERS
# ==========================================

def parse_num(v):
    if pd.isna(v) or not str(v).strip() or str(v).strip() in ['-', 'None', 'nan']:
        return 0.0
    clean = re.sub(r'[^0-9\.]', '', str(v).strip())
    try:
        return float(clean) if clean else 0.0
    except ValueError:
        return 0.0

# ==========================================
# 2. DEPARTMENTAL PARSING ENGINE
# ==========================================

def parse_hr_admin(df):
    """Parses row-wise KPI structure of HR & Admin."""
    df_clean = df.dropna(how='all').dropna(how='all', axis=1)
    kpi_col = df_clean.columns[0]
    df_clean = df_clean[df_clean[kpi_col].notna()]
    return df_clean

def parse_logistics(df):
    """Parses Dispatch & Freight tables."""
    df_c = df.dropna(how='all').copy()
    col_map = {str(c).strip().lower(): c for c in df_c.columns}
    
    qty_col = next((col_map[c] for c in col_map if any(k in c for k in ['qty', 'qnty', 'weight'])), None)
    freight_col = next((col_map[c] for c in col_map if 'freight' in c), None)
    
    total_qty = df_c[qty_col].apply(parse_num).sum() if qty_col else 0.0
    total_freight = df_c[freight_col].apply(parse_num).sum() if freight_col else 0.0
    
    return {
        "df": df_c,
        "total_dispatches": len(df_c),
        "total_qty": total_qty,
        "total_freight": total_freight
    }

def parse_purchase(df):
    """Parses Purchase PO, Plates, and Structure sheets."""
    df_c = df.dropna(how='all').copy()
    col_map = {str(c).strip().lower(): c for c in df_c.columns}
    
    recd_col = next((col_map[c] for c in col_map if 'recd' in c), None)
    pending_col = next((col_map[c] for c in col_map if 'pending' in c), None)
    
    tot_recd = df_c[recd_col].apply(parse_num).sum() if recd_col else 0.0
    tot_pending = df_c[pending_col].apply(parse_num).sum() if pending_col else 0.0
    
    return {
        "df": df_c,
        "total_pos": df_c[col_map.get('po no', df_c.columns[0])].nunique(),
        "total_recd": tot_recd,
        "total_pending": tot_pending
    }

def parse_accounts(df):
    """Parses Accounts side-by-side ledgers."""
    df_c = df.dropna(how='all').copy()
    # Identifies paired Amount columns
    amt_cols = [c for c in df_c.columns if 'AMT' in str(c).upper()]
    total_cashflow = sum([df_c[c].apply(parse_num).sum() for c in amt_cols])
    return {"df": df_c, "total_cashflow": total_cashflow}

# ==========================================
# 3. VISUALIZATION ENGINE
# ==========================================

def generate_comparison_chart(today_kpis, yest_kpis, title):
    fig, ax = plt.subplots(figsize=(8, 3), dpi=150)
    labels = list(today_kpis.keys())
    today_vals = [today_kpis[k] for k in labels]
    yest_vals = [yest_kpis.get(k, 0.0) for k in labels]
    
    x = np.arange(len(labels))
    width = 0.35
    
    rects1 = ax.bar(x - width/2, yest_vals, width, label='Yesterday', color='#94A3B8')
    rects2 = ax.bar(x + width/2, today_vals, width, label='Today', color='#2563EB')
    
    ax.set_ylabel('Metrics')
    ax.set_title(title, fontsize=10, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=15, fontsize=8)
    ax.legend()
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf

# ==========================================
# 4. STREAMLIT DASHBOARD & INTERFACE
# ==========================================

st.set_page_config(page_title="Enterprise MIS & Audit Portal", layout="wide")
st.title("🏭 Enterprise Departmental MIS & Comparison Portal")

st.sidebar.header("📁 Upload Workbooks")
today_file = st.sidebar.file_uploader("Upload Today's Excel Report", type=["xlsx"])
yesterday_file = st.sidebar.file_uploader("Upload Yesterday's Excel (For Comparison)", type=["xlsx"])

if today_file:
    xls_today = pd.ExcelFile(today_file)
    sheets = xls_today.sheet_names
    
    tab1, tab2 = st.tabs(["📊 Daily Dashboard & Analytics", "📄 Day-over-Day Comparison Report"])
    
    with tab1:
        st.subheader("Departmental Data Inspector")
        selected_sheet = st.selectbox("Select Department Sheet:", sheets)
        df_sheet = pd.read_excel(xls_today, sheet_name=selected_sheet)
        
        st.write(f"**Previewing Raw Data for: {selected_sheet}**")
        st.dataframe(df_sheet, use_container_width=True)
        
    with tab2:
        st.subheader("Day-over-Day Department Variance")
        if yesterday_file:
            xls_yest = pd.ExcelFile(yesterday_file)
            st.success("Both Today's and Yesterday's reports loaded. Ready for variance audit!")
            
            # Example Logistical KPI Comparison
            log_sheet = next((s for s in sheets if 'logistics' in s.lower() or 'dispatch' in s.lower()), None)
            if log_sheet and log_sheet in xls_yest.sheet_names:
                t_log = parse_logistics(pd.read_excel(xls_today, sheet_name=log_sheet))
                y_log = parse_logistics(pd.read_excel(xls_yest, sheet_name=log_sheet))
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Dispatched Tonnage (MT)", f"{t_log['total_qty']:,.2f}", f"{t_log['total_qty'] - y_log['total_qty']:+,.2f} MT")
                col2.metric("Total Vehicles Dispatched", t_log['total_dispatches'], f"{t_log['total_dispatches'] - y_log['total_dispatches']:+} Vehicles")
                col3.metric("Freight Expenditure (₹)", f"₹{t_log['total_freight']:,.2f}", f"₹{t_log['total_freight'] - y_log['total_freight']:+,.2f}")
                
                chart_buf = generate_comparison_chart(
                    {"Qty (MT)": t_log['total_qty'], "Vehicles": t_log['total_dispatches']},
                    {"Qty (MT)": y_log['total_qty'], "Vehicles": y_log['total_dispatches']},
                    "Logistics Daily Variance"
                )
                st.image(chart_buf)
        else:
            st.info("Upload Yesterday's Excel file in the sidebar to activate the Day-over-Day variance comparison.")
