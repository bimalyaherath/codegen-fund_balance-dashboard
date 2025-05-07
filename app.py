import streamlit as st
import pandas as pd
import datetime as dt
import glob
import os
import requests
import json
import tempfile

# Attempt to import export libs, otherwise disable export
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
def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            return json.load(open(HISTORY_FILE))
        except:
            return []
    return []
history = load_history()

# Upload new files
uploaded = st.sidebar.file_uploader(
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
version_labels = ['Latest'] + [h['timestamp'] for h in history]
version_choice = st.sidebar.selectbox('Select Data Version', version_labels)
version_files = (os.listdir(UPLOAD_DIR) if version_choice=='Latest'
                 else next(h['files'] for h in history if h['timestamp']==version_choice))

# Load and parse all data files
@st.cache_data
def load_fund_data(files):
    static = glob.glob('data/Fund_Balance_*.xlsx') + glob.glob('/mnt/data/Fund_Balance_*.xlsx') + glob.glob('Fund_Balance_*.xlsx')
    uploads = [os.path.join(UPLOAD_DIR, f) for f in files]
    paths = static + uploads
    frames = []
    for file in paths:
        label = os.path.basename(file).replace('Fund_Balance_','').replace('.xlsx','')
        try:
            df = pd.read_excel(file)
        except:
            continue
        mask = df['Details'].str.contains('Bank & Cash Balances|Cash Transactions During the Week|Cash Ins|Cash Outs', na=False)
        idx = df[mask].index.tolist()
        parts = []
        for i,start in enumerate(idx):
            end = idx[i+1] if i+1<len(idx) else len(df)
            section = df.loc[start,'Details']
            part = df.iloc[start+1:end].dropna(how='all').copy()
            part['Section'] = section
            parts.append(part)
        week_df = pd.concat(parts, ignore_index=True)
        week_df['Week'] = label
        frames.append(week_df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

fund_data = load_fund_data(version_files)
if fund_data.empty:
    st.error("No fund data found for selected version.")
    st.stop()

# Helper to sort weeks chronologically
current_year = dt.date.today().year
def parse_week(w):
    try:
        start = w.split('_to_')[0]
        return dt.datetime.strptime(start, '%B_%d').replace(year=current_year)
    except:
        return dt.datetime.min
weeks = sorted(fund_data['Week'].unique(), key=parse_week)

# Sidebar filters
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
    try:
        resp = requests.get('https://api.exchangerate.host/latest', params={'base':base,'symbols':symbol}, timeout=5)
        return resp.json().get('rates',{}).get(symbol)
    except:
        return None

st.sidebar.header('Currency Converter')
amt = st.sidebar.number_input('Amount', value=1.0)
frm = st.sidebar.selectbox('From Currency', currencies)
to = st.sidebar.selectbox('To Currency', currencies, index=1)
rate = get_rate(frm, to)
if rate:
    st.sidebar.write(f"1 {frm} = {rate:.4f} {to}")
    st.sidebar.write(f"{amt} {frm} = {amt*rate:.2f} {to}")
else:
    st.sidebar.error('Rate fetch failed')

# Main header
sd = parse_week(selected_week).date()
ed = sd + dt.timedelta(days=6)
st.title('📊 Weekly Fund Dashboard')
st.subheader(f"{selected_week.replace('_',' ')} ({sd} to {ed})")

# Filter for selected week
df_week = fund_data[fund_data['Week']==selected_week]

# 1. Weekly Summary
st.header('🔖 Weekly Summary')
sum_df = df_week.groupby('Section')[selected_currencies].sum().reset_index()
sum_df.columns = ['Category'] + [f'Total {c}' for c in selected_currencies]
st.table(sum_df)
st.download_button('Download Weekly Summary', sum_df.to_csv(index=False), f"{selected_week}_Weekly_Summary.csv", 'text/csv')

# 2. Cash Ins & Outs Breakdown
st.header('📂 Cash Ins & Outs Breakdown')
with st.expander('Cash Ins'):
    ins_tbl = df_week[df_week['Section']=='Cash Ins'][['Details']+selected_currencies].rename(columns={'Details':'Category'})
    st.table(ins_tbl)
with st.expander('Cash Outs'):
    outs_tbl = df_week[df_week['Section']=='Cash Outs'][['Details']+selected_currencies].rename(columns={'Details':'Category'})
    st.table(outs_tbl)

# 3. Weekly Comparison
st.header('📈 Weekly Comparison')
comp_weeks = st.multiselect('Select Weeks to Compare', weeks, default=weeks[-2:])
if comp_weeks:
    comp_df = fund_data[fund_data['Week'].isin(comp_weeks)]
    comp_sum = comp_df.groupby('Week')[selected_currencies].sum()
    st.line_chart(comp_sum)
else:
    st.info('Select at least one week to compare.')

# 4. Additional Charts
st.header('📊 Additional Charts')
st.subheader('Cash Ins vs Cash Outs')
st.bar_chart(df_week.groupby('Section')[selected_currencies].sum().loc[['Cash Ins','Cash Outs']])

# 5. Net Cash-Flow & Balances
st.header('💰 Net Cash-Flow & Balances')
for c in selected_currencies:
    opens = fund_data[fund_data['Section']=='Bank & Cash Balances'].groupby('Week')[c].sum()
    ins = fund_data[fund_data['Section']=='Cash Ins'].groupby('Week')[c].sum()
    outs = fund_data[fund_data['Section']=='Cash Outs'].groupby('Week')[c].sum()
    net = ins.sub(outs, fill_value=0)
    close = opens.add(net, fill_value=0)
    chart_df = pd.DataFrame({'Opening':opens,'Net Change':net,'Closing':close}).reindex(weeks)
    st.subheader(f'{c} Balances Over Time')
    st.line_chart(chart_df)

# 6. Alerts & Thresholds
st.header('🚨 Alerts & Thresholds')
thresh = {c: st.number_input(f'Threshold Net {c}', value=0.0, key=f'th_{c}') for c in selected_currencies}
ins_week = fund_data[(fund_data['Week']==selected_week)&(fund_data['Section']=='Cash Ins')].groupby('Week')[selected_currencies].sum().reindex([selected_week],fill_value=0)
outs_week = fund_data[(fund_data['Week']==selected_week)&(fund_data['Section']=='Cash Outs')].groupby('Week')[selected_currencies].sum().reindex([selected_week],fill_value=0)
net_week = ins_week.sub(outs_week, fill_value=0)
for c in selected_currencies:
    val = float(net_week[c]); th = thresh[c]
    if val < th: st.error(f'Alert: Net {c} = {val:.2f} < {th}')
    else: st.success(f'Net {c} = {val:.2f} ≥ {th}')

# 7. Date-Range & Rolling Periods
st.header('📅 Date-Range & Rolling Periods')
mode = st.radio('Mode',['Custom Date Range','Rolling Window'])
mdates = [parse_week(w).date() for w in weeks]; mn, mx = min(mdates), max(mdates)
if mode=='Custom Date Range':
    dr = st.date_input('Range',[mn,mx],min_value=mn,max_value=mx)
    if len(dr)==2:
        selw = [w for w in weeks if dr[0] <= parse_week(w).date() <= dr[1]]
        if selw:
            df2 = fund_data[fund_data['Week'].isin(selw)]
            s2 = df2.groupby('Section')[selected_currencies].sum().reset_index()
            s2.columns = ['Category'] + [f'Total {c}' for c in selected_currencies]
            st.write(s2)
        else:
            st.info('No data in this range')
elif mode=='Rolling Window':
    rw = st.selectbox('Window',['Last N Weeks','Month-to-Date','Quarter-to-Date'])
    if rw=='Last N Weeks': n=st.number_input('Weeks',1,len(weeks),4); selw=weeks[-int(n):]
    elif rw=='Month-to-Date':
        td=dt.date.today(); sd=td.replace(day=1); selw=[w for w in weeks if sd<=parse_week(w).date()<=td]
    else:
        td=dt.date.today(); q=(td.month-1)//3; sd=dt.date(td.year,q*3+1,1); selw=[w for w in weeks if sd<=parse_week(w).date()<=td]
    df2 = fund_data[fund_data['Week'].isin(selw)]
    s2 = df2.groupby('Section')[selected_currencies].sum().reset_index()
    s2.columns = ['Category'] + [f'Total {c}' for c in selected_currencies]
    st.write(s2)

# 8. Forecasting & Trends
import statsmodels.api as sm
st.header('🔮 Forecasting & Trends')
if comp_weeks:
    dfc = fund_data[fund_data['Week'].isin(comp_weeks)].groupby('Week')[selected_currencies].sum()
    for c in selected_currencies:
        series = dfc[c]
        ma = series.rolling(3,min_periods=1).mean()
        st.line_chart(pd.DataFrame({'Actual':series,'MA':ma}))
st.subheader('ARIMA Forecast')
for c in selected_currencies:
    opens = fund_data[fund_data['Section']=='Bank & Cash Balances'].groupby('Week')[c].sum()
    ins = fund_data[fund_data['Section']=='Cash Ins'].groupby('Week')[c].sum()
    outs = fund_data[fund_data['Section']=='Cash Outs'].groupby('Week')[c].sum()
    net = ins.sub(outs,fill_value=0)
    close = opens.add(net,fill_value=0)
    try:
        mod = sm.tsa.ARIMA(close,order=(1,1,0)).fit()
        fc = mod.forecast(1)
        st.write(f'Next close {c}: {fc.iloc[0]:.2f}')
    except:
        st.warning(f'Forecast failed for {c}')

# 9. Export & Sharing
st.header('📤 Export & Sharing')
if EXPORT_ENABLED:
    if st.button('Export Summary as PDF'):
        pdf = FPDF(); pdf.add_page(); pdf.set_font('Arial','',10)
        for i,row in sum_df.iterrows(): pdf.cell(0,8,'|'.join(str(v) for v in row.values),ln=1)
        st.download_button('Download PDF', pdf.output(dest='S').encode('latin1'), 'summary.pdf', 'application/pdf')
    if st.button('Export Summary as PPT'):
        prs = Presentation(); slide = prs.slides.add_slide(prs.slide_layouts[5])
        tb = slide.shapes.add_textbox(Inches(1),Inches(1),Inches(8),Inches(5)).text_frame
        for i,row in sum_df.iterrows(): tb.add_paragraph('|'.join(str(v) for v in row.values))
        buf = tempfile.BytesIO(); prs.save(buf); buf.seek(0)
        st.download_button('Download PPT', buf.read(), 'summary.pptx', 'application/vnd.openxmlformats-officedocument.presentationml.presentation')
else:
    st.info('Install fpdf and python-pptx to enable export')

# 10. Full Dataset
st.header('📁 Full Dataset')
st.dataframe(fund_data)

st.write('---')
st.caption('Created with ❤️ using Streamlit & GitHub')
