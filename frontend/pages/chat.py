import streamlit as st

from services.chat_api import ask_question

st.set_page_config(
    page_title="Enterprise Chat",
    layout="wide"
)

if "token" not in st.session_state:
    st.switch_page("app.py")

if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:

    st.title("Enterprise RAG")

    if st.button("Profile"):
        st.switch_page("pages/profile.py")

    if st.button("Logout"):
        st.session_state.clear()
        st.switch_page("app.py")

st.title("Enterprise Assistant")

for msg in st.session_state.messages:

    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

question = st.chat_input(
    "Ask a question..."
)

if question:

    st.session_state.messages.append(
        {
            "role": "user",
            "content": question
        }
    )

    with st.chat_message("user"):
        st.markdown(question)

    response = ask_question(
        st.session_state.token,
        question
    )

    if response.status_code == 200:

        result = response.json()

        answer = result["answer"]

        sources = result["sources"]

        source_text = ""

        if sources:
            source_text = (
                "\n\n**Sources:** "
                + ", ".join(
                    map(str, sources)
                )
            )

        full_response = (
            answer + source_text
        )

    else:

        full_response = (
            "Unable to generate response."
        )

    with st.chat_message("assistant"):
        st.markdown(full_response)

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": full_response
        }
    )

    st.rerun()