# backend/config.py
import os
import logging

config_logger = logging.getLogger(__name__)


# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# Η παραπάνω γραμμή μπορεί να προκαλέσει διπλό logging αν το app/__init__.py κάνει ήδη setup.
# Ας την αφήσουμε σχολιασμένη προς το παρόν, καθώς το app/__init__.py φαίνεται να χειρίζεται το logging.

def _is_truthy(val):
    if val is None: return False
    return str(val).lower() in ('true', '1', 't', 'y', 'yes')


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a-very-insecure-default-secret-key-must-change'
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))  # 16MB

    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')  # Θα έρθει από το .env μέσω docker-compose
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL')  # Από .env
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND')  # Από .env

    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
    S3_BUCKET = os.environ.get('S3_BUCKET')
    S3_REGION = os.environ.get('S3_REGION')

    TEXTKERNEL_API_KEY = os.environ.get('TEXTKERNEL_API_KEY')
    TEXTKERNEL_ACCOUNT_ID = os.environ.get('TEXTKERNEL_ACCOUNT_ID')
    TEXTKERNEL_BASE_ENDPOINT = os.environ.get('TEXTKERNEL_BASE_ENDPOINT')

    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = _is_truthy(os.environ.get('MAIL_USE_TLS', 'True'))  # Default True για port 587
    MAIL_USE_SSL = _is_truthy(os.environ.get('MAIL_USE_SSL', 'False'))
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_SENDER = os.environ.get('MAIL_SENDER', '"NEXONA App" <noreply@example.com>')
    MAIL_DEFAULT_SENDER = MAIL_SENDER  # Flask-Mail < 0.10 used MAIL_DEFAULT_SENDER

    # MAIL_DEBUG και MAIL_SUPPRESS_SEND θα οριστούν στις DevelopmentConfig/ProductionConfig

    APP_NAME = os.environ.get('APP_NAME') or 'NEXONA'
    APP_BASE_URL = os.environ.get('APP_BASE_URL') or 'http://localhost:5001'  # Ταιριάζει με το docker-compose port

    # Superadmin and Default Company Settings from Environment
    SUPERADMIN_EMAIL = os.environ.get('SUPERADMIN_EMAIL')
    SUPERADMIN_PASSWORD = os.environ.get('SUPERADMIN_PASSWORD')
    DEFAULT_COMPANY_NAME = os.environ.get('DEFAULT_COMPANY_NAME') or "Default Seed Company"

    # --- ΠΡΟΣΘΗΚΗ ΓΙΑ COMPANY DOMAINS (αν το χρησιμοποιείς για αυτόματη ανάθεση εταιρείας κατά την εγγραφή) ---
    # COMPANY_DOMAINS = [domain.strip() for domain in (os.environ.get('COMPANY_DOMAINS') or '').split(',') if domain.strip()]


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = _is_truthy(os.environ.get('SQLALCHEMY_ECHO', 'False'))  # False by default, True to see SQL
    MAIL_DEBUG = _is_truthy(os.environ.get('MAIL_DEBUG', 'True'))
    MAIL_SUPPRESS_SEND = _is_truthy(
        os.environ.get('MAIL_SUPPRESS_SEND', str(MAIL_DEBUG)))  # Suppress if MAIL_DEBUG is true
    # For development, Celery tasks can run eagerly
    CELERY_TASK_ALWAYS_EAGER = _is_truthy(
        os.environ.get('CELERY_TASK_ALWAYS_EAGER', 'False'))  # Set to True to debug tasks locally without worker
    CELERY_TASK_EAGER_PROPAGATES = _is_truthy(
        os.environ.get('CELERY_TASK_EAGER_PROPAGATES', str(CELERY_TASK_ALWAYS_EAGER)))


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_ECHO = False
    MAIL_DEBUG = False
    MAIL_SUPPRESS_SEND = False  # Emails should be sent in production
    # APP_BASE_URL = os.environ.get('APP_BASE_URL') or 'https://your.production.domain.com' # Ensure this is set for production


# Config dictionary for create_app factory
config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig  # Default to development if FLASK_ENV is not set or recognized
}


# Function to get config based on FLASK_ENV
def get_config():
    flask_env = os.environ.get('FLASK_ENV', 'default')
    return config_by_name.get(flask_env, DevelopmentConfig)


# For direct import (e.g. by create_admin.py if it doesn't use create_app with env selection)
# This ensures AppConfig is always a valid config class.
# However, create_app in your __init__.py already handles selection.
AppConfig = get_config()