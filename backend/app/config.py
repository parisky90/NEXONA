# backend/app/config.py
import os
from dotenv import load_dotenv
import logging
import json  # Δεν χρησιμοποιείται εδώ, αλλά μπορεί να είναι χρήσιμο για debugging

# Configure basic logging
config_logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Determine base directory (config.py is in /backend/app/)
# So, basedir should be /backend/
basedir = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..'))  # Αυτό πάει ένα επίπεδο πάνω από το app/ δηλαδή στο backend/
dotenv_path = os.path.join(basedir, '.env')  # Ψάχνει το .env στο backend/

config_logger.info(f"Config: Determined .env path: {dotenv_path}")
config_logger.info(f"Config: Checking if .env file exists at path: {os.path.exists(dotenv_path)}")

loaded = load_dotenv(dotenv_path=dotenv_path, verbose=True, override=True)

config_logger.info(f"Config: load_dotenv result (found and loaded?): {loaded}")
mail_debug_env_value = os.environ.get('MAIL_DEBUG')
config_logger.info(
    f"Config: Value of MAIL_DEBUG directly from os.environ after load_dotenv: '{mail_debug_env_value}' (Type: {type(mail_debug_env_value)})")


def _is_truthy(val):
    if val is None: return False
    return str(val).lower() in ('true', '1', 't', 'y', 'yes')


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a-very-insecure-default-secret-key-replace-me'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
                              'sqlite:///' + os.path.join(basedir, 'fallback_app.db')  # Fallback in backend/
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL') or 'redis://redis:6379/0'
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND') or 'redis://redis:6379/0'
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
    S3_BUCKET = os.environ.get('S3_BUCKET')
    S3_REGION = os.environ.get('S3_REGION')
    TEXTKERNEL_API_KEY = os.environ.get('TEXTKERNEL_API_KEY')
    TEXTKERNEL_ACCOUNT_ID = os.environ.get('TEXTKERNEL_ACCOUNT_ID')
    TEXTKERNEL_BASE_ENDPOINT = os.environ.get('TEXTKERNEL_BASE_ENDPOINT')
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or None
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = _is_truthy(os.environ.get('MAIL_USE_TLS', 'False'))
    MAIL_USE_SSL = _is_truthy(os.environ.get('MAIL_USE_SSL', 'False'))
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME') or None
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') or None
    MAIL_SENDER = os.environ.get('MAIL_SENDER', '"NEXONA App" <noreply@example.com>')
    MAIL_DEFAULT_SENDER = MAIL_SENDER
    MAIL_DEBUG = _is_truthy(os.environ.get('MAIL_DEBUG', 'True'))
    MAIL_SUPPRESS_SEND = MAIL_DEBUG  # Set suppress based on the evaluated boolean MAIL_DEBUG
    APP_NAME = os.environ.get('APP_NAME') or 'NEXONA'
    APP_BASE_URL = os.environ.get('APP_BASE_URL') or 'http://localhost:5000'
    # CORS Settings from .env or defaults
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*')  # Default to allow all
    CORS_SUPPORTS_CREDENTIALS = _is_truthy(os.environ.get('CORS_SUPPORTS_CREDENTIALS', 'True'))
    CORS_EXPOSE_HEADERS_CSV = os.environ.get('CORS_EXPOSE_HEADERS')  # e.g. "Content-Type,X-CSRFToken"
    if CORS_EXPOSE_HEADERS_CSV:
        CORS_EXPOSE_HEADERS = [h.strip() for h in CORS_EXPOSE_HEADERS_CSV.split(',')]
    else:
        CORS_EXPOSE_HEADERS = ["Content-Type", "X-CSRFToken"]  # Default list

    # Celery specific settings that might be good to have in config
    CELERY_TIMEZONE = os.environ.get('CELERY_TIMEZONE', 'UTC')
    CELERY_TASK_ALWAYS_EAGER = _is_truthy(os.environ.get('CELERY_TASK_ALWAYS_EAGER', 'False'))
    CELERY_TASK_EAGER_PROPAGATES = _is_truthy(
        os.environ.get('CELERY_TASK_EAGER_PROPAGATES', str(CELERY_TASK_ALWAYS_EAGER)))

    # Superadmin and Default Company Settings from Environment for seeding
    SUPERADMIN_EMAIL = os.environ.get('SUPERADMIN_EMAIL')
    SUPERADMIN_PASSWORD = os.environ.get('SUPERADMIN_PASSWORD')
    DEFAULT_COMPANY_NAME = os.environ.get('DEFAULT_COMPANY_NAME') or "Default Seed Company"


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = _is_truthy(os.environ.get('SQLALCHEMY_ECHO', 'False'))
    # Ensure MAIL_DEBUG is True for Development, overriding any .env setting if necessary for safety
    MAIL_DEBUG = True
    MAIL_SUPPRESS_SEND = True  # Always suppress emails in dev if MAIL_DEBUG is true
    # For development, Celery tasks can run eagerly
    CELERY_TASK_ALWAYS_EAGER = _is_truthy(os.environ.get('CELERY_TASK_ALWAYS_EAGER', 'False'))
    CELERY_TASK_EAGER_PROPAGATES = _is_truthy(
        os.environ.get('CELERY_TASK_EAGER_PROPAGATES', str(CELERY_TASK_ALWAYS_EAGER)))


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_ECHO = False
    # Ensure MAIL_DEBUG is False for production
    MAIL_DEBUG = False
    MAIL_SUPPRESS_SEND = False  # Emails should be sent in production
    APP_BASE_URL = os.environ.get('APP_BASE_URL') or 'https://your.production.backend.domain.com'
    CELERY_TASK_ALWAYS_EAGER = False  # Tasks should run via worker in production
    CELERY_TASK_EAGER_PROPAGATES = False


# --- Config Dictionary ---
config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}


# --- Function to get config based on FLASK_ENV or provided name ---
def get_config(config_name_str=None):
    """
    Retrieves a configuration class.
    If config_name_str is provided, it uses that.
    Otherwise, it uses the FLASK_ENV environment variable.
    Defaults to 'default' (which maps to DevelopmentConfig).
    """
    if config_name_str:
        selected_config_name = config_name_str
    else:
        selected_config_name = os.environ.get('FLASK_ENV', 'default')

    config_class = config_by_name.get(selected_config_name)
    if not config_class:
        config_logger.warning(
            f"Config name '{selected_config_name}' not found in config_by_name. Falling back to DevelopmentConfig."
        )
        config_class = DevelopmentConfig  # Fallback to a known default

    config_logger.info(
        f"get_config: Selected configuration '{config_class.__name__}' based on input/env '{selected_config_name}'.")
    return config_class


# --- AppConfig for direct import if needed, though get_config is preferred ---
# This will be evaluated when config.py is imported.
try:
    AppConfig = get_config()
except Exception as e:
    config_logger.critical(f"Failed to initialize AppConfig during import: {e}", exc_info=True)
    # Fallback to a base config to prevent complete failure if AppConfig is directly imported elsewhere
    # before the environment is fully set up for get_config (less likely with proper app factory).
    AppConfig = DevelopmentConfig 