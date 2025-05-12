# backend/create_candidate.py
import os
import sys
import uuid

# --- Προσθήκη του γονικού φακέλου (backend/) στο sys.path ---
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

try:
    from config import Config as AppConfig # Εισάγουμε την κλάση Config από το backend/config.py
    from app import create_app, db        # Εισάγουμε από το backend/app/
    from app.models import Candidate      # Εισάγουμε από το backend/app/models.py
except ImportError as e:
    print(f"Error importing modules in create_candidate.py: {e}")
    print("Please ensure that backend/config.py and backend/app exist and are importable.")
    print(f"Current sys.path: {sys.path}")
    sys.exit(1)
finally:
    # Αφαιρούμε την προσθήκη από το path μετά την εισαγωγή
    if sys.path[0] == os.path.abspath(os.path.dirname(__file__)):
        sys.path.pop(0)

# --- Χρησιμοποιούμε την κλάση Config που εισήχθη ---
app = create_app(AppConfig) # Περνάμε την κλάση Config

# --- ΟΡΙΣΕ ΤΑ ΣΤΟΙΧΕΙΑ ΤΟΥ ΥΠΟΨΗΦΙΟΥ ΕΔΩ ---
candidate_email = "pkyrkos@technomat.gr" # Το email που θέλουμε για το τεστ
first_name = "Paris (Test)"
last_name = "Kyrkos"
cv_filename = "dummy_cv_for_paris.pdf"
cv_path = f"cvs/test_candidate_paris_{uuid.uuid4()}.pdf" # Μοναδικό path
initial_status = "Interested" # Ένας λογικός αρχικός status
phone_number_test = "6900000000" # Προαιρετικό
# ----------------------------------------

def main():
    with app.app_context():
        print(f"Attempting to create test candidate: {first_name} {last_name} ({candidate_email})")
        existing_candidate = Candidate.query.filter_by(email=candidate_email).first()
        if existing_candidate:
            print(f"Candidate with email {candidate_email} already exists (ID: {existing_candidate.candidate_id}). Skipping creation.")
        else:
            try:
                new_candidate = Candidate(
                    email=candidate_email,
                    first_name=first_name,
                    last_name=last_name,
                    cv_original_filename=cv_filename,
                    cv_storage_path=cv_path,
                    current_status=initial_status,
                    confirmation_uuid=str(uuid.uuid4()), # Δημιουργία UUID
                    phone_number=phone_number_test
                    # Πρόσθεσε κι άλλα πεδία αν θέλεις
                )
                db.session.add(new_candidate)
                db.session.commit()
                print(f"Successfully created candidate '{first_name} {last_name}' with email {candidate_email} and ID {new_candidate.candidate_id}")
            except Exception as e:
                db.session.rollback()
                print(f"Error creating candidate '{first_name} {last_name}': {e}")
                app.logger.error(f"Error creating candidate: {e}", exc_info=True)

if __name__ == '__main__':
    main()