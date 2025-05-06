import streamlit as st
import pandas as pd

# Load data
@st.cache_data
def load_data():
    df = pd.read_excel("Dummy_Bank_Cash_Balance_Data.xlsx", sheet_name="Dummy_Bank_Cash_Balance_Data")
    df.rename(columns={df.columns[0]: "Category"}, inplace=True)
    df.dropna(how='all', inplace=True)
    df["Category"] = df["Category"].fillna(method='ffill')
    return df

df = load_data()

# --- UI Elements ---
st.title("💰 Weekly Fund Dashboard")

# Week Selector
weeks = df[df["Category"].str.contains("Bank & Cash Balances")]["Category"].unique()
selected_week = st.selectbox("Select Week", weeks)

# Filter data for selected week
week_index = df[df["Category"] == selected_week].index[0]
next_week_index = df[df.index > week_index][df["Category"].str.contains("Bank & Cash Balances")].index.min()
week_data = df.loc[week_index:next_week_index - 1] if not pd.isna(next_week_index) else df.loc[week_index:]

# Currency filter
currency_columns = ['LKR', 'USD', 'GBP', 'AUD', 'DKK', 'EUR', 'MXN', 'INR', 'AED', 'Total in LKR', 'Total in USD']
selected_currencies = st.multiselect("Select Currencies", currency_columns, default=['LKR', 'USD'])

# Show Balances
st.subheader("📌 Opening Balances")
for cat in ["Bank", "Cash in Hand"]:
    row = week_data[week_data["Category"] == cat]
    if not row.empty:
        st.write(f"**{cat}**")
        st.dataframe(row[selected_currencies].T.rename(columns={row.index[0]: 'Amount'}))

# Show Transactions
st.subheader("📥 Cash In")
cash_in = week_data[week_data["Category"] == "Cash Ins"]
if not cash_in.empty:
    st.dataframe(cash_in[selected_currencies].T.rename(columns={cash_in.index[0]: 'Amount'}))

st.subheader("📤 Cash Out")
cash_out = week_data[week_data["Category"] == "Cash Outs"]
if not cash_out.empty:
    st.dataframe(cash_out[selected_currencies].T.rename(columns={cash_out.index[0]: 'Amount'}))

# Placeholder: Graphs Section
st.subheader("📈 Charts (Coming Soon)")
st.info("Charts and deeper analysis will be added once transaction categories are mapped.")

