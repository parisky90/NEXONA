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

try:
    from .config import get_config, AppConfig  # Χρησιμοποιούμε σχετικό import
except ImportError as e:
    sys.stderr.write(f"CRITICAL ERROR in app/__init__.py: Could not import '.config'. Ensure app/config.py exists.\n")
    sys.stderr.write(f"Python sys.path: {sys.path}\n")
    sys.stderr.write(f"Error details: {e}\n")
    raise

db = SQLAlchemy()
migrate = Migrate()
cors = CORS()
mail = Mail()
login_manager = LoginManager()
login_manager.login_view = 'api.login'  # Προσαρμόστε αν το endpoint του login είναι διαφορετικό
login_manager.session_protection = "strong"

celery = Celery(__name__,
                include=['tasks.parsing',
                         'tasks.communication',
                         'tasks.reminders'])


@login_manager.user_loader
def load_user(user_id):
    from app.models import User
    try:
        return User.query.get(int(user_id))
    except ValueError:
        logging.getLogger(__name__).warning(f"load_user: Invalid user_id format: {user_id}")
        return None
    except Exception as e:
        logging.getLogger(__name__).error(f"Error loading user {user_id}: {e}", exc_info=True)
        return None


def create_app(config_name_or_class=None):
    app = Flask(__name__)

    if isinstance(config_name_or_class, str):
        chosen_config_obj = get_config(config_name_or_class)
    elif config_name_or_class is not None and not isinstance(config_name_or_class, str):
        chosen_config_obj = config_name_or_class
    else:
        chosen_config_obj = get_config()

    app.config.from_object(chosen_config_obj)

    startup_logger_name = f"{app.name}.startup"
    startup_logger = logging.getLogger(startup_logger_name)
    if not startup_logger.handlers:
        startup_logger.setLevel(logging.INFO)
        startup_handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        startup_handler.setFormatter(formatter)
        startup_logger.addHandler(startup_handler)
        startup_logger.propagate = False

    try:
        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', 'NOT SET')
        masked_db_uri = db_uri
        if isinstance(db_uri, str) and "@" in db_uri:
            parts = db_uri.split('@', 1)
            if "://" in parts[0]:
                protocol_user_pass = parts[0].split("://", 1)
                if len(protocol_user_pass) > 1 and ":" in protocol_user_pass[1]:
                    user, _ = protocol_user_pass[1].split(":", 1)
                    masked_db_uri = f"{protocol_user_pass[0]}://{user}:********@{parts[1]}"

        startup_logger.info(f"NEXONA APP STARTUP (app/__init__.py via create_app):")
        startup_logger.info(f"  Config Loaded: {chosen_config_obj.__name__}")
        startup_logger.info(f"  DEBUG Mode: {app.config.get('DEBUG')}")
        startup_logger.info(f"  SQLALCHEMY_DATABASE_URI: {masked_db_uri}")
        startup_logger.info(
            f"  MAIL_DEBUG: {app.config.get('MAIL_DEBUG')}, MAIL_SUPPRESS_SEND: {app.config.get('MAIL_SUPPRESS_SEND')}")
        startup_logger.info(f"  CELERY_BROKER_URL: {app.config.get('CELERY_BROKER_URL')}")
    except Exception as log_err:
        sys.stderr.write(f"Warning: Error during startup config logging: {log_err}\n")

    if not app.debug and not app.testing:
        if not app.logger.handlers:
            stream_handler = logging.StreamHandler(sys.stdout)
            stream_handler.setFormatter(logging.Formatter(
                '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
            ))
            app.logger.addHandler(stream_handler)
        app.logger.setLevel(logging.INFO)
    else:
        if not app.logger.handlers:
            stream_handler = logging.StreamHandler(sys.stdout)
            stream_handler.setFormatter(logging.Formatter(
                '%(asctime)s DEBUG: %(message)s [in %(pathname)s:%(lineno)d]'
            ))
            app.logger.addHandler(stream_handler)
        app.logger.setLevel(logging.DEBUG)

    app.logger.info('NEXONA Application Starting Up (Flask app logger)...')

    db.init_app(app)
    migrate.init_app(app, db)

    cors_origins_config = app.config.get('CORS_ORIGINS', '*')
    if isinstance(cors_origins_config, str) and ',' in cors_origins_config:
        effective_cors_origins = [o.strip() for o in cors_origins_config.split(',')]
    elif isinstance(cors_origins_config, str) and cors_origins_config != '*':
        effective_cors_origins = [cors_origins_config]
    else:
        effective_cors_origins = cors_origins_config

    cors.init_app(app,
                  supports_credentials=app.config.get('CORS_SUPPORTS_CREDENTIALS', True),
                  origins=effective_cors_origins,
                  expose_headers=app.config.get('CORS_EXPOSE_HEADERS', ["Content-Type", "X-CSRFToken"]))

    mail.init_app(app)
    login_manager.init_app(app)

    celery_config_updates = {
        'broker_url': app.config['CELERY_BROKER_URL'],
        'result_backend': app.config['CELERY_RESULT_BACKEND'],
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

    class ContextTask(Task):
        abstract = True

        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask

    # --- Register Blueprints ---
    # Τροποποίηση στον τρόπο που γίνονται import τα blueprints από το app.api sub-package

    # Κάνουμε import τα blueprints από το app.api package,
    # όπου το app/api/__init__.py τα έχει κάνει διαθέσιμα.
    try:
        from app.api import bp as main_api_bp  # Το bp από το app.api.routes (μέσω του app.api.__init__)
        from app.api import admin_bp as admin_api_bp_imported  # Το admin_bp από το app.api.routes_admin
        from app.api import \
            company_admin_bp as company_admin_bp_imported  # Το company_admin_bp από το app.api.routes_company_admin

        app.register_blueprint(main_api_bp, url_prefix='/api/v1')

        # Το admin_bp έχει ήδη url_prefix='/admin' στον ορισμό του στο routes_admin.py,
        # οπότε δεν χρειάζεται να το ορίσουμε ξανά εδώ.
        app.register_blueprint(admin_api_bp_imported)

        # Το company_admin_bp ΔΕΝ έχει prefix στον ορισμό του (στο routes_company_admin.py),
        # οπότε το βάζουμε εδώ.
        app.register_blueprint(company_admin_bp_imported, url_prefix='/api/v1')  # Τελικά URLs: /api/v1/company/...

    except ImportError as bp_import_error:
        # Αυτό θα μας βοηθήσει να δούμε αν υπάρχει πρόβλημα με το app/api/__init__.py
        # ή με τα αρχεία routes μέσα στο app/api/
        startup_logger.critical(f"Failed to import blueprints from app.api package: {bp_import_error}", exc_info=True)
        raise  # Σταματάμε την εκκίνηση αν τα blueprints δεν μπορούν να φορτωθούν.
    # --- End Register Blueprints ---

    if app.debug or os.environ.get("FLASK_ENV") == "development":
        route_logger = startup_logger
        route_logger.debug("\n" + "=" * 60)
        route_logger.debug("DEBUG: REGISTERED FLASK ROUTES AT END OF CREATE_APP")
        route_logger.debug("=" * 60)
        rules_to_log = []
        for rule in app.url_map.iter_rules():
            if rule.endpoint in ('static', '_debug_toolbar.static', '_debug_toolbar.redirect_to_build'):
                continue
            rules_to_log.append(
                f"Endpoint: {rule.endpoint:40s} Route: {str(rule):50s} Methods: {','.join(sorted(rule.methods))}")

        for line in sorted(rules_to_log, key=lambda x: x.split("Route: ")[1]):
            route_logger.debug(line)
        route_logger.debug("=" * 60 + "\n")

    @app.route('/health')
    def health_check():
        return "OK", 200

    return app