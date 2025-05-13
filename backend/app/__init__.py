# backend/app/__init__.py
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from flask_mail import Mail
from flask_login import LoginManager
from celery import Celery, Task
import logging
import os
import sys

# --- Corrected config import ---
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from config import get_config
except ImportError as e:
    print(f"CRITICAL: Could not import 'get_config' from 'config'. Error: {e}")
    print(f"Sys.path: {sys.path}")
    raise
finally:
    if sys.path and sys.path[0] == os.path.abspath(os.path.join(os.path.dirname(__file__), '..')):
        sys.path.pop(0)
# --- End corrected config import ---

db = SQLAlchemy()
migrate = Migrate()
cors = CORS()
mail = Mail()
login_manager = LoginManager()
login_manager.login_view = 'api.login'  # 'api' is the Blueprint name (from api_bp.name)
login_manager.session_protection = "strong"

celery = Celery(__name__,
                include=['app.tasks.parsing_tasks',
                         'app.tasks.communication_tasks',
                         'app.tasks.reminder_tasks'])


@login_manager.user_loader
def load_user(user_id):
    from app.models import User
    try:
        return User.query.get(int(user_id))
    except ValueError:
        return None
    except Exception as e:
        current_app_logger = logging.getLogger(__name__)
        current_app_logger.error(f"Error loading user {user_id}: {e}", exc_info=True)
        return None


def create_app(config_name_or_class=None):
    app = Flask(__name__)

    # --- Load Config ---
    if isinstance(config_name_or_class, str):
        chosen_config = get_config()
        # app.logger.info(f"Loading configuration by name (FLASK_ENV or default): {os.environ.get('FLASK_ENV', 'default')}")
    elif config_name_or_class is not None and not isinstance(config_name_or_class, str):
        chosen_config = config_name_or_class
        # app.logger.info(f"Loading configuration from direct class: {config_name_or_class.__name__}")
    else:
        chosen_config = get_config()
        # app.logger.info(f"Loading configuration by FLASK_ENV or default: {os.environ.get('FLASK_ENV', 'default')}")

    app.config.from_object(chosen_config)
    # --- End Load Config ---

    # Startup Logging
    try:
        startup_logger = logging.getLogger(f"{app.name}.startup")  # Use app.name for logger
        if not startup_logger.hasHandlers():
            startup_logger.setLevel(logging.INFO)
            startup_handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            startup_handler.setFormatter(formatter)
            startup_logger.addHandler(startup_handler)
            startup_logger.propagate = False

        mail_debug_val = app.config.get('MAIL_DEBUG')
        mail_suppress_val = app.config.get('MAIL_SUPPRESS_SEND')
        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', 'NOT SET')
        if isinstance(db_uri, str) and "@" in db_uri:
            parts = db_uri.split('@')
            if ":" in parts[0]:
                creds_part = parts[0].split("://")[1]
                user_pass = creds_part.split(':')
                masked_db_uri = f"{parts[0].split('://')[0]}://{user_pass[0]}:********@{parts[1]}"
            else:
                masked_db_uri = db_uri
        else:
            masked_db_uri = db_uri

        startup_logger.info(f"NEXONA APP STARTUP (app/__init__):")
        startup_logger.info(f"  Config Loaded: {chosen_config.__name__}")
        startup_logger.info(f"  DEBUG Mode: {app.config.get('DEBUG')}")
        startup_logger.info(f"  SQLALCHEMY_DATABASE_URI: {masked_db_uri}")
        startup_logger.info(f"  MAIL_DEBUG: {mail_debug_val}, MAIL_SUPPRESS_SEND: {mail_suppress_val}")
        startup_logger.info(f"  CELERY_BROKER_URL: {app.config.get('CELERY_BROKER_URL')}")
    except Exception as log_err:
        print(f"Warning: Error setting up startup config logger in app/__init__.py: {log_err}")

    # Standard Logging Setup for Flask app logger
    if not app.debug and not app.testing:
        if not app.logger.hasHandlers():
            stream_handler = logging.StreamHandler(sys.stdout)
            stream_handler.setFormatter(logging.Formatter(
                '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
            ))
            app.logger.addHandler(stream_handler)
    app.logger.setLevel(logging.INFO if not app.debug else logging.DEBUG)
    app.logger.info('NEXONA Application Starting Up (Flask app logger)...')

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    cors_origins = app.config.get('CORS_ORIGINS', '*')
    if isinstance(cors_origins, str) and ',' in cors_origins:
        cors_origins = [origin.strip() for origin in cors_origins.split(',')]
    elif isinstance(cors_origins, str) and cors_origins != '*':
        cors_origins = [cors_origins]

    cors.init_app(app, supports_credentials=True, origins=cors_origins)
    mail.init_app(app)
    login_manager.init_app(app)

    # Update Celery configuration
    celery_config_updates = {
        'broker_url': app.config.get('CELERY_BROKER_URL'),
        'result_backend': app.config.get('CELERY_RESULT_BACKEND'),
        'task_always_eager': app.config.get('CELERY_TASK_ALWAYS_EAGER', False),
        'task_eager_propagates': app.config.get('CELERY_TASK_EAGER_PROPAGATES', False),
        'beat_schedule': {
            'check-interview-reminders-every-minute': {
                'task': 'app.tasks.reminder_tasks.check_upcoming_interviews',
                'schedule': 60.0,
            },
        },
        'timezone': app.config.get('CELERY_TIMEZONE', 'UTC')
    }
    celery.conf.update(**celery_config_updates)

    class ContextTask(Task):
        abstract = True

        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask

    # Register Blueprints
    from app.api import api_bp  # <--- Η ΔΙΟΡΘΩΣΗ ΕΙΝΑΙ ΕΔΩ
    app.register_blueprint(api_bp, url_prefix='/api/v1')

    @app.route('/health')
    def health_check():
        return "OK", 200

    return app