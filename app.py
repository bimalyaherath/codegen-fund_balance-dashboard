import streamlit as st
import pandas as pd
import numpy as np
import datetime
import os

# Load the Excel file
FILE_PATH = '/mnt/data/Fund Balance Database Format - New.xlsx'
excel_file = pd.ExcelFile(FILE_PATH)

# Extract sheet names for weekly ranges
sheet_names = excel_file.sheet_names

# Extract available date ranges
week_ranges = [sheet.replace(' to ', ' - ') for sheet in sheet_names]

# Sidebar Configuration
st.sidebar.title("Fund Dashboard Settings")

# Select Week Range
selected_week = st.sidebar.selectbox("Select Week Range", week_ranges)

# Extract start and end dates from the selected week
start_date_str, end_date_str = selected_week.split(' - ')
start_date = datetime.datetime.strptime(start_date_str.strip(), '%B %d').replace(year=datetime.datetime.now().year)
end_date = datetime.datetime.strptime(end_date_str.strip(), '%B %d').replace(year=datetime.datetime.now().year)

# Ensure the selected date range is not in the future
if end_date > datetime.datetime.now():
    st.sidebar.error("Selected date range is in the future. Please select a valid past date range.")
else:
    # Load the selected week's data
    df = pd.read_excel(FILE_PATH, sheet_name=selected_week.replace(' - ', ' to '))
    
    # Currency Filter
    currencies = ["LKR", "USD", "GBP", "AUD", "DKK", "EUR", "MXN", "INR", "AED"]
    selected_currency = st.sidebar.selectbox("Select Currency", currencies)
    
    # Currency Converter
    st.sidebar.subheader("Currency Converter")
    conversion_rate = st.sidebar.number_input(f"Enter current exchange rate for {selected_currency} to LKR:", min_value=0.0, value=1.0)
    df["Converted Amount"] = df["Amount"] * conversion_rate
    st.sidebar.write(f"Note: Past fund values were calculated based on historical exchange rates.")
    
    # Main Dashboard
    st.title("Weekly Fund Dashboard")
    st.subheader(f"Data for {selected_week}")
    
    # Downloadable Weekly Summary
    st.download_button("Download Selected Weekly Summary", df.to_csv(index=False).encode('utf-8'), file_name=f"{selected_week}_summary.csv", mime='text/csv')
    
    # Opening Balances
    st.subheader("Opening Balances")
    st.write(df[df["Category"] == "Opening Balance"])
    
    # Cash Ins
    st.subheader("Cash Ins During the Week")
    st.write(df[df["Type"] == "Cash In"])
    
    # Cash Outs
    st.subheader("Cash Outs During the Week")
    st.write(df[df["Type"] == "Cash Out"])
    
    # Charts and Graphs
    st.subheader("Charts and Graphs")
    st.line_chart(df.groupby("Date")["Converted Amount"].sum())
    
    # Full Dataset
    st.subheader("Full Dataset for Selected Week")
    st.dataframe(df)
    st.download_button("Download Full Dataset", df.to_csv(index=False).encode('utf-8'), file_name=f"{selected_week}_full_dataset.csv", mime='text/csv')

    st.success("Dashboard loaded successfully.")
