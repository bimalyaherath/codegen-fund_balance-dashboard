import streamlit as st
import pandas as pd
import datetime

# Load the Excel file
FILE_PATH = '/mnt/data/Fund Balance Database Format - New.xlsx'
excel_file = pd.ExcelFile(FILE_PATH)
sheet_names = excel_file.sheet_names

# Extract available date ranges for the sidebar
week_ranges = [sheet.replace(' to ', ' - ') for sheet in sheet_names]

# Sidebar Configuration
st.sidebar.title("Fund Dashboard Settings")

# Select Week Range
selected_week = st.sidebar.selectbox("Select Week Range", week_ranges)

# Load the selected week's data
selected_sheet = selected_week.replace(' - ', ' to ')
df = pd.read_excel(FILE_PATH, sheet_name=selected_sheet)

# Remove empty rows and columns
df.dropna(how='all', inplace=True)
df.dropna(axis=1, how='all', inplace=True)

# Currency Filter
currencies = ["LKR", "USD", "GBP", "AUD", "DKK", "EUR", "MXN", "INR", "AED"]
selected_currency = st.sidebar.selectbox("Select Currency", currencies)

# Currency Converter
st.sidebar.subheader("Currency Converter")
conversion_rate = st.sidebar.number_input(f"Enter current exchange rate for {selected_currency} to LKR:", min_value=0.0, value=1.0)
st.sidebar.write("Note: Past fund values were calculated based on historical exchange rates.")

# Convert amounts based on selected currency
if selected_currency == "LKR":
    df["Converted Amount"] = df["Total in LKR"]
elif selected_currency == "USD":
    df["Converted Amount"] = df["Total in USD"] * conversion_rate
else:
    if selected_currency in df.columns:
        df["Converted Amount"] = df[selected_currency] * conversion_rate
    else:
        st.sidebar.error(f"No data available for {selected_currency} in this sheet.")

# Main Dashboard
st.title("Weekly Fund Dashboard")
st.subheader(f"Data for {selected_week}")

# Weekly Summary Download
st.subheader("Weekly Summary")
st.download_button("Download Weekly Summary", df.to_csv(index=False).encode('utf-8'), file_name=f"{selected_week}_summary.csv", mime='text/csv')

# Opening Balances
st.subheader("Opening Balances")
opening_balances = df[df["Details"].str.contains("Opening Balance", case=False, na=False)]
st.dataframe(opening_balances)

# Cash Ins
st.subheader("Cash Ins During the Week")
cash_ins = df[df["Details"].str.contains("Cash In", case=False, na=False)]
st.dataframe(cash_ins)

# Cash Outs
st.subheader("Cash Outs During the Week")
cash_outs = df[df["Details"].str.contains("Cash Out", case=False, na=False)]
st.dataframe(cash_outs)

# Full Dataset
st.subheader("Full Dataset for Selected Week")
st.dataframe(df)
st.download_button("Download Full Dataset", df.to_csv(index=False).encode('utf-8'), file_name=f"{selected_week}_full_dataset.csv", mime='text/csv')

st.success("Dashboard loaded successfully.")
