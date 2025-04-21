# backend/app/services/textkernel_service.py

import requests
from flask import current_app
import logging
import json
import base64
from datetime import datetime, timezone

# Import the S3 service
from . import s3_service # Ensure s3_service.py is in the same directory

# Basic logger
logger = logging.getLogger(__name__)

# --- Constants ---
# Use the correct path from documentation
PARSER_ENDPOINT_PATH = "parser/resume" # Correct path

def _get_tk_config():
    """Helper to retrieve Textkernel config."""
    config = {
        "api_key": current_app.config.get('TEXTKERNEL_API_KEY'), # This is the 'ServiceKey'
        "account_id": current_app.config.get('TEXTKERNEL_ACCOUNT_ID'),
        "base_endpoint": current_app.config.get('TEXTKERNEL_BASE_ENDPOINT'),
    }
    if not all([config["api_key"], config["account_id"], config["base_endpoint"]]):
        logger.error("Textkernel config incomplete (API Key, Account ID, Base Endpoint).")
        return None
    if config["base_endpoint"] and not config["base_endpoint"].endswith('/'):
         config["base_endpoint"] += '/'
    config["full_parser_endpoint"] = config["base_endpoint"] + PARSER_ENDPOINT_PATH
    return config

def parse_cv_via_textkernel(s3_key: str) -> dict | None:
    """
    Downloads CV from S3, sends Base64 to Textkernel parser, returns parsed data.
    """
    tk_config = _get_tk_config()
    if not tk_config or not s3_key:
        logger.error("Cannot parse CV: Missing Textkernel config or S3 key.")
        return None

    # 1. Download file content from S3
    logger.info(f"Downloading CV from S3 for parsing: {s3_key}")
    file_bytes = s3_service.get_file_bytes(s3_key)
    if file_bytes is None:
        logger.error(f"Failed to download file {s3_key} from S3. Cannot parse.")
        return None

    # 2. Encode file content as Base64 string
    try:
        base64_encoded_cv = base64.b64encode(file_bytes).decode('utf-8')
    except Exception as enc_err:
        logger.error(f"Failed to Base64 encode CV content for {s3_key}: {enc_err}")
        return None

    # 3. Get DocumentLastModified (Use current UTC time, format YYYY-MM-DD)
    # Note: Example used YYYY-MM-DD. API docs might specify ISO 8601. Using example's format for now.
    last_modified_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # 4. Construct the API Request Payload (Based on EXAMPLE code)
    request_payload = {
        "DocumentAsBase64String": base64_encoded_cv,
        "DocumentLastModified": last_modified_date
        # Add optional 'SkillsSettings', 'ProfessionsSettings' etc. here if needed
        # "SkillsSettings": { "Normalize": True }
    }

    # 5. Construct Headers (Based on EXAMPLE code - using lowercase keys)
    headers = {
        'accept': "application/json", # Lowercase 'accept' from example
        'content-type': "application/json", # Lowercase 'content-type' from example
        'tx-accountid': tk_config["account_id"], # Lowercase header name from example
        'tx-servicekey': tk_config["api_key"],  # Lowercase header name from example (API Key is the Service Key)
    }

    # --- Make the API Call ---
    try:
        logger.info(f"Sending request to Textkernel ({tk_config['full_parser_endpoint']}) for S3 key: {s3_key}")

        # Use data=json.dumps(payload) as shown in the example
        response = requests.post(
            tk_config["full_parser_endpoint"],
            headers=headers,
            data=json.dumps(request_payload), # Serialize payload manually
            timeout=120
        )
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

        # --- Process the Response ---
        response_data = response.json() # Use .json() shortcut which handles decoding
        logger.info(f"Received successful response from Textkernel for S3 key: {s3_key}")

        # --- Extract Parsed Data (Based on EXAMPLE code: Value.ResumeData) ---
        parsed_value = response_data.get('Value')
        if parsed_value is None:
             logger.warning(f"Textkernel response OK for {s3_key}, but 'Value' key is missing.")
             return {'error': 'Parsing response missing Value key'}

        # Access ResumeData within Value
        resume_data = parsed_value.get('ResumeData')
        if resume_data is None:
             logger.warning(f"Textkernel response OK for {s3_key}, but 'ResumeData' key is missing within 'Value'.")
             # You might still return parsed_value here if other parts of 'Value' are useful
             return {'error': 'Parsing response missing ResumeData key'}

        # Return the ResumeData dictionary
        return resume_data # Return the part containing actual fields

    except requests.exceptions.HTTPError as http_err:
        # ... (keep existing detailed HTTP error handling) ...
        error_content = "Could not decode error response."
        try: error_content = http_err.response.json()
        except json.JSONDecodeError: error_content = http_err.response.text
        logger.error(f"HTTPError from Textkernel for {s3_key}: {http_err.response.status_code} {http_err.response.reason}. Response: {error_content}")
        return None
    # ... (keep other existing exception handling) ...
    except Exception as e:
        logger.error(f"Unexpected error in Textkernel service for {s3_key}: {e}", exc_info=True)
        return None