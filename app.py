import streamlit as st
import pandas as pd
import datetime as dt
import glob
import os
import requests
import json
import tempfile
import io

# Try to import export libraries
try:
    from fpdf import FPDF
    from pptx import Presentation
    from pptx.util import Inches
    EXPORT_ENABLED = True
except ImportError:
    EXPORT_ENABLED = False

# --- Data Upload & Versioning Setup ---
UPLOAD_DIR = os.path.join(tempfile.gettempdir(), 'weekly_uploads')
HISTORY_FILE = os.path.join(UPLOAD_DIR, 'upload_history.json')
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Load upload history
if os.path.exists(HISTORY_FILE):
    try:
        history = json.load(open(HISTORY_FILE))
    except Exception:
        history = []
else:
    history = []

# File uploader for versioned weekly Excel files
duploaded = st.sidebar.file_uploader(
    "Upload Weekly Excel Files (versioned)",
    type=['xlsx'], accept_multiple_files=True
)
if uploaded:
    ts = dt.datetime.now().isoformat()
    saved = []
    for f in uploaded:
        fn = f"{ts}_{f.name}"
        path = os.path.join(UPLOAD_DIR, fn)
        with open(path, 'wb') as out:
            out.write(f.getbuffer())
        saved.append(fn)
    history.append({'timestamp': ts, 'files': saved})
    json.dump(history, open(HISTORY_FILE, 'w'))
    st.sidebar.success(f"Uploaded {len(saved)} files at {ts}")

# Version selection
dlabels = ['Latest'] + [h['timestamp'] for h in history]
version_choice = st.sidebar.selectbox('Select Data Version', dlabels)
if version_choice == 'Latest':
    version_files = os.listdir(UPLOAD_DIR)
else:
    version_files = next(h['files'] for h in history if h['timestamp'] == version_choice)

# Load and parse data
@st.cache_data
def load_fund_data(files):
    static_paths = glob.glob('data/Fund_Balance_*.xlsx') + glob.glob('/mnt/data/Fund_Balance_*.xlsx') + glob.glob('Fund_Balance_*.xlsx')
    upload_paths = [os.path.join(UPLOAD_DIR, f) for f in files]
    all_paths = static_paths + upload_paths
    weeks_data = []
    for filepath in all_paths:
        label = os.path.basename(filepath).replace('Fund_Balance_','').replace('.xlsx','')
        try:
            df = pd.read_excel(filepath)
        except Exception:
            continue
        mask = df['Details'].str.contains('Bank & Cash Balances|Cash Ins|Cash Outs', na=False)
        idx = df[mask].index.tolist()
        parts = []
        for i, start in enumerate(idx):
            end = idx[i+1] if i+1 < len(idx) else len(df)
            section = df.loc[start, 'Details']
            part = df.iloc[start+1:end].dropna(how='all').copy()
            part['Section'] = section
            parts.append(part)
        week_df = pd.concat(parts, ignore_index=True)
        week_df['Week'] = label
        weeks_data.append(week_df)
    return pd.concat(weeks_data, ignore_index=True) if weeks_data else pd.DataFrame()

fund_data = load_fund_data(version_files)
if fund_data.empty:
    st.error("No fund data found for selected version.")
    st.stop()

# Helper to sort weeks chronologically
def parse_week(w):
    try:
        dt_str = w.split('_to_')[0]
        return dt.datetime.strptime(dt_str, '%B_%d').replace(year=dt.date.today().year)
    except Exception:
        return dt.datetime.min

weeks = sorted(fund_data['Week'].unique(), key=parse_week)

# --- Sidebar Filters ---
st.sidebar.title('Dashboard Settings')
selected_week = st.sidebar.selectbox('Select Week', weeks)

currencies = ['LKR','USD','GBP','AUD','DKK','EUR','MXN','INR','AED']
selected_currencies = st.sidebar.multiselect('Select Currencies', currencies, default=[currencies[0]])
if not selected_currencies:
    st.sidebar.error('Select at least one currency')
    st.stop()

# Live currency converter
@st.cache_data(ttl=3600)
def get_rate(base, symbol):
    resp = requests.get('https://api.exchangerate.host/latest', params={'base': base, 'symbols': symbol}, timeout=5)
    return resp.json().get('rates', {}).get(symbol)

