import re
import json
import uuid
import pandas as pd
from difflib import SequenceMatcher
from google import genai
from google.genai import types

def run_disclosure_analysis(excel_path: str, pdf_bytes: bytes) -> list:
    # 1. Initialize client
    api_key = "AIzaSyDDOmjGVkrr8T_ufR9DsPFUAyBHp-32jxA"
    client = genai.Client(api_key=api_key)

    # 2. Load standard disclosures
    df = pd.read_excel(excel_path, engine="openpyxl")
    std_disclosures = df["Unnamed: 4"].dropna().astype(str).tolist()

    # 3. Prompts
    system_prompt = (
        "You are an expert compliance checker. Extract all disclosure texts "
        "from the provided PDF document and return in JSON format, "
        "mapping each disclosure to the pages they appear on."
    )
    user_prompt = (
        "Return JSON like: {\"disclosures\": [{\"text\": \"disclosure A\", \"pages\": \"1,2\"}, ...]}"
    )

    # 4. Call Gemini with inline PDF data
    try:
        # Create PDF part using types.Part
        pdf_part = types.Part.from_bytes(
            data=pdf_bytes, 
            mime_type="application/pdf"
        )
        
        # Generate content with PDF and text prompt
        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=[pdf_part, system_prompt + "\n\n" + user_prompt]
        )
        
        response_text = response.text
        
    except Exception as e:
        print(f"Gemini API error: {e}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return []

    # 5. Parse AI JSON output
    try:
        # Remove markdown code fences if present
        cleaned = re.sub(r"^```json\s*|\s*```$", "", response_text, flags=re.DOTALL)
        ai_disclosures = json.loads(cleaned).get("disclosures", [])
    except Exception as e:
        print(f"JSON parsing error: {e}")
        print(f"Response text: {response_text[:500]}")
        ai_disclosures = []

    # 6. Compare with standard disclosures
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
            "id": str(uuid.uuid4()),
            "expected_disclosure": std,
            "matched_text": best["text"],
            "pages": best["pages"],
            "match_score": best["score"],
            "status": status,
        })

    # 7. Filter only partially present or missing disclosures
    filtered_results = [r for r in results if r["status"] in ["Partially Present", "Not Present"]]
    return filtered_results

# ------------------------------
# Test
# ------------------------------
if __name__ == "__main__":
    pdf_path = "TC21_FS_BlkRock_institutional-fund-sl-agency-shares Original.pdf"
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    disclosures = run_disclosure_analysis("data/Disclosure Library_TEMPLATE_DRAFT.xlsx", pdf_bytes)
    print(json.dumps(disclosures, indent=4))