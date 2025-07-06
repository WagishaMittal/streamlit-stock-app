import streamlit as st
import gspread
import pandas as pd
from gspread_dataframe import get_as_dataframe, set_with_dataframe
from io import BytesIO
from google.oauth2.service_account import Credentials
from datetime import datetime
import streamlit.components.v1 as components

# --- Configuration ---
USERS = {
    "user1": "pass1",
    "user2": "pass2",
    "user3": "pass3",
    "user4": "pass4",
    "user5": "pass5",
}
ITEMS_PER_PAGE = 10

# --- Auth ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.username = None
    st.session_state.customer_name = ""
    st.session_state.customer_id = ""

if not st.session_state.authenticated:
    with st.form("login_form"):
        st.title("🔐 Login")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        login = st.form_submit_button("Login")
        if login:
            if username in USERS and USERS[username] == password:
                st.session_state.authenticated = True
                st.session_state.username = username
                st.rerun()
            else:
                st.error("Invalid username or password")
    st.stop()

# --- Ask for Customer Name ---
if not st.session_state.customer_name:
    with st.form("customer_name_form"):
        customer_name = st.text_input("Enter Customer Name")
        submit_customer = st.form_submit_button("Proceed")
        if submit_customer and customer_name.strip():
            prefix = customer_name.strip().upper()[:3].ljust(3, 'X')
            timestamp_suffix = datetime.now().strftime("%f")[-4:]
            st.session_state.customer_name = customer_name
            st.session_state.customer_id = f"{prefix}{timestamp_suffix}"
            st.success("Customer name recorded. Loading your products...")
            st.rerun()
    st.stop()

# --- Initialize Session State ---
if "cart" not in st.session_state:
    st.session_state.cart = []
if "page" not in st.session_state:
    st.session_state.page = 0
if "search" not in st.session_state:
    st.session_state.search = ""
if "viewing_cart" not in st.session_state:
    st.session_state.viewing_cart = False
if "order_complete" not in st.session_state:
    st.session_state.order_complete = False

# --- Load Google Sheet ---
def load_sheet():
    try:
        creds_dict = st.secrets["gcp_service_account"]
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scope)
        gc = gspread.authorize(credentials)
        sh = gc.open_by_key("1PrsSMbPddsn1FnjC4Fao2XJ63f1kG4u8X9aWZwmdK1A")
        ws = sh.get_worksheet(0)
        df = get_as_dataframe(ws).dropna(how='all')
        df["Available Qty"] = pd.to_numeric(df["Available Qty"], errors="coerce").fillna(0).astype(int)
        return df, sh, ws
    except Exception as e:
        st.error("Failed to load Google Sheet. Please check your credentials or network connection.")
        st.stop()

# --- Load and Filter Inventory ---
df, sheet, ws_inventory = load_sheet()

# --- Product Catalog ---
if not st.session_state.viewing_cart:
    st.title("🛒 Product Catalog")
    st.write(f"**Logged in as:** {st.session_state.username}")
    st.write(f"**Customer Name:** {st.session_state.customer_name} ({st.session_state.customer_id})")

    search_term = st.text_input("🔍 Search Products")
    filtered_df = df[df["SkuShortName"].str.contains(search_term, case=False, na=False)] if search_term else df

    start = st.session_state.page * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    paged_df = filtered_df[start:end]

    with st.form("product_form"):
        for idx, row in paged_df.iterrows():
            st.markdown("---")
            cols = st.columns([1, 3, 2, 2])
            image_url = row.get("Image URL", "")
            if image_url:
                cols[0].image(image_url, width=80)
            cols[1].markdown(f"**{row['SkuShortName']}**")
            cols[2].markdown(f"Available: {row['Available Qty']}")
            qty = cols[3].number_input("Qty", 0, int(row["Available Qty"]), key=f"qty_{idx}")

            if qty > 0:
                st.session_state.cart.append({
                    "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Login ID": st.session_state.username,
                    "Customer Name": st.session_state.customer_name,
                    "Customer ID": st.session_state.customer_id,
                    "SkuShortName": row['SkuShortName'],
                    "Available Qty": row['Available Qty'],
                    "Order Quantity": qty,
                    "Price": "",
                    "Remark": ""
                })

        col1, col2, col3 = st.columns(3)
        if col1.form_submit_button("⬅ Previous") and st.session_state.page > 0:
            st.session_state.page -= 1
            st.rerun()
        if col2.form_submit_button("Next ➡") and end < len(filtered_df):
            st.session_state.page += 1
            st.rerun()
        if col3.form_submit_button("🛒 View Cart"):
            st.session_state.viewing_cart = True
            st.rerun()

