# backend/app/config.py
import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
dotenv_path = os.path.join(basedir, '.env')

if os.path.exists(dotenv_path):
    print(f"INFO (config.py): Loading environment variables from: {dotenv_path}")
    load_dotenv(dotenv_path)
else:
    print(
        f"WARNING (config.py): .env file not found at {dotenv_path}. Relying on system environment variables or defaults.")


class Config:
    APP_NAME = os.getenv('APP_NAME', 'NEXONA')
    SECRET_KEY = os.getenv('SECRET_KEY', 'your_default_secret_key_123!')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = os.getenv('SQLALCHEMY_ECHO', 'False').lower() in ('true', '1', 't')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'postgresql://user:pass@host:port/db')

    # *** ΠΡΟΣΘΗΚΕΣ ΓΙΑ url_for() ΕΚΤΟΣ REQUEST CONTEXT ***
    SERVER_NAME = os.getenv('SERVER_NAME')  # Π.χ., localhost:5001 για development
    APPLICATION_ROOT = os.getenv('APPLICATION_ROOT', '/')
    PREFERRED_URL_SCHEME = os.getenv('PREFERRED_URL_SCHEME', 'http')  # 'https' για production
    # *** ΤΕΛΟΣ ΠΡΟΣΘΗΚΩΝ ***

    # Celery Configuration
    CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://redis:6379/0')
    CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://redis:6379/0')
    CELERY_TIMEZONE = os.getenv('CELERY_TIMEZONE', 'UTC')
    CELERY_TASK_ALWAYS_EAGER = os.getenv('CELERY_TASK_ALWAYS_EAGER', 'False').lower() in ('true', '1', 't')
    CELERY_TASK_EAGER_PROPAGATES = os.getenv('CELERY_TASK_EAGER_PROPAGATES', 'False').lower() in ('true', '1', 't')

    # Mail Configuration
    MAIL_SERVER = os.getenv('MAIL_SERVER')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'True').lower() in ('true', '1', 't')
    MAIL_USE_SSL = os.getenv('MAIL_USE_SSL', 'False').lower() in ('true', '1', 't')
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', '"NEXONA ATS" <noreply@yourdomain.com>')
    MAIL_DEBUG = os.getenv('MAIL_DEBUG', 'True').lower() in ('true', '1', 't')
    MAIL_SUPPRESS_SEND = os.getenv('MAIL_SUPPRESS_SEND', 'False').lower() in ('true', '1', 't')

    # AWS S3 Configuration
    S3_BUCKET = os.getenv('S3_BUCKET')
    S3_REGION = os.getenv('S3_REGION')
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
    S3_ENDPOINT_URL = os.getenv('S3_ENDPOINT_URL')

    # Textkernel Configuration
    TEXTKERNEL_ACCOUNT_ID = os.getenv('TEXTKERNEL_ACCOUNT_ID')
    TEXTKERNEL_API_KEY = os.getenv('TEXTKERNEL_API_KEY')
    TEXTKERNEL_BASE_ENDPOINT = os.getenv('TEXTKERNEL_BASE_ENDPOINT', 'https://api.eu.textkernel.com/tx/v10/')
    TEXTKERNEL_ENABLED = os.getenv('TEXTKERNEL_ENABLED', 'True').lower() in ('true', '1', 't')

    # CORS Configuration
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*')

    # Logging Level
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()

    # Frontend URL
    FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:5173')

    # Timezone, Tokens & Interview Settings
    LOCAL_TIMEZONE = os.getenv('LOCAL_TIMEZONE', 'Europe/Athens')
    INTERVIEW_TOKEN_EXPIRATION_DAYS = int(os.getenv('INTERVIEW_TOKEN_EXPIRATION_DAYS', 7))
    INTERVIEW_CANCELLATION_THRESHOLD_HOURS = int(os.getenv('INTERVIEW_CANCELLATION_THRESHOLD_HOURS', 12))
    MIN_INTERVIEW_REMINDER_LEAD_TIME = int(os.getenv('MIN_INTERVIEW_REMINDER_LEAD_TIME', 15))
    MAX_INTERVIEW_REMINDER_LEAD_TIME = int(os.getenv('MAX_INTERVIEW_REMINDER_LEAD_TIME', 2 * 24 * 60))


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = os.getenv('SQLALCHEMY_ECHO', 'True').lower() in ('true', '1', 't')
    MAIL_DEBUG = True
    MAIL_SUPPRESS_SEND = os.getenv('MAIL_SUPPRESS_SEND', 'True').lower() in ('true', '1', 't')

    # Για development, ορίζουμε το SERVER_NAME εδώ αν δεν υπάρχει στο .env
    SERVER_NAME = os.getenv('SERVER_NAME', 'localhost:5001')  # <--- ΣΗΜΑΝΤΙΚΗ ΠΡΟΣΘΗΚΗ ΓΙΑ DEVELOPMENT
    PREFERRED_URL_SCHEME = os.getenv('PREFERRED_URL_SCHEME', 'http')  # <--- ΣΗΜΑΝΤΙΚΗ ΠΡΟΣΘΗΚΗ ΓΙΑ DEVELOPMENT

    CELERY_TASK_ALWAYS_EAGER = False
    CELERY_TASK_EAGER_PROPAGATES = False
    LOG_LEVEL = os.getenv('LOG_LEVEL_DEV', 'DEBUG').upper()


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.getenv('TEST_DATABASE_URL', 'sqlite:///:memory:')
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True
    MAIL_SUPPRESS_SEND = True
    WTF_CSRF_ENABLED = False
    DEBUG = True
    LOG_LEVEL = 'DEBUG'
    SERVER_NAME = 'localhost.test'  # Χρειάζεται για tests που κάνουν url_for με _external=True
    PREFERRED_URL_SCHEME = 'http'


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_ECHO = False
    MAIL_DEBUG = False
    MAIL_SUPPRESS_SEND = False
    CELERY_TASK_ALWAYS_EAGER = False
    CELERY_TASK_EAGER_PROPAGATES = False
    LOG_LEVEL = os.getenv('LOG_LEVEL_PROD', 'INFO').upper()
    # Σε production, το SERVER_NAME και PREFERRED_URL_SCHEME πρέπει να ρυθμιστούν σωστά
    # μέσω environment variables ή απευθείας εδώ.
    SERVER_NAME = os.getenv('SERVER_NAME')  # Πρέπει να οριστεί στο περιβάλλον του server
    PREFERRED_URL_SCHEME = os.getenv('PREFERRED_URL_SCHEME', 'https')  # Συνήθως https σε production


config_by_name = dict(
    development=DevelopmentConfig,
    testing=TestingConfig,
    production=ProductionConfig,
    default=DevelopmentConfig
)


def get_config(config_name=None):
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'default')
    config_obj = config_by_name.get(config_name)
    if not config_obj:
        print(
            f"WARNING (config.py): Config name '{config_name}' not found in config_by_name. Falling back to 'default' (DevelopmentConfig).")
        config_obj = config_by_name['default']
    return config_obj