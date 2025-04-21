# backend/celery_worker.py
import os
from app import create_app, celery
import logging
import json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

logger.info("--- Celery Worker Script Starting ---")

try:
    app = create_app()
    logger.info("Flask app created successfully for Celery worker.")

    # Debug logging for config
    try:
         logger.info("--- Worker Initial Config Check (Non-Sensitive) ---")
         config_to_log = {}; sensitive_keys = ['SECRET', 'PASSWORD', 'KEY']
         for key, value in app.config.items():
             is_sensitive = any(word in key.upper() for word in sensitive_keys)
             config_to_log[key] = '********' if is_sensitive else value
         logger.info(json.dumps(config_to_log, indent=2, default=str))
         mail_debug_val = app.config.get('MAIL_DEBUG'); mail_suppress_val = app.config.get('MAIL_SUPPRESS_SEND')
         logger.info(f"Value of MAIL_DEBUG read from config: {mail_debug_val} (Type: {type(mail_debug_val)})")
         logger.info(f"Value of MAIL_SUPPRESS_SEND read from config: {mail_suppress_val} (Type: {type(mail_suppress_val)})")
         logger.info("--- End Worker Initial Config Check ---")
    except Exception as config_log_err: logger.error(f"Error logging worker config: {config_log_err}", exc_info=True)

    app.app_context().push()
    logger.info("App context pushed for Celery worker main process.")

except Exception as create_err:
    logger.critical(f"FATAL: Failed to create Flask app for Celery worker: {create_err}", exc_info=True)
    raise create_err

logger.info("--- Celery Worker Script Setup Complete - Worker should start now ---")