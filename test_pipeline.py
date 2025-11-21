import re 
from docling.document_converter import DocumentConverter
import os 
os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"
from test_compliance import run_text_review


converter = DocumentConverter()

def extract_text_from_pdf(local_pdf:str)->str:
    try:
        result = converter.convert(local_pdf)
        result = converter.convert(local_pdf)
        markdown = result.document.export_to_markdown(strict_text=True)
        clean_text = re.sub(r"<!-- image -->", "", markdown)

        text_res = run_text_review(clean_text)
        return text_res

def run_disclosure_analysis(excel_path: str, pdf_bytes: bytes) -> list:
    

    except Exception  as e :
        print("Error:"+str(e))  
    return None 

if __name__ == "__main__":
    pdf_path = "TC21_FS_BlkRock_institutional-fund-sl-agency-shares Original.pdf"   
    text = extract_text_from_pdf(pdf_path)

    print("\n===== EXTRACTED TEXT =====\n")
    print(text)
