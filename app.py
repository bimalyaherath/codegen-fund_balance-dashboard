import streamlit as st
import pandas as pd
import datetime

# Load the Excel file
FILE_PATH = '/mnt/data/Fund Balance Database Format - New.xlsx'
excel_file = pd.ExcelFile(FILE_PATH)
sheet_names = excel_file.sheet_names

# Extract available date ranges
week_ranges = [sheet.replace(' to ', ' - ') for sheet in sheet_names]

# Sidebar Configuration
st.sidebar.title("Fund Dashboard Settings")

# Select Week Range
selected_week = st.sidebar.selectbox("Select Week Range", week_ranges)

# Load the selected week's data
selected_sheet = selected_week.replace(' - ', ' to ')
df = pd.read_excel(FILE_PATH, sheet_name=selected_sheet)

# Currency Filter
currencies = ["LKR", "USD", "GBP", "AUD", "DKK", "EUR", "MXN", "INR", "AED"]
selected_currency = st.sidebar.selectbox("Select Currency", currencies)

# Currency Converter
conversion_rate = st.sidebar.number_input(f"Enter current exchange rate for {selected_currency} to LKR:", min_value=0.0, value=1.0)

# Check for the correct amount column based on selected currency
if selected_currency == 'LKR':
    df["Converted Amount"] = df["Total in LKR"]
else:
    if selected_currency in df.columns:
        df["Converted Amount"] = df[selected_currency] * conversion_rate
    else:
        st.sidebar.error(f"No data available for {selected_currency} in this sheet.")

st.sidebar.write("Note: Past fund values were calculated based on historical exchange rates.")

# Main Dashboard
st.title("Weekly Fund Dashboard")
st.subheader(f"Data for {selected_week}")

# Weekly Summary Download
st.download_button("Download Weekly Summary", df.to_csv(index=False).encode('utf-8'), file_name=f"{selected_week}_summary.csv", mime='text/csv')

# Full Dataset
st.subheader("Full Dataset for Selected Week")
st.dataframe(df)
st.download_button("Download Full Dataset", df.to_csv(index=False).encode('utf-8'), file_name=f"{selected_week}_full_dataset.csv", mime='text/csv')

st.success("Dashboard loaded successfully.")