st.sidebar.header('Currency Converter')
amt = st.sidebar.number_input('Amount', value=1.0)
frm = st.sidebar.selectbox('From Currency', currencies)
to_ = st.sidebar.selectbox('To Currency', currencies, index=1)
rate = get_rate(frm, to_)
if rate:
    st.sidebar.write(f"1 {frm} = {rate:.4f} {to_}")
    st.sidebar.write(f"{amt} {frm} = {amt*rate:.2f} {to_}")
else:
    st.sidebar.error('Failed to fetch live exchange rate')

# --- Main Dashboard ---
try:
    start_dt = parse_week(selected_week).date()
    end_dt = start_dt + dt.timedelta(days=6)
    subtitle = f"{selected_week.replace('_',' ')} ({start_dt} to {end_dt})"
except Exception:
    subtitle = selected_week.replace('_',' ')
st.title('📊 Weekly Fund Dashboard')
st.subheader(subtitle)

# Filter data for selected week
df_week = fund_data[fund_data['Week'] == selected_week]

# 1. Weekly Summary
st.header('🔖 Weekly Summary')
sum_df = df_week.groupby('Section')[selected_currencies].sum().reset_index()
sum_df.columns = ['Category'] + [f'Total {c}' for c in selected_currencies]
st.table(sum_df)
st.download_button('Download Weekly Summary', sum_df.to_csv(index=False), file_name=f"{selected_week}_Weekly_Summary.csv", mime='text/csv')

# 2. Cash Breakdown
st.header('📂 Cash Ins & Outs Breakdown')
with st.expander('Cash Ins'):
    ins_df = df_week[df_week['Section']=='Cash Ins'][['Details'] + selected_currencies].rename(columns={'Details':'Category'})
    st.table(ins_df)
with st.expander('Cash Outs'):
    outs_df = df_week[df_week['Section']=='Cash Outs'][['Details'] + selected_currencies].rename(columns={'Details':'Category'})
    st.table(outs_df)

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
st.subheader('Cash Ins vs Cash Outs')
st.bar_chart(df_week.groupby('Section')[selected_currencies].sum().loc[['Cash Ins','Cash Outs']])

# 5. Net Cash-Flow & Balances
st.header('💰 Net Cash-Flow & Balances')
for c in selected_currencies:
    open_bal = fund_data[fund_data['Section']=='Bank & Cash Balances'].groupby('Week')[c].sum()
    ins_bal = fund_data[fund_data['Section']=='Cash Ins'].groupby('Week')[c].sum()
    outs_bal = fund_data[fund_data['Section']=='Cash Outs'].groupby('Week')[c].sum()
    net_bal = ins_bal.sub(outs_bal, fill_value=0)
    close_bal = open_bal.add(net_bal, fill_value=0)
    chart_df = pd.DataFrame({'Opening': open_bal, 'Net Change': net_bal, 'Closing': close_bal}).reindex(weeks)
    st.subheader(f'{c} Balances Over Time')
    st.line_chart(chart_df)

# 6. Alerts & Thresholds
st.header('🚨 Alerts & Thresholds')
thresholds = {c: st.number_input(f'Threshold for net cash change in {c}', value=0.0, step=1.0, key=f'th_{c}') for c in selected_currencies}
ins_w = fund_data[(fund_data['Week']==selected_week) & (fund_data['Section']=='Cash Ins')].groupby('Week')[selected_currencies].sum().reindex([selected_week], fill_value=0)
outs_w = fund_data[(fund_data['Week']==selected_week) & (fund_data['Section']=='Cash Outs')].groupby('Week')[selected_currencies].sum().reindex([selected_week], fill_value=0)
net_w = ins_w.sub(outs_w, fill_value=0)
for c in selected_currencies:
    val = float(net_w[c])
    th = thresholds[c]
    if val < th:
        st.error(f"🚨 Alert! Net cash for {selected_week} in {c} is {val:.2f}, below your threshold of {th:.2f}. 📉 Review spending.")
    else:
        st.success(f"✅ Net cash for {selected_week} in {c} is {val:.2f}, above threshold {th:.2f}. Good job! 🎉")

