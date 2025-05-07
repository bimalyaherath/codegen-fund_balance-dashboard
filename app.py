import streamlit as st
import pandas as pd
import datetime as dt
import glob
import os
import requests

# 1. Load and clean weekly Excel files
@st.cache_data
def load_fund_data():
    paths = glob.glob('data/Fund_Balance_*.xlsx') \
             + glob.glob('/mnt/data/Fund_Balance_*.xlsx') \
             + glob.glob('Fund_Balance_*.xlsx')
    all_weeks = []
    for file in paths:
        week_label = os.path.basename(file).replace('Fund_Balance_','').replace('.xlsx','')
        try:
            df = pd.read_excel(file)
        except Exception as e:
            st.warning(f"Could not read {file}: {e}")
            continue
        mask = df['Details'].str.contains('Bank & Cash Balances|Cash Transactions During the Week|Cash Ins|Cash Outs', na=False)
        idx = df[mask].index.tolist()
        if not idx:
            st.warning(f"No valid sections in {file}")
            continue
        parts = []
        for i, start in enumerate(idx):
            end = idx[i+1] if i+1 < len(idx) else len(df)
            section_name = df.loc[start, 'Details']
            part = df.iloc[start+1:end].dropna(how='all').copy()
            part['Section'] = section_name
            parts.append(part)
        week_df = pd.concat(parts, ignore_index=True)
        week_df['Week'] = week_label
        all_weeks.append(week_df)
    return pd.concat(all_weeks, ignore_index=True) if all_weeks else pd.DataFrame()

# Load data
fund_data = load_fund_data()
if fund_data.empty:
    st.error("No weekly fund data found. Upload 'Fund_Balance_*.xlsx' files to the repo root, 'data/' or '/mnt/data'.")
    st.stop()

# Sidebar settings
st.sidebar.title('Dashboard Settings')
# Week selector for main summary
weeks = sorted(fund_data['Week'].unique())
selected_week = st.sidebar.selectbox('Select Week', weeks)
# Comparison weeks selector
comp_weeks = st.sidebar.multiselect('Select Weeks to Compare', weeks, default=weeks[-2:])
# Currency multiselect
currencies = ['LKR','USD','GBP','AUD','DKK','EUR','MXN','INR','AED']
selected_currencies = st.sidebar.multiselect('Select Currencies', currencies, default=['LKR'])
if not selected_currencies:
    st.sidebar.error('Select at least one currency')
    st.stop()

# Live currency converter
def get_rate(base: str, symbol: str) -> float:
    resp = requests.get('https://api.exchangerate.host/latest', params={'base': base, 'symbols': symbol}, timeout=5)
    data = resp.json()
    return data.get('rates', {}).get(symbol)

st.sidebar.header('Currency Converter')
amount = st.sidebar.number_input('Amount to convert', min_value=0.0, value=1.0, step=0.1)
from_cur = st.sidebar.selectbox('From Currency', currencies, index=0)
to_cur = st.sidebar.selectbox('To Currency', currencies, index=1)
rate = get_rate(from_cur, to_cur)
if rate is None:
    st.sidebar.error('Failed to fetch live exchange rate.')
else:
    converted = amount * rate
    st.sidebar.write(f'1 {from_cur} = {rate:.4f} {to_cur}')
    st.sidebar.write(f'{amount} {from_cur} = {converted:.2f} {to_cur}')

# Main header
dt_today = dt.date.today()
try:
    start_str, end_str = selected_week.split('_to_')
    start_dt = dt.datetime.strptime(start_str, '%B_%d').replace(year=dt_today.year).date()
    end_dt = dt.datetime.strptime(end_str, '%B_%d').replace(year=dt_today.year).date()
    subtitle = f"{selected_week.replace('_',' ')} ({start_dt} to {end_dt})"
except:
    subtitle = selected_week.replace('_',' ')

st.title('📊 Weekly Fund Dashboard')
st.subheader(subtitle)

# Filter for selected week
df_week = fund_data[fund_data['Week'] == selected_week]

# Weekly Summary
st.header('🔖 Weekly Summary')
summary = df_week.groupby('Section')[selected_currencies].sum().reset_index()
summary.columns = ['Category'] + [f'Total {cur}' for cur in selected_currencies]
st.table(summary)
st.download_button('Download Weekly Summary', summary.to_csv(index=False), file_name=f"{selected_week}_Weekly_Summary.csv", mime='text/csv')

# Cash Ins & Outs Breakdown
st.header('📂 Cash Ins & Outs Breakdown')
with st.expander('Cash Ins'):
    ins = df_week[df_week['Section']=='Cash Ins'][['Details'] + selected_currencies]
    ins.columns = ['Category'] + selected_currencies
    st.table(ins)
with st.expander('Cash Outs'):
    outs = df_week[df_week['Section']=='Cash Outs'][['Details'] + selected_currencies]
    outs.columns = ['Category'] + selected_currencies
    st.table(outs)

# Weekly Comparison Chart
st.header('📈 Weekly Comparison')
if comp_weeks:
    comp_df = fund_data[fund_data['Week'].isin(comp_weeks)]
    comp_summary = comp_df.groupby('Week')[selected_currencies].sum()
    st.line_chart(comp_summary)
else:
    st.info('Select at least one week to compare.')

# Full Dataset
st.header('📁 Full Dataset')
with st.expander('View Full Dataset'):
    st.dataframe(fund_data)
    st.download_button('Download Full Dataset', fund_data.to_csv(index=False), file_name='Full_Weekly_Fund_Data.csv', mime='text/csv')

st.write('---')
st.caption('Created with ❤️ using Streamlit & GitHub')
