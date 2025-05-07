import streamlit as st
import pandas as pd
import datetime as dt
import glob
import os
import requests
import json
import tempfile
from fpdf import FPDF
from pptx import Presentation
from pptx.util import Inches
import statsmodels.api as sm

# --- Data Upload & Versioning Setup ---
temp_dir = tempfile.gettempdir()
UPLOAD_DIR = os.path.join(temp_dir, 'weekly_uploads')
HISTORY_FILE = os.path.join(UPLOAD_DIR, 'upload_history.json')
os.makedirs(UPLOAD_DIR, exist_ok=True)

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            return json.load(open(HISTORY_FILE))
        except:
            return []
    return []
history = load_history()

# Sidebar: Uploader & Version selection
st.sidebar.title('Data Upload & Versioning')
upl = st.sidebar.file_uploader(
    "Upload Weekly Excel files", type=['xlsx'], accept_multiple_files=True
)
if upl:
    ts = dt.datetime.now().isoformat()
    saved = []
    for f in upl:
        fname = f"{ts}_{f.name}"
        path = os.path.join(UPLOAD_DIR, fname)
        with open(path, 'wb') as out:
            out.write(f.getbuffer())
        saved.append(fname)
    history.append({'timestamp': ts, 'files': saved})
    json.dump(history, open(HISTORY_FILE, 'w'))
    st.sidebar.success(f"Uploaded {len(saved)} files at {ts}")

versions = ['Latest'] + [h['timestamp'] for h in history]
version_choice = st.sidebar.selectbox('Select Version', versions)
if version_choice == 'Latest':
    version_files = os.listdir(UPLOAD_DIR)
else:
    version_files = next(h['files'] for h in history if h['timestamp'] == version_choice)

# --- Data Loading ---
@st.cache_data
def load_fund_data(upload_files):
    static_paths = glob.glob('data/Fund_Balance_*.xlsx') + glob.glob('/mnt/data/Fund_Balance_*.xlsx') + glob.glob('Fund_Balance_*.xlsx')
    upload_paths = [os.path.join(UPLOAD_DIR, f) for f in upload_files]
    all_paths = static_paths + upload_paths
    weeks = []
    for file in all_paths:
        label = os.path.basename(file).replace('Fund_Balance_','').replace('.xlsx','')
        try:
            df = pd.read_excel(file)
        except:
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
        wdf = pd.concat(parts, ignore_index=True)
        wdf['Week'] = label
        weeks.append(wdf)
    return pd.concat(weeks, ignore_index=True) if weeks else pd.DataFrame()

fund_data = load_fund_data(version_files)
if fund_data.empty:
    st.error('No fund data for selected version.')
    st.stop()

# Helper: parse week for sorting
def parse_week(w):
    try:
        start = w.split('_to_')[0]
        return dt.datetime.strptime(start, '%B_%d').replace(year=dt.date.today().year)
    except:
        return dt.datetime.min
weeks = sorted(fund_data['Week'].unique(), key=parse_week)

# --- Sidebar: Filters ---
st.sidebar.title('Dashboard Settings')
selected_week = st.sidebar.selectbox('Select Week', weeks)
currencies = ['LKR','USD','GBP','AUD','DKK','EUR','MXN','INR','AED']
selected_currencies = st.sidebar.multiselect('Select Currencies', currencies, default=[currencies[0]])
if not selected_currencies:
    st.sidebar.error('Select at least one currency')
    st.stop()

# Currency Converter
@st.cache_data(ttl=3600)
def get_rate(base, symbol):
    resp = requests.get('https://api.exchangerate.host/latest', params={'base': base, 'symbols': symbol}, timeout=5)
    rates = resp.json().get('rates', {})
    return rates.get(symbol)

st.sidebar.header('Currency Converter')
amt = st.sidebar.number_input('Amount', min_value=0.0, value=1.0, step=0.1)
frm = st.sidebar.selectbox('From', currencies)
to = st.sidebar.selectbox('To', currencies, index=1)
rate = get_rate(frm, to)
if rate:
    st.sidebar.write(f'1 {frm} = {rate:.4f} {to}')
    st.sidebar.write(f'{amt} {frm} = {amt*rate:.2f} {to}')
