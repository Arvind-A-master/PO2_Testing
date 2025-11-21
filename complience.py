import re
import json
import pandas as pd
from typing import List, Dict, Any # Added List, Dict, and Any import
from vertexai.preview.generative_models import Part
from .prompts import (
    base_review_prompt_template,
    text_input_instruction,
    multimodal_input_instruction,
    synthesis_prompt_template,
    typo_date_prompt_sys,
    typo_date_prompt_user,
    false_positives_guardrails
)
from .models import review_model, synthesis_model, typo_model, disclosure_model
from .utils import parse_response_to_json , run_ai_analysis
from config.logger import get_logger 
import uuid # Import uuid
from difflib import SequenceMatcher
from bson import ObjectId
from pymongo.database import Database
from models.document_model import DocumentVersions # For type hinting
from .prompts import document_comparison_prompt # Import the new prompt
from starlette.concurrency import run_in_threadpool
from models.comaparision_results_model import ComparisonResultsModel # Import the new model
from datetime import datetime # Import datetime for timestamp
from models.schemas import SelectionRegion # New import for PDF processing
from .prompts import tell_me_why_prompt_template # Import the new prompt template


#inference : reviews  text andgenrates o/p
def run_text_review(text: str) -> dict:
    if not text:
        return {
            "document_name": "Text Review Skipped (Empty Input)",
            "sections": [],
            "overall_conclusion": "Text-based review skipped: Input text was empty."
        }

    cleaned_text = text.strip()
    cleaned_text = re.sub(r'\n\s*\n', '\n', cleaned_text)
    compliance_doc_name = "Document"
    formatted_instruction = text_input_instruction.format(
        input_doc_text=cleaned_text,
        compliance_doc_name=compliance_doc_name
    )
    full_prompt = base_review_prompt_template + "\n\n" + formatted_instruction
    content = [Part.from_text(full_prompt)]

    #logger.info(f"Text Review - Request to Gemini: {full_prompt}...")
    response = review_model.generate_content(content)

    parts = response.candidates[0].content.parts
    response_text = "".join(p.text for p in parts).strip()
    #logger.info(f"Text Review - Response from Gemini: {response_text}...")

    return parse_response_to_json(response_text, "Text Review")

#inference : take pdf files and generate review based on that 
def run_multimodal_review(pdf_bytes: bytes) -> dict:
    prompt_part = Part.from_text(base_review_prompt_template + "\n\n" + multimodal_input_instruction)
    pdf_part = Part.from_data(mime_type="application/pdf", data=pdf_bytes)
    content = [pdf_part, prompt_part]

    #logger.info(f"Multimodal Review - Request to Gemini (text part): {getattr(prompt_part, 'text', 'N/A')}...")
    #logger.info(f"Multimodal Review - Request to Gemini (PDF bytes length): {len(getattr(pdf_part, 'data', b''))}")
    response = review_model.generate_content(content)
    #logger.info("Received response from review_model for multimodal review.")
    parts = response.candidates[0].content.parts
    response_text = "".join(p.text for p in parts).strip()
    #logger.info(f"Multimodal Review - Response from Gemini: {response_text}...")

    result = parse_response_to_json(response_text, "Multimodal Review")
    result["document_name"] = result.get("document_name", "").replace(
        "<placeholder>", "Multimodal Review"
    )
    return result

# takes the review of both 
def run_synthesis_review(text_res: dict, multi_res: dict, pdf_bytes: bytes) -> dict:
    report1 = json.dumps(text_res, indent=2)
    report2 = json.dumps(multi_res, indent=2)

    prompt_text = str(synthesis_prompt_template).format(
        doc_name=text_res.get("document_name", "Document"),
        report1_json_string=report1,
        report2_json_string=report2,
        false_positives_guardrails=false_positives_guardrails
    )
    prompt_part = Part.from_text(prompt_text)
    pdf_part = Part.from_data(mime_type="application/pdf", data=pdf_bytes)
    content = [pdf_part, prompt_part]

    #logger.info(f"Synthesis Review - Request to Gemini (text part): {getattr(prompt_part, 'text', 'N/A')}...")
    #logger.info(f"Synthesis Review - Request to Gemini (PDF bytes length): {len(getattr(pdf_part, 'data', b''))}")
    response = synthesis_model.generate_content(content)
    #logger.info("Received response from synthesis_model for synthesis review.")

    parts = response.candidates[0].content.parts
    response_text = "".join(p.text for p in parts).strip()
    #logger.info(f"Synthesis Review - Response from Gemini: {response_text}...")

    return parse_response_to_json(response_text, "Synthesis Review")

