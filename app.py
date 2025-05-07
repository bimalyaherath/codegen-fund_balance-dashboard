import streamlit as st
import pandas as pd
import datetime as dt
import glob
import os
import requests
import json
tempfile_dir = __import__('tempfile').gettempdir()

# --- Data Upload & Versioning Setup ---
import tempfile
UPLOAD_DIR = os.path.join(tempfile_dir, 'weekly_uploads')
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

uploaded_files = st.sidebar.file_uploader(
    "Upload Weekly Excel Files (versioned)",
    type=['xlsx'], accept_multiple_files=True
)
if uploaded_files:
    ts = dt.datetime.now().isoformat()
    saved = []
    for f in uploaded_files:
        fn = f"{ts}_{f.name}"
        with open(os.path.join(UPLOAD_DIR, fn), 'wb') as out:
            out.write(f.getbuffer())
        saved.append(fn)
    history.append({'timestamp': ts, 'files': saved})
    json.dump(history, open(HISTORY_FILE, 'w'))
    st.sidebar.success(f"Uploaded {len(saved)} files at {ts}")

version_labels = ['Latest'] + [h['timestamp'] for h in history]
version_choice = st.sidebar.selectbox('Select Data Version', version_labels)
if version_choice == 'Latest':
    version_files = os.listdir(UPLOAD_DIR)
else:
    version_files = next(h['files'] for h in history if h['timestamp']==version_choice)

@st.cache_data
def load_fund_data(files):
    static = glob.glob('data/Fund_Balance_*.xlsx') + glob.glob('/mnt/data/Fund_Balance_*.xlsx') + glob.glob('Fund_Balance_*.xlsx')
    uploads = [os.path.join(UPLOAD_DIR, f) for f in files]
    all = static + uploads
    weeks = []
    for file in all:
        label = os.path.basename(file).replace('Fund_Balance_','').replace('.xlsx','')
        try: df = pd.read_excel(file)
        except: continue
        mask = df['Details'].str.contains('Bank & Cash Balances|Cash Transactions During the Week|Cash Ins|Cash Outs', na=False)
        idx = df[mask].index.tolist()
        parts = []
        for i,start in enumerate(idx):
            end = idx[i+1] if i+1<len(idx) else len(df)
            sec = df.loc[start,'Details']
            part = df.iloc[start+1:end].dropna(how='all').copy()
            part['Section'] = sec
            parts.append(part)
        wdf = pd.concat(parts,ignore_index=True)
        wdf['Week']=label
        weeks.append(wdf)
    return pd.concat(weeks,ignore_index=True) if weeks else pd.DataFrame()

fund_data = load_fund_data(version_files)
if fund_data.empty:
    st.error("No fund data for selected version.")
    st.stop()

# Helper to sort weeks chronologically
def parse_week(w):
    try: return dt.datetime.strptime(w.split('_to_')[0], '%B_%d').replace(year=dt.date.today().year)
    except: return dt.datetime.min
weeks = sorted(fund_data['Week'].unique(), key=parse_week)

# Sidebar filters
st.sidebar.title('Dashboard Settings')
selected_week = st.sidebar.selectbox('Select Week', weeks)
currencies = ['LKR','USD','GBP','AUD','DKK','EUR','MXN','INR','AED']
sel_cur = st.sidebar.multiselect('Select Currencies', currencies, default=[currencies[0]])
if not sel_cur: st.stop()

# Currency converter
@st.cache_data(ttl=3600)
def get_rate(b,s): return requests.get('https://api.exchangerate.host/latest',params={'base':b,'symbols':s},timeout=5).json().get('rates',{}).get(s)
st.sidebar.header('Currency Converter')
amt = st.sidebar.number_input('Amount',value=1.0)
frm = st.sidebar.selectbox('From',currencies)
to = st.sidebar.selectbox('To',currencies,1)
r = get_rate(frm,to)
if r: st.sidebar.write(f"1 {frm} = {r:.4f} {to} | {amt* r:.2f} {to}")
else: st.sidebar.error('Rate fetch failed')

# Main header
st.title('📊 Weekly Fund Dashboard')
wd = fund_data[fund_data['Week']==selected_week]

# Weekly Summary
st.header('🔖 Weekly Summary')
sum_df = wd.groupby('Section')[sel_cur].sum().reset_index()
sum_df.columns = ['Category']+[f'Total {c}' for c in sel_cur]
st.table(sum_df)

# Cash breakdown
st.header('📂 Cash Ins & Outs Breakdown')
with st.expander('Cash Ins'): st.table(wd[wd['Section']=='Cash Ins'][['Details']+sel_cur].rename(columns={'Details':'Category'}))
with st.expander('Cash Outs'): st.table(wd[wd['Section']=='Cash Outs'][['Details']+sel_cur].rename(columns={'Details':'Category'}))

# Weekly comparison
st.header('📈 Weekly Comparison')\cw = st.multiselect('Weeks to Compare',weeks,default=weeks[-2:])
if cw: st.line_chart(fund_data[fund_data['Week'].isin(cw)].groupby('Week')[sel_cur].sum())

# Additional Charts
st.header('📊 Additional Charts')
st.subheader('Cash Ins vs Outs')
st.bar_chart(wd.groupby('Section')[sel_cur].sum().loc[['Cash Ins','Cash Outs']])

