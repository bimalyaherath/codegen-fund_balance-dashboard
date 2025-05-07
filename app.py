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
        df = pd.read_excel(file_path, sheet_name=sheet, header=1)
        # Rename the first column for consistency
        df.rename(columns={df.columns[0]: 'Category'}, inplace=True)
        # Strip any whitespace from column names
        df.columns = df.columns.str.strip()
        all_sheets.append(df)
    return all_sheets

all_weeks_data = load_data(DATA_FILE)

# Extract available weeks
week_labels = [f"Week {i+1} - {datetime.now().strftime('%d/%m/%Y')}" for i in range(len(all_weeks_data))]

# Sidebar for week range, week selection, and currency filter
st.sidebar.header("🗓️ Select Week Range")
start_date = st.sidebar.date_input("Select start date:", datetime.now().date())
end_date = st.sidebar.date_input("Select end date:", datetime.now().date())

# Filter available weeks based on the selected date range
selected_weeks = []
for label in week_labels:
    try:
        # Extract the date part after the last hyphen
        week_date_str = label.split("-")[-1].strip()
        week_date = datetime.strptime(week_date_str, "%d/%m/%Y").date()
        # Check if the date is within the selected range
        if start_date <= week_date <= end_date:
            selected_weeks.append(label)
    except ValueError:
        # Skip labels without valid date parts
        continue

selected_week_index = st.sidebar.selectbox("Choose a specific week:", list(range(len(selected_weeks))), format_func=lambda x: selected_weeks[x])
selected_week_data = all_weeks_data[selected_week_index]

# Extract currency columns
currency_columns = [col for col in selected_week_data.columns if col not in ['Category', 'Unnamed: 0']]

# Currency filter
selected_currencies = st.sidebar.multiselect("💱 Select Currencies", currency_columns, default=currency_columns[:2])

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
selected_week_name = selected_weeks[selected_week_index]
st.subheader(f"📅 Week: {selected_week_name}")

# Weekly Summary
with st.expander("📌 Weekly Summary"):
    try:
        opening_bank = selected_week_data[selected_week_data["Category"] == "Bank"]
        opening_cash = selected_week_data[selected_week_data["Category"] == "Cash in Hand"]
        cash_in = selected_week_data[selected_week_data["Category"] == "Cash Ins"]
        cash_out = selected_week_data[selected_week_data["Category"] == "Cash Outs"]
        if not opening_bank.empty and not opening_cash.empty and not cash_in.empty and not cash_out.empty:
            summary_df = pd.DataFrame({
                "Opening Bank": opening_bank[selected_currencies].iloc[0],
                "Opening Cash": opening_cash[selected_currencies].iloc[0],
                "Cash In": cash_in[selected_currencies].iloc[0],
                "Cash Out": cash_out[selected_currencies].iloc[0],
                "Closing Bank": opening_bank[selected_currencies].iloc[0],
                "Closing Cash": opening_cash[selected_currencies].iloc[0],
                "Net Change": (opening_bank[selected_currencies].values + opening_cash[selected_currencies].values - cash_out[selected_currencies].values)[0]
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
        else:
            st.warning("⚠️ Some data is missing for the selected week. Please check the data file.")
    except KeyError as e:
        st.error(f"Data not found for selected currencies: {e}")
