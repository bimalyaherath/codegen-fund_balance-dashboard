import streamlit as st
import pandas as pd
import datetime as dt
import glob
import os

# 1. Load and clean all weekly Excel files from the "data" folder
@st.cache_data
def load_fund_data():
    files = glob.glob('data/Fund_Balance_*.xlsx')
    all_weeks = []
    for file in files:
        # Derive week label from filename, e.g. "March_31_to_April_4"
        base = os.path.basename(file).replace('Fund_Balance_','').replace('.xlsx','')
        week_label = base
        df = pd.read_excel(file)
        # Identify section header rows
        mask = df['Details'].str.contains('Bank & Cash Balances|Cash Transactions During the Week|Cash Ins|Cash Outs', na=False)
        idx = df[mask].index.tolist()
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
    combined = pd.concat(all_weeks, ignore_index=True)
    return combined

fund_data = load_fund_data()

# 2. Sidebar: Settings and Filters
st.sidebar.title('Weekly Fund Dashboard Settings')

# A. Week selector
weeks = sorted(fund_data['Week'].unique())
selected_week = st.sidebar.selectbox('1. Select Week', weeks)
# Parse start and end dates for validation and display
start_str, end_str = selected_week.split('_to_')
start_dt = dt.datetime.strptime(start_str, '%B_%d').replace(year=2025)
end_dt = dt.datetime.strptime(end_str, '%B_%d').replace(year=2025)
today = dt.date.today()
if end_dt.date() > today:
    st.sidebar.error('⚠️ Selected week contains future dates! Please choose a past week.')

# B. Currency filter
currencies = ['LKR','USD','GBP','AUD','DKK','EUR','MXN','INR','AED']
selected_currency = st.sidebar.selectbox('2. Select Currency', currencies)

# C. Currency converter
st.sidebar.header('Currency Converter')
amount = st.sidebar.number_input('Amount to convert', min_value=0.0, value=1.0, step=0.1)
from_cur = st.sidebar.selectbox('From', currencies, index=0, key='from')
to_cur = st.sidebar.selectbox('To', currencies, index=1, key='to')
rate = st.sidebar.number_input(f'Exchange rate ({from_cur}→{to_cur})', min_value=0.0001, value=1.0, step=0.0001)
converted = amount * rate
st.sidebar.write(f'{amount} {from_cur} = {converted:.2f} {to_cur}')
st.sidebar.info('Note: Historical fund values used the exchange rates of that period.')

# 3. Main Dashboard Header
st.title('📊 Weekly Fund Dashboard')
st.subheader(f'Data for {selected_week.replace("_", " ")} ({start_dt.date()} to {end_dt.date()})')

# Filter fund_data for selected week
week_df = fund_data[fund_data['Week'] == selected_week]

# 4. Downloadable Weekly Summaries
st.header('🔖 Weekly Summaries')
summary_option = st.selectbox('Download Summary:', ['Opening Balances', 'Cash Ins', 'Cash Outs'])
# Match Section name
mapping = {
    'Opening Balances': 'Bank & Cash Balances',
    'Cash Ins': 'Cash Ins',
    'Cash Outs': 'Cash Outs'
}
sec_name = mapping[summary_option]\nsummary_df = week_df[week_df['Section'].str.contains(sec_name, na=False)]

with st.expander(f'{summary_option} Details'):
    st.write(summary_df[['Details', selected_currency, 'Total in LKR', 'Total in USD']])
    st.download_button(
        label=f'Download {summary_option}.csv',
        data=summary_df.to_csv(index=False),
        file_name=f"{selected_week}_{summary_option.replace(' ', '_')}.csv",
        mime='text/csv'
    )

# 5. Detailed Sections
st.header('📂 Detailed Breakdown')
for section in ['Bank & Cash Balances', 'Cash Ins', 'Cash Outs']:
    sec_df = week_df[week_df['Section'].str.contains(section, na=False)]
    with st.expander(section):
        st.table(sec_df[['Details', selected_currency, 'Total in LKR', 'Total in USD']].rename(columns={'Details':'Category', selected_currency:selected_currency}))

# 6. Charts & Graphs
st.header('📈 Charts & Graphs')
# A. Weekly Cash Ins trend
ins_trend = fund_data[fund_data['Section']=='Cash Ins'].groupby('Week')[selected_currency].sum()
st.line_chart(ins_trend.rename('Cash Ins'))
# B. Weekly Cash Outs trend
outs_trend = fund_data[fund_data['Section']=='Cash Outs'].groupby('Week')[selected_currency].sum()
st.line_chart(outs_trend.rename('Cash Outs'))
# C. Comparison Bar Chart for selected week
chart_df = week_df.groupby('Section')[selected_currency].sum().reset_index()
st.bar_chart(chart_df.set_index('Section'))

# 7. Full Dataset View & Download
st.header('📂 Full Dataset')
with st.expander('View Full Dataset'):
    st.dataframe(fund_data)
    st.download_button(
        label='Download Full Dataset',
        data=fund_data.to_csv(index=False),
        file_name='Full_Weekly_Fund_Data.csv',
        mime='text/csv'
    )

# End of Dashboard
st.write('---')
st.caption('Created with ❤️ using Streamlit and GitHub')
