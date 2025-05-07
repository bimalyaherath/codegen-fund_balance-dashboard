import streamlit as st
import pandas as pd
import datetime as dt
import glob
import os
import requests

# 1. Load and clean all weekly Excel files
@st.cache_data
def load_fund_data():
    paths = glob.glob('data/Fund_Balance_*.xlsx') \
             + glob.glob('/mnt/data/Fund_Balance_*.xlsx') \
             + glob.glob('Fund_Balance_*.xlsx')
    all_weeks = []
    for file in paths:
        base = os.path.basename(file).replace('Fund_Balance_','').replace('.xlsx','')
        week_label = base
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
    if not all_weeks:
        return pd.DataFrame()
    return pd.concat(all_weeks, ignore_index=True)

fund_data = load_fund_data()
if fund_data.empty:
    st.error("No weekly fund data found. Upload 'Fund_Balance_*.xlsx' files to the repo root, 'data/' or '/mnt/data'.")
    st.stop()

# 2. Sidebar: Settings
st.sidebar.title('Dashboard Settings')

# A. Week selector
weeks = sorted(fund_data['Week'].unique())
selected_week = st.sidebar.selectbox('Select Week', weeks)
try:
    start_str, end_str = selected_week.split('_to_')
    start_dt = dt.datetime.strptime(start_str, '%B_%d').replace(year=dt.date.today().year)
    end_dt = dt.datetime.strptime(end_str, '%B_%d').replace(year=dt.date.today().year)
except ValueError:
    start_dt, end_dt = None, None
if end_dt and end_dt.date() > dt.date.today():
    st.sidebar.error('⚠️ Selected week is in the future!')

# B. Currency multiselect
currencies = ['LKR','USD','GBP','AUD','DKK','EUR','MXN','INR','AED']
selected_currencies = st.sidebar.multiselect('Select Currencies', currencies, default=['LKR'])
if not selected_currencies:
    st.sidebar.error('Select at least one currency')
    st.stop()

# C. Live Currency converter with fallback
@st.cache_data(ttl=3600)
def get_rate(base: str, symbol: str) -> float:
    try:
        resp = requests.get(
            'https://api.exchangerate.host/latest',
            params={'base': base, 'symbols': symbol}, timeout=5
        )
        data = resp.json()
        return data.get('rates', {}).get(symbol)
    except Exception:
        return None

st.sidebar.header('Currency Converter')
amount = st.sidebar.number_input('Amount', min_value=0.0, value=1.0, step=0.1)
from_cur = st.sidebar.selectbox('From', currencies, index=0)
to_cur = st.sidebar.selectbox('To', currencies, index=1)
# Attempt live rate
rate = get_rate(from_cur, to_cur)
if rate:
    st.sidebar.write(f'Live rate: 1 {from_cur} = {rate:.4f} {to_cur}')
else:
    st.sidebar.warning('Could not fetch live rate; please enter manually:')
    rate = st.sidebar.number_input(f'Manual rate ({from_cur}→{to_cur})', min_value=0.0001, value=1.0, step=0.0001)
converted = amount * rate
st.sidebar.write(f'{amount} {from_cur} = {converted:.2f} {to_cur}')
st.sidebar.info('Live rates via exchangerate.host; cached hourly.')

# 3. Main Title
st.title('📊 Weekly Fund Dashboard')
subtitle = selected_week.replace('_', ' ')
if start_dt and end_dt:
    subtitle += f' ({start_dt.date()} to {end_dt.date()})'
st.subheader(subtitle)

# Filter data by week
week_df = fund_data[fund_data['Week'] == selected_week]

# 4. Weekly Summary
st.header('🔖 Weekly Summary')
summary_df = week_df.groupby('Section')[selected_currencies].sum().reset_index()
col_names = ['Category'] + [f'Total {cur}' for cur in selected_currencies]
summary_df.columns = col_names
st.table(summary_df)
st.download_button(
    label='Download Weekly Summary',
    data=summary_df.to_csv(index=False),
    file_name=f"{selected_week}_Weekly_Summary.csv",
    mime='text/csv'
)

# 5. Detailed Breakdown
st.header('📂 Detailed Breakdown')
for section in ['Bank & Cash Balances','Cash Ins','Cash Outs']:
    sec_df = week_df[week_df['Section'].str.contains(section, na=False)]
    with st.expander(section):
        cols = ['Details'] + selected_currencies + ['Total in LKR', 'Total in USD']
        display_df = sec_df[cols].rename(columns={'Details':'Category'})
        st.table(display_df)

# 6. Charts & Graphs
st.header('📈 Charts & Graphs')
ins_trend_df = fund_data[fund_data['Section']=='Cash Ins'].groupby('Week')[selected_currencies].sum()
st.line_chart(ins_trend_df)
outs_trend_df = fund_data[fund_data['Section']=='Cash Outs'].groupby('Week')[selected_currencies].sum()
st.line_chart(outs_trend_df)
chart_df = week_df.groupby('Section')[selected_currencies].sum().reset_index()
st.bar_chart(chart_df.set_index('Section'))

# 7. Full Dataset
st.header('📁 Full Dataset')
with st.expander('View Full Dataset'):
    st.dataframe(fund_data)
    st.download_button(
        label='Download Full Dataset',
        data=fund_data.to_csv(index=False),
        file_name='Full_Weekly_Fund_Data.csv',
        mime='text/csv'
    )

# Footer
st.write('---')
st.caption('Created with ❤️ using Streamlit & GitHub')