else:
    st.sidebar.error('Failed to fetch live rate')

# Main header
title = '📊 Weekly Fund Dashboard'
st.title(title)
try:
    sd = parse_week(selected_week).date()
    ed = sd + dt.timedelta(days=6)
    subtitle = f"{selected_week.replace('_',' ')} ({sd} to {ed})"
except:
    subtitle = selected_week.replace('_',' ')
st.subheader(subtitle)

# Filter week
df_week = fund_data[fund_data['Week'] == selected_week]

# 1. Weekly Summary
st.header('🔖 Weekly Summary')
sum_df = df_week.groupby('Section')[selected_currencies].sum().reset_index()
sum_df.columns = ['Category'] + [f'Total {c}' for c in selected_currencies]
st.table(sum_df)
st.download_button('Download Weekly Summary', sum_df.to_csv(index=False), file_name=f"{selected_week}_summary.csv", mime='text/csv')

# 2. Breakdown
st.header('📂 Cash Ins & Outs Breakdown')
with st.expander('Cash Ins'):
    ins = df_week[df_week['Section']=='Cash Ins'][['Details']+selected_currencies]
    ins.columns = ['Category']+selected_currencies
    st.table(ins)
with st.expander('Cash Outs'):
    outs = df_week[df_week['Section']=='Cash Outs'][['Details']+selected_currencies]
    outs.columns = ['Category']+selected_currencies
    st.table(outs)

# 3. Weekly Comparison
st.header('📈 Weekly Comparison')
comp_weeks = st.multiselect('Select Weeks to Compare', weeks, default=weeks[-2:])
if comp_weeks:
    comp_df = fund_data[fund_data['Week'].isin(comp_weeks)]
    comp_sum = comp_df.groupby('Week')[selected_currencies].sum()
    st.line_chart(comp_sum)
else:
    st.info('Select at least one week to compare')

# 4. Additional Charts
st.header('📊 Additional Charts')
st.subheader('Cash Ins vs Cash Outs')
chart_df = df_week.groupby('Section')[selected_currencies].sum().loc[['Cash Ins','Cash Outs']]
st.bar_chart(chart_df)

# 5. Net Cash-Flow & Balances
st.header('💰 Net Cash-Flow & Balances')
for cur in selected_currencies:
    opens = fund_data[fund_data['Section']=='Bank & Cash Balances'].groupby('Week')[cur].sum()
    insv = fund_data[fund_data['Section']=='Cash Ins'].groupby('Week')[cur].sum()
    outv = fund_data[fund_data['Section']=='Cash Outs'].groupby('Week')[cur].sum()
    net = insv.sub(outv, fill_value=0)
    close = opens.add(net, fill_value=0)
    dfb = pd.DataFrame({'Opening':opens,'Net Change':net,'Closing':close}).reindex(weeks)
    st.subheader(f'{cur} Over Time')
    st.line_chart(dfb)

# 6. Alerts & Thresholds
st.header('🚨 Alerts & Thresholds')
thresholds = {}
for c in selected_currencies:
    thresholds[c] = st.number_input(f'Threshold Net Change {c}', value=0.0, step=1.0, key=f'th_{c}')
ins_w = fund_data[(fund_data['Week']==selected_week)&(fund_data['Section']=='Cash Ins')].groupby('Week')[selected_currencies].sum().reindex([selected_week],fill_value=0)
out_w = fund_data[(fund_data['Week']==selected_week)&(fund_data['Section']=='Cash Outs')].groupby('Week')[selected_currencies].sum().reindex([selected_week],fill_value=0)
net_w = ins_w.sub(out_w, fill_value=0)
for c in selected_currencies:
    v = float(net_w[c])
    t = thresholds[c]
    if v < t:
        st.error(f'Net change {c}: {v:.2f} < threshold {t}')
    else:
        st.success(f'Net change {c}: {v:.2f} >= threshold {t}')

