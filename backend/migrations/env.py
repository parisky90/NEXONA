import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# --- START OF NEXONA CUSTOMIZATION ---
# Add the project's root directory (backend/) to the Python path
# so that Alembic can find the 'app' module and its models.
sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), '..')))

try:
    # Your create_app is in app/__init__.py and db is also initialized there
    from app import create_app, db as flask_db
    # Import all models to ensure they are registered with SQLAlchemy's metadata
    import app.models # This ensures all models in app/models.py are loaded
except ImportError as e:
    print(f"Error importing Flask app components: {e}")
    print("Please ensure that the backend directory is in sys.path and app structure is correct.")
    print(f"Current sys.path: {sys.path}")
    raise

# Get the Flask application instance.
# Your create_app function likely uses os.getenv('FLASK_CONFIG') or a default
# to determine which configuration to load. We don't need to pass 'config_name'.
try:
    # Call create_app WITHOUT any arguments, or with arguments it actually expects.
    # Based on typical Flask patterns and your previous logs,
    # it likely determines config from FLASK_CONFIG env var or has a default.
    flask_app = create_app()
except Exception as e:
    print(f"Error creating Flask app instance: {e}")
    print("Ensure create_app can be called (possibly without arguments if it uses FLASK_CONFIG env var).")
    raise

# Use the SQLAlchemy URI from the Flask app's configuration.
db_uri = flask_app.config.get('SQLALCHEMY_DATABASE_URI')
if not db_uri:
    raise ValueError("SQLALCHEMY_DATABASE_URI not found in Flask app configuration.")
config.set_main_option('sqlalchemy.url', db_uri)

# The target_metadata should be your Flask-SQLAlchemy db.metadata
target_metadata = flask_db.metadata
# --- END OF NEXONA CUSTOMIZATION ---


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = flask_db.engine

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()