# Net Cash balances
st.header('💰 Net Cash-Flow & Balances')
for c in sel_cur:
    o=fund_data[fund_data['Section']=='Bank & Cash Balances'].groupby('Week')[c].sum()
    i=fund_data[fund_data['Section']=='Cash Ins'].groupby('Week')[c].sum()
    o2=i - fund_data[fund_data['Section']=='Cash Outs'].groupby('Week')[c].sum()
    close = o.add(o2,fill_value=0)
    dfb=pd.DataFrame({'Opening':o,'Net':o2,'Closing':close}).reindex(weeks)
    st.subheader(c); st.line_chart(dfb)

# Alerts
st.header('🚨 Alerts & Thresholds')
alg = {} 
for c in sel_cur:
    alg[c]=st.number_input(f'Threshold Net {c}',value=0.0,key=c)
nw=(fund_data[(fund_data['Section']=='Cash Ins')&(fund_data['Week']==selected_week)].groupby('Week')[sel_cur].sum() - fund_data[(fund_data['Section']=='Cash Outs')&(fund_data['Week']==selected_week)].groupby('Week')[sel_cur].sum()).reindex([selected_week],fill_value=0)
for c in sel_cur:
    v=float(nw[c]); t=alg[c]
    st.error(f'Net {c} {v:.2f} below {t}') if v< t else st.success(f'Net {c} {v:.2f} OK')

# Date & Rolling
st.header('📅 Date-Range & Rolling')
mode=st.radio('Mode',['Custom Range','Rolling'])
mdates=[parse_week(w).date() for w in weeks]
mn,mx=min(mdates),max(mdates)
if mode=='Custom Range':
    dr=st.date_input('Range',[mn,mx],min_value=mn,max_value=mx)
    if len(dr)==2:
        selw=[w for w in weeks if dr[0]<=parse_week(w).date()<=dr[1]]
        df2=fund_data[fund_data['Week'].isin(selw)]
        s2=df2.groupby('Section')[sel_cur].sum().reset_index(); s2.columns=['Category']+[f'Total {c}' for c in sel_cur]
        st.write(s2)
else:
    rw=st.selectbox('Window',['Last N Weeks','MTD','QTD'])
    if rw=='Last N Weeks':n=st.number_input('N',1,len(weeks),4); selw=weeks[-n:]
    elif rw=='MTD':td=dt.date.today();start=td.replace(day=1);selw=[w for w in weeks if start<=parse_week(w).date()<=td]
    else:td=dt.date.today();q=(td.month-1)//3;start=dt.date(td.year,q*3+1,1);selw=[w for w in weeks if start<=parse_week(w).date()<=td]
    df2=fund_data[fund_data['Week'].isin(selw)]; s2=df2.groupby('Section')[sel_cur].sum().reset_index();s2.columns=['Category']+[f'Total {c}' for c in sel_cur]; st.write(s2)

# Forecasting & Trends
import statsmodels.api as sm
st.header('🔮 Forecasting & Trends')
# Moving avg
st.subheader('Moving Averages')
if cw:
    dfc=fund_data[fund_data['Week'].isin(cw)].groupby('Week')[sel_cur].sum()
    for c in sel_cur:
        s = dfc[c]; ma=s.rolling(3,min_periods=1).mean(); st.line_chart(pd.DataFrame({'Actual':s,'MA':ma}))
# ARIMA
st.subheader('ARIMA Forecast')
for c in sel_cur:
    o=fund_data[fund_data['Section']=='Bank & Cash Balances'].groupby('Week')[c].sum()
    i=fund_data[fund_data['Section']=='Cash Ins'].groupby('Week')[c].sum()
    o2=i - fund_data[fund_data['Section']=='Cash Outs'].groupby('Week')[c].sum()
    close=o.add(o2,fill_value=0)
    try:
        mod=sm.tsa.ARIMA(close,order=(1,1,0)).fit(); f=mod.forecast(1)
        st.write(f'Next {c} closing: {f.iloc[0]:.2f}')
    except:
        st.warning(f'ARIMA failed for {c}')

# Export & Sharing
st.header('📤 Export & Sharing')
# PDF export of summary table
def to_pdf(df):
    from fpdf import FPDF
    pdf=FPDF(); pdf.add_page(); pdf.set_font('Arial','',12)
    for i,row in df.iterrows():
        line=' | '.join(str(v) for v in row.values)
        pdf.cell(0,10,line,ln=1)
    return pdf.output(dest='S').encode('latin1')
if st.button('Export Summary as PDF'):
    pdf_data = to_pdf(sum_df)
    st.download_button('Download PDF',pdf_data,file_name='summary.pdf',mime='application/pdf')
# PPT export
from pptx import Presentation
from pptx.util import Inches
if st.button('Export Summary as PPT'):
    prs=Presentation(); slide=prs.slides.add_slide(prs.slide_layouts[5])
    left, top, width, height = Inches(1), Inches(1), Inches(8), Inches(5)
    tb=slide.shapes.add_textbox(left,top,width,height).text_frame
    for i,row in sum_df.iterrows(): tb.add_paragraph(' | '.join(str(v) for v in row.values))
    buf=io.BytesIO(); prs.save(buf); buf.seek(0)
    st.download_button('Download PPT',buf.read(),file_name='summary.pptx',mime='application/vnd.openxmlformats-officedocument.presentationml.presentation')

# Full Dataset
st.header('📁 Full Dataset')
st.dataframe(fund_data)

st.write('---')
st.caption('Created with ❤️ using Streamlit & GitHub')
