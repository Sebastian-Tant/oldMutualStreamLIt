import streamlit as st
import pandas as pd

st.set_page_config(page_title="Performance Attribution", layout="wide")

st.title("📊 Performance Attribution Dashboard")

@st.cache_data
def load_and_clean_data():
    path = 'Data (1).xlsx'
    
    p_df = pd.read_excel(path, sheet_name='prices')
    a_df = pd.read_excel(path, sheet_name='attributes')
    b_df = pd.read_excel(path, sheet_name='benchmark')
    
    try:
        f_df = pd.read_excel(path, sheet_name='funds_20231231')
    except:
        f_df = pd.read_excel(path, sheet_name='funds')
    
    p_df['Date'] = pd.to_datetime(p_df['Date'])
    
    f_df.columns = f_df.iloc[0]
    f_df = f_df.iloc[1:].reset_index(drop=True)
    
    return p_df, a_df, b_df, f_df

try:
    prices, attributes, benchmark, funds = load_and_clean_data()
    ready = True
except Exception as e:
    st.error(f"Logic Error: {e}")
    st.info("Ensure sheet names are: prices, attributes, benchmark, and funds_20231231")
    ready = False

if ready:
    with st.sidebar:
        st.header("Dashboard Controls")
        available_dates = sorted(prices['Date'].unique())
        
        start_val = st.selectbox("Start Date", available_dates, index=available_dates.index(pd.Timestamp('2023-12-31')))
        end_val   = st.selectbox("End Date", available_dates, index=len(available_dates)-1)
        
        attr_type = st.selectbox("Group By Attribute", ["Asset  Attribute 1", "Asset  Attribute 2"])
        fund_type = st.radio("Select Target Fund", ["Fund A", "Fund B"])

    p_start = prices[prices['Date'] == start_val].set_index('Asset ID')['Price']
    p_end   = prices[prices['Date'] == end_val].set_index('Asset ID')['Price']
    asset_rets = (p_end / p_start) - 1

    if fund_type == "Fund A":
        f_clean = funds.iloc[:, [0, 1]].dropna()
    else:
        f_clean = funds.iloc[:, [4, 5]].dropna()
    
    f_clean.columns = ['Asset ID', 'Holdings']
    f_clean['Holdings'] = pd.to_numeric(f_clean['Holdings'], errors='coerce')
    f_clean = f_clean.dropna()

    f_merged = f_clean.merge(p_start.rename('Price'), on='Asset ID')
    f_merged['MV'] = f_merged['Holdings'] * f_merged['Price']
    f_merged['w_p'] = f_merged['MV'] / f_merged['MV'].sum()

    b_merged = benchmark[['Asset ID', 'Holdings']].copy()
    b_merged = b_merged.merge(p_start.rename('Price'), on='Asset ID')
    b_merged['MV'] = b_merged['Holdings'] * b_merged['Price']
    b_merged['w_b'] = b_merged['MV'] / b_merged['MV'].sum()

    master = attributes[['Asset ID', attr_type]].merge(f_merged[['Asset ID', 'w_p']], on='Asset ID', how='outer')
    master = master.merge(b_merged[['Asset ID', 'w_b']], on='Asset ID', how='outer')
    master = master.merge(asset_rets.rename('Return'), on='Asset ID', how='left')
    master.fillna(0, inplace=True)

    grouped = master.groupby(attr_type).apply(lambda x: pd.Series({
        'w_p': x['w_p'].sum(),
        'w_b': x['w_b'].sum(),
        'r_p': (x['w_p'] * x['Return']).sum() / x['w_p'].sum() if x['w_p'].sum() != 0 else 0,
        'r_b': (x['w_b'] * x['Return']).sum() / x['w_b'].sum() if x['w_b'].sum() != 0 else 0
    })).reset_index()

    grouped['Allocation'] = (grouped['w_p'] - grouped['w_b']) * grouped['r_b']
    grouped['Selection']  = grouped['w_b'] * (grouped['r_p'] - grouped['r_b'])
    grouped['Interaction'] = (grouped['w_p'] - grouped['w_b']) * (grouped['r_p'] - grouped['r_b'])
    grouped['Total Alpha'] = grouped['Allocation'] + grouped['Selection'] + grouped['Interaction']

    p_total = (grouped['w_p'] * grouped['r_p']).sum()
    b_total = (grouped['w_b'] * grouped['r_b']).sum()
    
    c1, c2, c3 = st.columns(3)
    c1.metric(f"{fund_type} Return", f"{p_total:.2%}")
    c2.metric("Benchmark Return", f"{b_total:.2%}")
    c3.metric("Alpha", f"{p_total - b_total:.2%}")

    st.divider()
    st.subheader(f"Brinson Attribution Breakdown: {attr_type}")
    
    st.dataframe(grouped.style.format({
        'w_p': '{:.2%}', 'w_b': '{:.2%}', 'r_p': '{:.2%}', 'r_b': '{:.2%}',
        'Allocation': '{:.4%}', 'Selection': '{:.4%}', 'Interaction': '{:.4%}', 'Total Alpha': '{:.4%}'
    }), use_container_width=True)
    
    st.bar_chart(grouped.set_index(attr_type)[['Allocation', 'Selection', 'Interaction']])