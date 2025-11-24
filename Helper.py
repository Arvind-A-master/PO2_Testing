import json
from typing import List, Dict, Any, Optional


def load_json(input_json: str) -> Dict[str, Any]:
    try:
        return json.loads(input_json)
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON input")


def extract_ai_observations(data: Dict[str, Any]) -> List[str]:
    """
    Returns observations in the format:
    "in the page no {page_number} | rule citation: {rule_citation} | {observation}"
    """
    observations_list = []

    for section in data.get("sections", []):
        page       = section.get("page_number")
        citation   = section.get("rule_citation", "")
        obs        = section.get("observations", "")

        page_number = page if page is not None else "unknown"

        formatted = (
            f"in the page no {page_number} | "
            f"rule citation: {citation} | "
            f"{obs}"
        )

        observations_list.append(formatted)

    return observations_list

def extract_recommendations(data: Dict[str, Any]) -> List[str]:    
    return [sec.get("recommendations", "") for sec in data.get("sections", [])]

def get_document_name(data: Dict[str, Any]) -> Optional[str]:    
    return data.get("document_name")


def process_document(input_json: str) -> Dict[str, Any]:    
    data = load_json(input_json)
    return {
        "document_name": get_document_name(data),
        "ai_observations": extract_ai_observations(data),
        "ai_recommendations": extract_recommendations(data)
    }


def process_output(pipe_res:str):
    result = process_document(pipe_res)
    print(json.dumps(result, indent=4))
    return result
