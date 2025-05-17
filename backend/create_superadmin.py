# backend/create_superadmin.py
import os
from dotenv import load_dotenv
from app import create_app, db
from app.models import User

dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    print(f"Loading environment variables from: {dotenv_path}")
    load_dotenv(dotenv_path)
else:
    dotenv_path_parent = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    if os.path.exists(dotenv_path_parent):
        print(f"Loading environment variables from: {dotenv_path_parent}")
        load_dotenv(dotenv_path_parent)
    else:
        print("Warning: .env file not found. Relying on system environment variables.")

try:
    app_instance = create_app(os.getenv('FLASK_ENV') or 'development')
except Exception as e:
    print(f"FATAL: Could not create Flask app instance for script. Error: {e}")
    exit(1)


def setup_superadmin(username, email, password):
    """Creates or updates a superadmin user."""
    with app_instance.app_context():
        if not username or not email or not password:
            print("Error: Username, email, and password for superadmin must all be provided.")
            return

        user = User.query.filter_by(username=username).first()
        if not user:  # Αν δεν υπάρχει ο χρήστης, έλεγξε και με email
            user_by_email = User.query.filter_by(email=email).first()
            if user_by_email:
                print(
                    f"Error: Email '{email}' is already in use by user '{user_by_email.username}'. Cannot create new superadmin with this email if username differs.")
                return

            # Δημιουργία νέου superadmin
            print(f"User '{username}' not found. Creating new superadmin...")
            user = User(
                username=username,
                email=email,
                role='superadmin',
                is_active=True,
                company_id=None
            )
            user.set_password(password)
            db.session.add(user)
            action_taken = "created"
        else:
            # Ο χρήστης υπάρχει, ενημέρωσε τον ρόλο (αν δεν είναι ήδη superadmin) και τον κωδικό
            print(f"User '{username}' found. Updating role to superadmin (if not already) and resetting password.")
            user.role = 'superadmin'  # Διασφάλιση ρόλου
            user.is_active = True  # Διασφάλιση ενεργοποίησης
            user.company_id = None  # Διασφάλιση ότι δεν έχει company_id
            user.set_password(password)
            action_taken = "updated (password reset, role/status ensured)"

        try:
            db.session.commit()
            print(f"Superadmin user '{username}' {action_taken} successfully with email '{email}'.")
        except Exception as e:
            db.session.rollback()
            print(f"Error setting up superadmin '{username}': {e}")
            app_instance.logger.error(f"Error setting up superadmin '{username}': {e}", exc_info=True)


if __name__ == '__main__':
    print("--- setup_superadmin.py script started ---")

    sa_username = os.getenv("SUPERADMIN_USERNAME")
    sa_email = os.getenv("SUPERADMIN_EMAIL")
    sa_password = os.getenv("SUPERADMIN_PASSWORD")

    print(
        f"Read from ENV: Username='{sa_username}', Email='{sa_email}', Password {'is set' if sa_password else 'is NOT set'}")

    if not all([sa_username, sa_email, sa_password]):
        print(
            "\nERROR: SUPERADMIN_USERNAME, SUPERADMIN_EMAIL, and SUPERADMIN_PASSWORD environment variables must be set.")
    elif len(sa_password) < 8:
        print("\nERROR: SUPERADMIN_PASSWORD is too short. Please use a password with at least 8 characters.")
    else:
        setup_superadmin(sa_username, sa_email, sa_password)

    print("--- setup_superadmin.py script finished ---")