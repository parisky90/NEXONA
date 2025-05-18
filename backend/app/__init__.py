# backend/app/__init__.py
import os
from flask import Flask, jsonify, request, current_app as flask_current_app
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, current_user
from flask_mail import Mail
from flask_cors import CORS
from celery import Celery, Task
import logging
from logging.handlers import RotatingFileHandler

try:
    from .config import get_config
except ImportError:
    from config import get_config
    # --- ΠΡΟΣΘΗΚΗ LOGGING ΓΙΑ ΑΥΤΗ ΤΗΝ ΠΕΡΙΠΤΩΣΗ ---
    import logging as temp_logger_init

    temp_logger_init.basicConfig(level=temp_logger_init.WARNING)
    temp_logger_init.warning(
        "Imported 'get_config' from top-level 'config' in app/__init__.py. Ensure 'app/config.py' is used if it exists.")

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()


@login_manager.unauthorized_handler
def unauthorized():
    flask_current_app.logger.warning(f"Unauthorized access attempt to: {request.path}")
    return jsonify(error="Unauthorized", message="Authentication is required to access this resource."), 401


login_manager.session_protection = "strong"
mail = Mail()
cors = CORS()

from .services.s3_service import S3Service

s3_service_instance = S3Service()

celery = Celery(__name__)

from .models import User


@login_manager.user_loader
def load_user(user_id):
    logger_instance = flask_current_app.logger if flask_current_app else logging.getLogger(__name__)
    try:
        user_id_int = int(user_id)
        user = db.session.get(User, user_id_int)
        return user
    except Exception as e:
        logger_instance.error(f"Error loading user {user_id}: {e}", exc_info=True)
        return None


def make_celery(app_instance):
    class ContextTask(Task):
        def __call__(self, *args, **kwargs):
            with app_instance.app_context():
                return self.run(*args, **kwargs)

    global celery
    celery.conf.broker_url = app_instance.config['CELERY_BROKER_URL']
    celery.conf.result_backend = app_instance.config['CELERY_RESULT_BACKEND']
    celery.conf.task_always_eager = app_instance.config.get('TASK_ALWAYS_EAGER', False)
    celery.conf.task_eager_propagates = app_instance.config.get('TASK_EAGER_PROPAGATES', False)
    celery.conf.timezone = app_instance.config.get('CELERY_TIMEZONE', 'UTC')

    celery_flask_config = {key: value for key, value in app_instance.config.items() if
                           key.startswith('CELERY_') or key.startswith('TASK_')}
    celery.conf.update(celery_flask_config)
    celery.Task = ContextTask

    try:
        celery.autodiscover_tasks(['tasks'], related_name=None, force=True)
        app_instance.logger.info("Celery autodiscover_tasks configured for 'tasks' package.")
    except Exception as e:
        app_instance.logger.error(f"Error during Celery autodiscover_tasks: {e}", exc_info=True)
    return celery


