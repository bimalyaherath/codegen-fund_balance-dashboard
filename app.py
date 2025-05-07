import streamlit as st
import pandas as pd
import datetime as dt
import glob
import os
import requests
import json

# --- Data Upload & Versioning Setup ---
import tempfile
# Use system temp directory for uploads to avoid permission issues
UPLOAD_DIR = os.path.join(tempfile.gettempdir(), 'weekly_uploads')
HISTORY_FILE = os.path.join(UPLOAD_DIR, 'upload_history.json')
# Create upload directory if not exists
os.makedirs(UPLOAD_DIR, exist_ok=True)

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            return json.load(open(HISTORY_FILE))
        except:
            return []
    return []

history = load_history()

# File uploader for new weekly Excel files
uploaded_files = st.sidebar.file_uploader(
    "Upload Weekly Excel Files (versioned)",
    type=['xlsx'], accept_multiple_files=True
)
if uploaded_files:
    timestamp = dt.datetime.now().isoformat()
    saved = []
    for f in uploaded_files:
        save_name = f"{timestamp}_{f.name}"
        with open(os.path.join(UPLOAD_DIR, save_name), 'wb') as out:
            out.write(f.getbuffer())
        saved.append(save_name)
    history.append({"timestamp": timestamp, "files": saved})
    with open(HISTORY_FILE, 'w') as hist_f:
        json.dump(history, hist_f)
    st.sidebar.success(f"Uploaded {len(saved)} files at {timestamp}")

# Version selection
version_labels = [entry['timestamp'] for entry in history]
version_choice = st.sidebar.selectbox(
    'Select Data Version', ['Latest'] + version_labels
)
if version_choice == 'Latest':
    version_files = os.listdir(UPLOAD_DIR)
else:
    version_files = next(e['files'] for e in history if e['timestamp'] == version_choice)

# --- Data Loading Function ---
@st.cache_data
def load_fund_data(version_files):
    # Static files
    static_paths = glob.glob('data/Fund_Balance_*.xlsx') \
                   + glob.glob('/mnt/data/Fund_Balance_*.xlsx') \
                   + glob.glob('Fund_Balance_*.xlsx')
    # Uploaded versioned files
    upload_paths = [os.path.join(UPLOAD_DIR, f) for f in version_files]
    all_paths = static_paths + upload_paths
    all_weeks = []
    for file in all_paths:
        week_label = os.path.basename(file).replace('Fund_Balance_','').replace('.xlsx','')
        try:
            df = pd.read_excel(file)
        except Exception as e:
            st.warning(f"Could not read {file}: {e}")
            continue
        mask = df['Details'].str.contains(
            'Bank & Cash Balances|Cash Transactions During the Week|Cash Ins|Cash Outs',
            na=False
        )
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

# Load dataset based on version selection
fund_data = load_fund_data(version_files)
if fund_data.empty:
    st.error("No fund data found for selected version.")
    st.stop()

# --- Helper Functions ---
current_year = dt.date.today().year

def parse_week_start(w):
    try:
        start = w.split('_to_')[0]
        return dt.datetime.strptime(start, '%B_%d').replace(year=current_year)
    except:
        return dt.datetime.min

# Chronological weeks
weeks = sorted(fund_data['Week'].unique(), key=parse_week_start)

# --- Sidebar Filters ---
st.sidebar.title('Dashboard Settings')
selected_week = st.sidebar.selectbox('Select Week', weeks)

# Currency multiselect
currencies = ['LKR','USD','GBP','AUD','DKK','EUR','MXN','INR','AED']
selected_currencies = st.sidebar.multiselect(
    'Select Currencies', currencies, default=[currencies[0]]
)
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

# --- Main Dashboard ---
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

# 1. Weekly Summary
st.header('🔖 Weekly Summary')
summary = df_week.groupby('Section')[selected_currencies].sum().reset_index()
summary.columns = ['Category'] + [f'Total {cur}' for cur in selected_currencies]
st.table(summary)
st.download_button('Download Weekly Summary', summary.to_csv(index=False), file_name=f"{selected_week}_Weekly_Summary.csv", mime='text/csv')

# 2. Cash Ins & Outs Breakdown
st.header('📂 Cash Ins & Outs Breakdown')
with st.expander('Cash Ins'):
    ins = df_week[df_week['Section']=='Cash Ins'][['Details'] + selected_currencies]
    ins.columns = ['Category'] + selected_currencies
    st.table(ins)
with st.expander('Cash Outs'):
    outs = df_week[df_week['Section']=='Cash Outs'][['Details'] + selected_currencies]
    outs.columns = ['Category'] + selected_currencies
    st.table(outs)

# 3. Weekly Comparison
st.header('📈 Weekly Comparison')
comp_weeks = st.multiselect('Select Weeks to Compare', weeks, default=weeks[-2:])
if comp_weeks:
    comp_df = fund_data[fund_data['Week'].isin(comp_weeks)]
    comp_summary = comp_df.groupby('Week')[selected_currencies].sum()
    st.line_chart(comp_summary)
else:
    st.info('Select at least one week to compare.')

# 4. Additional Charts
st.header('📊 Additional Charts')
sec_totals = df_week.groupby('Section')[selected_currencies].sum().loc[['Cash Ins','Cash Outs']]
st.bar_chart(sec_totals)

# 5. Net Cash-Flow & Balances
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

# 6. Alerts & Thresholds
st.header('🚨 Alerts & Thresholds')
thresholds = {}
for cur in selected_currencies:
    thresholds[cur] = st.number_input(f'Threshold for net cash change in {cur}', value=0.0, step=1.0, key=f'th_{cur}')
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

# 7. Date-Range & Rolling Periods
st.header('📅 Date Range & Rolling Periods')
mode = st.radio('Select Mode:', ['Custom Date Range', 'Rolling Window'])
min_date, max_date = min(parse_week_start(w).date() for w in weeks), max(parse_week_start(w).date() for w in weeks)
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
elif mode == 'Rolling Window':
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

# Footer
st.write('---')
st.caption('Created with ❤️ using Streamlit & GitHub')
