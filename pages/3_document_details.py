import streamlit as st
from database import SessionLocal
import CRUD

st.set_page_config(page_title="Document Details", layout="wide")
st.title("Document Details & Edit")

if "selected_doc_id" not in st.session_state:
    st.info("Please select a document from the 'All Documents' page.")
else:
    doc_id = st.session_state["selected_doc_id"]

    db = SessionLocal()
    doc_data = CRUD.get_document_by_id(db, doc_id)
    db.close()

    if not doc_data:
        st.error("Document not found.")
    else:
        st.subheader(f"📄 {doc_data.document_name}")

        st.write(f"**Pages:** {doc_data.number_of_pages}")
        st.write(f"**Submitted:** {doc_data.submitted_on}")
        st.write(f"**Status:** {'Completed' if doc_data.status else 'Pending'}")

        # Editable fields
        comments = st.text_area("Comments", value=doc_data.comments or "")
        status = st.checkbox("Mark as Completed", value=doc_data.status)

        if st.button("Save Changes"):
            db = SessionLocal()
            CRUD.update_document(db, doc_id, status=status, comments=comments)
            db.close()
            st.success("Document updated!")

        st.subheader("AI Observations & Recommendations")

        for fb in doc_data.ai_feedback:
            st.markdown(f"""
            ### Observation #{fb.id}
            **Observation:**  
            {fb.ai_observation}

            **Recommendation:**  
            {fb.ai_recommendation}

            --- 
            """)

        if st.button("Delete Document"):
            db = SessionLocal()
            CRUD.delete_document(db, doc_id)
            db.close()
            st.warning("Document deleted!")
            st.session_state.pop("selected_doc_id")
            st.rerun()