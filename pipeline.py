import asyncio  # Import asyncio
import json  # New import for json.dumps
import logging
import os
import re
import uuid
from typing import Dict, List  # New import

from bson import ObjectId  # Import ObjectId
from docling.document_converter import DocumentConverter
from pymongo.database import Database  # Import Database for type hinting
from starlette.concurrency import run_in_threadpool

from config.logger import get_logger
from infrastructure.db.connection import get_db_connection
from infrastructure.email.sendgrid_service import (
    send_sendgrid_email,
)  # Import SendGrid email service
from infrastructure.email.templates import (
    get_compliance_review_email_template,
)  # Import the new email template
from models.schemas import SelectionRegion  # New import
from models.user_model import UserModel  # Import UserModel to get email
from services import (  # Import services to fetch user, project, and document details
    documents_services,
    projects_services,
    users_services,
)
from services.compliance import run_pdf_schema_extraction  # New import
from services.compliance import (
    run_disclosure_analysis,
    run_multimodal_review,
    run_synthesis_review,
    run_text_review,
    run_typo_analysis,
)

logger = get_logger(__name__)

converter = DocumentConverter()


async def run_full_pipeline(version_id: str, local_pdf: str, user_email: str):
    await run_in_threadpool(_sync_full_pipeline, version_id, local_pdf, user_email)


def _sync_full_pipeline(version_id: str, local_pdf: str, user_email: str):
    db = get_db_connection()
    reviews = db["ai-compliance-pre-check"]
    document_versions_collection = db["document_versions"]

    logger.info(f"Starting pipeline for document: {version_id}")
    try:
        # 1. Upload raw PDF
        # gcs_pdf = upload_file(bucket, local_pdf, f"raw/{version_id}.pdf")
        # reviews.update_one({"version_id": version_id}, {"$set": {"gcs_pdf": gcs_pdf, "timestamp": datetime.now()}})
        # logger.info(f"Uploaded raw PDF to GCS: {gcs_pdf}")

        # 2. Text extraction (this was blocking before!)
        result = converter.convert(local_pdf)
        markdown = result.document.export_to_markdown(strict_text=True)
        clean_text = re.sub(r"<!-- image -->", "", markdown)

        # 3. Text review
        text_res = run_text_review(clean_text)
        reviews.update_one(
            {"version_id": version_id}, {"$set": {"text_review": text_res}}
        )

        # 4. Multimodal review
        pdf_bytes = open(local_pdf, "rb").read()
        multi_res = run_multimodal_review(pdf_bytes)
        reviews.update_one(
            {"version_id": version_id}, {"$set": {"multimodal_review": multi_res}}
        )

        # 5. Synthesis
        synth_res = run_synthesis_review(text_res, multi_res, pdf_bytes)

        # Add new fields to each section
        if "sections" in synth_res and isinstance(synth_res["sections"], list):
            for section in synth_res["sections"]:
                section["id"] = str(uuid.uuid4())
                section["isAccepted"] = False
                section["isRejected"] = False
                section["rejectionReason"] = None
                # Ensure page_number is stored as a string
                if "page_number" in section and not isinstance(section["page_number"], str):
                    section["page_number"] = str(section["page_number"])

        reviews.update_one(
            {"version_id": version_id}, {"$set": {"synthesis_review": synth_res}}
        )

        # 6. Typo & date
        typo_res = run_typo_analysis(pdf_bytes)

        # Add new fields to each missing percent detail
        if "missing_percent_details" in typo_res and isinstance(
            typo_res["missing_percent_details"], list
        ):
            for detail in typo_res["missing_percent_details"]:
                detail["id"] = str(uuid.uuid4())
                detail["isAccepted"] = False
                detail["isRejected"] = False
                detail["rejectionReason"] = None
                # Ensure page is stored as a string
                if "page" in detail and not isinstance(detail["page"], str):
                    detail["page"] = str(detail["page"])

        reviews.update_one(
            {"version_id": version_id}, {"$set": {"typo_analysis": typo_res}}
        )
        # 7. Disclosure
        disclosure_res = run_disclosure_analysis(
            "data/Disclosure Library_TEMPLATE_DRAFT.xlsx", pdf_bytes
        )
        # Filter and add new fields to each disclosure detail
        processed_disclosure_analysis = []
        for d in disclosure_res:
            if d.get("status") == "Partially Present":
                # Ensure item is a dictionary before adding fields
                if isinstance(d, dict):
                    d["id"] = str(uuid.uuid4())
                    d["isAccepted"] = False
                    d["isRejected"] = False
                    d["rejectionReason"] = None
                    # Ensure pages are stored as strings if they exist
                    if "pages" in d and isinstance(d["pages"], list):
                        d["pages"] = [str(p) if not isinstance(p, str) else p for p in d["pages"]]
                    processed_disclosure_analysis.append(d)
                else:
                    logger.warning(f"Skipping non-dict item in disclosure_res: {d}")

        reviews.update_one(
            {"version_id": version_id},
            {"$set": {"disclosure_analysis": processed_disclosure_analysis}},
        )

  
        # 8. Mark done
        reviews.update_one({"version_id": version_id}, {"$set": {"status": "done"}})
        logger.info(f"Pipeline complete for {version_id}; status set to 'done'.")

        document_versions_collection.update_one(
            {
                "_id": ObjectId(version_id),
            },
            {
                "$set": {"status": "ai_compliance_review_completed"},
            },
        )

    
    except Exception as e:
        logger.exception(f"Pipeline failed for document: {version_id}")
        reviews.update_one(
            {"version_id": version_id},
            {"$set": {"status": "failed", "error_message": str(e)}},
        )
        document_versions_collection.update_one(
            {
                "_id": ObjectId(version_id),
            },
            {
                "$set": {"status": "failed"},
            },
        )

    finally:
        # Cleanup local file
        if os.path.exists(local_pdf):
            os.remove(local_pdf)
            logger.info(f"Removed local file {local_pdf}")