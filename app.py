import streamlit as st
import pandas as pd
import datetime as dt
import glob
import os
import requests
import json
import tempfile

# Try imports for export functionality
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

# Load history
if os.path.exists(HISTORY_FILE):
    try:
        history = json.load(open(HISTORY_FILE))
    except:
        history = []
else:
    history = []

# File uploader
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
if version_choice == 'Latest':
    version_files = os.listdir(UPLOAD_DIR)
else:
    version_files = next(h['files'] for h in history if h['timestamp'] == version_choice)

# Load and parse data
@st.cache_data
def load_fund_data(files):
    static = glob.glob('data/Fund_Balance_*.xlsx') + glob.glob('/mnt/data/Fund_Balance_*.xlsx') + glob.glob('Fund_Balance_*.xlsx')
    uploads = [os.path.join(UPLOAD_DIR, f) for f in files]
    paths = static + uploads
    frames = []
    for file in paths:
        week_label = os.path.basename(file).replace('Fund_Balance_','').replace('.xlsx','')
        try:
            df = pd.read_excel(file)
        except:
            continue
        mask = df['Details'].str.contains('Bank & Cash Balances|Cash Transactions During the Week|Cash Ins|Cash Outs', na=False)
        idx = df[mask].index.tolist()
        parts = []
        for i, start in enumerate(idx):
            end = idx[i+1] if i+1 < len(idx) else len(df)
            sec = df.loc[start, 'Details']
            part = df.iloc[start+1:end].dropna(how='all').copy()
            part['Section'] = sec
            parts.append(part)
        wdf = pd.concat(parts, ignore_index=True)
        wdf['Week'] = week_label
        frames.append(wdf)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

fund_data = load_fund_data(version_files)
if fund_data.empty:
    st.error("No fund data found for selected version.")
    st.stop()

# Helper to parse week start
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
sel_cur = st.sidebar.multiselect('Select Currencies', currencies, default=[currencies[0]])
if not sel_cur:
    st.sidebar.error('Select at least one currency')
    st.stop()

# Live currency converter
@st.cache_data(ttl=3600)
def get_rate(b, s):
    resp = requests.get('https://api.exchangerate.host/latest', params={'base': b, 'symbols': s}, timeout=5)
    return resp.json().get('rates', {}).get(s)

st.sidebar.header('Currency Converter')
amt = st.sidebar.number_input('Amount', value=1.0)
frm = st.sidebar.selectbox('From', currencies)
to = st.sidebar.selectbox('To', currencies, index=1)
r = get_rate(frm, to)
if r:
    st.sidebar.write(f"1 {frm} = {r:.4f} {to}")
    st.sidebar.write(f"{amt} {frm} = {amt*r:.2f} {to}")
else:
    st.sidebar.error('Rate fetch failed')

# Main header
try:
    sd = parse_week(selected_week).date()
    ed = sd + dt.timedelta(days=6)
    subtitle = f"{selected_week.replace('_',' ')} ({sd} to {ed})"
except:
    subtitle = selected_week.replace('_',' ')
st.title('📊 Weekly Fund Dashboard')
st.subheader(subtitle)

# Filter week
wd = fund_data[fund_data['Week'] == selected_week]

# 1. Weekly Summary
st.header('🔖 Weekly Summary')
sum_df = wd.groupby('Section')[sel_cur].sum().reset_index()
sum_df.columns = ['Category'] + [f'Total {c}' for c in sel_cur]
st.table(sum_df)
st.download_button('Download Weekly Summary', sum_df.to_csv(index=False), file_name=f"{selected_week}_Weekly_Summary.csv", mime='text/csv')

# 2. Cash Ins & Outs Breakdown
st.header('📂 Cash Ins & Outs Breakdown')
with st.expander('Cash Ins'):
    table_ins = wd[wd['Section']=='Cash Ins'][['Details'] + sel_cur].rename(columns={'Details':'Category'})
    st.table(table_ins)
with st.expander('Cash Outs'):
    table_outs = wd[wd['Section']=='Cash Outs'][['Details'] + sel_cur].rename(columns={'Details':'Category'})
    st.table(table_outs)

# 3. Weekly Comparison
st.header('📈 Weekly Comparison')
comp_weeks = st.multiselect('Select Weeks to Compare', weeks, default=weeks[-2:])
if comp_weeks:
    dfc = fund_data[fund_data['Week'].isin(comp_weeks)]
    cs = dfc.groupby('Week')[sel_cur].sum()
    st.line_chart(cs)
else:
    st.info('Select at least one week to compare.')

# 4. Additional Charts
st.header('📊 Additional Charts')
st.subheader('Cash Ins vs Cash Outs')
st.bar_chart(wd.groupby('Section')[sel_cur].sum().loc[['Cash Ins','Cash Outs']])

# 5. Net Cash-Flow & Balances
st.header('💰 Net Cash-Flow & Balances')
for c in sel_cur:
    op = fund_data[fund_data['Section']=='Bank & Cash Balances'].groupby('Week')[c].sum()
    ins = fund_data[fund_data['Section']=='Cash Ins'].groupby('Week')[c].sum()
    outs = fund_data[fund_data['Section']=='Cash Outs'].groupby('Week')[c].sum()
    net = ins.sub(outs, fill_value=0)
    close = op.add(net, fill_value=0)
    dfb = pd.DataFrame({'Opening':op, 'Net Change':net, 'Closing':close}).reindex(weeks)
    st.subheader(f'{c} Balances Over Time')
    st.line_chart(dfb)

