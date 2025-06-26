import streamlit as st
import gspread
import pandas as pd
from gspread_dataframe import get_as_dataframe
from io import BytesIO
from google.oauth2.service_account import Credentials

# -----------------------
# Load data from Google Sheets
# -----------------------
def load_sheet():
    creds_dict = st.secrets["gcp_service_account"]
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials = Credentials.from_service_account_info(creds_dict, scopes=scope)
    gc = gspread.authorize(credentials)
    sh = gc.open_by_key("1PrsSMbPddsn1FnjC4Fao2XJ63f1kG4u8X9aWZwmdK1A")  # Your sheet key
    ws = sh.get_worksheet(0)
    df = get_as_dataframe(ws).dropna(how='all')
    df["Available Qty"] = pd.to_numeric(df["Available Qty"], errors="coerce").fillna(0).astype(int)
    return df

df = load_sheet()

# -----------------------
# App UI
# -----------------------
st.title("📦 Stock Order System")

# Step 1: Ask customer name
with st.form("customer_form"):
    customer_name = st.text_input("Enter Customer Name")
    submitted_name = st.form_submit_button("Proceed")
    if not submitted_name:
        st.stop()
    elif not customer_name.strip():
        st.warning("Please enter a valid customer name to continue.")
        st.stop()

st.success(f"Placing order for: {customer_name}")

# Step 2: Show available products and get quantities
st.write("## 📋 Available Products")

with st.form("order_form"):
    selected_items = []

    for i, row in df.iterrows():
        cols = st.columns([4, 3, 3, 4])
        cols[0].markdown(f"**{row['SkuShortName']}**")
        cols[1].markdown("SKU: -")  # No SKU in your sheet
        cols[2].markdown(f"Available: {row['Available Qty']}")
        qty = cols[3].number_input(
            "Qty",
            min_value=0,
            max_value=int(row["Available Qty"]),
            step=1,
            key=f"qty_{i}"
        )
        if qty > 0:
            row_data = row.to_dict()
            row_data["Order Quantity"] = qty
            row_data["Customer Name"] = customer_name
            selected_items.append(row_data)

    generate = st.form_submit_button("✅ Submit Order")

# Step 3: Show and download summary
if generate:
    if not selected_items:
        st.warning("No items selected!")
    else:
        order_df = pd.DataFrame(selected_items)

        st.write("## 🧾 Order Summary")
        st.dataframe(order_df[["Customer Name", "SkuShortName", "Available Qty", "Order Quantity"]])

        # Convert to Excel
        def to_excel(df):
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Order Summary')
            return output.getvalue()

        excel_data = to_excel(order_df)

        st.download_button(
            label="⬇️ Download Order Summary",
            data=excel_data,
            file_name=f"order_{customer_name.replace(' ', '_')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
