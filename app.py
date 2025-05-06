import streamlit as st
import pandas as pd
import plotly.express as px

# Load data
@st.cache_data
def load_data():
    df = pd.read_excel("Dummy_Bank_Cash_Balance_Data.xlsx", sheet_name="Dummy_Bank_Cash_Balance_Data")
    df.rename(columns={df.columns[0]: "Category"}, inplace=True)
    df.dropna(how='all', inplace=True)
    df["Category"] = df["Category"].fillna(method='ffill')
    return df

df = load_data()

# --- UI Header ---
st.title("💰 Weekly Fund Dashboard")

# --- Define filters ---
weeks = df[df["Category"].str.contains("Bank & Cash Balances")]["Category"].unique()
selected_week = st.selectbox("📅 Select Week", weeks)

currency_columns = ['LKR', 'USD', 'GBP', 'AUD', 'DKK', 'EUR', 'MXN', 'INR', 'AED', 'Total in LKR', 'Total in USD']
selected_currencies = st.multiselect("💱 Select Currencies", currency_columns, default=["LKR", "USD"])

# --- Filter Data by Week ---
week_index = df[df["Category"] == selected_week].index[0]
next_week_index = df[df.index > week_index][df["Category"].str.contains("Bank & Cash Balances")].index.min()
week_data = df.loc[week_index:next_week_index - 1] if not pd.isna(next_week_index) else df.loc[week_index:]

# --- Opening Balances ---
st.subheader("🏦 Opening Balances")
for cat in ["Bank", "Cash in Hand"]:
    row = week_data[week_data["Category"] == cat]
    if not row.empty:
        st.write(f"**{cat}**")
        st.dataframe(row[selected_currencies].T.rename(columns={row.index[0]: 'Amount'}))

# --- Cash In / Out Summary ---
st.subheader("📥 Cash In")
cash_in = week_data[week_data["Category"] == "Cash Ins"]
if not cash_in.empty:
    st.dataframe(cash_in[selected_currencies].T.rename(columns={cash_in.index[0]: 'Amount'}))

st.subheader("📤 Cash Out")
cash_out = week_data[week_data["Category"] == "Cash Outs"]
if not cash_out.empty:
    st.dataframe(cash_out[selected_currencies].T.rename(columns={cash_out.index[0]: 'Amount'}))

# --- Transaction Categories ---
cash_in_categories = [
    'Customer Payments', 'Investor Funding', 'Loan Proceeds', 'Intercompany Transfers In',
    'Interest Received', 'Sale of Assets', 'Forex Gains', 'Grants/Subsidies', 'Other Income'
]

cash_out_categories = [
    'Supplier Payments', 'Salaries & Wages', 'Office Rent & Utilities', 'Loan Repayments',
    'Intercompany Transfers Out', 'Capital Expenditures', 'Taxes & Duties',
    'Marketing & Advertising', 'Miscellaneous Expenses'
]

cash_in_data = df[df["Category"].isin(cash_in_categories)].copy()
cash_out_data = df[df["Category"].isin(cash_out_categories)].copy()

# --- Charts Section ---
st.subheader("📈 Charts & Analysis")

# Cash In Pie Chart (LKR)
if not cash_in_data.empty and "LKR" in cash_in_data.columns:
    cash_in_data_lkr = cash_in_data[["Category", "LKR"]].dropna()
    fig_in = px.pie(cash_in_data_lkr, names="Category", values="LKR", title="Cash In Breakdown (LKR)")
    st.plotly_chart(fig_in)

# Cash Out Pie Chart (LKR)
if not cash_out_data.empty and "LKR" in cash_out_data.columns:
    cash_out_data_lkr = cash_out_data[["Category", "LKR"]].dropna()
    fig_out = px.pie(cash_out_data_lkr, names="Category", values="LKR", title="Cash Out Breakdown (LKR)")
    st.plotly_chart(fig_out)

# Footer Note
if cash_in_data["LKR"].isna().all() and cash_out_data["LKR"].isna().all():
    st.info("ℹ️ Charts not shown because Cash In/Out category values are missing or not in LKR.")
