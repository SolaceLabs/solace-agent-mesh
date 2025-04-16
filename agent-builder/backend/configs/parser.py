
import json
import re

def parse_configs_json(configs_json):
    """
    Parse the JSON string into a Python dictionary.
    """
    # Step 1: Try to find JSON content within the response
    code_block_pattern = r"```json\s*([\s\S]*?)```"
    code_block_match = re.search(code_block_pattern, configs_json)

    if code_block_match:
        extracted_json = code_block_match.group(1).strip()
        try:
            result = json.loads(extracted_json)
            if "file_content" in result:
                return result
        except json.JSONDecodeError:
            pass
    
    # Step 2: Try to find JSON content without code block
    json_pattern = r"({[\s\S]*})"
    json_match = re.search(json_pattern, configs_json)

    if json_match:
        extracted_json = json_match.group(1).strip()
        try:
            result = json.loads(extracted_json)
            if "file_content" in result:
                return result
        except json.JSONDecodeError:
            pass

    raise ValueError("Invalid JSON format in the response. Please check the output format.")