# 7. Date-Range & Rolling Periods
st.header('📅 Date-Range & Rolling Periods')
mode = st.radio('Select Mode:', ['Custom Date Range', 'Rolling Window'])
mdates = [parse_week(w).date() for w in weeks]
min_date, max_date = min(mdates), max(mdates)
if mode == 'Custom Date Range':
    dr = st.date_input('Date range:', [min_date, max_date], min_value=min_date, max_value=max_date)
    if len(dr) == 2:
        start_d, end_d = dr
        selw = [w for w in weeks if start_d <= parse_week(w).date() <= end_d]
        if selw:
            df2 = fund_data[fund_data['Week'].isin(selw)]
            sum2 = df2.groupby('Section')[selected_currencies].sum().reset_index()
            sum2.columns = ['Category'] + [f'Total {c}' for c in selected_currencies]
            st.write(sum2)
        else:
            st.info('No data in this date range.')
elif mode == 'Rolling Window':
    rw = st.selectbox('Window Type:', ['Last N Weeks', 'Month-to-Date', 'Quarter-to-Date'])
    if rw == 'Last N Weeks':
        n = st.number_input('Number of weeks:', min_value=1, max_value=len(weeks), value=4)
        selw = weeks[-int(n):]
    elif rw == 'Month-to-Date':
        today = dt.date.today()
        start_m = today.replace(day=1)
        selw = [w for w in weeks if start_m <= parse_week(w).date() <= today]
    else:
        today = dt.date.today()
        q = (today.month - 1) // 3
        start_q = dt.date(today.year, q*3+1, 1)
        selw = [w for w in weeks if start_q <= parse_week(w).date() <= today]
    df2 = fund_data[fund_data['Week'].isin(selw)]
    sum2 = df2.groupby('Section')[selected_currencies].sum().reset_index()
    sum2.columns = ['Category'] + [f'Total {c}' for c in selected_currencies]
    st.write(sum2)

# 8. Forecasting & Trends
import statsmodels.api as sm
st.header('🔮 Forecasting & Trends')
# Moving Averages
if comp_weeks:
    dfc = fund_data[fund_data['Week'].isin(comp_weeks)].groupby('Week')[selected_currencies].sum()
    for c in selected_currencies:
        s = dfc[c]
        ma = s.rolling(3, min_periods=1).mean()
        st.subheader(f'{c} Actual vs MA')
        st.line_chart(pd.DataFrame({'Actual': s, 'MA (3wk)': ma}))
# ARIMA
st.subheader('ARIMA Next-Week Forecast')
for c in selected_currencies:
    op = fund_data[fund_data['Section']=='Bank & Cash Balances'].groupby('Week')[c].sum()
    ins = fund_data[fund_data['Section']=='Cash Ins'].groupby('Week')[c].sum()
    outs = fund_data[fund_data['Section']=='Cash Outs'].groupby('Week')[c].sum()
    net = ins.sub(outs, fill_value=0)
    close = op.add(net, fill_value=0)
    try:
        model = sm.tsa.ARIMA(close, order=(1,1,0)).fit()
        fcast = model.forecast(steps=1)
        st.write(f'Next week closing {c}: {fcast.iloc[0]:.2f}')
    except Exception as e:
        st.warning(f'Could not forecast {c}: {e}')

# 9. Export & Sharing
st.header('📤 Export & Sharing')
if EXPORT_ENABLED:
    if st.button('Export Weekly Summary as PDF'):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font('Arial','',10)
        for _, row in sum_df.iterrows():
            pdf.cell(0,8,' | '.join(str(v) for v in row.values), ln=1)
        pdf_data = pdf.output(dest='S').encode('latin1')
        st.download_button('Download PDF', pdf_data, 'summary.pdf', 'application/pdf')
    if st.button('Export Weekly Summary as PPT'):
        prs = Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[5])
        tb = slide.shapes.add_textbox(Inches(1),Inches(1),Inches(8),Inches(5)).text_frame
        for _, row in sum_df.iterrows():
            tb.add_paragraph(' | '.join(str(v) for v in row.values))
        buf = io.BytesIO()
        prs.save(buf)
        buf.seek(0)
        st.download_button('Download PPT', buf.read(), 'summary.pptx', 'application/vnd.openxmlformats-officedocument.presentationml.presentation')
else:
    st.info('Install `fpdf` and `python-pptx` to enable Export & Sharing')

# 10. Full Dataset
st.header('📁 Full Dataset')
st.dataframe(fund_data)

st.write('---')
st.caption('Created with ❤️ using Streamlit & GitHub')
