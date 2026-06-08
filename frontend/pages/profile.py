import streamlit as st

from services.user_api import get_me

st.set_page_config(
    page_title="My Profile",
    layout="centered"
)

if "token" not in st.session_state:
    st.switch_page("app.py")

response = get_me(
    st.session_state.token
)

if response.status_code != 200:
    st.error("Unable to load profile")
    st.stop()

user = response.json()

st.title("My Profile")

st.markdown("---")

st.write(f"**Email:** {user['email']}")
st.write(f"**Role:** {user['role']}")
st.write(f"**Enterprise ID:** {user['enterprise_id']}")
st.write(f"**Active:** {user['is_active']}")

st.markdown("---")

col1, col2 = st.columns(2)

with col1:

    if st.button("Back"):

        if user["role"] == "admin":
            st.switch_page("pages/admin_users.py")
        else:
            st.switch_page("pages/chat.py")

with col2:

    if st.button("Logout"):
        st.session_state.clear()
        st.switch_page("app.py")