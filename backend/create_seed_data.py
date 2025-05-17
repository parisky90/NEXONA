# backend/create_seed_data.py
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

try:
    from app.config import get_config
    from app import create_app, db
    from app.models import User, Company, CompanySettings
except ImportError as e:
    print(f"Error importing modules in create_seed_data.py: {e}")
    sys.exit(1)
finally:
    if sys.path and sys.path[0] == os.path.abspath(os.path.dirname(__file__)):
        sys.path.pop(0)

app = create_app()


def seed_data():
    with app.app_context():
        print("Starting data seeding process...")

        # 1. Superadmin Setup
        superadmin_email_env = os.environ.get('SUPERADMIN_EMAIL')
        superadmin_password_env = os.environ.get('SUPERADMIN_PASSWORD')
        superadmin_username_env = os.environ.get('SUPERADMIN_USERNAME', "superadmin")

        print(f"DEBUG (create_seed_data.py): Read SUPERADMIN_EMAIL from os.environ: '{superadmin_email_env}'")
        print(
            f"DEBUG (create_seed_data.py): Read SUPERADMIN_PASSWORD from os.environ: {'********' if superadmin_password_env else 'Not Set'}")
        print(f"DEBUG (create_seed_data.py): Read SUPERADMIN_USERNAME from os.environ: '{superadmin_username_env}'")

        if not superadmin_email_env or not superadmin_password_env or not superadmin_username_env:
            print("Error: SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD, and SUPERADMIN_USERNAME must be set. Aborting.")
            return

        superadmin = User.query.filter_by(username=superadmin_username_env).first()
        superadmin_created_or_updated = False

        if not superadmin:
            superadmin_by_email = User.query.filter_by(email=superadmin_email_env).first()
            if superadmin_by_email:
                superadmin = superadmin_by_email
                print(
                    f"User with email '{superadmin_email_env}' found with username '{superadmin.username}'. Will update.")
                if superadmin.username != superadmin_username_env:
                    check_new_username = User.query.filter_by(username=superadmin_username_env).first()
                    if check_new_username and check_new_username.id != superadmin.id:
                        print(
                            f"ERROR: Cannot update username to '{superadmin_username_env}' as it's taken. Keeping '{superadmin.username}'.")
                    else:
                        superadmin.username = superadmin_username_env
                        superadmin_created_or_updated = True
            else:
                superadmin = User(username=superadmin_username_env, email=superadmin_email_env)
                db.session.add(superadmin)
                print(f"Superadmin user '{superadmin.username}' will be created.")
                superadmin_created_or_updated = True

        if superadmin.role != 'superadmin':
            superadmin.role = 'superadmin'
            superadmin_created_or_updated = True
        if not superadmin.password_hash or not superadmin.check_password(superadmin_password_env):
            superadmin.set_password(superadmin_password_env)
            superadmin_created_or_updated = True
        if not superadmin.is_active:
            superadmin.is_active = True
            superadmin_created_or_updated = True
        if superadmin.is_active and not superadmin.confirmed_on:  # Ensure confirmed_on is set if active
            superadmin.confirmed_on = datetime.now(timezone.utc)
            superadmin_created_or_updated = True

        if superadmin_created_or_updated:
            print(f"Superadmin user '{superadmin.username}' processed (created/updated).")
        else:
            print(
                f"Superadmin user '{superadmin.username}' (Email: {superadmin.email}) already exists and is correctly configured.")

        # 2. Company Setup
        default_company_name_env = os.environ.get('DEFAULT_COMPANY_NAME')
        print(f"DEBUG (create_seed_data.py): Read DEFAULT_COMPANY_NAME from os.environ: '{default_company_name_env}'")
        if not default_company_name_env:
            default_company_name_env = "Default Seed Company"
            print(f"Warning: DEFAULT_COMPANY_NAME not set. Using fallback '{default_company_name_env}'.")

        company = Company.query.filter_by(name=default_company_name_env).first()
        company_just_created = False
        if not company:
            company = Company(name=default_company_name_env)
            db.session.add(company)
            company_just_created = True
            print(f"Company '{company.name}' will be created.")
        else:
            print(f"Company '{company.name}' (ID: {company.id}) already exists.")

        # Commit superadmin changes and new company (if any) to get IDs before proceeding
        try:
            db.session.commit()  # This commit handles superadmin and potentially new company
            print("Superadmin and initial company (if new) committed.")
        except Exception as e:
            db.session.rollback()
            print(f"Error committing superadmin/initial company: {e}")
            app.logger.error(f"Error committing superadmin/initial company: {e}", exc_info=True)
            return

        # Now company object (whether new or existing) will have an ID.

        # 3. Company Settings
        if company and (company_just_created or not company.settings):  # company.id is now guaranteed
            if not company.settings:
                settings = CompanySettings(company_id=company.id)
                db.session.add(settings)
                print(f"Default settings will be created for company '{company.name}'.")

        # 4. Company Admin Setup
        company_admin_to_assign_as_owner = None  # Θα κρατήσουμε εδώ τον admin που θα γίνει owner
        if company:
            company_admin_email_seed = "admin@mynexonacompany.com"
            company_admin_username_seed = f"admin_{company.id}"  # company.id is now available
            company_admin_password_seed = "companyadminpassword"

            if default_company_name_env != "My Nexona Company" and company_admin_email_seed == "admin@mynexonacompany.com":
                print(
                    f"Warning: DEFAULT_COMPANY_NAME is '{default_company_name_env}', but using Company Admin email '{company_admin_email_seed}'.")

            existing_ca = User.query.filter_by(email=company_admin_email_seed).first()
            ca_created_or_updated = False

            if not existing_ca:
                check_ca_username = User.query.filter_by(username=company_admin_username_seed).first()
                if check_ca_username:
                    print(
                        f"ERROR: Username '{company_admin_username_seed}' for company admin is taken. Skipping CA setup.")
                else:
                    company_admin_to_assign_as_owner = User(
                        username=company_admin_username_seed,
                        email=company_admin_email_seed,
                        role='company_admin',
                        is_active=True,
                        confirmed_on=datetime.now(timezone.utc),
                        company_id=company.id
                    )
                    company_admin_to_assign_as_owner.set_password(company_admin_password_seed)
                    db.session.add(company_admin_to_assign_as_owner)
                    ca_created_or_updated = True
                    print(
                        f"Company Admin '{company_admin_to_assign_as_owner.username}' will be created for company '{company.name}'.")
            else:
                company_admin_to_assign_as_owner = existing_ca
                print(f"User with email '{company_admin_email_seed}' found: {existing_ca.username}. Will check/update.")
                if existing_ca.username != company_admin_username_seed:
                    check_new_ca_username = User.query.filter_by(username=company_admin_username_seed).first()
                    if check_new_ca_username and check_new_ca_username.id != existing_ca.id:
                        print(
                            f"  WARNING: Cannot update CA username to '{company_admin_username_seed}' (taken). Keeping '{existing_ca.username}'.")
                    else:
                        existing_ca.username = company_admin_username_seed
                        ca_created_or_updated = True
                if existing_ca.company_id != company.id:
                    existing_ca.company_id = company.id
                    ca_created_or_updated = True
                if existing_ca.role != 'company_admin':
                    existing_ca.role = 'company_admin'
                    ca_created_or_updated = True
                if not existing_ca.is_active:
                    existing_ca.is_active = True
                    existing_ca.confirmed_on = datetime.now(timezone.utc)
                    ca_created_or_updated = True
                if not existing_ca.check_password(company_admin_password_seed):
                    existing_ca.set_password(company_admin_password_seed)
                    ca_created_or_updated = True

            if ca_created_or_updated:
                print(f"Company Admin '{company_admin_to_assign_as_owner.username}' processed (created/updated).")
            elif company_admin_to_assign_as_owner:  # Existed and was correct
                print(
                    f"Company Admin '{company_admin_to_assign_as_owner.username}' already exists and is correctly configured.")

            # Assign owner if company admin is determined and company has no owner
            if company_admin_to_assign_as_owner and not company.owner_user_id:
                # We need the ID of company_admin_to_assign_as_owner.
                # If it's a new user, it won't have an ID until flush/commit.
                # If it's an existing user, it has an ID.
                # Let's try to commit here to ensure IDs are set before final assignment attempt.
                try:
                    db.session.flush()  # Ensure new CA gets an ID if it was just added to session
                    if company_admin_to_assign_as_owner.id:
                        company.owner_user_id = company_admin_to_assign_as_owner.id
                        print(
                            f"Will set '{company_admin_to_assign_as_owner.username}' (ID: {company_admin_to_assign_as_owner.id}) as owner for company '{company.name}'.")
                    else:
                        print(
                            f"WARNING: Company Admin '{company_admin_to_assign_as_owner.username}' does not have an ID after flush. Cannot set as owner yet.")
                except Exception as e_flush_ca:
                    print(f"Error during flush for company admin ID: {e_flush_ca}")
                    # db.session.rollback() # Might be too early for full rollback

        # Final Commit for everything (settings, company admin, company owner update)
        try:
            db.session.commit()
            print("Data seeding process completed successfully.")
        except Exception as e:
            db.session.rollback()
            print(f"Final commit failed during seeding: {e}")
            app.logger.error(f"Final commit failed: {e}", exc_info=True)


if __name__ == '__main__':
    seed_data()