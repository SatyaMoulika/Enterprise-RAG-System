import streamlit as st

from services.user_api import (
    get_all_users,
    create_user,
    delete_user
)

st.set_page_config(
    page_title="User Management",
    layout="wide"
)

if "token" not in st.session_state:
    st.switch_page("app.py")

if st.session_state.role != "admin":
    st.error("Access denied")
    st.stop()

st.title("User Management")

with st.sidebar:

    st.header("Admin")

    if st.button("Documents"):
        st.switch_page("pages/admin_documents.py")

    if st.button("Profile"):
        st.switch_page("pages/profile.py")

    if st.button("Logout"):
        st.session_state.clear()
        st.switch_page("app.py")

st.divider()

st.subheader("Create User")

email = st.text_input("Email")

password = st.text_input(
    "Password",
    type="password"
)

role = st.selectbox(
    "Role",
    [
        "employee",
        "admin"
    ]
)

if st.button("Create User"):

    response = create_user(
        token=st.session_state.token,
        email=email,
        password=password,
        role=role
    )

    if response.status_code in [200, 201]:
        st.success("User created")
        st.rerun()
    else:
        st.error(response.text)

st.divider()

st.subheader("Users")

response = get_all_users(
    st.session_state.token
)

if response.status_code == 200:

    users = response.json()

    for user in users:

        col1, col2, col3, col4, col5 = st.columns(
            [3, 2, 2, 2, 1]
        )

        with col1:
            st.write(user["email"])

        with col2:
            st.write(user["role"])

        with col3:
            st.write(user["enterprise_id"])

        with col4:
            st.write(
                "Active"
                if user["is_active"]
                else "Inactive"
            )

        with col5:

            if st.button(
                "Delete",
                key=f"user_{user['id']}"
            ):

                delete_user(
                    st.session_state.token,
                    user["id"]
                )

                st.rerun()

else:

    st.error(
        "Unable to load users"
    )