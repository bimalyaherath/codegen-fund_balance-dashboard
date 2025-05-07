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
            section = df.loc[start, 'Details']
            part = df.iloc[start+1:end].dropna(how='all').copy()
            part['Section'] = section
            parts.append(part)
        week_df = pd.concat(parts, ignore_index=True)
        week_df['Week'] = week_label
        all_weeks.append(week_df)
    return pd.concat(all_weeks, ignore_index=True) if all_weeks else pd.DataFrame()

fund_data = load_fund_data()
if fund_data.empty:
    st.error("No weekly fund data found. Upload 'Fund_Balance_*.xlsx' files to the repo root, 'data/' or '/mnt/data'.")
    st.stop()

# 2. Helper to parse week start date
current_year = dt.date.today().year

def parse_week_start(w):
    try:
        start = w.split('_to_')[0]
        return dt.datetime.strptime(start, '%B_%d').replace(year=current_year)
    except:
        return dt.datetime.min

# Chronologically sorted weeks
weeks = sorted(fund_data['Week'].unique(), key=parse_week_start)
week_start_dates = [parse_week_start(w).date() for w in weeks]
min_date, max_date = min(week_start_dates), max(week_start_dates)

# 3. Sidebar Settings
st.sidebar.title('Dashboard Settings')
selected_week = st.sidebar.selectbox('Select Week', weeks)

# Currency multiselect
currencies = ['LKR','USD','GBP','AUD','DKK','EUR','MXN','INR','AED']
selected_currencies = st.sidebar.multiselect('Select Currencies', currencies, default=[currencies[0]])
if not selected_currencies:
    st.sidebar.error('Select at least one currency')
    st.stop()

# Live Currency Converter
@st.cache_data(ttl=3600)
def get_rate(base: str, symbol: str) -> float:
    resp = requests.get(
        'https://api.exchangerate.host/latest',
        params={'base': base, 'symbols': symbol}, timeout=5
    )
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

# 4. Main Dashboard Header
try:
    sd = parse_week_start(selected_week).date()
    ed = sd + dt.timedelta(days=6)
    subtitle = f"{selected_week.replace('_',' ')} ({sd} to {ed})"
except:
    subtitle = selected_week.replace('_',' ')
st.title('📊 Weekly Fund Dashboard')
st.subheader(subtitle)

# Filter for selected week
df_week = fund_data[fund_data['Week'] == selected_week]

# 5. Weekly Summary
st.header('🔖 Weekly Summary')
summary = df_week.groupby('Section')[selected_currencies].sum().reset_index()
summary.columns = ['Category'] + [f'Total {cur}' for cur in selected_currencies]
st.table(summary)
st.download_button('Download Weekly Summary', summary.to_csv(index=False), file_name=f"{selected_week}_Weekly_Summary.csv", mime='text/csv')

# 6. Cash Ins & Outs Breakdown
st.header('📂 Cash Ins & Outs Breakdown')
with st.expander('Cash Ins'):
    ins = df_week[df_week['Section']=='Cash Ins'][['Details'] + selected_currencies]
    ins.columns = ['Category'] + selected_currencies
    st.table(ins)
with st.expander('Cash Outs'):
    outs = df_week[df_week['Section']=='Cash Outs'][['Details'] + selected_currencies]
    outs.columns = ['Category'] + selected_currencies
    st.table(outs)

# 7. Weekly Comparison
st.header('📈 Weekly Comparison')
comp_weeks = st.multiselect('Select Weeks to Compare', weeks, default=weeks[-2:])
if comp_weeks:
    comp_df = fund_data[fund_data['Week'].isin(comp_weeks)]
    comp_summary = comp_df.groupby('Week')[selected_currencies].sum()
    st.line_chart(comp_summary)
else:
    st.info('Select at least one week to compare.')

# 8. Additional Charts
st.header('📊 Additional Charts')
# A. Cash Ins vs Cash Outs Totals for Selected Week
st.subheader('Cash Ins vs Cash Outs Totals')
sec_totals = df_week.groupby('Section')[selected_currencies].sum().loc[['Cash Ins','Cash Outs']]
st.bar_chart(sec_totals)

# 9. Net Cash-Flow & Balances
st.header('💰 Net Cash-Flow & Balances')
for cur in selected_currencies:
    open_vals = fund_data[fund_data['Section']=='Bank & Cash Balances'].groupby('Week')[cur].sum()
    ins_vals = fund_data[fund_data['Section']=='Cash Ins'].groupby('Week')[cur].sum()
    outs_vals = fund_data[fund_data['Section']=='Cash Outs'].groupby('Week')[cur].sum()
    net_vals = ins_vals.sub(outs_vals, fill_value=0)
    close_vals = open_vals.add(net_vals, fill_value=0)
    stats = pd.DataFrame({
        'Opening': open_vals,
        'Net Change': net_vals,
        'Closing': close_vals
    }).reindex(weeks)
    st.subheader(f'{cur} Balances Over Time')
    st.line_chart(stats)

