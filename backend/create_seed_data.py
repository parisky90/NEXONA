# backend/create_seed_data.py
import os
import sys
from datetime import datetime, timezone

# --- Adjust sys.path to allow imports from 'app' and 'config' ---
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

try:
    # Assuming create_seed_data.py is in backend/
    # and config.py is in backend/app/config.py
    # and __init__.py is in backend/app/__init__.py
    from app.config import get_config # Άλλαξε αυτό για να παίρνει το config από το app/
    from app import create_app, db
    from app.models import User, Company, CompanySettings # Αυτά είναι ΟΚ
except ImportError as e:
    print(f"Error importing modules in create_seed_data.py: {e}")
    # ... (το υπόλοιπο error handling)
    sys.exit(1)
    print("Please ensure that backend/config.py and backend/app exist and are importable.")
    print(f"Current sys.path: {sys.path}")
    sys.exit(1)
finally:
    if sys.path and sys.path[0] == os.path.abspath(os.path.dirname(__file__)):
        sys.path.pop(0)

app = create_app()  # create_app θα χρησιμοποιήσει το get_config() για να πάρει το σωστό config


def seed_data():
    with app.app_context():
        print("Starting data seeding process...")

        # 1. Get Superadmin details from config (via app.config)
        superadmin_email_cfg = app.config.get('SUPERADMIN_EMAIL')
        superadmin_password_cfg = app.config.get('SUPERADMIN_PASSWORD')
        superadmin_username_cfg = "superadmin"  # Σταθερό username για τον superadmin

        if not superadmin_email_cfg or not superadmin_password_cfg:
            print("Error: SUPERADMIN_EMAIL or SUPERADMIN_PASSWORD not set in .env/configuration. Aborting.")
            return

        existing_superadmin = User.query.filter_by(email=superadmin_email_cfg).first()
        if not existing_superadmin:
            superadmin = User(
                username=superadmin_username_cfg,
                email=superadmin_email_cfg,
                role='superadmin',
                is_active=True,  # Superadmin is active by default
                confirmed_on=datetime.now(timezone.utc)  # Auto-confirm superadmin
                # company_id is None for superadmin
            )
            superadmin.set_password(superadmin_password_cfg)
            db.session.add(superadmin)
            print(f"Superadmin user '{superadmin.username}' created with email '{superadmin.email}'.")
        else:
            superadmin = existing_superadmin
            if superadmin.role != 'superadmin':
                superadmin.role = 'superadmin'
                print(f"Updated existing user '{superadmin.username}' to role 'superadmin'.")
            else:
                print(
                    f"Superadmin user '{superadmin.username}' (Email: {superadmin.email}) already exists with correct role.")

        # 2. Get Default Company details from config
        default_company_name_cfg = app.config.get('DEFAULT_COMPANY_NAME')
        if not default_company_name_cfg:
            print("Warning: DEFAULT_COMPANY_NAME not set in .env/configuration. Using fallback 'Default Seed Company'.")
            default_company_name_cfg = "Default Seed Company"

        company = Company.query.filter_by(name=default_company_name_cfg).first()
        company_just_created = False
        if not company:
            company = Company(
                name=default_company_name_cfg
                # owner_user_id can be set later
            )
            db.session.add(company)
            try:
                db.session.commit()  # Commit to get company.id
                print(f"Company '{company.name}' created with ID {company.id}.")
                company_just_created = True
            except Exception as e:
                db.session.rollback()
                print(f"Error creating company '{default_company_name_cfg}': {e}")
                app.logger.error(f"Error creating company '{default_company_name_cfg}': {e}", exc_info=True)
                return  # Stop if company creation fails
        else:
            print(f"Company '{company.name}' (ID: {company.id}) already exists.")

        # 3. Ensure CompanySettings exist for the company
        if company and (company_just_created or not company.settings):
            if not company.settings:  # Check again in case it was created but not linked
                try:
                    settings = CompanySettings(company_id=company.id)
                    db.session.add(settings)
                    # db.session.commit() # Commit settings separately or with the final commit
                    print(f"Default settings created/ensured for company '{company.name}'.")
                except Exception as e:
                    db.session.rollback()
                    print(f"Error creating/ensuring settings for company '{company.name}': {e}")
                    app.logger.error(f"Error creating settings for '{company.name}': {e}", exc_info=True)

        # 4. Create a Company Admin for the Default Company (matching test_endpoints.py)
        if company:  # Ensure company exists
            # Credentials που θα χρησιμοποιηθούν στο test_endpoints.py
            company_admin_email_seed = "admin@mynexonacompany.com"
            company_admin_username_seed = f"admin_{company.id}"  # e.g., "admin_1"
            company_admin_password_seed = "companyadminpassword"

            # Έλεγχος αν το όνομα της εταιρείας ταιριάζει με αυτό που περιμένει το email
            # Αυτό είναι για να είμαστε σίγουροι ότι το email είναι λογικό για την εταιρεία.
            # Αν το DEFAULT_COMPANY_NAME στο .env δεν είναι "My Nexona Company", αυτό το email μπορεί να μην είναι "σωστό".
            # Ωστόσο, για τις δοκιμές, θα το κρατήσουμε σταθερό όπως στο test_endpoints.py.
            if default_company_name_cfg != "My Nexona Company" and company_admin_email_seed == "admin@mynexonacompany.com":
                print(
                    f"Warning: DEFAULT_COMPANY_NAME is '{default_company_name_cfg}', but seeding Company Admin with email '{company_admin_email_seed}'. Ensure this is intended for testing.")

            existing_company_admin = User.query.filter_by(email=company_admin_email_seed).first()
            if not existing_company_admin:
                new_company_admin = User(
                    username=company_admin_username_seed,
                    email=company_admin_email_seed,
                    role='company_admin',
                    is_active=True,
                    confirmed_on=datetime.now(timezone.utc),
                    company_id=company.id
                )
                new_company_admin.set_password(company_admin_password_seed)
                db.session.add(new_company_admin)
                print(
                    f"Company Admin '{new_company_admin.username}' created for company '{company.name}' with email '{new_company_admin.email}'.")

                if not company.owner_user_id:  # Assign as owner if no owner is set
                    company.owner_user_id = new_company_admin.id
                    print(f"Set '{new_company_admin.username}' as owner for company '{company.name}'.")
            else:
                print(
                    f"User with email '{company_admin_email_seed}' (intended as Company Admin) already exists: {existing_company_admin.username}, Role: {existing_company_admin.role}, CompanyID: {existing_company_admin.company_id}")
                # Ensure the existing user is correctly configured for this company
                if existing_company_admin.company_id != company.id:
                    existing_company_admin.company_id = company.id
                    print(
                        f"  Updated company for existing user '{existing_company_admin.username}' to '{company.name}'.")
                if existing_company_admin.role != 'company_admin':
                    existing_company_admin.role = 'company_admin'
                    print(f"  Updated role for existing user '{existing_company_admin.username}' to 'company_admin'.")
                if not existing_company_admin.is_active:
                    existing_company_admin.is_active = True
                    print(f"  Activated existing user '{existing_company_admin.username}'.")

        try:
            db.session.commit()
            print("Data seeding process completed successfully.")
        except Exception as e:
            db.session.rollback()
            print(f"Final commit failed during seeding: {e}")
            app.logger.error(f"Final commit failed: {e}", exc_info=True)


if __name__ == '__main__':
    seed_data()