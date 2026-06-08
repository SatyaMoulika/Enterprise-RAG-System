import streamlit as st

from services.auth_api import login
from services.user_api import get_me

st.set_page_config(page_title="Login")

st.title("Login")

email = st.text_input("Email")

password = st.text_input(
    "Password",
    type="password"
)

if st.button("Login"):

    response = login(
        email=email,
        password=password
    )

    if response.status_code == 200:
        data = response.json()
        token = data["access_token"]
        me_response = get_me(token)

        if me_response.status_code != 200:
            st.error("Unable to load profile")
            st.stop()

        user = me_response.json()

        st.session_state.token = token
        st.session_state.role = user["role"]
        st.session_state.email = user["email"]
        st.session_state.enterprise_id = user["enterprise_id"]
        st.success("Login successful")
        st.rerun()

    else:

        st.error(
            response.json().get(
                "detail",
                "Login failed"
            )
        )

if st.button("Back"):
    st.switch_page("app.py")