# --- Cart View ---
if st.session_state.viewing_cart:
    st.header("🧾 Review Cart")
    if not st.session_state.cart:
        st.info("Your cart is empty.")
        if st.button("⬅ Back to Products"):
            st.session_state.viewing_cart = False
            st.rerun()
        st.stop()

    for i, item in enumerate(st.session_state.cart):
        st.markdown(f"**{item['SkuShortName']}**")
        st.session_state.cart[i]["Price"] = st.text_input(f"Price for {item['SkuShortName']}", item["Price"], key=f"price_{i}")
        st.session_state.cart[i]["Remark"] = st.text_input(f"Remark for {item['SkuShortName']}", item["Remark"], key=f"remark_{i}")

    if not st.session_state.order_complete and st.button("✅ Submit Order"):
        order_df = pd.DataFrame(st.session_state.cart)
        try:
            try:
                orders_ws = sheet.worksheet("Orders")
            except gspread.exceptions.WorksheetNotFound:
                orders_ws = sheet.add_worksheet(title="Orders", rows="1000", cols="20")
            existing_orders = get_as_dataframe(orders_ws).dropna(how='all')
            updated_orders = pd.concat([existing_orders, order_df], ignore_index=True)
            orders_ws.clear()
            set_with_dataframe(orders_ws, updated_orders)
            st.success("✔️ Order saved to Google Sheet")
        except Exception as e:
            st.error(f"❗ Failed to save order: {e}")

        for item in st.session_state.cart:
            df.loc[df["SkuShortName"] == item["SkuShortName"], "Available Qty"] -= item["Order Quantity"]
        ws_inventory.clear()
        set_with_dataframe(ws_inventory, df)

        excel_buffer = BytesIO()
        order_df.to_excel(excel_buffer, index=False)
        st.download_button("⬇️ Download Order Summary", excel_buffer.getvalue(), file_name=f"order_{st.session_state.customer_id}.xlsx")

        html = f"""
        <html>
        <body>
        <div id='print-area'>
        <h2>🧾 Order Summary</h2>
        <p><b>Customer ID:</b> {st.session_state.customer_id}<br>
        <b>Login ID:</b> {st.session_state.username}<br>
        <b>Customer:</b> {st.session_state.customer_name}</p>
        <table border='1' cellpadding='6' cellspacing='0'>
        <tr><th>Product</th><th>Qty</th><th>Price</th><th>Remark</th></tr>
        """
        for _, row in order_df.iterrows():
            html += f"<tr><td>{row['SkuShortName']}</td><td>{row['Order Quantity']}</td><td>{row['Price']}</td><td>{row['Remark']}</td></tr>"
        html += "</table><br><button onclick='window.print()'>🖨️ Print Summary</button></div></body></html>"
        components.html(html, height=600)

        st.session_state.order_complete = True

    if st.session_state.order_complete:
        if st.button("🆕 Start New Order"):
            st.session_state.cart = []
            st.session_state.viewing_cart = False
            st.session_state.order_complete = False
            st.rerun()

    if st.button("⬅ Back to Products"):
        st.session_state.viewing_cart = False
        st.rerun()

    st.stop()