# 10. Alerts & Thresholds
st.header('🚨 Alerts & Thresholds')
thresholds = {}
for cur in selected_currencies:
    thresholds[cur] = st.number_input(
        f'Threshold for net cash change in {cur}',
        value=0.0, step=1.0, key=f'th_{cur}'
    )
ins_week = fund_data[(fund_data['Week']==selected_week) & (fund_data['Section']=='Cash Ins')].groupby('Week')[selected_currencies].sum().reindex([selected_week], fill_value=0)
outs_week = fund_data[(fund_data['Week']==selected_week) & (fund_data['Section']=='Cash Outs')].groupby('Week')[selected_currencies].sum().reindex([selected_week], fill_value=0)
net_week = ins_week - outs_week
for cur in selected_currencies:
    net_val = float(net_week[cur])
    th = thresholds[cur]
    if net_val < th:
        st.error(f'Alert: Net cash change for {selected_week} in {cur} is {net_val:.2f}, below threshold {th}.')
    else:
        st.success(f'Net cash change for {selected_week} in {cur} is {net_val:.2f}, meets threshold {th}.')

# 11. Date-Range & Rolling Periods
st.header('📅 Date Range & Rolling Periods')
mode = st.radio('Select Mode:', ['Custom Date Range', 'Rolling Window'])

if mode == 'Custom Date Range':
    drange = st.date_input('Date range:', [min_date, max_date], min_value=min_date, max_value=max_date)
    if len(drange) == 2:
        start_d, end_d = drange
        period_weeks = [w for w in weeks if start_d <= parse_week_start(w).date() <= end_d]
        if period_weeks:
            pr_df = fund_data[fund_data['Week'].isin(period_weeks)]
            pr_sum = pr_df.groupby('Section')[selected_currencies].sum().reset_index()
            pr_sum.columns = ['Category'] + [f'Total {cur}' for cur in selected_currencies]
            st.write(pr_sum)
        else:
            st.info('No data in this date range.')

if mode == 'Rolling Window':
    rw = st.selectbox('Window Type:', ['Last N Weeks', 'Month-to-Date', 'Quarter-to-Date'])
    if rw == 'Last N Weeks':
        n = st.number_input('Number of weeks:', min_value=1, max_value=len(weeks), value=4)
        rw_weeks = weeks[-n:]
    elif rw == 'Month-to-Date':
        today = dt.date.today()
        start_m = today.replace(day=1)
        rw_weeks = [w for w in weeks if start_m <= parse_week_start(w).date() <= today]
    else:
        today = dt.date.today()
        q = (today.month - 1) // 3
        start_q = dt.date(today.year, q*3+1, 1)
        rw_weeks = [w for w in weeks if start_q <= parse_week_start(w).date() <= today]
    pr_df = fund_data[fund_data['Week'].isin(rw_weeks)]
    pr_sum = pr_df.groupby('Section')[selected_currencies].sum().reset_index()
    pr_sum.columns = ['Category'] + [f'Total {cur}' for cur in selected_currencies]
    st.write(pr_sum)

# 12. Forecasting & Trends
st.header('🔮 Forecasting & Trends')
# A. Moving Averages on Weekly Comparison
st.subheader('Moving Averages on Weekly Comparison')
if comp_weeks:
    comp_df = fund_data[fund_data['Week'].isin(comp_weeks)]
    comp_summary = comp_df.groupby('Week')[selected_currencies].sum()
    for cur in selected_currencies:
        series = comp_summary[cur]
        # 3-week moving average
        ma = series.rolling(window=3, min_periods=1).mean()
        df_plot = pd.DataFrame({
            'Actual': series,
            'Moving Average (3wk)': ma
        })
        st.line_chart(df_plot)
else:
    st.info('Select weeks above to show moving averages.')

# B. ARIMA Forecast for Closing Balance
st.subheader('ARIMA Forecast for Closing Balance')
from statsmodels.tsa.arima.model import ARIMA
for cur in selected_currencies:
    # Prepare closing balance series for all weeks
    open_vals = fund_data[fund_data['Section']=='Bank & Cash Balances'].groupby('Week')[cur].sum()
    ins_vals = fund_data[fund_data['Section']=='Cash Ins'].groupby('Week')[cur].sum()
    outs_vals = fund_data[fund_data['Section']=='Cash Outs'].groupby('Week')[cur].sum()
    net_vals = ins_vals.sub(outs_vals, fill_value=0)
    close_vals = open_vals.add(net_vals, fill_value=0)
    try:
        model = ARIMA(close_vals, order=(1,1,0))
        res = model.fit()
        fcast = res.forecast(steps=1)
        st.write(f'Forecast next week closing balance in {cur}: {fcast.iloc[0]:.2f} {cur}')
    except Exception as e:
        st.warning(f'Could not forecast for {cur}: {e}')

# 13. Full Dataset
st.header('📁 Full Dataset')
with st.expander('View Full Dataset'):
    st.dataframe(fund_data)
    st.download_button('Download Full Dataset', fund_data.to_csv(index=False), file_name='Full_Weekly_Fund_Data.csv', mime='text/csv')

st.write('---')
st.caption('Created with ❤️ using Streamlit & GitHub')
