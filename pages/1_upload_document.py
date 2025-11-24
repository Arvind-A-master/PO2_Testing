import streamlit as st
import os
from pathlib import Path
from PyPDF2 import PdfReader
from database import SessionLocal
import CRUD
from test_pipeline import run_pipeline
from Helper import process_output
import time

UPLOAD_DIR = "uploaded_pdfs"
os.makedirs(UPLOAD_DIR, exist_ok=True)

st.set_page_config(page_title="Upload Document", layout="wide")
st.title("Upload PDF for Review")

uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

if uploaded_file:
    # Create a unique identifier for this file
    file_id = f"{uploaded_file.name}_{uploaded_file.size}"
    
    # Check if this is a new file upload
    if "last_file_id" not in st.session_state or st.session_state.last_file_id != file_id:
        st.session_state.last_file_id = file_id
        st.session_state.pipeline_run = False
        st.session_state.output = None
        st.session_state.page_count = 0
        st.session_state.pdf_path = None
    
    # Only run pipeline if not already run for this file
    if not st.session_state.pipeline_run:
        filename = f"{int(time.time())}_{uploaded_file.name}"
        pdf_path = Path(UPLOAD_DIR) / filename
        with open(pdf_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        st.session_state.pdf_path = str(pdf_path)

        # st.subheader("Pipeline Output Preview")
        try:
            with st.spinner("Running pipeline..."):
                res = run_pipeline(pdf_path)

            if not res:
                st.error("Pipeline returned no results")
            else:
                output = process_output(res[0])

                try:
                    reader = PdfReader(pdf_path)
                    page_count = len(reader.pages)
                except Exception:
                    page_count = 0

                # Store in session state
                st.session_state.output = output
                st.session_state.page_count = page_count
                st.session_state.pipeline_run = True

        except Exception as e:
            st.error(f"Pipeline Error: {e}")
    
    # Display results from session state
    if st.session_state.pipeline_run and st.session_state.output:
        # st.subheader("Pipeline Output Preview")
        st.write("Pages:", st.session_state.page_count)
        
        output = st.session_state.output
        # st.markdown(f"**Document Name:** {output.get('document_name', 'N/A')}")
        # with st.expander("AI Observations"):
        #     st.write(output.get("ai_observations", "None"))
        # with st.expander("AI Recommendations"):
        #     st.write(output.get("ai_recommendations", "None"))

        if st.button("Save to Database"):
            db = SessionLocal()
            try:
                CRUD.create_document_with_ai(
                    db,
                    document_name=output.get("document_name", "Unnamed Document"),
                    number_of_pages=st.session_state.page_count,
                    ai_observations=output.get("ai_observations", []),
                    ai_recommendations=output.get("ai_recommendations", [])
                )
                st.success("Document saved successfully!")
                # Optionally clear the session state after saving
                # st.session_state.pipeline_run = False
            except Exception as e:
                st.error(f"Failed to save document: {e}")
            finally:
                db.close()