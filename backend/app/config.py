# backend/app/config.py

import os
from dotenv import load_dotenv
import logging
import json

# Configure basic logging
config_logger = logging.getLogger(__name__)
# Set level to DEBUG temporarily to see dotenv verbose output if needed
# logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Determine base directory (assuming config.py is in /backend/app/)
basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
dotenv_path = os.path.join(basedir, '.env')

config_logger.info(f"Config: Determined .env path: {dotenv_path}")
config_logger.info(f"Config: Checking if .env file exists at path: {os.path.exists(dotenv_path)}")

# Load the .env file (verbose=True helps debug loading issues)
loaded = load_dotenv(dotenv_path=dotenv_path, verbose=True, override=True) # override=True ensures env vars take precedence if set elsewhere

config_logger.info(f"Config: load_dotenv result (found and loaded?): {loaded}")
mail_debug_env_value = os.environ.get('MAIL_DEBUG')
config_logger.info(f"Config: Value of MAIL_DEBUG directly from os.environ after load_dotenv: '{mail_debug_env_value}' (Type: {type(mail_debug_env_value)})")

# Helper function for boolean conversion
def _is_truthy(val):
    if val is None: return False
    return str(val).lower() in ('true', '1', 't', 'y', 'yes')

class Config:
    """Base configuration settings, loading from environment variables."""

    # --- Core Flask Settings ---
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a-very-insecure-default-secret-key-replace-me' # MUST BE REPLACED

    # --- Database Configuration ---
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'fallback_app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- Celery Configuration ---
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL') or 'redis://redis:6379/0'
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND') or 'redis://redis:6379/0'

    # --- AWS / S3 Configuration ---
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
    S3_BUCKET = os.environ.get('S3_BUCKET') # Use S3_BUCKET as in .env
    S3_REGION = os.environ.get('S3_REGION') # Use S3_REGION as in .env

    # --- Textkernel Configuration ---
    TEXTKERNEL_API_KEY = os.environ.get('TEXTKERNEL_API_KEY')
    TEXTKERNEL_ACCOUNT_ID = os.environ.get('TEXTKERNEL_ACCOUNT_ID')
    TEXTKERNEL_BASE_ENDPOINT = os.environ.get('TEXTKERNEL_BASE_ENDPOINT')

    # --- Email Configuration ---
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or None
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587) # Default to 587 if not set
    MAIL_USE_TLS = _is_truthy(os.environ.get('MAIL_USE_TLS', 'False')) # Default False if not set
    MAIL_USE_SSL = _is_truthy(os.environ.get('MAIL_USE_SSL', 'False')) # Default False if not set
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME') or None
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') or None
    MAIL_SENDER = os.environ.get('MAIL_SENDER', '"NEXONA App" <noreply@example.com>') # Default sender
    MAIL_DEFAULT_SENDER = MAIL_SENDER # Use the same for default sender

    # Load MAIL_DEBUG (Defaults to True if not set in .env, safer for dev)
    MAIL_DEBUG = _is_truthy(os.environ.get('MAIL_DEBUG', 'True'))
    # Set suppress based on the evaluated boolean MAIL_DEBUG value
    MAIL_SUPPRESS_SEND = MAIL_DEBUG
    config_logger.info(f"Config Class: MAIL_DEBUG evaluated to: {MAIL_DEBUG}") # Log evaluated value
    config_logger.info(f"Config Class: MAIL_SUPPRESS_SEND set to: {MAIL_SUPPRESS_SEND}")
    # --- END Email Configuration ---

    # --- Application Settings ---
    APP_NAME = os.environ.get('APP_NAME') or 'NEXONA'
    APP_BASE_URL = os.environ.get('APP_BASE_URL') or 'http://localhost:5000' # Default backend URL
    # --- END Application Settings ---

# --- Development Configuration ---
class DevelopmentConfig(Config):
    DEBUG = True # Enable Flask debug mode
    # SQLALCHEMY_ECHO = True # Uncomment to see SQL queries
    # Ensure MAIL_DEBUG is True, even if .env somehow had False
    MAIL_DEBUG = True
    MAIL_SUPPRESS_SEND = True

# --- Production Configuration ---
class ProductionConfig(Config):
    DEBUG = False
    # Ensure MAIL_DEBUG is False for production
    MAIL_DEBUG = False
    MAIL_SUPPRESS_SEND = False
    # Override APP_BASE_URL if not set via environment for production
    APP_BASE_URL = os.environ.get('APP_BASE_URL') or 'https://your.production.backend.domain.com' # Replace with actual domain

# --- Config Dictionary ---
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig # Default to development
}