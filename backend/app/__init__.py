# backend/app/__init__.py

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from flask_mail import Mail
from flask_login import LoginManager # Keep import even if auth disabled now
from celery import Celery, Task
# Assuming config.py is one level up from 'app' directory
from config import Config # Corrected import assuming standard structure
import logging
import os
import json

db = SQLAlchemy()
migrate = Migrate()
cors = CORS()
mail = Mail()
login_manager = LoginManager() # Keep init
login_manager.login_view = 'api.login' # Keep config, points to blueprint route

# Initialize Celery - Use new config keys directly where possible
# The include list tells Celery where to find tasks
celery = Celery(__name__,
                broker=Config.CELERY_BROKER_URL,
                backend=Config.CELERY_RESULT_BACKEND,
                include=['tasks.parsing', 'tasks.communication', 'tasks.reminders'])

# Keep user_loader for when Flask-Login is re-enabled
@login_manager.user_loader
def load_user(user_id):
    # Import inside function to avoid circular dependency
    from app.models import User # Corrected import assuming models.py is in 'app'
    try:
        return User.query.get(int(user_id))
    except:
        return None

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Optional: Log Mail Debug status on startup for confirmation
    try:
        startup_logger = logging.getLogger(f"{__name__}.startup_config_check")
        startup_logger.setLevel(logging.INFO)
        if not startup_logger.hasHandlers():
            startup_handler = logging.StreamHandler()
            # Optional: Add formatting to handler if desired
            # formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            # startup_handler.setFormatter(formatter)
            startup_logger.addHandler(startup_handler)

        mail_debug_val = app.config.get('MAIL_DEBUG')
        mail_suppress_val = app.config.get('MAIL_SUPPRESS_SEND')
        startup_logger.info(f"WEB APP STARTUP: MAIL_DEBUG={mail_debug_val}, MAIL_SUPPRESS_SEND={mail_suppress_val}")
    except Exception as log_err:
        # Prevent logging setup failure from crashing app start
        print(f"Warning: Error setting up startup config logger: {log_err}")


    # Standard Logging Setup
    if not app.debug and not app.testing:
        # Avoid adding duplicate handlers if called multiple times
        if not app.logger.hasHandlers():
            stream_handler = logging.StreamHandler()
            stream_handler.setLevel(logging.INFO)
            app.logger.addHandler(stream_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('CV Manager App Starting Up...')

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    # Configure CORS properly - Allow credentials and specify origin(s)
    # Use '*' only for development, replace with actual frontend URL in production
    cors.init_app(app, supports_credentials=True, origins=app.config.get('CORS_ORIGINS', '*'))
    mail.init_app(app)
    login_manager.init_app(app) # Keep LoginManager init for future use

    # --- Update Celery configuration from Flask app config using NEW keys ---
    # Celery 5+ uses lowercase keys without the CELERY_ prefix
    celery_config_updates = {
        'broker_url': app.config['CELERY_BROKER_URL'],
        'result_backend': app.config['CELERY_RESULT_BACKEND'],
        # Pass Mail settings needed by tasks (these are custom, not core Celery keys)
        'MAIL_SERVER': app.config.get('MAIL_SERVER'),
        'MAIL_PORT': app.config.get('MAIL_PORT'),
        'MAIL_USE_TLS': app.config.get('MAIL_USE_TLS'),
        'MAIL_USE_SSL': app.config.get('MAIL_USE_SSL'),
        'MAIL_USERNAME': app.config.get('MAIL_USERNAME'),
        'MAIL_PASSWORD': app.config.get('MAIL_PASSWORD'), # Ensure tasks handle sensitive data carefully
        'MAIL_SENDER': app.config.get('MAIL_SENDER'),
        'MAIL_DEBUG': app.config.get('MAIL_DEBUG'), # Pass debug flag to tasks
        'MAIL_SUPPRESS_SEND': app.config.get('MAIL_SUPPRESS_SEND'), # Pass suppress flag
        # Beat schedule using new key format
        'beat_schedule': {
            'check-interview-reminders-every-minute': {
                'task': 'tasks.reminders.check_upcoming_interviews',
                'schedule': 60.0, # Run every 60 seconds
            },
        },
        # --- Timezone setting using NEW key format ---
        'timezone': 'UTC'
        # --------------------------------------------
    }
    celery.conf.update(**celery_config_updates)
    # ------------------------------------------------------------------

    # Celery ContextTask: Ensure tasks run within Flask application context
    class ContextTask(Task):
         def __call__(self, *args, **kwargs):
             with app.app_context():
                 # Log entry into task context if needed for debugging
                 # app.logger.debug(f"Entering app context for task {self.name}")
                 return self.run(*args, **kwargs)
    celery.Task = ContextTask # Make this the default Task class for Celery

    # Register Blueprints
    # Import inside function to avoid circular dependencies at module level
    from app.api import api_bp # Assuming api blueprint is defined in app/api/__init__.py or app/api/routes.py
    app.register_blueprint(api_bp) # No need for url_prefix here if set in Blueprint

    # Basic Health Check Route
    @app.route('/health')
    def health_check():
        # Could add checks here (e.g., DB connection) if needed
        return "OK", 200

    return app