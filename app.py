import streamlit as st
import pandas as pd
import datetime as dt

# Set the title for the Streamlit app
st.title('Weekly Fund Dashboard')

# File Upload
uploaded_file = st.file_uploader("Upload the Fund Balance Database Excel File", type=["xlsx"])

if uploaded_file:
    # Load the Excel file and list available sheets (weeks)
    excel_file = pd.ExcelFile(uploaded_file)
    weeks = excel_file.sheet_names

    # Sidebar for selecting the week and filtering currencies
    st.sidebar.header('Filter Options')

    # Week selection
    selected_week = st.sidebar.selectbox(
        'Select Week', weeks, index=len(weeks) - 1
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
    df = pd.read_excel(uploaded_file, sheet_name=selected_week)

    # Display the data
    st.subheader(f'Weekly Summary: {selected_week}')
    st.dataframe(df)

    # Download full dataset
    csv_file = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label='Download Full Dataset',
        data=csv_file,
        file_name=f'{selected_week}_full_data.csv',
        mime='text/csv'
    )
