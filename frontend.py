from main import check_compliance,load_sec_rules
import streamlit as st
import json

st.title("SEC Compliance Checker")

# Input box for the text chunk
text_chunk_input = st.text_area("Enter the Text Chunk to Review", height=200)

SEC_RULES = """
    (Insert your SEC rules here or load from a file)
    Example: "Performance data represents past performance and does not guarantee future results."
    """

if text_chunk_input:
    # Load the SEC rules
    sec_rules = load_sec_rules()

    if sec_rules == "":
        st.error("SEC rules file 'extracted_text.txt' not found or empty.")
    else:
        # Check compliance when the button is pressed
        if st.button("Check Compliance"):
            # Perform compliance check
            result = check_compliance(text_chunk_input, sec_rules)

            # Try parsing the result as JSON to display it properly
            try:
                result_json = json.loads(result)
                st.json(result_json)
            except json.JSONDecodeError:
                st.error("Failed to decode the response as JSON. Please try again.")
                st.text(result)