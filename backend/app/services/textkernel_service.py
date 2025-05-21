# backend/app/services/textkernel_service.py

import requests
from flask import current_app
import logging
import json
import base64
from datetime import datetime, timezone as dt_timezone  # Changed timezone to dt_timezone for consistency

# Import the S3 service INSTANCE from the main app package
from app import s3_service_instance  # <<< ΑΛΛΑΓΗ ΕΔΩ

# Basic logger
logger = logging.getLogger(__name__)

# --- Constants ---
PARSER_ENDPOINT_PATH = "parser/resume"


def _get_tk_config():
    """Helper to retrieve Textkernel config."""
    config = {
        "api_key": current_app.config.get('TEXTKERNEL_API_KEY'),
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
        return {'error': 'Textkernel configuration or S3 key missing.'}  # Return a dict for consistency

    # 1. Download file content from S3
    logger.info(f"Downloading CV from S3 for parsing: {s3_key}")
    # file_bytes = s3_service.get_file_bytes(s3_key) # <<< ΠΑΛΙΑ ΛΑΘΟΣ ΚΛΗΣΗ
    file_bytes = s3_service_instance.get_file_bytes(s3_key)  # <<< ΣΩΣΤΗ ΚΛΗΣΗ ΜΕ ΤΟ INSTANCE
    if file_bytes is None:
        logger.error(f"Failed to download file {s3_key} from S3. Cannot parse.")
        return {'error': f'Failed to download S3 file {s3_key}'}  # Return a dict

    # 2. Encode file content as Base64 string
    try:
        base64_encoded_cv = base64.b64encode(file_bytes).decode('utf-8')
    except Exception as enc_err:
        logger.error(f"Failed to Base64 encode CV content for {s3_key}: {enc_err}")
        return {'error': f'Base64 encoding failed for {s3_key}'}  # Return a dict

    # 3. Get DocumentLastModified
    last_modified_date = datetime.now(dt_timezone.utc).strftime("%Y-%m-%d")  # Use dt_timezone

    # 4. Construct the API Request Payload
    request_payload = {
        "DocumentAsBase64String": base64_encoded_cv,
        "DocumentLastModified": last_modified_date
    }

    # 5. Construct Headers
    headers = {
        'accept': "application/json",
        'content-type': "application/json",
        'tx-accountid': tk_config["account_id"],
        'tx-servicekey': tk_config["api_key"],
    }

    # --- Make the API Call ---
    try:
        logger.info(f"Sending request to Textkernel ({tk_config['full_parser_endpoint']}) for S3 key: {s3_key}")
        response = requests.post(
            tk_config["full_parser_endpoint"],
            headers=headers,
            data=json.dumps(request_payload),
            timeout=120
        )
        response.raise_for_status()
        response_data = response.json()
        logger.info(f"Received successful response from Textkernel for S3 key: {s3_key}")

        parsed_value = response_data.get('Value')
        if parsed_value is None:
            logger.warning(f"Textkernel response OK for {s3_key}, but 'Value' key is missing.")
            return {'error': 'Parsing response from Textkernel missing "Value" key'}

        resume_data = parsed_value.get('ResumeData')
        if resume_data is None:
            logger.warning(f"Textkernel response OK for {s3_key}, but 'ResumeData' key is missing within 'Value'.")
            return {'error': 'Parsing response from Textkernel missing "ResumeData" key'}

        # Add a success flag or specific structure if needed by the calling task
        # For now, just returning resume_data as it was before, but now it should actually get here.
        return resume_data

    except requests.exceptions.HTTPError as http_err:
        error_content = "Could not decode error response."
        try:
            error_content = http_err.response.json()
        except json.JSONDecodeError:
            error_content = http_err.response.text
        logger.error(
            f"HTTPError from Textkernel for {s3_key}: {http_err.response.status_code} {http_err.response.reason}. Response: {error_content}")
        return {'error': f"Textkernel HTTPError {http_err.response.status_code}: {error_content}"}
    except requests.exceptions.RequestException as req_err:  # Catch other request errors like timeout, connection error
        logger.error(f"RequestException during Textkernel call for {s3_key}: {req_err}", exc_info=True)
        return {'error': f"Textkernel RequestException: {req_err}"}
    except Exception as e:
        logger.error(f"Unexpected error in Textkernel service for {s3_key}: {e}", exc_info=True)
        return {'error': f"Unexpected error in Textkernel service: {e}"}