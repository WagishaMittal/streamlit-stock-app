import streamlit as st
import gspread
import pandas as pd
from gspread_dataframe import get_as_dataframe
from io import BytesIO
from google.oauth2.service_account import Credentials

def load_sheet():
    creds_dict = st.secrets["gcp_service_account"]
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials = Credentials.from_service_account_info(creds_dict, scopes=scope)
    gc = gspread.authorize(credentials)
    sh = gc.open_by_key("1PrsSMbPddsn1FnjC4Fao2XJ63f1kG4u8X9aWZwmdK1A")  # your sheet ID
    ws = sh.get_worksheet(0)
    df = get_as_dataframe(ws).dropna(how="all")
    df["Available Qty"] = pd.to_numeric(df["Available Qty"], errors="coerce").fillna(0).astype(int)
    return df

df = load_sheet()

st.title("📦 Stock Order System")

customer_name = st.sidebar.text_input("Customer Name")
customer_id = st.sidebar.text_input("Customer ID")
if not customer_name or not customer_id:
    st.warning("Enter customer name and ID")
    st.stop()

search = st.text_input("Search SKU or Name")
filtered_df = df.copy()
if search:
    filtered_df = df[df["SkuShortName"].str.contains(search, case=False) | df["SKU"].str.contains(search, case=False)]

st.write("### Enter Quantities")
with st.form("order_form"):
    updated = []
    for i, row in filtered_df.iterrows():
        cols = st.columns([3, 5, 2, 3])
        cols[0].markdown(f"**{row['SKU']}**")
        cols[1].markdown(row['SkuShortName'])
        cols[2].markdown(f"{row['Available Qty']}")
        qty = cols[3].number_input("Qty", 0, int(row["Available Qty"]), key=f"qty_{i}")
        updated.append({**row, "Order Quantity": qty})

    submit = st.form_submit_button("Generate Order")

if submit:
    order_df = pd.DataFrame(updated)
    order_summary = order_df[order_df["Order Quantity"] > 0]
    if not order_summary.empty:
        st.success("✅ Order Ready!")
        order_summary.insert(0, "Customer Name", customer_name)
        order_summary.insert(1, "Customer ID", customer_id)

        def to_excel(data):
            out = BytesIO()
            with pd.ExcelWriter(out, engine="openpyxl") as writer:
                data.to_excel(writer, index=False)
            return out.getvalue()

        st.download_button("⬇️ Download Order", to_excel(order_summary),
                           file_name=f"order_{customer_id}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.warning("⚠️ No items selected.")
