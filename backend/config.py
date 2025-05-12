# backend/config.py
import os
# Removed dotenv import: from dotenv import load_dotenv
import logging
import json # Keep for potential future use

# Basic logging setup for this module if needed elsewhere
config_logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s') # Configure in app/__init__ instead

# --- Removed dotenv loading ---
# basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
# dotenv_path = os.path.join(basedir, '.env')
# loaded = load_dotenv(dotenv_path=dotenv_path, verbose=True)
# config_logger.info(f"Config: load_dotenv result (found and loaded?): {loaded}")
# --- End Removed dotenv loading ---

# Helper function to interpret boolean environment variables
def _is_truthy(val):
    if val is None: return False
    return str(val).lower() in ('true', '1', 't', 'y', 'yes')

class Config:
    # --- General Flask Settings ---
    # Read SECRET_KEY from environment, fallback to insecure default only for dev
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a-very-insecure-default-secret-key'
    # Set max content length for uploads (e.g., 16MB)
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))

    # --- Database Settings ---
    # Read DATABASE_URL directly from environment set by Docker Compose env_file
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    # Disable modification tracking unless needed (saves resources)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Optional: Add engine options if needed
    # SQLALCHEMY_ENGINE_OPTIONS = { "pool_pre_ping": True }

    # --- Celery Settings ---
    # Read Broker/Backend URLs directly from environment
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL')
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND')

    # --- AWS S3 Settings ---
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
    S3_BUCKET = os.environ.get('S3_BUCKET')
    S3_REGION = os.environ.get('S3_REGION')

    # --- Textkernel Settings ---
    TEXTKERNEL_API_KEY = os.environ.get('TEXTKERNEL_API_KEY')
    TEXTKERNEL_ACCOUNT_ID = os.environ.get('TEXTKERNEL_ACCOUNT_ID')
    TEXTKERNEL_BASE_ENDPOINT = os.environ.get('TEXTKERNEL_BASE_ENDPOINT')

    # --- Flask-Mail Settings ---
    # Read directly from environment, provide defaults mainly for local testing
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or None
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 25)
    MAIL_USE_TLS = _is_truthy(os.environ.get('MAIL_USE_TLS', 'false'))
    MAIL_USE_SSL = _is_truthy(os.environ.get('MAIL_USE_SSL', 'false'))
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME') or None
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') or None
    MAIL_SENDER = os.environ.get('MAIL_SENDER', '"CV Manager App" <noreply@example.com>')
    # MAIL_DEBUG controls console output vs actual sending
    MAIL_DEBUG = _is_truthy(os.environ.get('MAIL_DEBUG', 'false'))
    # MAIL_SUPPRESS_SEND directly mirrors MAIL_DEBUG for simplicity
    MAIL_SUPPRESS_SEND = MAIL_DEBUG

    # --- CORS Settings (Optional) ---
    # Example: Allow specific frontend origin in production
    # CORS_ORIGINS = os.environ.get('CORS_ORIGINS', 'http://localhost:5173') # Read from env or default

# --- Sanity Check (Optional): Ensure required variables are present ---
# You could add checks here to log warnings or raise errors if essential
# environment variables like DATABASE_URL, S3_BUCKET, etc., are missing.
# Example:
# if not Config.DATABASE_URL:
#     config_logger.critical("FATAL ERROR: DATABASE_URL environment variable not set.")
#     # raise EnvironmentError("DATABASE_URL must be set") # Optional: stop startup
# if not Config.SECRET_KEY or Config.SECRET_KEY == 'a-very-insecure-default-secret-key':
#      config_logger.warning("WARNING: SECRET_KEY is not set or is insecure. Set a strong SECRET_KEY environment variable.")