import streamlit as st
import pandas as pd
import numpy as np
import datetime as dt

# Load the consolidated data
fund_data = pd.read_csv('/mnt/data/combined_fund_data.csv')

# Sidebar - Week Selection
st.sidebar.title('Fund Dashboard - Weekly Overview')
all_weeks = fund_data['Week'].unique()
selected_week = st.sidebar.selectbox('Select Week', all_weeks)

# Sidebar - Date Range Validation (Future Date Error)
week_dates = {
    'Week 1': ('2025-03-31', '2025-04-04'),
    'Week 2': ('2025-04-04', '2025-04-11'),
    'Week 3': ('2025-04-11', '2025-04-18'),
    'Week 4': ('2025-04-18', '2025-04-25')
}
start_date, end_date = week_dates[selected_week]
current_date = dt.datetime.now().strftime('%Y-%m-%d')

if end_date > current_date:
    st.sidebar.error('Selected week contains future dates. Please select a past week.')

# Sidebar - Currency Filter
currencies = ['LKR', 'USD', 'GBP', 'AUD', 'DKK', 'EUR', 'MXN', 'INR', 'AED']
selected_currency = st.sidebar.selectbox('Select Currency', currencies)

# Main Dashboard Title and Subtitle
st.title('Weekly Fund Dashboard')
st.subheader(f'Data for {selected_week} ({start_date} to {end_date})')

# Weekly Summary Dropdown
st.header('Weekly Summary')
summary_df = fund_data[fund_data['Week'] == selected_week]
summary_download = st.selectbox('Download Weekly Summary', ['Opening Balances', 'Cash Ins', 'Cash Outs'])

# Download Button
st.download_button(
    label=f"Download {summary_download} for {selected_week}",
    data=summary_df.to_csv(index=False),
    file_name=f"{selected_week}_{summary_download}.csv",
    mime='text/csv'
)

# Data Preview
st.dataframe(summary_df)

# Placeholder for charts and graphs
st.header('Charts and Graphs')
st.text('Charts will be added here...')

# Full Dataset View and Download
st.header('Full Dataset')
st.dataframe(fund_data)
st.download_button(
    label='Download Full Dataset',
    data=fund_data.to_csv(index=False),
    file_name='Full_Fund_Data.csv',
    mime='text/csv'
)
