import streamlit as st

st.set_page_config(
    page_title="Enterprise RAG",
    page_icon="🤖",
    layout="wide"
)

if "token" not in st.session_state:
    st.session_state.token = None

if "role" not in st.session_state:
    st.session_state.role = None

st.title("Enterprise RAG Assistant")

if not st.session_state.token:

    st.markdown("### Welcome")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Login", use_container_width=True):
            st.switch_page("pages/login.py")

    with col2:
        if st.button("Register Enterprise", use_container_width=True):
            st.switch_page("pages/register.py")

else:

    if st.session_state.role == "admin":
        st.switch_page("pages/admin_users.py")
    else:
        st.switch_page("pages/chat.py")