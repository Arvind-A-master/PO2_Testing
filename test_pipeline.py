import re 
from docling.document_converter import DocumentConverter
import os 
os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"
from test_compliance import run_text_review
from test_desclosure import disclosure
from test_multimodal import run_multimodal
from test_syn import run_syn


converter = DocumentConverter()

def extract_text_from_pdf(local_pdf:str)->str:
    try:
        result = converter.convert(local_pdf)
        result = converter.convert(local_pdf)
        markdown = result.document.export_to_markdown(strict_text=True)
        clean_text = re.sub(r"<!-- image -->", "", markdown)

        text_res = run_text_review(clean_text)
        print(text_res)
        desclosure_res = disclosure(local_pdf)
        print(desclosure_res)
        multimodal_res = run_multimodal(local_pdf)
        print(multimodal_res)
        syn_res = run_syn(text_res,multimodal_res)
        print(syn_res)
        return text_res



    except Exception  as e :
        print("Error:"+str(e))  
    return None 

if __name__ == "__main__":
    pdf_path = "TC21_FS_BlkRock_institutional-fund-sl-agency-shares Original.pdf"   
    text = extract_text_from_pdf(pdf_path)
    print("\n===== FULL REPORT =====\n")
  
