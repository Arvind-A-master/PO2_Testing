import re
import json
import pandas as pd
from typing import List, Dict, Any
import base64
from prompts import (
    base_review_prompt_template,
    text_input_instruction,
    multimodal_input_instruction,
    synthesis_prompt_template,
    typo_date_prompt_sys,
    typo_date_prompt_user,
    false_positives_guardrails
)
from google import genai
from dotenv import load_dotenv
from pathlib import Path
from google.genai import types

load_dotenv()

review_config = {"temperature": 0.0, "top_p": 0.15, "top_k": 6}
REVIEW_MODEL_NAME = "gemini-2.5-flash"
review_model = genai.Client()

def parse_response_to_json(response_text, source_name):
    import json, re
    try:
        return json.loads(response_text)
    except:
        pass
    json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except:
            pass
    return {
        "document_name": source_name,
        "sections": [],
        "overall_conclusion": "Failed to parse JSON from model response.",
        "raw_response": response_text
    }

def pdf_to_bytes(pdf_path) -> bytes:
    """
    Read a PDF file from the given path and return its contents as bytes.
    
    Args:
        pdf_path: Path to the PDF file (can be string or Path object)
    
    Returns:
        bytes: The PDF file contents as bytes
    
    Raises:
        FileNotFoundError: If the PDF file doesn't exist
        IOError: If there's an error reading the file
    """
    pdf_path = Path(pdf_path)
    
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    
    if not pdf_path.suffix.lower() == '.pdf':
        raise ValueError(f"File must be a PDF, got: {pdf_path.suffix}")
    
    with open(pdf_path, 'rb') as f:
        return f.read()

# Inference: take pdf files and generate review based on that 
def run_multimodal_review(pdf_bytes: bytes) -> dict:
    prompt_text = base_review_prompt_template + "\n\n" + multimodal_input_instruction
    
    # Create Part objects
    pdf_part = types.Part.from_bytes(
        data=pdf_bytes,
        mime_type="application/pdf"
    )
    
    content = [pdf_part, prompt_text]
    
    response = review_model.models.generate_content(
        model=REVIEW_MODEL_NAME,
        contents=content,
        config={
            "temperature": review_config["temperature"],
            "top_p": review_config["top_p"],
            "top_k": review_config["top_k"]
        }
    )
    
    response_text = (getattr(response, "text", "") or "").strip()
    # print(response_text)
    # print("*"*50)
    result = parse_response_to_json(response_text, "Multimodal Review")
    result["document_name"] = result.get("document_name", "").replace(
        "<placeholder>", "Multimodal Review"
    )
    return result

if __name__ == "__main__":
    pdf_path = r"TC21_FS_BlkRock_institutional-fund-sl-agency-shares Original.pdf"

    pdf_bytes = pdf_to_bytes(pdf_path=pdf_path)

    result = run_multimodal_review(pdf_bytes=pdf_bytes)
    # print("#"*50)

    print(result)