import streamlit as st
from database import init_db

init_db()

st.set_page_config(page_title="AI Compliance Review", layout="wide")
st.title("AI Compliance Review Dashboard")

st.write("Welcome to the AI Compliance Review System!")
st.write("Use the sidebar to navigate between pages:")
st.write("- **Upload Document**: Upload and process PDFs")
st.write("- **All Documents**: View all uploaded documents")
st.write("- **Document Details**: View and edit document details")