import streamlit as st
import gspread
import pandas as pd
from gspread_dataframe import get_as_dataframe, set_with_dataframe
from io import BytesIO
from google.oauth2.service_account import Credentials
from datetime import datetime

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
            st.session_state.customer_name = customer_name
            st.rerun()
    st.stop()

# --- Load Google Sheet ---
def load_sheet():
    creds_dict = st.secrets["gcp_service_account"]
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials = Credentials.from_service_account_info(creds_dict, scopes=scope)
    gc = gspread.authorize(credentials)
    sh = gc.open_by_key("1PrsSMbPddsn1FnjC4Fao2XJ63f1kG4u8X9aWZwmdK1A")
    ws = sh.get_worksheet(0)
    df = get_as_dataframe(ws).dropna(how='all')
    df["Available Qty"] = pd.to_numeric(df["Available Qty"], errors="coerce").fillna(0).astype(int)
    return df, sh, ws

# --- Initialize Session State ---
if "cart" not in st.session_state:
    st.session_state.cart = []
if "page" not in st.session_state:
    st.session_state.page = 0
if "search" not in st.session_state:
    st.session_state.search = ""

# --- Load and Filter Inventory ---
df, sheet, ws_inventory = load_sheet()
search_term = st.text_input("🔍 Search Products", st.session_state.search)
st.session_state.search = search_term
if search_term:
    df = df[df["SkuShortName"].str.contains(search_term, case=False, na=False)]

# --- Pagination ---
total_pages = (len(df) - 1) // ITEMS_PER_PAGE + 1
start_idx = st.session_state.page * ITEMS_PER_PAGE
end_idx = start_idx + ITEMS_PER_PAGE
current_page_data = df.iloc[start_idx:end_idx]

# --- Product Catalog ---
st.title("🛒 Product Catalog")
st.subheader(f"Logged in as: {st.session_state.username}")
st.markdown(f"**Customer Name:** {st.session_state.customer_name}")

with st.form("product_form"):
    for idx, row in current_page_data.iterrows():
        st.markdown("---")
        cols = st.columns([1, 3, 2, 2])
        if 'Image URL' in row and pd.notna(row['Image URL']):
            cols[0].image(row['Image URL'], width=80)
        else:
            cols[0].empty()
        cols[1].markdown(f"**{row['SkuShortName']}**")
        cols[2].markdown(f"Available: {row['Available Qty']}")
        qty = cols[3].number_input("Qty", 0, int(row["Available Qty"]), key=f"qty_{idx}")

        if qty > 0:
            already_in_cart = any(item['SkuShortName'] == row['SkuShortName'] for item in st.session_state.cart)
            if not already_in_cart:
                st.session_state.cart.append({
                    "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Login ID": st.session_state.username,
                    "Customer Name": st.session_state.customer_name,
                    "SkuShortName": row['SkuShortName'],
                    "Available Qty": row['Available Qty'],
                    "Order Quantity": qty,
                    "Price": "",
                    "Remark": ""
                })

    col_prev, col_next = st.columns(2)
    with col_prev:
        if st.session_state.page > 0:
            if st.form_submit_button("⬅ Previous"):
                st.session_state.page -= 1
                st.rerun()
    with col_next:
        if st.session_state.page < total_pages - 1:
            if st.form_submit_button("Next ➡"):
                st.session_state.page += 1
                st.rerun()

    st.form_submit_button("🛒 View Cart")