#inference : checks for typo in the pdf
def run_typo_analysis(pdf_bytes: bytes) -> dict:
    """
    Performs typo and date format analysis on the document using Vertex AI.

    Returns a dict with details of missing '%' signs and incorrect date formats.
    """
    #logger.info("Preparing prompt for typo analysis...")

    # Prepare multimodal input
    pdf_part = Part.from_data(mime_type="application/pdf", data=pdf_bytes)
    sys_part = Part.from_text(typo_date_prompt_sys)
    user_part = Part.from_text(typo_date_prompt_user)

    # Pass only the PDF part along with the text prompts. The AI will analyze the PDF.
    prompt_parts = [pdf_part, sys_part, user_part]

    #logger.info(f"Typo Analysis - Request to Gemini (system prompt): {getattr(sys_part, 'text', 'N/A')}...")
    #logger.info(f"Typo Analysis - Request to Gemini (user prompt): {getattr(user_part, 'text', 'N/A')}...")
    #logger.info(f"Typo Analysis - Request to Gemini (PDF bytes length): {len(getattr(pdf_part, 'data', b''))}")
    raw_response = run_ai_analysis(typo_model, prompt_parts, source_label="Typo/Date Analysis")

    if raw_response.startswith(("BLOCKED:", "NO_CONTENT_OR_SAFETY_INFO", "API_ERROR:")):
        logger.error(f"Typo analysis failed or blocked: {raw_response}")
        return {
            "missing_percent_details": [],
            "error": f"Typo analysis failed: {raw_response}"
        }

    typo_res = parse_response_to_json(raw_response, source_label="Typo/Date Analysis")
    #logger.info(f"Typo Analysis - Parsed response (typo_res): {json.dumps(typo_res, indent=2)}")
    return typo_res

#inference : runs the disclosure analysis when the excel is given and pdf is given 
def run_disclosure_analysis(excel_path: str, pdf_bytes: bytes) -> list:
    """
    Extract disclosures from PDF using AI and compare with standard disclosures from Excel.
    Returns a list of matched results.
    """
    #logger.info("Running disclosure analysis...")

    # 1. Load standard disclosures
    df = pd.read_excel(excel_path, engine="openpyxl")
    std_disclosures = df["Unnamed: 4"].dropna().astype(str).tolist()

    # 2. AI Extraction
    system_prompt = (
        "You are an expert compliance checker. Extract all disclosure texts from the provided PDF document "
        "and return in JSON format, mapping each disclosure to the pages they appear on."
    )
    user_prompt = (
        "Return JSON like: {\"disclosures\": [{\"text\": \"disclosure A\", \"pages\": \"1,2\"}, ...]}"
    )
    
    pdf_part = Part.from_data(mime_type="application/pdf", data=pdf_bytes)
    parts = [pdf_part, Part.from_text(system_prompt), Part.from_text(user_prompt)]

    #logger.info(f"Disclosure Analysis - Request to Gemini (system prompt): {system_prompt}...")
    #logger.info(f"Disclosure Analysis - Request to Gemini (user prompt): {user_prompt}...")
    #logger.info(f"Disclosure Analysis - Request to Gemini (PDF bytes length): {len(getattr(pdf_part, 'data', b''))}")
    raw_response = run_ai_analysis(disclosure_model, parts, source_label="Disclosure Analysis")

    try:
        cleaned = re.sub(r"^```json\s*|\s*```$", "", raw_response, flags=re.DOTALL)
        ai_disclosures = json.loads(cleaned).get("disclosures", [])
    except Exception as e:
        #logger.error(f"Disclosure response parsing failed: {e}")
        ai_disclosures = []

    #logger.info(f"Disclosure Analysis - Raw response from Gemini: {raw_response}...")
    # 3. Match against standard disclosures
    results = []
    for std in std_disclosures:
        best = {"score": 0, "text": "", "pages": "N/A"}
        for ai in ai_disclosures:
            score = SequenceMatcher(None, std, ai.get("text", "")).ratio() * 100
            if score > best["score"]:
                best = {"score": score, "text": ai.get("text", ""), "pages": ai.get("pages", "N/A")}
        
        status = (
            "Present" if best["score"] == 100 else
            "Partially Present" if best["score"] >= 80 else
            "Not Present"
        )
        results.append({
            "id": str(uuid.uuid4()), # Add a unique ID
            "expected_disclosure": std,
            "matched_text": best["text"],
            "pages": best["pages"],
            "match_score": best["score"],
            "status": status,
            
        })

    filtered_results = [
        r for r in results if r["status"] in ["Partially Present", "Not Present"]
    ]
    #logger.info(f"Filtered disclosure analysis results: {filtered_results}")
    #logger.info("Disclosure analysis completed.")
    return filtered_results

