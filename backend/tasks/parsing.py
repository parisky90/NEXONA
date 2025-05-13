# backend/tasks/parsing.py

from flask import current_app # Import current_app to access config, logger within task context
from app import celery, db    # Import celery instance and db instance
from app.models import Candidate # Import Candidate model
from app.services import textkernel_service # Import the textkernel service
import logging
import json # For logging raw data
from datetime import datetime, timezone # For potentially adding timestamps to notes

# Basic logger for this module
logger = logging.getLogger(__name__)

@celery.task(bind=True, name='tasks.parsing.parse_cv_task')
def parse_cv_task(self, candidate_id, s3_file_key, company_id):
    """
    Celery task to parse a CV using Textkernel service and update the database.
    """
    logger.info(f"[TASK START] Processing parse_cv_task for Candidate ID: {candidate_id}, S3 Key: {s3_file_key}")

    candidate = None # Initialize candidate variable

    try:
        # 1. Fetch the candidate record
        candidate = Candidate.query.get(candidate_id)
        if not candidate:
            logger.error(f"[TASK FAIL] Candidate {candidate_id} not found in database. Aborting task.")
            return f"Candidate {candidate_id} not found."

        # Allow processing if status indicates initial state or previous failure
        if candidate.current_status not in ['Processing', 'ParsingFailed']:
             logger.warning(f"[TASK SKIP] Candidate {candidate_id} status is '{candidate.current_status}', skipping parsing.")
             return f"Skipped parsing for candidate {candidate_id} due to status."

        # 2. Call the Textkernel service
        logger.info(f"[TASK] Calling Textkernel service for candidate {candidate_id}, key {s3_file_key}")
        # Expects 'ResumeData' dictionary or None/Error dict
        parsed_data = textkernel_service.parse_cv_via_textkernel(s3_file_key)

        # 3. Process the result from Textkernel
        if parsed_data is None:
            logger.error(f"[TASK FAIL] Textkernel service call failed critically for candidate {candidate_id}. Setting status to ParsingFailed.")
            candidate.current_status = 'ParsingFailed'
            candidate.notes = (candidate.notes or "") + f"\nTextkernel API Critical Error: {datetime.now(timezone.utc).isoformat()}"
            db.session.commit()
            return f"Textkernel service failed critically for candidate {candidate_id}."

        if isinstance(parsed_data, dict) and parsed_data.get('error'):
             logger.warning(f"[TASK WARN] Textkernel service returned parsing issue for {candidate_id}: {parsed_data['error']}")
             logger.error(f"[TASK DEBUG] Raw error data from service: {parsed_data}")
             candidate.current_status = 'ParsingFailed'
             candidate.notes = (candidate.notes or "") + f"\nTextkernel Parsing Issue: {parsed_data['error']} - {datetime.now(timezone.utc).isoformat()}"
             db.session.commit()
             return f"Textkernel parsing issue for candidate {candidate_id}."

        # --- Log Raw Data for Debugging (Optional: remove later) ---
        try:
            logger.info(f"[TASK DEBUG] Raw Parsed 'ResumeData' Received for Candidate {candidate_id}:")
            logger.info(json.dumps(parsed_data, indent=2)) # Pretty print JSON ResumeData
        except Exception as log_err:
            logger.error(f"[TASK DEBUG] Error logging parsed_data: {log_err}")
        # --- End Logging Block ---


        # --- 4. Update Candidate Record with Parsed Data ---
        # !! VERIFY and REFINE these extraction paths based on logged JSON !!
        logger.info(f"[TASK] Updating candidate {candidate_id} with parsed data.")
        try:
            # --- Personal Info ---
            contact_info = parsed_data.get('ContactInformation', {})
            person_names = contact_info.get('CandidateName', {})
            personal_attrs = parsed_data.get('PersonalAttributes', {})

            candidate.first_name = person_names.get('GivenName', candidate.first_name)
            candidate.last_name = person_names.get('FamilyName', candidate.last_name) # Might need manual correction

            # --- Corrected Email Extraction ---
            email_list = contact_info.get('EmailAddresses', []) # Get list of emails
            if isinstance(email_list, list) and email_list:
                 candidate.email = email_list[0] # Take the first email found
            elif candidate.email is None: # Only clear if currently None and none found
                 candidate.email = None

            # --- Corrected Phone Extraction ---
            phone_list = contact_info.get('Telephones', []) # Get list of phone objects
            if isinstance(phone_list, list) and phone_list:
                 first_phone_obj = phone_list[0]
                 if isinstance(first_phone_obj, dict):
                      # Prioritize 'Normalized', fallback to 'Raw'
                      candidate.phone_number = first_phone_obj.get('Normalized', first_phone_obj.get('Raw'))
            elif candidate.phone_number is None:
                 candidate.phone_number = None

            # --- Age Extraction (From DateOfBirth if available) ---
            dob_str = personal_attrs.get('DateOfBirth', {}).get('Date') # Expects YYYY-MM-DD
            if dob_str:
                try:
                    birth_date = datetime.strptime(dob_str, "%Y-%m-%d").date()
                    today = datetime.now(timezone.utc).date()
                    # Calculate age (simple calculation)
                    age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
                    candidate.age = age
                except ValueError:
                    logger.warning(f"[TASK WARN] Could not parse DateOfBirth: {dob_str}")
                    candidate.age = None # Set age to None if parsing fails
            elif candidate.age is None:
                 candidate.age = None

            # --- Corrected Education Extraction ---
            # Using Education.EducationDetails based on typical TK structure (VERIFY THIS PATH!)
            education_section = parsed_data.get('Education', {}).get('EducationDetails', [])
            if not education_section: # Fallback if EducationDetails path is wrong
                education_section = parsed_data.get('EducationHistory', {}).get('SchoolOrInstitution', [])

            if isinstance(education_section, list):
                 edu_texts = []
                 for edu in education_section:
                      if not isinstance(edu, dict): continue
                      school = edu.get('SchoolName', {}).get('Normalized', edu.get('SchoolName', {}).get('Raw', 'N/A')) # Prefer Normalized name
                      degree_name = edu.get('Degree', {}).get('Name', {}).get('Normalized', edu.get('Degree', {}).get('Name', {}).get('Raw', 'N/A'))
                      start_date = edu.get('DatesOfAttendance', {}).get('StartDate', {}).get('Date', '') # Get YYYY-MM-DD if available
                      end_date_obj = edu.get('DatesOfAttendance', {}).get('EndDate', {})
                      end_date = end_date_obj.get('Date', 'Present') if not end_date_obj.get('StringDate') == 'current' else 'Present'
                      edu_texts.append(f"School: {school}, Degree: {degree_name}, Dates: {start_date} - {end_date}")
                 candidate.education = "\n---\n".join(edu_texts) if edu_texts else None
            else:
                 candidate.education = None # Clear if not a list

            # --- Corrected Work Experience Extraction ---
            # Using EmploymentHistory.Positions based on your JSON snippet
            experience_section = parsed_data.get('EmploymentHistory', {}).get('Positions', [])
            if isinstance(experience_section, list):
                 exp_texts = []
                 for exp in experience_section:
                     if not isinstance(exp, dict): continue
                     # Get Employer Name
                     employer = exp.get('Employer', {}).get('Name', {}).get('Normalized', exp.get('Employer', {}).get('Name', {}).get('Raw', 'N/A'))
                     # Get Job Title
                     title = exp.get('JobTitle', {}).get('Normalized', exp.get('JobTitle', {}).get('Raw', 'N/A'))
                     # Get Description
                     description = exp.get('Description', '')
                     exp_texts.append(f"Employer: {employer}, Title: {title}\n   Description: {description.strip()}")
                 candidate.work_experience = "\n------\n".join(exp_texts) if exp_texts else None
            else:
                 candidate.work_experience = None

            # --- Skills Extraction (Seems OK based on logs) ---
            skills_section = parsed_data.get('Skills', {}).get('Raw', [])
            if isinstance(skills_section, list):
                skills_list = [s.get('Name') for s in skills_section if isinstance(s, dict) and s.get('Name')]
                if skills_list:
                     skills_text = ", ".join(filter(None, skills_list))
                     notes_prefix = "Parsed Skills: "
                     current_notes = candidate.notes or ""
                     if notes_prefix not in current_notes: # Avoid adding duplicates
                          candidate.notes = f"{current_notes}\n{notes_prefix}{skills_text}".strip()
            # No 'else' needed, notes remain as they were if no skills found

            # --- Languages Extraction (Seems OK based on logs) ---
            languages_section = parsed_data.get('LanguageCompetencies', [])
            if isinstance(languages_section, list):
                lang_list = [lang.get('Language') for lang in languages_section if isinstance(lang, dict) and lang.get('Language')]
                if lang_list:
                     lang_text = ", ".join(filter(None, lang_list))
                     candidate.languages = lang_text # Assign to dedicated field
            elif candidate.languages is None:
                 candidate.languages = None

            # --- Seminars / Training Extraction (Placeholder - VERIFY PATH) ---
            seminar_section = parsed_data.get('Training', {}).get('TrainingDetails', []) # GUESSING PATH
            if isinstance(seminar_section, list):
                seminar_texts = []
                for sem in seminar_section:
                    if not isinstance(sem, dict): continue
                    name = sem.get('Name', 'N/A') # GUESSING KEY
                    date = sem.get('Date', '')    # GUESSING KEY
                    seminar_texts.append(f"Seminar: {name} ({date})")
                candidate.seminars = "\n---\n".join(seminar_texts) if seminar_texts else None
            else:
                 candidate.seminars = None


            # --- Update Status ---
            candidate.current_status = 'NeedsReview' # Parsing successful

            db.session.commit()
            logger.info(f"[TASK SUCCESS] Candidate {candidate_id} updated successfully from parsed CV. Status: {candidate.current_status}")
            return f"Successfully parsed and updated candidate {candidate_id}."

        except Exception as update_err:
             db.session.rollback()
             logger.error(f"[TASK FAIL] Error updating DB for candidate {candidate_id} after parsing: {update_err}", exc_info=True)
             try:
                 candidate_refetch = Candidate.query.get(candidate_id)
                 if candidate_refetch:
                      candidate_refetch.current_status = 'ParsingFailed'
                      # Add error details to notes (append carefully)
                      error_note = f"\nDB update failed after parsing: {update_err} at {datetime.now(timezone.utc).isoformat()}"
                      candidate_refetch.notes = (candidate_refetch.notes or "") + error_note
                      db.session.commit()
             except Exception as final_err:
                 logger.error(f"[TASK FAIL] Failed to set status to ParsingFailed for candidate {candidate_id}: {final_err}")
             return f"Failed to update DB for candidate {candidate_id} after parsing."


    except Exception as e:
        db.session.rollback()
        logger.error(f"[TASK FAIL] Unexpected error in parse_cv_task for Candidate ID {candidate_id}: {e}", exc_info=True)
        try:
             if candidate: # Check if candidate object was fetched before error
                 candidate_refetch = Candidate.query.get(candidate_id)
                 if candidate_refetch:
                      candidate_refetch.current_status = 'ParsingFailed'
                      error_note = f"\nUnexpected task error: {e} at {datetime.now(timezone.utc).isoformat()}"
                      candidate_refetch.notes = (candidate_refetch.notes or "") + error_note
                      db.session.commit()
        except Exception as final_err:
             logger.error(f"[TASK FAIL] Failed final status update for candidate {candidate_id} after unexpected error: {final_err}")
        # Do not retry automatically for now, as it might repeat the same error
        # self.retry(exc=e, countdown=...)
        return f"Unexpected error processing candidate {candidate_id}."