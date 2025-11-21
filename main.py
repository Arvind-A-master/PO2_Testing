from datetime import datetime
import os
import base64
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
load_dotenv()

# ------------------------------------------------------------------------------
# Shared Template Values
# ------------------------------------------------------------------------------

current_date = datetime.now().strftime("%d %B %Y")

# ------------------------------------------------------------------------------
# PDF Text Extraction
# ------------------------------------------------------------------------------

# Specify your input PDF file

output_txt = "extracted_text.txt"

# Extract text from PDF
# print(f"Extracting text from {input_pdf}...")
# extracted_text = extract_text_from_pdf(input_pdf)

# # Save to file
# save_text(extracted_text, output_txt)

# print(f"\nExtraction complete!")
# print(f"- Extracted {len(extracted_text)} characters")
# print(f"- Saved to {output_txt}")
# print(f"- Text is now available in 'extracted_text' variable")

# # The extracted text is now available in the 'extracted_text' variable
# # You can use it in your compliance review or other processing
# print("\nFirst 500 characters of extracted text:")
# print("="*50)
# print(extracted_text[:500])
# print("="*50)

def load_sec_rules():
    """Function to load the SEC rules from the text file"""
    try:
        with open(output_txt, "r", encoding="utf-8") as f:
            sec_rules = f.read().strip()
        return sec_rules
    except FileNotFoundError:
        return ""

# print(extracted_text)

# ------------------------------------------------------------------------------
# Prompt: Base Review Template (Used for both text and multimodal reviews)
# ------------------------------------------------------------------------------

# Specific prompt instructions for text vs. file input (for Step 1 & 2)
text_chunk = '''Performance data represents past performance and does guarantee
future results. Yields will not vary. Current performance may be lower or higher than the performance data quoted. Please call 800- 441-7450 or log on to www.blackrock.com/cash to obtain performance data
current to the most recent month-end'''


schema ={
    "type": "object",
    "properties": {
        "compliance": {"type": "string"},
        "REJECTION_EXPLANATION": {"type": "string"},
        "SINGLE_BEST_ALTERNATIVE": {"type": "string"},
    },
    "required": ["compliance", "REJECTION_EXPLANATION", "SINGLE_BEST_ALTERNATIVE"]
}


def check_compliance(text_chunk,SEC_RULESET):    
    base_review_prompt_template = f"""
    You are an AI compliance assistant specialized in reviewing financial marketing materials against SEC regulations.

    You will be provided with a TEXT_CHUNK from a document and supporting information including SEC rules, FAQs, and disclosure guidelines.

    SEC_RULESET:
    {SEC_RULESET}

    TEXT_CHUNK:
    {text_chunk}



    Analyze the TEXT_CHUNK from a filings document against the SEC_RULESET to determine compliance.

    1. IF COMPLIANT (PASS):
    The document segment is compliant with all rules.
    Your output MUST consist *only* of the single raw string:
    COMPLIANT

    2. IF NON-COMPLIANT (FAIL):
    The document segment violates one or more rules.
    Your output MUST be a valid JSON object (and nothing else) with the following two keys:
    "[A concise, paragraph-long explanation detailing which specific rule is violated, which exact word/phrase/sentence from the DOCUMENT_CHUNK causes the violation, and precisely how the document segment fails to comply. The explanation must cite the relevant rule from RETRIEVED_RULES.]",
    "SINGLE_BEST_ALTERNATIVE": "[The single best, complete, and fully compliant alternative wording that resolves the issue identified above. Do not include introductory phrases (e.g., 'We suggest...'). Provide the clean, revised text only.]"

    YOUR RULES
    ---
    your output should be in the json which is mentioned.
    if the document is compliant, leave the rejection explanation and single best alternative as blank strings.
    output json : 
    {{
        "compliance":"COMPLIANT or REJECT",
        "REJECTION_EXPLANATION": "[A concise, paragraph-long explanation detailing which specific rule is violated, which exact word/phrase/sentence from the DOCUMENT_CHUNK causes the violation, and precisely how the document segment fails to comply. The explanation must cite the relevant rule from RETRIEVED_RULES.]",
        "SINGLE_BEST_ALTERNATIVE": "[The single best, complete, and fully compliant alternative wording that resolves the issue identified above. Do not include introductory phrases (e.g., 'We suggest...'). Provide the clean, revised text only.]"
    }}

    ---
    EXAMPLES:
    Example 1: FAIL Output (REJECT)
    {{
        "compliance": "REJECT",
        "REJECTION_EXPLANATION": "The claim 'Guaranteed 12% annual return' violates SEC Rule 10b-5 by making an untrue statement of a material fact regarding expected performance. Such guarantees are considered misleading for non-insured securities.",
        "SINGLE_BEST_ALTERNATIVE": "Our strategy targets a 12% annual return; however, all investments involve risk, and returns are not guaranteed. Past performance is not indicative of future results."
    }}

    ---
    Example 2: PASS Output (COMPLIANT)
    {{
        "compliance": "COMPLIANT",
        "REJECTION_EXPLANATION": "",
        "SINGLE_BEST_ALTERNATIVE": ""
    }}
    
    """


    api_key = os.getenv('GEMINI_API_KEY')
        
    if api_key is None:
        raise ValueError("API key not found. Please set GEMINI_API_KEY environment variable or pass api_key parameter.")

       

    
    llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            api_key=api_key,
            temperature=0,
            response_schema=schema 
        )

    # ------------------------------------------------------------------------------
    # Run LLM with Prompt
    # ------------------------------------------------------------------------------

    print("Running compliance review with LLM...")
    print("="*80)

    # Create the message
    message = HumanMessage(content=base_review_prompt_template)

    # Get response from LLM
    response = llm.invoke([message])

    # Display the result
    print("\n" + "="*80)
    print("COMPLIANCE REVIEW RESULT:")
    print("="*80)
    print(response.content)
    print("="*80)

    # Optionally save the result
    #result_file = "compliance_result.txt"
    #with open(result_file, 'w', encoding='utf-8') as f:
     #   f.write(response.content)
    return response.content