#inference : image extraction maybe ?? 
def run_pdf_schema_extraction(pdf_bytes: bytes, extraction_schema: dict) -> List[SelectionRegion]:
    """
    Extracts text and coordinates from a PDF based on a given schema using Gemini.
    The schema guides what 'sections' to look for and how to structure the output.
    """
    logger.info("Starting PDF schema extraction using Gemini...")

    # Construct a prompt that instructs Gemini to extract information
    # including coordinates and text based on the provided schema.
    # This is a challenging task for a pure LLM without specific vision tools.
    # We will ask Gemini to output in a JSON format matching SelectionRegion.
    prompt_text = (
        "You are an expert document analysis agent. From the provided PDF document, "
        "identify sections that match the following conceptual schema. "
        "For each identified section, extract the exact text and its approximate "
        "bounding box coordinates (left, top, width, height) and the page index. "
        "The coordinates should be relative to the top-left corner of the page, "
        "with units being points (1/72 of an inch). "
        "Return the results as a JSON array of objects, where each object conforms to the SelectionRegion schema:\n"
        "{\n"
        "  \"left\": float,\n"
        "  \"top\": float,\n"
        "  \"width\": float,\n"
        "  \"height\": float,\n"
        "  \"page_index\": int,\n"
        "  \"selected_text\": string\n"
        "}\n\n"
        f"Here is the conceptual schema to guide your extraction: {json.dumps(extraction_schema, indent=2)}\n\n"
        "Please provide only the JSON array in your response, without any additional text or markdown fences."
    )

    pdf_part = Part.from_data(mime_type="application/pdf", data=pdf_bytes)
    prompt_part = Part.from_text(prompt_text)
    content = [pdf_part, prompt_part]

    logger.info(f"PDF Schema Extraction - Request to Gemini (text part): {prompt_text[:200]}...") # Log first 200 chars
    logger.info(f"PDF Schema Extraction - Request to Gemini (PDF bytes length): {len(pdf_bytes)}")

    try:
        response = review_model.generate_content(content)
        response_text = "".join(p.text for p in response.candidates[0].content.parts).strip()
        logger.info(f"PDF Schema Extraction - Raw Gemini API response: '{response_text}'")

        # Attempt to parse the response as a JSON array of SelectionRegion objects
        # Gemini might include markdown fences, so try to remove them.
        if response_text.startswith("```json") and response_text.endswith("```"):
            response_text = response_text[len("```json\n"):-len("\n```")].strip()
        
        extracted_regions_data = json.loads(response_text)
        
        # Validate and convert to List[SelectionRegion]
        extracted_regions: List[SelectionRegion] = []
        for region_data in extracted_regions_data:
            try:
                extracted_regions.append(SelectionRegion(**region_data))
            except Exception as e:
                logger.warning(f"Skipping invalid SelectionRegion data: {region_data}. Error: {e}")
        
        logger.info(f"PDF Schema Extraction - Successfully extracted {len(extracted_regions)} regions.")
        return extracted_regions

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Gemini API response as JSON for schema extraction: {e}", exc_info=True)
        return []
    except Exception as e:
        logger.error(f"Error during PDF schema extraction with Gemini API: {e}", exc_info=True)
        return []