# 7. Date Range & Rolling
st.header('📅 Date-Range & Rolling Periods')
mode = st.radio('Mode',['Custom Range','Rolling Window'])
dates = [parse_week(w).date() for w in weeks]
mn, mx = min(dates), max(dates)
if mode=='Custom Range':
    dr = st.date_input('Select Date Range',[mn,mx], min_value=mn, max_value=mx)
    if len(dr)==2:
        selw = [w for w in weeks if dr[0] <= parse_week(w).date() <= dr[1]]
        df2 = fund_data[fund_data['Week'].isin(selw)]
        s2 = df2.groupby('Section')[selected_currencies].sum().reset_index()
        s2.columns=['Category']+[f'Total {c}' for c in selected_currencies]
        st.write(s2)
elif mode=='Rolling Window':
    rw = st.selectbox('Window',['Last N Weeks','MTD','QTD'])
    if rw=='Last N Weeks':
        n=st.number_input('N weeks',min_value=1,max_value=len(weeks),value=4)
        selw=weeks[-n:]
    elif rw=='MTD':
        td=dt.date.today(); sm = td.replace(day=1)
        selw=[w for w in weeks if sm<=parse_week(w).date()<=td]
    else:
        td=dt.date.today(); q=(td.month-1)//3; sq=dt.date(td.year,q*3+1,1)
        selw=[w for w in weeks if sq<=parse_week(w).date()<=td]
    df2=fund_data[fund_data['Week'].isin(selw)]
    s2=df2.groupby('Section')[selected_currencies].sum().reset_index()
    s2.columns=['Category']+[f'Total {c}' for c in selected_currencies]
    st.write(s2)

# 8. Forecasting & Trends
st.header('🔮 Forecasting & Trends')
st.subheader('Moving Averages')
if comp_weeks:
    dfc = fund_data[fund_data['Week'].isin(comp_weeks)].groupby('Week')[selected_currencies].sum()
    for c in selected_currencies:
        s = dfc[c]; ma = s.rolling(3, min_periods=1).mean();
        st.line_chart(pd.DataFrame({'Actual':s,'MA':ma}))
st.subheader('ARIMA Forecast')
for c in selected_currencies:
    opens = fund_data[fund_data['Section']=='Bank & Cash Balances'].groupby('Week')[c].sum()
    insv = fund_data[fund_data['Section']=='Cash Ins'].groupby('Week')[c].sum()
    outv = fund_data[fund_data['Section']=='Cash Outs'].groupby('Week')[c].sum()
    net = insv.sub(outv, fill_value=0); close = opens.add(net, fill_value=0)
    try:
        mod = sm.tsa.ARIMA(close, order=(1,1,0)).fit(); f = mod.forecast(steps=1)
        st.write(f'Next {c} closing: {f.iloc[0]:.2f} {c}')
    except:
        st.warning(f'ARIMA failed for {c}')

# 9. Export & Sharing
st.header('📤 Export & Sharing')
def summary_to_pdf(df):
    pdf = FPDF(); pdf.add_page(); pdf.set_font('Arial','',12)
    for r in df.values:
        pdf.cell(0,10,' | '.join(map(str,r)),ln=1)
    return pdf.output(dest='S').encode('latin1')
if st.button('Export Summary as PDF'):
    pdf_data = summary_to_pdf(sum_df)
    st.download_button('Download PDF', pdf_data, file_name='summary.pdf', mime='application/pdf')
if st.button('Export Summary as PPT'):
    prs = Presentation(); sl = prs.slides.add_slide(prs.slide_layouts[5])
    tb = sl.shapes.add_textbox(Inches(1),Inches(1),Inches(8),Inches(5)).text_frame
    for r in sum_df.values:
        tb.add_paragraph(' | '.join(map(str,r)))
    import io; buf = io.BytesIO(); prs.save(buf); buf.seek(0)
    st.download_button('Download PPT', buf.read(), file_name='summary.pptx', mime='application/vnd.openxmlformats-officedocument.presentationml.presentation')

# 10. Full Dataset
st.header('📁 Full Dataset')
st.dataframe(fund_data)

st.write('---')
st.caption('Created with ❤️ using Streamlit & GitHub')
