# backend/create_test_candidate_and_position.py
import os
import sys
import uuid
from datetime import datetime, timezone as dt_timezone

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

try:
    from app import create_app, db
    from app.models import Candidate, Position, User, Company
except ImportError as e:
    print(f"Error importing modules: {e}")
    sys.exit(1)
finally:
    if sys.path and sys.path[0] == os.path.abspath(os.path.dirname(__file__)):
        sys.path.pop(0)

app = create_app()

# --- Στοιχεία για Δημιουργία ---
COMPANY_ADMIN_EMAIL = "admin@mynexonacompany.com"  # Ο χρήστης που θα "κατέχει" τα δεδομένα

CANDIDATE_EMAIL = f"test_candidate_{uuid.uuid4().hex[:6]}@example.com"
CANDIDATE_FIRST_NAME = "Test"
CANDIDATE_LAST_NAME = "Candidate"
CANDIDATE_STATUS = "Interested"  # Έτοιμος για πρόταση συνέντευξης

POSITION_NAME = f"Test Developer Position {uuid.uuid4().hex[:4]}"
POSITION_DESCRIPTION = "A test position for a skilled developer."
POSITION_STATUS = "Open"


# -----------------------------

def main():
    with app.app_context():
        # 1. Βρες την εταιρεία του Company Admin
        admin_user = User.query.filter_by(email=COMPANY_ADMIN_EMAIL).first()
        if not admin_user:
            print(f"Company Admin with email {COMPANY_ADMIN_EMAIL} not found. Run seed_data.py first.")
            return
        if not admin_user.company_id:
            print(f"Company Admin {COMPANY_ADMIN_EMAIL} is not associated with a company.")
            return

        target_company_id = admin_user.company_id
        target_company = db.session.get(Company, target_company_id)
        if not target_company:
            print(f"Company with ID {target_company_id} (for admin {COMPANY_ADMIN_EMAIL}) not found.")
            return

        print(f"Targeting company: '{target_company.name}' (ID: {target_company.id})")

        # 2. Δημιουργία Θέσης (Position)
        existing_position = Position.query.filter_by(company_id=target_company_id, position_name=POSITION_NAME).first()
        position_to_use = None
        if existing_position:
            print(f"Position '{POSITION_NAME}' already exists for company {target_company.name}.")
            position_to_use = existing_position
        else:
            new_position = Position(
                company_id=target_company_id,
                position_name=POSITION_NAME,
                description=POSITION_DESCRIPTION,
                status=POSITION_STATUS
            )
            db.session.add(new_position)
            try:
                # Κάνουμε flush για να πάρουμε το ID της θέσης αν χρειαστεί άμεσα
                db.session.flush()
                position_to_use = new_position
                print(
                    f"Position '{new_position.position_name}' (ID: {new_position.position_id}) created for company {target_company.name}.")
            except Exception as e:
                db.session.rollback()
                print(f"Error creating position '{POSITION_NAME}': {e}")
                return

        # 3. Δημιουργία Υποψηφίου (Candidate)
        existing_candidate = Candidate.query.filter_by(company_id=target_company_id, email=CANDIDATE_EMAIL).first()
        if existing_candidate:
            print(f"Candidate with email {CANDIDATE_EMAIL} already exists for company {target_company.name}.")
            candidate_to_use = existing_candidate
        else:
            new_candidate = Candidate(
                company_id=target_company_id,
                email=CANDIDATE_EMAIL,
                first_name=CANDIDATE_FIRST_NAME,
                last_name=CANDIDATE_LAST_NAME,
                current_status=CANDIDATE_STATUS,
                submission_date=datetime.now(dt_timezone.utc)
            )
            db.session.add(new_candidate)
            try:
                db.session.flush()  # Για να πάρουμε το ID του υποψηφίου
                candidate_to_use = new_candidate
                print(
                    f"Candidate '{new_candidate.full_name}' (ID: {new_candidate.candidate_id}) created for company {target_company.name}.")
            except Exception as e:
                db.session.rollback()
                print(f"Error creating candidate '{CANDIDATE_EMAIL}': {e}")
                return

        # 4. Σύνδεση Υποψηφίου με Θέση (αν υπάρχουν και τα δύο)
        if candidate_to_use and position_to_use:
            if position_to_use not in candidate_to_use.positions:
                candidate_to_use.positions.append(position_to_use)
                print(
                    f"Associated candidate '{candidate_to_use.full_name}' with position '{position_to_use.position_name}'.")
            else:
                print(
                    f"Candidate '{candidate_to_use.full_name}' already associated with position '{position_to_use.position_name}'.")

        # 5. Τελικό Commit
        try:
            db.session.commit()
            print("Successfully committed test candidate and position.")
        except Exception as e:
            db.session.rollback()
            print(f"Final commit failed: {e}")


if __name__ == '__main__':
    main()