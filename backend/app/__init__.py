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

# --- ΣΩΣΤΗ ΕΙΣΑΓΩΓΗ: Το config.py είναι ένα επίπεδο πάνω ---
# Χρησιμοποιούμε sys.path modification ή PYTHONPATH για να το βρει το Python.
# Εναλλακτικά, αν το backend/ είναι στο PYTHONPATH, τότε το 'from config import ...' δουλεύει.
# Για απλότητα, αν το config.py είναι ΠΑΝΤΑ ένα επίπεδο πάνω, μπορούμε να το κάνουμε έτσι:
import sys
# Προσθέτουμε τον γονικό φάκελο (backend/) στο sys.path
# ώστε να μπορούμε να κάνουμε import το 'config' module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import Config as DefaultConfigClass # Εισάγουμε την κλάση Config από το backend/config.py
# Αφαιρούμε την προσθήκη από το path μετά την εισαγωγή για να μην επηρεάζει άλλα imports
sys.path.pop(0)
# --- ΤΕΛΟΣ ΣΩΣΤΗΣ ΕΙΣΑΓΩΓΗΣ ---


db = SQLAlchemy()
migrate = Migrate()
cors = CORS()
mail = Mail()
login_manager = LoginManager()
login_manager.login_view = 'api.login' # 'api' είναι το όνομα του Blueprint

# Initialize Celery - Broker/Backend URLs are now set directly from app.config
celery = Celery(__name__,
                include=['tasks.parsing', 'tasks.communication', 'tasks.reminders'])

@login_manager.user_loader
def load_user(user_id):
    from app.models import User # Import here to avoid circularity
    try:
        return User.query.get(int(user_id))
    except:
        return None

def create_app(config_class_override=None): # Η παράμετρος είναι η κλάση config
    app = Flask(__name__)

    # --- ΦΟΡΤΩΣΗ CONFIG ---
    # Χρησιμοποιούμε την override αν δόθηκε, αλλιώς την DefaultConfigClass
    config_to_load = config_class_override if config_class_override else DefaultConfigClass
    app.config.from_object(config_to_load)
    # --- ΤΕΛΟΣ ΦΟΡΤΩΣΗΣ CONFIG ---

    # Startup Logging
    try:
        startup_logger = logging.getLogger(f"{__name__}.startup_config_check")
        if not startup_logger.hasHandlers():
            startup_logger.setLevel(logging.INFO)
            startup_handler = logging.StreamHandler()
            startup_logger.addHandler(startup_handler)
            startup_logger.propagate = False

        mail_debug_val = app.config.get('MAIL_DEBUG')
        mail_suppress_val = app.config.get('MAIL_SUPPRESS_SEND')
        startup_logger.info(f"WEB APP STARTUP (app/__init__): MAIL_DEBUG={mail_debug_val}, MAIL_SUPPRESS_SEND={mail_suppress_val}")
    except Exception as log_err:
        print(f"Warning: Error setting up startup config logger in app/__init__.py: {log_err}")

    # Standard Logging Setup for Flask app logger
    if not app.debug and not app.testing:
        if not app.logger.hasHandlers():
            stream_handler = logging.StreamHandler()
            stream_handler.setLevel(logging.INFO)
            app.logger.addHandler(stream_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('CV Manager App Starting Up (from app/__init__.py)...')

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    cors.init_app(app, supports_credentials=True, origins=app.config.get('CORS_ORIGINS', '*'))
    mail.init_app(app)
    login_manager.init_app(app)

    # Update Celery configuration from Flask app config
    celery_config_updates = {
        'broker_url': app.config.get('CELERY_BROKER_URL'),
        'result_backend': app.config.get('CELERY_RESULT_BACKEND'),
        'task_always_eager': app.config.get('CELERY_TASK_ALWAYS_EAGER', False),
        'task_eager_propagates': app.config.get('CELERY_TASK_EAGER_PROPAGATES', False),
        'beat_schedule': {
            'check-interview-reminders-every-minute': {
                'task': 'tasks.reminders.check_upcoming_interviews',
                'schedule': 60.0,
            },
        },
        'timezone': app.config.get('CELERY_TIMEZONE', 'UTC')
    }
    celery.conf.update(**celery_config_updates)

    # Celery ContextTask
    class ContextTask(Task):
         def __call__(self, *args, **kwargs):
             with app.app_context():
                 return self.run(*args, **kwargs)
    celery.Task = ContextTask

    # Register Blueprints
    from app.api import api_bp
    app.register_blueprint(api_bp)

    # Basic Health Check Route
    @app.route('/health')
    def health_check():
        return "OK", 200

    return app