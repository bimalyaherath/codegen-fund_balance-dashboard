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
st.subheader("📥 Cash In (Weekly Total)")
cash_in = week_data[week_data["Category"] == "Cash Ins"]
if not cash_in.empty:
    st.dataframe(cash_in[selected_currencies].T.rename(columns={cash_in.index[0]: 'Amount'}))

st.subheader("📤 Cash Out (Weekly Total)")
cash_out = week_data[week_data["Category"] == "Cash Outs"]
if not cash_out.empty:
    st.dataframe(cash_out[selected_currencies].T.rename(columns={cash_out.index[0]: 'Amount'}))

# --- Expandable Category Details ---
cash_in_categories = [
    'Customer Payments', 'Investor Funding', 'Loan Proceeds', 'Intercompany Transfers In',
    'Interest Received', 'Sale of Assets', 'Forex Gains', 'Grants/Subsidies', 'Other Income'
]

cash_out_categories = [
    'Supplier Payments', 'Salaries & Wages', 'Office Rent & Utilities', 'Loan Repayments',
    'Intercompany Transfers Out', 'Capital Expenditures', 'Taxes & Duties',
    'Marketing & Advertising', 'Miscellaneous Expenses'
]

st.subheader("🔻 Detailed Transactions")

# Cash In: one dropdown, with all categories shown inside
with st.expander("💰 Cash In Categories"):
    for category in cash_in_categories:
        try:
            label = str(category).strip() if category else "Unnamed Category"
            cat_data = df[df["Category"] == category]
            if not cat_data.empty:
                st.markdown(f"**🔹 {label}**")
                st.dataframe(cat_data[selected_currencies].T.rename(columns={cat_data.index[0]: 'Amount'}))
            else:
                st.markdown(f"- *No data for {label}*")
        except Exception as e:
            st.error(f"Error displaying category '{label}': {e}")

# Cash Out: one dropdown, with all categories shown inside
with st.expander("💸 Cash Out Categories"):
    for category in cash_out_categories:
        try:
            label = str(category).strip() if category else "Unnamed Category"
            cat_data = df[df["Category"] == category]
            if not cat_data.empty:
                st.markdown(f"**🔻 {label}**")
                st.dataframe(cat_data[selected_currencies].T.rename(columns={cat_data.index[0]: 'Amount'}))
            else:
                st.markdown(f"- *No data for {label}*")
        except Exception as e:
            st.error(f"Error displaying category '{label}': {e}")

import plotly.express as px
import plotly.graph_objects as go

# --- Charts for Other Financial Values ---

st.subheader("📊 Other Relevant Financial Visuals")

# Define chart options and types
chart_options = {
    "Fixed Deposits - Open": "bar",
    "Fixed Deposits - Under Lien": "line",
    "Debentures": "treemap",
    "Bank (Closing Balance)": "funnel",
    "Cash in Hand (Closing Balance)": "pie"
}

selected_chart = st.selectbox("Select a metric to visualize:", list(chart_options.keys()))
selected_category = selected_chart
chart_type = chart_options[selected_chart]

# Get data row for selected category
category_row = df[df["Category"] == selected_category]

if not category_row.empty:
    row = category_row.iloc[0][currency_columns]
    chart_df = pd.DataFrame({
        "Currency": row.index,
        "Amount": row.values
    }).dropna()

    # Draw appropriate chart
    if chart_type == "bar":
        fig = px.bar(
            chart_df, x="Currency", y="Amount", text="Amount",
            title=f"{selected_category} by Currency", color="Currency"
        )

    elif chart_type == "line":
        fig = px.line(
            chart_df, x="Currency", y="Amount", markers=True,
            title=f"{selected_category} Trend Across Currencies"
        )

    elif chart_type == "treemap":
        fig = px.treemap(
            chart_df, path=["Currency"], values="Amount",
            title=f"{selected_category} Distribution Treemap"
        )

    elif chart_type == "funnel":
        fig = px.funnel(
            chart_df, x="Amount", y="Currency",
            title=f"{selected_category} - Liquidity Funnel"
        )

    elif chart_type == "pie":
        fig = px.pie(
            chart_df, names="Currency", values="Amount",
            title=f"{selected_category} Cash Distribution",
            hole=0.4
        )

    else:
        fig = go.Figure()

    st.plotly_chart(fig)

else:
    st.warning(f"No data available for '{selected_chart}'")
