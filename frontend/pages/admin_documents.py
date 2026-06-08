import streamlit as st

from services.document_api import (
    upload_document,
    get_documents,
    delete_document
)

st.set_page_config(
    page_title="Documents",
    layout="wide"
)

if "token" not in st.session_state:
    st.switch_page("app.py")

if st.session_state.role != "admin":
    st.error("Access denied")
    st.stop()

st.title("Document Management")

with st.sidebar:

    st.header("Admin")

    if st.button("Users"):
        st.switch_page(
            "pages/admin_users.py"
        )

    if st.button("Profile"):
        st.switch_page(
            "pages/profile.py"
        )

    if st.button("Logout"):
        st.session_state.clear()
        st.switch_page("app.py")

st.divider()

st.subheader("Upload Document")

uploaded_file = st.file_uploader(
    "Choose file",
    type=[
        "pdf",
        "txt",
        "docx"
    ]
)

if uploaded_file:

    if st.button("Upload"):

        response = upload_document(
            st.session_state.token,
            uploaded_file
        )

        if response.status_code in [200, 201]:
            st.success("Uploaded")
            st.rerun()
        else:
            st.error(response.text)

st.divider()

st.subheader("Documents")

response = get_documents(
    st.session_state.token
)

if response.status_code == 200:

    documents = response.json()

    for document in documents:

        col1, col2, col3 = st.columns(
            [5, 3, 1]
        )

        with col1:
            st.write(document["title"])

        with col2:
            st.write(
                document["created_at"]
            )

        with col3:

            if st.button(
                "Delete",
                key=f"doc_{document['id']}"
            ):

                delete_document(
                    st.session_state.token,
                    document["id"]
                )

                st.rerun()

else:

    st.error(
        "Unable to load documents"
    )