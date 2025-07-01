import streamlit as st
import gspread
import pandas as pd
from gspread_dataframe import get_as_dataframe, set_with_dataframe
from io import BytesIO
from google.oauth2.service_account import Credentials
from datetime import datetime

# Load Google Sheet
def load_sheet():
    creds_dict = st.secrets["gcp_service_account"]
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials = Credentials.from_service_account_info(creds_dict, scopes=scope)
    gc = gspread.authorize(credentials)
    sh = gc.open_by_key("1PrsSMbPddsn1FnjC4Fao2XJ63f1kG4u8X9aWZwmdK1A")
    ws = sh.get_worksheet(0)
    df = get_as_dataframe(ws).dropna(how='all')
    df["Available Qty"] = pd.to_numeric(df["Available Qty"], errors="coerce").fillna(0).astype(int)
    return df, sh

# Load data and sheet
st.set_page_config(layout="wide")
st.title("📦 Stock Order System")
df, sheet = load_sheet()

# Step 1: Customer Name Input
with st.form("name_form"):
    customer_name = st.text_input("Enter Customer Name")
    proceed = st.form_submit_button("Proceed")

if not proceed or not customer_name.strip():
    st.stop()

st.success(f"Placing order for: {customer_name}")
st.write("## 📋 Available Products")

# Step 2: Quantity Selection
selected_items = []
qty_inputs = {}
with st.form("order_form"):
    for i, row in df.iterrows():
        cols = st.columns([6, 3, 3])
        cols[0].markdown(f"**{row['SkuShortName']}**")
        cols[1].markdown(f"Available: {row['Available Qty']}")
        qty_inputs[i] = cols[2].number_input("Qty", min_value=0, max_value=int(row["Available Qty"]), step=1, key=f"qty_{i}")
    generate = st.form_submit_button("✅ Submit Order")

# Step 3: Generate Summary and Save
if generate:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for i, row in df.iterrows():
        qty = qty_inputs[i]
        if qty > 0:
            row_data = row.to_dict()
            row_data["Order Quantity"] = qty
            row_data["Customer Name"] = customer_name
            row_data["Timestamp"] = timestamp
            selected_items.append(row_data)

    if not selected_items:
        st.warning("⚠️ No items selected!")
        st.stop()

    order_df = pd.DataFrame(selected_items)[["Timestamp", "Customer Name", "SkuShortName", "Available Qty", "Order Quantity"]]

    # Save to central 'Orders' sheet
    try:
        try:
            orders_ws = sheet.worksheet("Orders")
        except gspread.exceptions.WorksheetNotFound:
            orders_ws = sheet.add_worksheet(title="Orders", rows="1000", cols="10")

        existing_orders = get_as_dataframe(orders_ws).dropna(how='all')
        updated_orders = pd.concat([existing_orders, order_df], ignore_index=True)
        orders_ws.clear()
        set_with_dataframe(orders_ws, updated_orders)
        st.success("✔️ Order saved to sheet: Orders")
    except Exception as e:
        st.error(f"❗ Could not save order: {e}")

    # Printable Summary in Markdown (Streamlit-compatible)
    st.markdown("## 🧾 Order Summary (Printable View)")
    st.markdown(f"**Customer Name:** {customer_name}")
    st.markdown(f"**Order Date:** {timestamp}")
    
    summary_md = "| Product | Available Qty | Order Qty |\n|---|---|---|\n"
    for _, row in order_df.iterrows():
        summary_md += f"| {row['SkuShortName']} | {row['Available Qty']} | {row['Order Quantity']} |\n"
    
    st.markdown(summary_md)
    st.markdown(f"**Total Items Ordered:** {order_df['Order Quantity'].sum()}")
    
    st.info("To print this page, use your browser's Print option (Ctrl+P or Cmd+P)")

    def to_excel(df):
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Order Summary')
        return output.getvalue()

    st.download_button(
        label="⬇️ Download Order Summary as Excel",
        data=to_excel(order_df),
        file_name=f"order_{customer_name.replace(' ', '_')}_{timestamp.replace(':', '-')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