def setup_logging(app_instance):
    log_level_str = app_instance.config.get('LOG_LEVEL', 'INFO').upper()
    log_level = getattr(logging, log_level_str, logging.INFO)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    log_dir = os.path.join(project_root, 'logs')

    for handler in list(app_instance.logger.handlers):
        app_instance.logger.removeHandler(handler)

    if not app_instance.debug and not app_instance.testing:
        if not os.path.exists(log_dir):
            try:
                os.makedirs(log_dir, exist_ok=True)
            except OSError as e:
                console_fallback_handler = logging.StreamHandler()
                console_fallback_handler.setFormatter(
                    logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
                app_instance.logger.addHandler(console_fallback_handler)
                app_instance.logger.error(f"Could not create log directory {log_dir}: {e}. Logging to stderr.")
                app_instance.logger.setLevel(log_level)
                return

        if os.path.exists(log_dir):
            file_handler = RotatingFileHandler(os.path.join(log_dir, 'nexona_app.log'), maxBytes=102400, backupCount=10)
            file_handler.setFormatter(
                logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
            file_handler.setLevel(log_level)
            app_instance.logger.addHandler(file_handler)
            app_instance.logger.info('NEXONA application logging to file initialized.')
        else:
            app_instance.logger.warning(f"Log directory {log_dir} still not available. Logging to stderr.")
    else:
        if not app_instance.logger.handlers:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(logging.Formatter(
                '%(asctime)s %(levelname)s %(name)s [%(module)s.%(funcName)s:%(lineno)d]: %(message)s'))
            app_instance.logger.addHandler(console_handler)
        app_instance.logger.info('NEXONA application console logging for development/debug initialized.')
    app_instance.logger.setLevel(log_level)


def create_app(config_name_from_env=None):
    backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    templates_dir = os.path.join(backend_root, 'templates')
    app = Flask(__name__, instance_relative_config=False, template_folder=templates_dir)
    effective_config_name = config_name_from_env or os.getenv('FLASK_ENV') or 'development'
    selected_config_obj = get_config(effective_config_name)

    if selected_config_obj is None:
        print(f"CRITICAL: Configuration '{effective_config_name}' not found. Using minimal fallback.")
        app.config.from_mapping(
            SECRET_KEY=os.getenv('SECRET_KEY', 'fallback_secret_key_for_testing_only_123!'),
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            SQLALCHEMY_DATABASE_URI=os.getenv('DATABASE_URL', 'sqlite:///./default_fallback_app.db'),
            CELERY_BROKER_URL=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
            CELERY_RESULT_BACKEND=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
            LOG_LEVEL='DEBUG',
            CORS_ORIGINS='*'
        )
    else:
        app.config.from_object(selected_config_obj)

    setup_logging(app)
    app.logger.info(f"NEXONA APP STARTUP (app/__init__.py via create_app):")
    app.logger.info(
        f"  Config Loaded: {selected_config_obj.__name__ if selected_config_obj else 'Minimal Fallback Config'}")

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)

    cors_origins_config = app.config.get('CORS_ORIGINS', '*')
    if isinstance(cors_origins_config, str) and cors_origins_config != '*':
        actual_cors_origins = [origin.strip() for origin in cors_origins_config.split(',')]
    elif isinstance(cors_origins_config, list):
        actual_cors_origins = cors_origins_config
    else:
        actual_cors_origins = "*"
    cors.init_app(app, resources={r"/api/v1/*": {"origins": actual_cors_origins}}, supports_credentials=True)
    app.logger.info(f"CORS initialized for /api/v1/* with origins: {actual_cors_origins}")

    s3_service_instance.init_app(app)
    make_celery(app)

    # --- ΕΙΣΑΓΩΓΗ BLUEPRINTS ΕΔΩ ---
    try:
        from .api.routes import bp as main_api_bp
        from .api.routes_admin import admin_bp
        from .api.routes_company_admin import company_admin_bp

        # --- ΠΡΟΣΘΗΚΗ LOGGING ΓΙΑ ΤΗΝ ΕΙΣΑΓΩΓΗ ---
        app.logger.info(f"DEBUG: main_api_bp imported in create_app: {main_api_bp}")
        app.logger.info(f"DEBUG: admin_bp imported in create_app: {admin_bp}")
        app.logger.info(f"DEBUG: company_admin_bp imported in create_app: {company_admin_bp}")

        if main_api_bp:
            app.register_blueprint(main_api_bp)
            app.logger.info(f"Registered main_api_bp with effective prefix: {main_api_bp.url_prefix}")
        else:
            app.logger.error("main_api_bp (aka 'bp' from routes.py) not loaded or defined.")
        if admin_bp:
            app.register_blueprint(admin_bp)
            app.logger.info(f"Registered admin_bp with effective prefix: {admin_bp.url_prefix}")
        else:
            app.logger.error("admin_bp not loaded or defined.")
        if company_admin_bp:
            app.register_blueprint(company_admin_bp)
            app.logger.info(f"Registered company_admin_bp with effective prefix: {company_admin_bp.url_prefix}")
        else:
            app.logger.error("company_admin_bp not loaded or defined.")
    except ImportError as e_bp:
        app.logger.critical(f"Failed to import blueprints for registration: {e_bp}", exc_info=True)
    except Exception as e_reg:
        app.logger.critical(f"An unexpected error occurred during blueprint registration: {e_reg}", exc_info=True)

    @app.errorhandler(404)
    def not_found_error(error):
        app.logger.warning(f"404 Not Found: {request.path} (Accept: {request.accept_mimetypes})")
        if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
            return jsonify(error="Not found",
                           message=f"The requested URL {request.path} was not found on this server."), 404
        return jsonify(error="Resource not found (404). Please check the URL."), 404

    @app.errorhandler(401)
    def unauthorized_error_handler_app(error):
        app.logger.warning(f"App-level 401 Unauthorized: {request.path}")
        return jsonify(error="Unauthorized", message="Authentication is required to access this resource."), 401

    @app.errorhandler(403)
    def forbidden_error(error):
        app.logger.warning(
            f"403 Forbidden: {request.path} by user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
        return jsonify(error="Forbidden",
                       message="You do not have the necessary permissions to access this resource."), 403

    @app.errorhandler(500)
    def internal_error(error):
        try:
            db.session.rollback()
        except Exception as rb_exc:
            app.logger.error(f"Error during rollback: {rb_exc}", exc_info=True)
        app.logger.error(f"500 Internal Server Error: {request.path}", exc_info=error)
        if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
            return jsonify(error="Internal server error", message="An unexpected error occurred on the server."), 500
        return jsonify(error="An internal server error occurred (500). Please try again later."), 500

    app.logger.info("Flask app creation completed.")
    return app