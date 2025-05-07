import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import io
import requests

# Load the new data file
DATA_FILE = 'Fund Balance Database Format - New.xlsx'

@st.cache_data
def load_data(file_path):
    # Read the Excel file
    xls = pd.ExcelFile(file_path)
    # Extract all sheets (each representing a week)
    all_sheets = []
    for sheet in xls.sheet_names:
        df = pd.read_excel(file_path, sheet_name=sheet)
        # Rename the first column for consistency
        df.rename(columns={df.columns[0]: 'Category'}, inplace=True)
        all_sheets.append(df)
    return all_sheets

all_weeks_data = load_data(DATA_FILE)

# Extract available weeks
week_labels = [f"Week {i+1}" for i in range(len(all_weeks_data))]

# Sidebar for week range, week selection, and currency filter
st.sidebar.header("🗓️ Select Week Range")
selected_week_index = st.sidebar.selectbox("Choose a week:", list(range(len(week_labels))), format_func=lambda x: week_labels[x])
selected_week_data = all_weeks_data[selected_week_index]

# Currency filter
currency_columns = ['LKR', 'USD', 'GBP', 'AUD', 'DKK', 'EUR', 'MXN', 'INR', 'AED', 'Total in LKR', 'Total in USD']
selected_currencies = st.sidebar.multiselect("💱 Select Currencies", currency_columns, default=["LKR", "USD"])

# Live Currency Converter
st.sidebar.header("💸 Currency Converter")
base_currency = st.sidebar.selectbox("From Currency", currency_columns, index=0)
target_currency = st.sidebar.selectbox("To Currency", currency_columns, index=1)
amount = st.sidebar.number_input(f"Amount in {base_currency}", min_value=0.0, value=100.0, step=1.0)

try:
    api_url = f"https://api.exchangerate-api.com/v4/latest/{base_currency}"
    response = requests.get(api_url)
    data = response.json()
    rate = data["rates"].get(target_currency, 1)
    converted_value = amount * rate
    st.sidebar.success(f"{amount} {base_currency} = {converted_value:.2f} {target_currency}")
except Exception as e:
    st.sidebar.error(f"Failed to fetch exchange rate: {e}")

# Main Dashboard Title
st.title("💰 Weekly Fund Dashboard")
selected_week_name = week_labels[selected_week_index]
st.subheader(f"📅 Week: {selected_week_name}")

# Weekly Summary
with st.expander("📌 Weekly Summary"):
    opening_bank = selected_week_data[selected_week_data["Category"] == "Bank"]
    opening_cash = selected_week_data[selected_week_data["Category"] == "Cash in Hand"]
    cash_in = selected_week_data[selected_week_data["Category"] == "Cash Ins"]
    cash_out = selected_week_data[selected_week_data["Category"] == "Cash Outs"]
    closing_bank = opening_bank.copy()
    closing_cash = opening_cash.copy()
    net_change = (closing_bank[selected_currencies].values + closing_cash[selected_currencies].values) - (cash_out[selected_currencies].values)
    summary_df = pd.DataFrame({
        "Opening Bank": opening_bank[selected_currencies].iloc[0],
        "Opening Cash": opening_cash[selected_currencies].iloc[0],
        "Cash In": cash_in[selected_currencies].iloc[0],
        "Cash Out": cash_out[selected_currencies].iloc[0],
        "Closing Bank": closing_bank[selected_currencies].iloc[0],
        "Closing Cash": closing_cash[selected_currencies].iloc[0],
        "Net Change": net_change[0]
    })
    st.dataframe(summary_df)
    # Download button
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        summary_df.to_excel(writer, sheet_name="Weekly Summary")
    st.download_button(
        label="📥 Download Summary as Excel",
        data=output.getvalue(),
        file_name="Weekly_Summary.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# Opening Balances
with st.expander("🏦 Opening Balances"):
    for cat in ["Bank", "Cash in Hand"]:
        row = selected_week_data[selected_week_data["Category"] == cat]
        if not row.empty:
            st.write(f"**{cat}**")
            st.dataframe(row[selected_currencies].T.rename(columns={row.index[0]: 'Amount'}))

# Cash Ins
with st.expander("📥 Cash Ins"):
    cash_in_section = selected_week_data[selected_week_data["Category"] == "Cash Ins"]
    if not cash_in_section.empty:
        st.dataframe(cash_in_section[selected_currencies].T.rename(columns={cash_in_section.index[0]: 'Amount'}))

# Cash Outs
with st.expander("📤 Cash Outs"):
    cash_out_section = selected_week_data[selected_week_data["Category"] == "Cash Outs"]
    if not cash_out_section.empty:
        st.dataframe(cash_out_section[selected_currencies].T.rename(columns={cash_out_section.index[0]: 'Amount'}))

# Charts and Graphs
with st.expander("📊 Charts and Graphs"):
    st.write("Charts and graphs for weekly comparison and other relevant metrics will be added here.")

# Full Dataset Download
with st.expander("📂 View & Download Full Dataset"):
    st.dataframe(selected_week_data, use_container_width=True)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        selected_week_data.to_excel(writer, sheet_name=selected_week_name)
    st.download_button(
        label="📥 Download Selected Week Data as Excel",
        data=output.getvalue(),
        file_name=f"{selected_week_name}_Data.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
