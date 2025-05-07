import streamlit as st
import pandas as pd
import datetime

# Load the Excel file
FILE_PATH = 'Fund Balance Database Format - New.xlsx'
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
df["Converted Amount"] = df["Amount"] * conversion_rate
st.sidebar.write("Note: Past fund values were calculated based on historical exchange rates.")

# Main Dashboard
st.title("Weekly Fund Dashboard")
st.subheader(f"Data for {selected_week}")

# Weekly Summary Download
st.download_button("Download Weekly Summary", df.to_csv(index=False).encode('utf-8'), file_name=f"{selected_week}_summary.csv", mime='text/csv')

# Opening Balances
opening_balances = df[df["Category"] == "Opening Balance"]
st.subheader("Opening Balances")
st.dataframe(opening_balances)

# Cash Ins
cash_ins = df[df["Type"] == "Cash In"]
st.subheader("Cash Ins During the Week")
st.dataframe(cash_ins)

# Cash Outs
cash_outs = df[df["Type"] == "Cash Out"]
st.subheader("Cash Outs During the Week")
st.dataframe(cash_outs)

# Full Dataset
st.subheader("Full Dataset for Selected Week")
st.dataframe(df)
st.download_button("Download Full Dataset", df.to_csv(index=False).encode('utf-8'), file_name=f"{selected_week}_full_dataset.csv", mime='text/csv')

st.success("Dashboard loaded successfully.")