# 6. Alerts & Thresholds
st.header('🚨 Alerts & Thresholds')
thr = {c: st.number_input(f'Threshold Net {c}', value=0.0, key=f'th_{c}') for c in sel_cur}
ins_w = fund_data[(fund_data['Week']==selected_week)&(fund_data['Section']=='Cash Ins')].groupby('Week')[sel_cur].sum().reindex([selected_week], fill_value=0)
outs_w = fund_data[(fund_data['Week']==selected_week)&(fund_data['Section']=='Cash Outs')].groupby('Week')[sel_cur].sum().reindex([selected_week], fill_value=0)
net_w = ins_w.sub(outs_w, fill_value=0)
for c in sel_cur:
    v = float(net_w[c]); t = thr[c]
    if v < t: st.error(f'Alert: Net {c} = {v:.2f} < threshold {t}')
    else: st.success(f'Net {c} = {v:.2f} ≥ threshold {t}')

# 7. Date-Range & Rolling Periods
st.header('📅 Date-Range & Rolling Periods')
mode = st.radio('Mode', ['Custom Date Range','Rolling Window'])
mdates = [parse_week(w).date() for w in weeks]; mn, mx = min(mdates), max(mdates)
if mode=='Custom Date Range':
    dr = st.date_input('Range', [mn, mx], min_value=mn, max_value=mx)
    if len(dr)==2:
        selw = [w for w in weeks if dr[0] <= parse_week(w).date() <= dr[1]]
        if selw:
            df2 = fund_data[fund_data['Week'].isin(selw)]
            s2 = df2.groupby('Section')[sel_cur].sum().reset_index()
            s2.columns = ['Category'] + [f'Total {c}' for c in sel_cur]
            st.write(s2)
        else:
            st.info('No data in this range')
elif mode=='Rolling Window':
    rw = st.selectbox('Window', ['Last N Weeks','Month-to-Date','Quarter-to-Date'])
    if rw=='Last N Weeks': n=st.number_input('Weeks',1,len(weeks),4); selw=weeks[-int(n):]
    elif rw=='Month-to-Date':
        td=dt.date.today(); sd=td.replace(day=1); selw=[w for w in weeks if sd<=parse_week(w).date()<=td]
    else:
        td=dt.date.today(); q=(td.month-1)//3; sd=dt.date(td.year,q*3+1,1); selw=[w for w in weeks if sd<=parse_week(w).date()<=td]
    df2=fund_data[fund_data['Week'].isin(selw)]; s2=df2.groupby('Section')[sel_cur].sum().reset_index(); s2.columns=['Category']+[f"Total {c}" for c in sel_cur]; st.write(s2)

# 8. Forecasting & Trends
import statsmodels.api as sm
st.header('🔮 Forecasting & Trends')
# Moving Averages
if comp_weeks:
    dfc=fund_data[fund_data['Week'].isin(comp_weeks)].groupby('Week')[sel_cur].sum()
    for c in sel_cur:
        s=dfc[c]; ma=s.rolling(3,min_periods=1).mean()
        st.line_chart(pd.DataFrame({'Actual':s,'MA':ma}))
# ARIMA
st.subheader('ARIMA Forecast')
for c in sel_cur:
    op = fund_data[fund_data['Section']=='Bank & Cash Balances'].groupby('Week')[c].sum()
    ins = fund_data[fund_data['Section']=='Cash Ins'].groupby('Week')[c].sum()
    outs= fund_data[fund_data['Section']=='Cash Outs'].groupby('Week')[c].sum()
    net=ins.sub(outs,fill_value=0); close=op.add(net,fill_value=0)
    try:
        m=sm.tsa.ARIMA(close,order=(1,1,0)).fit(); f=m.forecast(1)
        st.write(f'Next close {c}: {f.iloc[0]:.2f}')
    except:
        st.warning(f'Forecast failed for {c}')

# 9. Export & Sharing
st.header('📤 Export & Sharing')
if EXPORT_ENABLED:
    if st.button('Export Summary as PDF'):
        pdf = FPDF(); pdf.add_page(); pdf.set_font('Arial','',10)
        for i,row in sum_df.iterrows():
            pdf.cell(0,8,' | '.join(str(v) for v in row.values), ln=1)
        st.download_button('Download PDF', pdf.output(dest='S').encode('latin1'), 'summary.pdf', 'application/pdf')
    if st.button('Export Summary as PPT'):
        prs=Presentation(); slide=prs.slides.add_slide(prs.slide_layouts[5])
        tb=slide.shapes.add_textbox(Inches(1),Inches(1),Inches(8),Inches(5)).text_frame
        for i,row in sum_df.iterrows(): tb.add_paragraph(' | '.join(str(v) for v in row.values))
        buf = tempfile.BytesIO(); prs.save(buf); buf.seek(0)
        st.download_button('Download PPT', buf.read(), 'summary.pptx', 'application/vnd.openxmlformats-officedocument.presentationml.presentation')
else:
    st.info('Install fpdf and python-pptx for Export & Sharing')

# 10. Full Dataset
st.header('📁 Full Dataset')
st.dataframe(fund_data)

st.write('---')
st.caption('Created with ❤️ using Streamlit & GitHub')