# inference : this we need to skip 
async def run_document_comparison(version_id_1: str, version_id_2: str, db: Database) -> dict:
    logger.info(f"Starting document comparison for versions: {version_id_1} and {version_id_2}")
    document_versions_collection = db.get_collection("document_versions")

    doc1 = await run_in_threadpool(document_versions_collection.find_one, {"_id": ObjectId(version_id_1)})
    doc2 = await run_in_threadpool(document_versions_collection.find_one, {"_id": ObjectId(version_id_2)})

    if not doc1:
        logger.error(f"Document version 1 with ID {version_id_1} not found for comparison.")
        raise ValueError(f"Document version 1 with ID {version_id_1} not found.")
    if not doc2:
        logger.error(f"Document version 2 with ID {version_id_2} not found for comparison.")
        raise ValueError(f"Document version 2 with ID {version_id_2} not found.")

    gcp_path_1 = doc1.get("gcp_path")
    gcp_path_2 = doc2.get("gcp_path")

    if not gcp_path_1 or not gcp_path_2:
        logger.error("GCP path not found for one or both documents during comparison.")
        raise ValueError("GCP path not found for one or both documents.")

    # Prepare parts for Gemini API
    prompt_part = Part.from_text(document_comparison_prompt)
    doc1_part = Part.from_uri(mime_type="application/pdf", uri=gcp_path_1)
    doc2_part = Part.from_uri(mime_type="application/pdf", uri=gcp_path_2)

    content = [prompt_part, doc1_part, doc2_part]

    logger.info(f"Sending document comparison request to Gemini API for {version_id_1} and {version_id_2}.")
    try:
        response = await review_model.generate_content_async(content)
        response_text = "".join(p.text for p in response.candidates[0].content.parts).strip()
        # Remove markdown code block fences if present
        if response_text.startswith("```json") and response_text.endswith("```"):
            response_text = response_text[len("```json\n"):-len("\n```")].strip()
        
        logger.info(f"Raw Gemini API response before JSON parsing: '{response_text}'") # Added log
        try:
            comparison_json = json.loads(response_text)
            # Extract the 'example' field if it exists, otherwise return the whole JSON
            if "example" in comparison_json:
                result_data = comparison_json["example"]
            else:
                result_data = comparison_json
            
            logger.info(f"Received Gemini API response for comparison (extracted result): {result_data}")

            # Store the comparison result in the database
            comparison_entry = ComparisonResultsModel(
                version1_id=ObjectId(version_id_1),
                version2_id=ObjectId(version_id_2),
                gcs_link_version1=gcp_path_1, # Pass GCS links
                gcs_link_version2=gcp_path_2, # Pass GCS links
                compared_at=datetime.utcnow(),
                gemini_comparison_result=result_data
            )
            
            comparison_collection = db.get_collection("document_comparisons")
            insert_result = await run_in_threadpool(comparison_collection.insert_one, comparison_entry.model_dump(by_alias=True, exclude_none=True))
            inserted_id = str(insert_result.inserted_id)
            logger.info(f"Stored comparison result in 'document_comparisons' collection for {version_id_1} and {version_id_2}. Inserted ID: {inserted_id}")

            # Return the inserted ID along with the result data
            
            return {"comparison_id": inserted_id, "result": result_data}
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini API response as JSON for schema extraction: {e}", exc_info=True)
            raise RuntimeError(f"Failed to parse AI comparison result: {e}")
    except Exception as e:
        logger.error(f"Error during document comparison with Gemini API: {e}", exc_info=True)
        raise RuntimeError(f"Failed to compare documents with AI: {e}")

#inference : ?? 
async def run_tell_me_why_summary(compliance_section: Dict[str, Any], gcp_path: str) -> str:
    """
    Generates a detailed explanation for a specific compliance finding.
    """
 

    # Prepare the prompt with the compliance section JSON
    compliance_section_json = json.dumps(compliance_section, indent=2)
    prompt_text = tell_me_why_prompt_template.format(compliance_section_json=compliance_section_json)

    # Prepare multimodal input
    pdf_part = Part.from_uri(mime_type="application/pdf", uri=gcp_path)
    prompt_part = Part.from_text(prompt_text)
    content = [pdf_part, prompt_part]

     try:
        response = await review_model.generate_content_async(content)
        response_text = "".join(p.text for p in response.candidates[0].content.parts).strip()
        return response_text
    except Exception as e:
        raise RuntimeError(f"Failed to generate 'Tell Me Why' summary: {e}")