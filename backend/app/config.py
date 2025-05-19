# backend/app/config.py
import os
from dotenv import load_dotenv

# Προσδιορισμός της διαδρομής του .env αρχείου ένα επίπεδο πάνω από τον φάκελο 'app'
# δηλαδή στον βασικό κατάλογο του backend.
basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))  # Αυτό δείχνει στο backend/
dotenv_path = os.path.join(basedir, '.env')

if os.path.exists(dotenv_path):
    print(f"INFO (config.py): Loading environment variables from: {dotenv_path}")
    load_dotenv(dotenv_path)
else:
    print(
        f"WARNING (config.py): .env file not found at {dotenv_path}. Relying on system environment variables or defaults.")


class Config:
    APP_NAME = os.getenv('APP_NAME', 'NEXONA')
    SECRET_KEY = os.getenv('SECRET_KEY', 'your_default_secret_key_123!')  # Άλλαξε το αυτό σε production!
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = os.getenv('SQLALCHEMY_ECHO', 'False').lower() in ('true', '1', 't')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'postgresql://user:pass@host:port/db')  # Άλλαξε τα defaults

    # Celery Configuration
    CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL',
                                  'redis://redis:6379/0')  # Το 'redis' είναι το όνομα του service στο docker-compose
    CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://redis:6379/0')
    CELERY_TIMEZONE = os.getenv('CELERY_TIMEZONE', 'UTC')  # Συνιστάται η Celery να δουλεύει πάντα με UTC

    # Για Celery 5+, τα ονόματα των settings είναι με το prefix CELERY_
    CELERY_TASK_ALWAYS_EAGER = os.getenv('CELERY_TASK_ALWAYS_EAGER', 'False').lower() in ('true', '1', 't')
    CELERY_TASK_EAGER_PROPAGATES = os.getenv('CELERY_TASK_EAGER_PROPAGATES', 'False').lower() in ('true', '1', 't')
    # Αν χρησιμοποιείς παλαιότερη έκδοση Celery (<5), μπορεί να χρειαστείς TASK_ALWAYS_EAGER κλπ.

    # Mail Configuration
    MAIL_SERVER = os.getenv('MAIL_SERVER')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'True').lower() in ('true', '1', 't')
    MAIL_USE_SSL = os.getenv('MAIL_USE_SSL', 'False').lower() in ('true', '1', 't')
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER',
                                    '"NEXONA ATS" <noreply@yourdomain.com>')  # Άλλαξε το yourdomain.com
    MAIL_DEBUG = os.getenv('MAIL_DEBUG', 'True').lower() in ('true', '1', 't')  # Συνήθως False σε production
    MAIL_SUPPRESS_SEND = os.getenv('MAIL_SUPPRESS_SEND', 'False').lower() in (
    'true', '1', 't')  # True για testing/dev χωρίς αποστολή

    # AWS S3 Configuration
    S3_BUCKET = os.getenv('S3_BUCKET')
    S3_REGION = os.getenv('S3_REGION')  # π.χ. 'eu-north-1'
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
    S3_ENDPOINT_URL = os.getenv('S3_ENDPOINT_URL')  # Για MinIO ή άλλα S3-compatible, αλλιώς None

    # Textkernel Configuration
    TEXTKERNEL_ACCOUNT_ID = os.getenv('TEXTKERNEL_ACCOUNT_ID')
    TEXTKERNEL_API_KEY = os.getenv('TEXTKERNEL_API_KEY')
    TEXTKERNEL_BASE_ENDPOINT = os.getenv('TEXTKERNEL_BASE_ENDPOINT',
                                         'https://api.eu.textkernel.com/tx/v10/')  # Ή όποιο είναι το δικό σου
    TEXTKERNEL_ENABLED = os.getenv('TEXTKERNEL_ENABLED', 'True').lower() in ('true', '1', 't')

    # CORS Configuration
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*')  # Σε production, όρισε συγκεκριμένα origins

    # Logging Level
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()

    # Frontend URL (χρήσιμο για τη δημιουργία links στα emails)
    FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:5173')  # Το port του Vite dev server

    # *** ΝΕΕΣ ΠΡΟΣΘΗΚΕΣ ΓΙΑ TIMEZONE, TOKENS ΚΑΙ ΡΥΘΜΙΣΕΙΣ ΣΥΝΕΝΤΕΥΞΕΩΝ ***
    LOCAL_TIMEZONE = os.getenv('LOCAL_TIMEZONE', 'Europe/Athens')
    INTERVIEW_TOKEN_EXPIRATION_DAYS = int(os.getenv('INTERVIEW_TOKEN_EXPIRATION_DAYS', 7))
    INTERVIEW_CANCELLATION_THRESHOLD_HOURS = int(os.getenv('INTERVIEW_CANCELLATION_THRESHOLD_HOURS', 12))
    MIN_INTERVIEW_REMINDER_LEAD_TIME = int(os.getenv('MIN_INTERVIEW_REMINDER_LEAD_TIME', 15))  # σε λεπτά
    MAX_INTERVIEW_REMINDER_LEAD_TIME = int(
        os.getenv('MAX_INTERVIEW_REMINDER_LEAD_TIME', 2 * 24 * 60))  # σε λεπτά (π.χ. 2 μέρες)
    # *** ΤΕΛΟΣ ΝΕΩΝ ΠΡΟΣΘΗΚΩΝ ***


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = os.getenv('SQLALCHEMY_ECHO', 'True').lower() in (
    'true', '1', 't')  # Περισσότερα logs από SQLAlchemy
    MAIL_DEBUG = True  # Περισσότερα logs από Flask-Mail
    MAIL_SUPPRESS_SEND = os.getenv('MAIL_SUPPRESS_SEND', 'True').lower() in (
    'true', '1', 't')  # Να μην στέλνονται email στο dev

    # Αν θέλεις να τρέχουν τα tasks συγχρονικά για ευκολότερο debug στο development:
    # Για Celery 5+
    CELERY_TASK_ALWAYS_EAGER = os.getenv('CELERY_TASK_ALWAYS_EAGER_DEV', 'True').lower() in ('true', '1', 't')
    CELERY_TASK_EAGER_PROPAGATES = os.getenv('CELERY_TASK_EAGER_PROPAGATES_DEV', 'True').lower() in ('true', '1', 't')
    LOG_LEVEL = os.getenv('LOG_LEVEL_DEV', 'DEBUG').upper()  # Πιο αναλυτικό logging στο dev


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.getenv('TEST_DATABASE_URL', 'sqlite:///:memory:')  # In-memory SQLite για tests
    # Για Celery 5+
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True
    MAIL_SUPPRESS_SEND = True  # Να μην στέλνονται email κατά τα tests
    WTF_CSRF_ENABLED = False  # Αν χρησιμοποιείς Flask-WTF forms
    DEBUG = True  # Μπορεί να θέλεις DEBUG=True για να βλέπεις καλύτερα τα exceptions στα tests
    LOG_LEVEL = 'DEBUG'


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_ECHO = False
    MAIL_DEBUG = False
    MAIL_SUPPRESS_SEND = False  # Να στέλνονται email σε production
    # Σε production, οι Celery tasks πρέπει να είναι ασύγχρονες
    CELERY_TASK_ALWAYS_EAGER = False
    CELERY_TASK_EAGER_PROPAGATES = False
    LOG_LEVEL = os.getenv('LOG_LEVEL_PROD', 'INFO').upper()
    # Βεβαιώσου ότι το SECRET_KEY και το DATABASE_URL είναι σωστά ρυθμισμένα στο .env για production


config_by_name = dict(
    development=DevelopmentConfig,
    testing=TestingConfig,
    production=ProductionConfig,
    default=DevelopmentConfig  # Το default αν δεν οριστεί το FLASK_ENV
)


def get_config(config_name=None):
    """
    Retrieves the configuration class based on the provided name or FLASK_ENV.
    """
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'default')  # Αν δεν δοθεί, παίρνει από FLASK_ENV, αλλιώς 'default'

    config_obj = config_by_name.get(config_name)
    if not config_obj:
        print(
            f"WARNING (config.py): Config name '{config_name}' not found in config_by_name. Falling back to 'default' (DevelopmentConfig).")
        config_obj = config_by_name['default']

    # print(f"DEBUG (config.py): Using configuration: {config_obj.__name__}") # Για έλεγχο ποιο config φορτώνεται
    return config_obj