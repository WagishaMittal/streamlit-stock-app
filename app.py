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
        cols = st.columns([4, 3, 3, 2])
        cols[0].markdown(f"**{row['SkuShortName']}**")
        cols[1].markdown("SKU: -")
        cols[2].markdown(f"Available: {row['Available Qty']}")
        qty_inputs[i] = cols[3].number_input("Qty", min_value=0, max_value=int(row["Available Qty"]), step=1, key=f"qty_{i}")
    generate = st.form_submit_button("✅ Submit Order")

# Step 3: Generate Summary and Save
if generate:
    for i, row in df.iterrows():
        qty = qty_inputs[i]
        if qty > 0:
            row_data = row.to_dict()
            row_data["Order Quantity"] = qty
            row_data["Customer Name"] = customer_name
            row_data["Timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            selected_items.append(row_data)

    if not selected_items:
        st.warning("⚠️ No items selected!")
        st.stop()

    order_df = pd.DataFrame(selected_items)[["Timestamp", "Customer Name", "SkuShortName", "Available Qty", "Order Quantity"]]
    st.write("Saving the following order data:", order_df)

    # Save to Sheet (debug-safe)
    try:
        try:
            worksheet = sheet.worksheet("Orders")
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sheet.add_worksheet(title="Orders", rows="1000", cols="10")
        existing = get_as_dataframe(worksheet).dropna(how='all')
        combined = pd.concat([existing, order_df], ignore_index=True)
        worksheet.clear()
        set_with_dataframe(worksheet, combined)
        st.success("✔️ Order saved to Google Sheet!")
    except Exception as e:
        st.error(f"❗ Error saving to sheet: {e}")

    # Printable Summary
    html = f"""
    <div id='print-area' style='padding:20px;'>
        <h2>🧾 Order Summary</h2>
        <p><strong>Customer:</strong> {customer_name}</p>
        <p><strong>Date:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        <table border='1' style='border-collapse:collapse;width:100%'>
            <tr><th>Product</th><th>Available</th><th>Ordered</th></tr>"""

    for _, row in order_df.iterrows():
        html += f"<tr><td>{row['SkuShortName']}</td><td>{row['Available Qty']}</td><td>{row['Order Quantity']}</td></tr>"

    html += f"""
        </table>
        <p><strong>Total Ordered:</strong> {order_df['Order Quantity'].sum()}</p>
        <button onclick='window.print()' style='margin-top:10px;padding:10px;background:#4CAF50;color:white;border:none;'>🖨️ Print</button>
    </div>"""

    st.markdown("## 🧾 Download & Print")
    st.components.v1.html(html, height=600, scrolling=True)

    def to_excel(df):
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Order Summary')
        return output.getvalue()

    st.download_button(
        label="⬇️ Download Order Summary as Excel",
        data=to_excel(order_df),
        file_name=f"order_{customer_name.replace(' ', '_')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
