# backend/config.py
import os
# Removed dotenv import: from dotenv import load_dotenv
import logging
import json # Keep for potential future use

config_logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def _is_truthy(val):
    if val is None: return False
    return str(val).lower() in ('true', '1', 't', 'y', 'yes')

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a-very-insecure-default-secret-key'
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL')
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND')
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
    MAIL_DEBUG = _is_truthy(os.environ.get('MAIL_DEBUG', 'true')) # Default True για dev
    MAIL_SUPPRESS_SEND = MAIL_DEBUG
    APP_NAME = os.environ.get('APP_NAME') or 'NEXONA' # Προσθήκη αν λείπει
    APP_BASE_URL = os.environ.get('APP_BASE_URL') or 'http://localhost:5000' # Προσθήκη αν λείπει

    # --- ΠΡΟΣΘΗΚΗ ΓΙΑ COMPANY DOMAINS ---
    COMPANY_DOMAINS = [domain.strip() for domain in (os.environ.get('COMPANY_DOMAINS') or '').split(',') if domain.strip()]
    # --- ΤΕΛΟΣ ΠΡΟΣΘΗΚΗΣ ---

# DevelopmentConfig και ProductionConfig (αν υπάρχουν) θα πρέπει να κληρονομούν από την Config
class DevelopmentConfig(Config):
    DEBUG = True
    # Εδώ μπορείς να κάνεις override συγκεκριμένες ρυθμίσεις για development
    # π.χ. MAIL_DEBUG = True (αν και το default της Config είναι ήδη True)

class ProductionConfig(Config):
    DEBUG = False
    MAIL_DEBUG = False # Σημαντικό για παραγωγή
    MAIL_SUPPRESS_SEND = False
    # Π.χ. APP_BASE_URL = os.environ.get('APP_BASE_URL') or 'https://your.production.domain.com'

# Το dictionary για την επιλογή config στο app/__init__.py
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}