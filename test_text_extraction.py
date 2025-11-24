import re 
from langchain_community.document_loaders import UnstructuredPDFLoader
import os 
os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"
from test_compliance import run_text_review
from test_desclosure import disclosure
from test_multimodal import run_multimodal
from test_syn import run_syn
from typing import Optional, List


def clean_pdf_text(text: str) -> str:
    # Remove carriage returns
    text = text.replace("\r", "")

    # Replace multiple newlines with a single newline
    text = re.sub(r"\n\s*\n+", "\n\n", text)

    # Replace multiple spaces with a single space
    text = re.sub(r"[ ]{2,}", " ", text)

    # Strip whitespace at start/end of each line
    text = "\n".join(line.strip() for line in text.splitlines())

    text = re.sub(r"<!-- image -->", "", text)

    # Remove leading/trailing blank lines
    text = text.strip()

    return text

def extract_text_from_pdf(local_pdf:str)->Optional[str]:
    try:
        # changed the document text loading from docling to langchain as it is not extracting text properly and often return empty string

        loader = UnstructuredPDFLoader(local_pdf, mode="elements", languages=["eng"])
        result = loader.load()
        page_content = ""
        for text in result:
            page_content += " " + text.page_content
        clean_text = clean_pdf_text(page_content)
        return clean_text

    except Exception  as e :
        print("Error:"+str(e))  
        return None

if __name__ == "__main__":
    extracted_text = extract_text_from_pdf(r"TC21_FS_BlkRock_institutional-fund-sl-agency-shares Original.pdf")
    print(extracted_text)