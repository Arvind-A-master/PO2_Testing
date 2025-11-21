from google import genai
import os 
from dotenv import load_dotenv
api_key = os.getenv('GEMINI_API_KEY')
from prompts import (
    base_review_prompt_template,
    text_input_instruction,
    multimodal_input_instruction,
    synthesis_prompt_template,
    typo_date_prompt_sys,
    typo_date_prompt_user,
    false_positives_guardrails
)
import json ,re

#### UTILS #####

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










api_key ="AIzaSyDDOmjGVkrr8T_ufR9DsPFUAyBHp-32jxA"





client = genai.Client(api_key=api_key)
def run_text_review(text:str):
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
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=full_prompt
        )
        response_text = response.text.strip() if hasattr(response, "text") else ""
        if not response_text:
            response_text = str(response)

    except Exception as e:
        return {
            "document_name": compliance_doc_name,
            "sections": [],
            "overall_conclusion": f"Gemini API error: {str(e)}"
        }
    return parse_response_to_json(response_text, "Text Review")


text_chunk = '''Performance data represents past performance and does guarantee
future results. Yields will not vary. Current performance may be lower or higher than the performance data quoted. Please call 800- 441-7450 or log on to www.blackrock.com/cash to obtain performance data
current to the most recent month-end'''

if __name__ == "__main__":
    pdf_path = "TC21_FS_BlkRock_institutional-fund-sl-agency-shares Original.pdf"   
    text = run_text_review(text_chunk)

    print("\n===== EXTRACTED TEXT =====\n")
    print(text)
