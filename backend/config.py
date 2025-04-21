# backend/config.py
import os
from dotenv import load_dotenv
import logging
import json

config_logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
dotenv_path = os.path.join(basedir, '.env')

config_logger.info(f"Config: Determined .env path: {dotenv_path}")
config_logger.info(f"Config: Checking if .env file exists at path: {os.path.exists(dotenv_path)}")
loaded = load_dotenv(dotenv_path=dotenv_path, verbose=True)
config_logger.info(f"Config: load_dotenv result (found and loaded?): {loaded}")
mail_debug_env_value = os.environ.get('MAIL_DEBUG')
config_logger.info(f"Config: Value of MAIL_DEBUG directly from os.environ after load_dotenv: '{mail_debug_env_value}' (Type: {type(mail_debug_env_value)})")

def _is_truthy(val):
    if val is None: return False
    return str(val).lower() in ('true', '1', 't', 'y', 'yes')

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a-very-insecure-default-secret-key'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'fallback_app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL') or 'redis://localhost:6379/0'
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND') or 'redis://localhost:6379/0'
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
    S3_BUCKET = os.environ.get('S3_BUCKET')
    S3_REGION = os.environ.get('S3_REGION')
    TEXTKERNEL_API_KEY = os.environ.get('TEXTKERNEL_API_KEY')
    TEXTKERNEL_ACCOUNT_ID = os.environ.get('TEXTKERNEL_ACCOUNT_ID')
    TEXTKERNEL_BASE_ENDPOINT = os.environ.get('TEXTKERNEL_BASE_ENDPOINT')
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or None
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 25)
    MAIL_USE_TLS = _is_truthy(os.environ.get('MAIL_USE_TLS', 'false'))
    MAIL_USE_SSL = _is_truthy(os.environ.get('MAIL_USE_SSL', 'false'))
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME') or None
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') or None
    MAIL_SENDER = os.environ.get('MAIL_SENDER', '"CV Manager App" <noreply@example.com>')
    MAIL_DEBUG = _is_truthy(os.environ.get('MAIL_DEBUG', 'false'))
    MAIL_SUPPRESS_SEND = MAIL_DEBUG
    # CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*') # Example for CORS config