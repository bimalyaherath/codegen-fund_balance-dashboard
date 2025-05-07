import streamlit as st
import pandas as pd
import datetime as dt
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import requests
from io import BytesIO

# Set the title for the Streamlit app
st.title('Weekly Fund Dashboard')

# GitHub file URL (replace with your actual GitHub raw file URL)
github_url = 'https://raw.githubusercontent.com/YourGitHubUsername/YourRepoName/main/Fund%20Balance%20Database%20Format%20-%20New.xlsx'

# Attempt to load the Excel file from GitHub
try:
    response = requests.get(github_url)
    response.raise_for_status()
    excel_file = pd.ExcelFile(BytesIO(response.content))
    weeks = excel_file.sheet_names

    # Sidebar for selecting the week and filtering currencies
    st.sidebar.header('Filter Options')

    # Week selection
    selected_week = st.sidebar.selectbox(
        'Select Week', weeks, index=len(weeks)-1
    )

    # Extracting date range from the selected sheet name
    start_date_str, end_date_str = selected_week.split(' to ')
    start_date = dt.datetime.strptime(start_date_str + ' 2025', '%B %d %Y')
    end_date = dt.datetime.strptime(end_date_str + ' 2025', '%B %d %Y')
    current_date = dt.datetime.now()

    # Check if selected week is in the future
    if start_date > current_date:
        st.sidebar.error('The selected date range is in the future. Please select a valid week.')

    # Currency filter
    currencies = ['LKR', 'USD', 'GBP', 'AUD', 'DKK', 'EUR', 'MXN', 'INR', 'AED']
    selected_currencies = st.sidebar.multiselect('Select Currencies', currencies, default=currencies)

    # Load the selected week's data
    df = pd.read_excel(BytesIO(response.content), sheet_name=selected_week)

    # Extracting relevant sections
    opening_balances = df[df['Details'].str.contains('Bank & Cash Balances', case=False, na=False)]
    cash_ins = df[df['Details'].str.contains('Cash Ins', case=False, na=False)]
    cash_outs = df[df['Details'].str.contains('Cash Outs', case=False, na=False)]

    # Weekly Summary
    st.subheader(f'Weekly Summary: {selected_week}')

    # Opening Balances (Dropdown)
    with st.expander('Opening Balances'):
        st.dataframe(opening_balances)

    # Cash Ins (Dropdown)
    with st.expander('Cash Ins'):
        st.dataframe(cash_ins)
        cash_in_total = cash_ins[selected_currencies].sum()
        st.write('Total Cash Ins:', cash_in_total)

    # Cash Outs (Dropdown)
    with st.expander('Cash Outs'):
        st.dataframe(cash_outs)
        cash_out_total = cash_outs[selected_currencies].sum()
        st.write('Total Cash Outs:', cash_out_total)

    # Full Dataset
    with st.expander('Full Dataset'):
        st.dataframe(df)

    # Download full dataset
    csv_file = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label='Download Full Dataset',
        data=csv_file,
        file_name=f'{selected_week}_full_data.csv',
        mime='text/csv'
    )

    # Charts and Graphs
    with st.expander('Charts and Graphs'):
        fig, ax = plt.subplots(figsize=(14, 8))
        cash_ins_plot = cash_ins[selected_currencies].sum()
        sns.barplot(x=cash_ins_plot.index, y=cash_ins_plot.values, ax=ax)
        ax.set_title('Cash Ins Overview')
        ax.set_xlabel('Currency')
        ax.set_ylabel('Total Value')
        st.pyplot(fig)

        fig, ax = plt.subplots(figsize=(14, 8))
        cash_outs_plot = cash_outs[selected_currencies].sum()
        sns.barplot(x=cash_outs_plot.index, y=cash_outs_plot.values, ax=ax)
        ax.set_title('Cash Outs Overview')
        ax.set_xlabel('Currency')
        ax.set_ylabel('Total Value')
        st.pyplot(fig)

    # Weekly Total Comparison
    with st.expander('Weekly Total Comparison'):
        weekly_totals = pd.DataFrame({
            'Cash Ins': cash_ins[selected_currencies].sum(),
            'Cash Outs': cash_outs[selected_currencies].sum()
        })
        weekly_totals.plot(kind='bar', figsize=(14, 8))
        plt.title('Weekly Cash In vs Cash Out Comparison')
        plt.xlabel('Currency')
        plt.ylabel('Total Value')
        st.pyplot(plt)

except requests.exceptions.RequestException as e:
    st.error(f'Error loading the Excel file from GitHub: {e}')
except Exception as e:
    st.error(f'An unexpected error occurred: {e}')
