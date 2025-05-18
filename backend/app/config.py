import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
dotenv_path = os.path.join(basedir, '.env')

if os.path.exists(dotenv_path):
    print(f"INFO (config.py): Loading environment variables from: {dotenv_path}")
    load_dotenv(dotenv_path)
else:
    print(f"WARNING (config.py): .env file not found at {dotenv_path}. Relying on system environment variables.")


class Config:
    APP_NAME = os.getenv('APP_NAME', 'NEXONA')
    SECRET_KEY = os.getenv('SECRET_KEY', 'your_default_secret_key_123!')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = os.getenv('SQLALCHEMY_ECHO', 'False').lower() in ('true', '1', 't')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'postgresql://user:pass@host:port/db')

    # Celery Configuration (Changed to UPPERCASE)
    CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://redis:6379/0')
    CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://redis:6379/0')
    CELERY_TIMEZONE = os.getenv('CELERY_TIMEZONE', 'UTC') # Αυτό ήταν ήδη ΟΚ
    TASK_ALWAYS_EAGER = os.getenv('CELERY_TASK_ALWAYS_EAGER', 'False').lower() in ('true', '1', 't') # Για Celery 5+ συχνά CELERY_TASK_ALWAYS_EAGER
    TASK_EAGER_PROPAGATES = os.getenv('CELERY_TASK_EAGER_PROPAGATES', 'False').lower() in ('true', '1', 't') # CELERY_TASK_EAGER_PROPAGATES

    # Mail Configuration
    MAIL_SERVER = os.getenv('MAIL_SERVER')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'True').lower() in ('true', '1', 't')
    MAIL_USE_SSL = os.getenv('MAIL_USE_SSL', 'False').lower() in ('true', '1', 't')
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', '"NEXONA App" <noreply@example.com>')
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


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = os.getenv('SQLALCHEMY_ECHO', 'True').lower() in ('true', '1', 't')
    MAIL_DEBUG = True
    MAIL_SUPPRESS_SEND = os.getenv('MAIL_SUPPRESS_SEND', 'True').lower() in ('true', '1', 't')
    # Αν θέλεις να τρέχουν τα tasks συγχρονικά για ευκολότερο debug στο development:
    # TASK_ALWAYS_EAGER = True
    # TASK_EAGER_PROPAGATES = True


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.getenv('TEST_DATABASE_URL', 'sqlite:///:memory:')
    TASK_ALWAYS_EAGER = True
    TASK_EAGER_PROPAGATES = True
    MAIL_SUPPRESS_SEND = True
    WTF_CSRF_ENABLED = False


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_ECHO = False
    MAIL_DEBUG = False
    MAIL_SUPPRESS_SEND = False


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
        print(f"Warning: Config name '{config_name}' not found in config_by_name. Falling back to 'default'.")
        config_obj = config_by_name['default']
    return config_obj