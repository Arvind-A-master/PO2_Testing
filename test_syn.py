from prompts import (
    base_review_prompt_template,
    text_input_instruction,
    multimodal_input_instruction,
    synthesis_prompt_template,
    typo_date_prompt_sys,
    typo_date_prompt_user,
    false_positives_guardrails
)
import os
import re
import json
from pathlib import Path
from google import genai
from google.genai import types
from dotenv import load_dotenv
from pathlib import Path



load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")  # or just paste your key: "AIza..."
client = genai.Client(api_key=API_KEY)
SYNTHESIS_MODEL_NAME = "gemini-2.5-flash"
review_config = {"temperature": 0.0, "top_p": 0.15, "top_k": 6}

def parse_response_to_json(response_text: str, source_name: str) -> dict:
    """
    Safely parse model response text into a JSON object. 
    If parsing fails, return a fallback structure.
    """
    try:
        return json.loads(response_text)
    except:
        pass
    
    # Try to extract JSON from text
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



def run_synthesis_review(text_res: dict, multi_res: dict, pdf_bytes: bytes) -> dict:
    report1 = json.dumps(text_res, indent=2)
    report2 = json.dumps(multi_res, indent=2)

    prompt_text = str(synthesis_prompt_template).format(
        doc_name="Document",
        report1_json_string=report1,
        report2_json_string=report2,
        false_positives_guardrails=false_positives_guardrails
    )
    prompt_part = types.Part.from_text(text=prompt_text)
    pdf_part = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")

    # Generate synthesis response
    response = client.models.generate_content(
        model=SYNTHESIS_MODEL_NAME,
        contents=[pdf_part, prompt_part],
        config=review_config
    )

    # Extract text from response parts
    response_text = ""
    if hasattr(response, "candidates"):
        for candidate in response.candidates:
            if hasattr(candidate, "content"):
                for part in candidate.content.parts:
                    response_text += getattr(part, "text", "")

    return parse_response_to_json(response_text, "Synthesis Review")



def pdf_to_bytes(pdf_path) -> bytes:
    pdf_path = Path(pdf_path)
    
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    
    if not pdf_path.suffix.lower() == '.pdf':
        raise ValueError(f"File must be a PDF, got: {pdf_path.suffix}")
    
    with open(pdf_path, 'rb') as f:
        return f.read()



def run_syn(text_res,multi_res):
    #text_res = {'document_name': 'Document (Text Review)', 'sections': [{'section_title': '% Net total return 3 (3/31/25)', 'page_number': 'N/A', 'observations': 'A table presenting annualized net total returns for various periods (1-Year, 3-Years, 5-Years, 10-Years, Since Inception) is provided, but the document lacks a clear disclosure of the calculation methodology used for these net total returns. Footnote 3 clarifies the relationship between yield and total return but does not detail the specific methodology for calculating the total return figures themselves, which is a required element for performance disclosures.', 'rule_citation': 'SEC Marketing Rule 206(4)-1(a)(1), SEC Marketing Rule 206(4)-1(a)(6)', 'recommendations': "Add a clear and prominent disclosure explaining the calculation methodology for the '% Net total return' figures. This disclosure should detail how the returns are computed (e.g., whether they reflect the reinvestment of dividends and capital gains, and the specific impact of fees and expenses). This disclosure should be included either in a footnote directly associated with the table or in a dedicated 'Performance Calculation Methodology' section for full transparency.", 'category': 'Inadequate or Missing Disclosures'}]}
    #multi_res = {'document_name': 'BlackRock Cash Funds Institutional Fund (SL Agency shares) May 2025 Factsheet (Multimodal Review)', 'sections': [{'section_title': '% Net total return³ (3/31/25)', 'page_number': '1', 'observations': 
#"The table presents 'Net total return' for various periods (1 Year, 3 Years, 5 Years, 10 Years, Since Inception). While the fee basis (net) and time periods are disclosed, the calculation methodology for how the 'Net total return' is derived is not explicitly provided in the table, its associated footnote (footnote 3), or elsewhere in the document. This omission prevents a complete understanding of the performance figures.", 'rule_citation': 'SEC Marketing Rule 206(4)-1(a)(1), SEC Marketing Rule 206(4)-1(a)(6)', 'recommendations': "Add a clear and prominent disclosure explaining the calculation methodology for the 'Net total return' figures. This should detail what is included (e.g., capital appreciation, income) and excluded (e.g., specific fees, expenses), and how the returns are annualized or compounded, to ensure full transparency for investors. For example, a footnote could state: 'Net total return reflects the change in the net asset value of the Fund, assuming reinvestment of all dividends and capital gain distributions, and is net of all applicable fees and expenses. Returns for periods greater than one year are annualized.'"}]}

    pdf_path = "TC21_FS_BlkRock_institutional-fund-sl-agency-shares Original.pdf"
    pdf_bytes = pdf_to_bytes(pdf_path)
    synth_res = run_synthesis_review(text_res, multi_res, pdf_bytes)
    return json.dumps(synth_res, indent=4)