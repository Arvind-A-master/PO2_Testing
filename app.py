import streamlit as st
import os
from pathlib import Path
from PyPDF2 import PdfReader
from database import init_db, SessionLocal
import CRUD
from test_pipeline import run_pipeline
from Helper import process_output

init_db()

UPLOAD_DIR = "uploaded_pdfs"
os.makedirs(UPLOAD_DIR, exist_ok=True)

st.set_page_config(page_title="AI Compliance Review", layout="wide")
st.title("AI Compliance Review Dashboard")

tab1, tab2, tab3 = st.tabs(["Upload Document", "All Documents", "Document Details"])

# -------------------------------
# TAB 1 – UPLOAD PDF
# -------------------------------
with tab1:
    st.header("Upload PDF for Review")

    uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

    if uploaded_file:
        pdf_path = Path(UPLOAD_DIR) / uploaded_file.name
        with open(pdf_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        st.subheader("Pipeline Output Preview")
        try:
            res = run_pipeline(pdf_path)
            output = process_output(res[0])

            reader = PdfReader(pdf_path)
            page_count = len(reader.pages)
            st.write("Pages:", page_count)

        except Exception as e:
            st.error(f"Pipeline Error: {e}")

        if st.button("Save to Database"):
            db = SessionLocal()
            CRUD.create_document_with_ai(
                db,
                document_name=output["document_name"],
                number_of_pages=page_count,
                ai_observations=output["ai_observations"],
                ai_recommendations=output["ai_recommendations"]
            )
            db.close()
            st.success("Document saved successfully!")


# -------------------------------
# TAB 2 – LIST ALL DOCUMENTS
# -------------------------------
with tab2:
    st.header("All Documents")

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
        st.success("Open Tab 3 now.")


# -------------------------------
# TAB 3 – DOCUMENT DETAILS
# -------------------------------
with tab3:
    st.header("Document Details & Edit")

    if "selected_doc_id" not in st.session_state:
        st.info("Select a document from Tab 2.")
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
