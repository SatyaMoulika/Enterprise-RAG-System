import streamlit as st

from services.auth_api import register

st.set_page_config(page_title="Register")

st.title("Register Enterprise")

enterprise_name = st.text_input(
    "Enterprise Name"
)

email = st.text_input(
    "Admin Email"
)

password = st.text_input(
    "Password",
    type="password"
)

if st.button("Register"):

    response = register(
        enterprise_name,
        email,
        password
    )

    if response.status_code == 201:

        st.success(
            "Enterprise created successfully"
        )

    else:

        st.error(
            response.json().get(
                "detail",
                "Registration failed"
            )
        )

if st.button("Back"):
    st.switch_page("app.py")