# backend/config.py

import os
from dotenv import load_dotenv
import logging # Import logging
import json # For pretty printing config later if needed

# Configure basic logging for this specific file/module during import
# This ensures these messages appear even before Flask's logger is fully set up
config_logger = logging.getLogger(__name__) # Use __name__ for logger name
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s') # Basic format

# Determine the base directory of the 'backend' folder
# Assumes config.py is in /backend/app/
basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Construct the path to the .env file located in the base 'backend' directory
dotenv_path = os.path.join(basedir, '.env')

# --- ADDED: Log before loading ---
config_logger.info(f"Config: Determined .env path: {dotenv_path}")
config_logger.info(f"Config: Checking if .env file exists at path: {os.path.exists(dotenv_path)}")
# ---

# Load the .env file
# Use verbose=True to get debug output from dotenv itself
loaded = load_dotenv(dotenv_path=dotenv_path, verbose=True)

# --- ADDED: Log after loading ---
config_logger.info(f"Config: load_dotenv result (found and loaded?): {loaded}")
# Check the critical environment variable DIRECTLY from os.environ immediately after loading
mail_debug_env_value = os.environ.get('MAIL_DEBUG')
config_logger.info(f"Config: Value of MAIL_DEBUG directly from os.environ after load_dotenv: '{mail_debug_env_value}' (Type: {type(mail_debug_env_value)})")
# --- END LOGGING ---


# Helper function to reliably convert env var strings to boolean True
def _is_truthy(val):
    """Converts a string environment variable to a boolean."""
    if val is None: return False
    return str(val).lower() in ('true', '1', 't', 'y', 'yes')

class Config:
    """Base configuration settings, loading from environment variables."""

    # --- Core Flask Settings ---
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a-very-insecure-default-secret-key'

    # --- Database Configuration ---
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'fallback_app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- Celery Configuration ---
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL') or 'redis://localhost:6379/0'
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND') or 'redis://localhost:6379/0'

    # --- AWS / S3 Configuration ---
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
    S3_BUCKET = os.environ.get('S3_BUCKET')
    S3_REGION = os.environ.get('S3_REGION')

    # --- Textkernel Configuration ---
    TEXTKERNEL_API_KEY = os.environ.get('TEXTKERNEL_API_KEY')
    TEXTKERNEL_ACCOUNT_ID = os.environ.get('TEXTKERNEL_ACCOUNT_ID')
    TEXTKERNEL_BASE_ENDPOINT = os.environ.get('TEXTKERNEL_BASE_ENDPOINT')

    # --- Email Configuration ---
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or None
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 25)
    MAIL_USE_TLS = _is_truthy(os.environ.get('MAIL_USE_TLS', 'false'))
    MAIL_USE_SSL = _is_truthy(os.environ.get('MAIL_USE_SSL', 'false'))
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME') or None
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') or None
    MAIL_SENDER = os.environ.get('MAIL_SENDER', '"CV Manager App" <noreply@example.com>')

    # Use helper function for MAIL_DEBUG for robust boolean conversion
    MAIL_DEBUG = _is_truthy(os.environ.get('MAIL_DEBUG', 'false'))
    # Set suppress based on the evaluated boolean MAIL_DEBUG value
    MAIL_SUPPRESS_SEND = MAIL_DEBUG
    # --- END Email Configuration ---