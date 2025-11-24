import streamlit as st
from database import SessionLocal
import CRUD

st.set_page_config(page_title="All Documents", layout="wide")
st.title("All Documents")

db = SessionLocal()
docs = CRUD.get_all_documents(db)
db.close()

if not docs:
    st.info("No documents found.")
else:
    st.dataframe(
        [
            {
                "id": d.id,
                "name": d.document_name,
                "pages": d.number_of_pages,
                "status": d.status,
                "submitted_on": d.submitted_on
            }
            for d in docs
        ]
    )

doc_id_input = st.number_input("Enter Document ID", min_value=1)

if st.button("Go to Details"):
    st.session_state["selected_doc_id"] = doc_id_input
    st.success("Document ID saved! Navigate to 'Document Details' page from the sidebar.")