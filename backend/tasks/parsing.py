# backend/app/tasks/parsing.py

from flask import current_app
from app import celery, db
from app.models import Candidate, Position  # Βεβαιώσου ότι το Position είναι εδώ αν το χρησιμοποιείς
from app.services import textkernel_service, s3_service
import logging
import json  # Αν και δεν χρησιμοποιείται άμεσα εδώ, μπορεί να είναι χρήσιμο για debugging
from datetime import datetime, timezone as dt_timezone
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import func

logger = logging.getLogger(__name__)


def _extract_parsed_field(data_dict, primary_key, secondary_key=None, default_value=None):
    """Helper to safely extract values from nested dictionaries."""
    if not isinstance(data_dict, dict):
        return default_value
    value = data_dict.get(primary_key)
    if secondary_key and isinstance(value, dict):
        return value.get(secondary_key, default_value)
    return value if value is not None else default_value


def _update_candidate_fields_from_parsed_data(candidate_to_update: Candidate, parsed_cv_data: dict, new_cv_s3_key: str,
                                              new_cv_original_filename: str, is_update_for_existing: bool):
    """
    Helper function to update candidate fields from parsed CV data.
    Manages CV path replacement and history.
    """
    logger.debug(
        f"Updating fields for candidate ID: {candidate_to_update.candidate_id} with data from S3 key: {new_cv_s3_key}")

    contact_info = _extract_parsed_field(parsed_cv_data, 'ContactInformation', default_value={})
    person_names = _extract_parsed_field(contact_info, 'CandidateName', default_value={})
    personal_attrs = _extract_parsed_field(parsed_cv_data, 'PersonalAttributes', default_value={})

    candidate_to_update.first_name = _extract_parsed_field(person_names, 'GivenName') or candidate_to_update.first_name
    candidate_to_update.last_name = _extract_parsed_field(person_names, 'FamilyName') or candidate_to_update.last_name

    # --- MODIFIED EMAIL HANDLING ---
    email_list_cv = _extract_parsed_field(contact_info, 'EmailAddresses', default_value=[])
    parsed_email_from_cv = None
    if isinstance(email_list_cv, list) and email_list_cv:
        parsed_email_from_cv = email_list_cv[0].lower().strip()

    if parsed_email_from_cv:
        if not candidate_to_update.email:  # If placeholder or existing candidate had no email
            candidate_to_update.email = parsed_email_from_cv
            logger.info(
                f"Candidate {candidate_to_update.candidate_id}: Email set to '{parsed_email_from_cv}' from CV (was empty).")
            # No specific history event here as this is part of initial population or placeholder update
        elif is_update_for_existing and candidate_to_update.email.lower().strip() != parsed_email_from_cv:
            # Email in CV is different from existing candidate's email.
            # Check if the new email from CV is already used by ANOTHER candidate in the same company.
            existing_other_candidate_with_new_email = Candidate.query.filter(
                Candidate.email == parsed_email_from_cv,  # Case-insensitive handled by .lower().strip() before
                Candidate.company_id == candidate_to_update.company_id,
                Candidate.candidate_id != candidate_to_update.candidate_id  # Exclude the current candidate
            ).first()

            if existing_other_candidate_with_new_email:
                logger.warning(
                    f"Candidate {candidate_to_update.candidate_id}: New CV has email '{parsed_email_from_cv}', "
                    f"which is already used by another candidate (ID: {existing_other_candidate_with_new_email.candidate_id}) "
                    f"in company {candidate_to_update.company_id}. Existing email '{candidate_to_update.email}' retained."
                )
                candidate_to_update.add_history_event(
                    event_type="email_update_conflict",
                    description=(
                        f"Email in new CV ('{parsed_email_from_cv}') conflicts with another existing candidate. "
                        f"Original email ('{candidate_to_update.email}') was retained."
                    ),
                    actor_id=None,  # System action
                    details={"cv_email": parsed_email_from_cv, "record_email": candidate_to_update.email,
                             "conflicting_candidate_id": str(existing_other_candidate_with_new_email.candidate_id)}
                )
            else:
                # New email is free. Update the email.
                old_email_for_history = candidate_to_update.email
                candidate_to_update.email = parsed_email_from_cv
                logger.info(
                    f"Candidate {candidate_to_update.candidate_id}: Email updated from '{old_email_for_history}' to '{parsed_email_from_cv}' based on new CV."
                )
                candidate_to_update.add_history_event(
                    event_type="email_updated_from_cv",
                    description=f"Email updated from '{old_email_for_history}' to '{parsed_email_from_cv}' based on new CV.",
                    actor_id=None,  # System action
                    details={"old_email": old_email_for_history, "new_email": parsed_email_from_cv}
                )
        # If parsed_email_from_cv is same as candidate_to_update.email, or not is_update_for_existing and email was already there, no change, no log here.
    # --- END OF MODIFIED EMAIL HANDLING ---

    phone_list = _extract_parsed_field(contact_info, 'Telephones', default_value=[])
    if isinstance(phone_list, list) and phone_list:
        first_phone_obj = phone_list[0]
        if isinstance(first_phone_obj, dict):
            # Prefer Normalized, fallback to Raw
            phone_to_set = _extract_parsed_field(first_phone_obj, 'Normalized')
            if not phone_to_set:
                phone_to_set = _extract_parsed_field(first_phone_obj, 'Raw')
            candidate_to_update.phone_number = phone_to_set

    dob_str = _extract_parsed_field(_extract_parsed_field(personal_attrs, 'DateOfBirth', default_value={}), 'Date')
    if dob_str:
        try:
            birth_date = datetime.strptime(dob_str, "%Y-%m-%d").date()  # Expects YYYY-MM-DD
            today = datetime.now(dt_timezone.utc).date()
            age_val = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
            candidate_to_update.age = age_val
        except ValueError:
            logger.warning(
                f"Could not parse DateOfBirth: {dob_str} for candidate {candidate_to_update.candidate_id}. Expected YYYY-MM-DD.")

    education_section = _extract_parsed_field(_extract_parsed_field(parsed_cv_data, 'Education', default_value={}),
                                              'EducationDetails', default_value=[])
    if isinstance(education_section, list) and education_section:
        edu_texts = []
        for edu_entry in education_section:  # Renamed 'edu' to 'edu_entry' to avoid conflict
            if not isinstance(edu_entry, dict): continue
            school_name_obj = _extract_parsed_field(edu_entry, 'SchoolName', default_value={})
            school = _extract_parsed_field(school_name_obj, 'Normalized') or _extract_parsed_field(school_name_obj,
                                                                                                   'Raw', 'N/A')

            degree_obj = _extract_parsed_field(edu_entry, 'Degree', default_value={})
            degree_name_obj = _extract_parsed_field(degree_obj, 'Name', default_value={})
            degree_name = _extract_parsed_field(degree_name_obj, 'Normalized') or _extract_parsed_field(degree_name_obj,
                                                                                                        'Raw', 'N/A')

            dates_of_attendance = _extract_parsed_field(edu_entry, 'DatesOfAttendance', default_value={})
            start_date_obj = _extract_parsed_field(dates_of_attendance, 'StartDate', default_value={})
            start_date = _extract_parsed_field(start_date_obj, 'Date', '')  # Assuming YYYY-MM-DD or similar

            end_date_obj = _extract_parsed_field(dates_of_attendance, 'EndDate', default_value={})
            end_date_str_from_parser = _extract_parsed_field(end_date_obj, 'StringDate',
                                                             '')  # Textkernel often uses 'StringDate' for 'current'
            end_date = _extract_parsed_field(end_date_obj, 'Date', '')  # Assuming YYYY-MM-DD or similar

            if end_date_str_from_parser and 'current' in end_date_str_from_parser.lower():
                end_date_display = 'Present'
            elif end_date:
                end_date_display = end_date
            else:
                end_date_display = 'N/A'

            start_date_display = start_date if start_date else 'N/A'

            edu_texts.append(
                f"School: {school}, Degree: {degree_name}, Dates: {start_date_display} - {end_date_display}")
        candidate_to_update.education_summary = "\n---\n".join(edu_texts) if edu_texts else None

    experience_section = _extract_parsed_field(
        _extract_parsed_field(parsed_cv_data, 'EmploymentHistory', default_value={}), 'Positions', default_value=[])
    if isinstance(experience_section, list) and experience_section:
        exp_texts = []
        for exp_entry in experience_section:  # Renamed 'exp' to 'exp_entry'
            if not isinstance(exp_entry, dict): continue
            employer_name_obj = _extract_parsed_field(exp_entry, 'Employer', default_value={})
            employer_name_data = _extract_parsed_field(employer_name_obj, 'Name', default_value={})
            employer = _extract_parsed_field(employer_name_data, 'Normalized') or _extract_parsed_field(
                employer_name_data, 'Raw', 'N/A')

            title_obj = _extract_parsed_field(exp_entry, 'JobTitle', default_value={})
            title = _extract_parsed_field(title_obj, 'Normalized') or _extract_parsed_field(title_obj, 'Raw', 'N/A')

            description = _extract_parsed_field(exp_entry, 'Description', '')
            exp_texts.append(f"Employer: {employer}, Title: {title}\n   Description: {description.strip()}")
        candidate_to_update.experience_summary = "\n------\n".join(exp_texts) if exp_texts else None

    skills_data = _extract_parsed_field(parsed_cv_data, 'Skills', default_value={})
    # Textkernel's "Raw" skills are often a list of skill objects, each with a "Name"
    raw_skills_list = _extract_parsed_field(skills_data, 'Raw', default_value=[])
    if isinstance(raw_skills_list, list) and raw_skills_list:
        skills_names = [_extract_parsed_field(s, 'Name') for s in raw_skills_list if
                        isinstance(s, dict) and _extract_parsed_field(s, 'Name')]
        candidate_to_update.skills_summary = ", ".join(filter(None, skills_names)) if skills_names else None
    else:  # Fallback for older structures or if "Raw" is not a list of dicts
        skills_text_blob = _extract_parsed_field(skills_data, 'Text')  # Might be a single string
        if skills_text_blob and not candidate_to_update.skills_summary:  # Only if not already populated by Raw
            candidate_to_update.skills_summary = skills_text_blob

    languages_section = _extract_parsed_field(parsed_cv_data, 'LanguageCompetencies', default_value=[])
    if isinstance(languages_section, list) and languages_section:
        lang_list = [_extract_parsed_field(lang, 'Language') for lang in languages_section if
                     isinstance(lang, dict) and _extract_parsed_field(lang, 'Language')]
        candidate_to_update.languages = ", ".join(filter(None, lang_list)) if lang_list else None

    seminar_section = _extract_parsed_field(_extract_parsed_field(parsed_cv_data, 'Training', default_value={}),
                                            'TrainingDetails', default_value=[])
    if isinstance(seminar_section, list) and seminar_section:
        seminar_texts = []
        for sem_entry in seminar_section:  # Renamed 'sem'
            if not isinstance(sem_entry, dict): continue
            name = _extract_parsed_field(sem_entry, 'Name', 'N/A')
            date_obj = _extract_parsed_field(sem_entry, 'Date', default_value={})  # Date can be an object or string
            date_str = ''
            if isinstance(date_obj, dict):
                date_str = _extract_parsed_field(date_obj, 'Date', '')  # Assuming YYYY-MM-DD
            elif isinstance(date_obj, str):
                date_str = date_obj

            seminar_texts.append(f"Seminar: {name} ({date_str.strip()})")
        candidate_to_update.seminars = "\n---\n".join(seminar_texts) if seminar_texts else None

    # CV Path and History Management
    old_cv_path_for_history = candidate_to_update.cv_storage_path
    old_cv_filename_for_history = candidate_to_update.cv_original_filename

    if old_cv_path_for_history and old_cv_path_for_history != new_cv_s3_key:
        logger.info(
            f"Candidate {candidate_to_update.candidate_id} has old CV {old_cv_path_for_history}. Replacing with {new_cv_s3_key}.")
        candidate_to_update.add_history_event(
            event_type="cv_replaced",
            description=f"New CV uploaded ('{new_cv_original_filename}'), replacing old one ('{old_cv_filename_for_history or 'Unknown old name'}').",
            actor_id=None,  # System action
            details={"old_cv_path": old_cv_path_for_history, "new_cv_path": new_cv_s3_key,
                     "old_filename": old_cv_filename_for_history, "new_filename": new_cv_original_filename}
        )
        try:
            logger.info(f"Attempting to delete old S3 file: {old_cv_path_for_history}")
            s3_service.delete_file(old_cv_path_for_history)
            logger.info(f"Successfully deleted old S3 file: {old_cv_path_for_history}")
        except Exception as s3_del_err:
            logger.error(f"Failed to delete old S3 file {old_cv_path_for_history}: {s3_del_err}")
    elif not old_cv_path_for_history and new_cv_s3_key:  # First CV for this candidate record
        candidate_to_update.add_history_event(
            event_type="cv_added",
            description=f"CV ('{new_cv_original_filename}') added.",
            actor_id=None,  # System action
            details={"new_cv_path": new_cv_s3_key, "new_filename": new_cv_original_filename}
        )
    # If cv_storage_path is same as new_cv_s3_key, it means we're re-processing the same CV,
    # no specific history event for replacement needed, but other fields might update.

    candidate_to_update.cv_storage_path = new_cv_s3_key
    candidate_to_update.cv_original_filename = new_cv_original_filename

    # General note about parsing
    parsed_note = f"CV data extracted/updated from '{new_cv_original_filename}' on {datetime.now(dt_timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}."
    if candidate_to_update.notes:
        # Avoid adding the same parsing note multiple times if re-parsing the same file
        if parsed_note not in candidate_to_update.notes:
            candidate_to_update.notes += f"\n{parsed_note}"
    else:
        candidate_to_update.notes = parsed_note

    flag_modified(candidate_to_update, "notes")  # Ensure notes are saved if modified
    candidate_to_update.updated_at = datetime.now(dt_timezone.utc)
    logger.debug(f"Candidate {candidate_to_update.candidate_id} fields prepared for database commit.")


@celery.task(bind=True, name='tasks.parsing.parse_cv_task', acks_late=True, max_retries=3, default_retry_delay=60)
def parse_cv_task(self, placeholder_candidate_id: str, s3_file_key: str, company_id: int):
    logger.info(
        f"[TASK START] parse_cv_task for placeholder_id: {placeholder_candidate_id}, S3: {s3_file_key}, Company: {company_id}. Attempt: {self.request.retries + 1}")

    placeholder_candidate = Candidate.query.get(placeholder_candidate_id)
    if not placeholder_candidate:
        logger.error(f"[TASK FAIL] Placeholder candidate {placeholder_candidate_id} not found. Aborting.")
        # Attempt to delete S3 file only if the placeholder is truly gone and not merged.
        # This logic might be complex if another process could have already handled it.
        # For now, let's assume if placeholder is gone, the S3 file might be orphaned.
        try:
            s3_service.delete_file(s3_file_key)
            logger.info(
                f"Deleted S3 file {s3_file_key} as placeholder {placeholder_candidate_id} was not found (final attempt).")
        except Exception as s3_del_err:
            logger.error(
                f"Failed to delete S3 file {s3_file_key} for non-existent placeholder {placeholder_candidate_id}: {s3_del_err}")
        return f"Placeholder candidate {placeholder_candidate_id} not found."

    # Original filename from the placeholder, as it was at the time of upload
    new_cv_original_filename = placeholder_candidate.cv_original_filename

    logger.info(f"[TASK] Calling Textkernel for placeholder_id: {placeholder_candidate_id}, S3: {s3_file_key}")
    try:
        parsed_cv_data = textkernel_service.parse_cv_via_textkernel(s3_file_key)
    except Exception as tk_api_exc:
        logger.error(f"[TASK RETRY/FAIL] Textkernel API call failed critically for {s3_file_key}: {tk_api_exc}",
                     exc_info=True)
        try:
            # Retry the task if it's a network issue, etc.
            raise self.retry(exc=tk_api_exc)
        except self.MaxRetriesExceededError:
            logger.error(f"[TASK FAIL] Max retries exceeded for Textkernel API call for {s3_file_key}.")
            placeholder_candidate.current_status = 'ParsingFailed'
            placeholder_candidate.notes = (
                                                      placeholder_candidate.notes or "") + f"\nTextkernel API Error (Max Retries): {str(tk_api_exc)[:200]} ({datetime.now(dt_timezone.utc).isoformat()})"
            flag_modified(placeholder_candidate, "notes")
            db.session.commit()
            return f"Textkernel API call failed critically after retries for {s3_file_key}."

    if parsed_cv_data is None or (isinstance(parsed_cv_data, dict) and 'error' in parsed_cv_data):
        error_msg = parsed_cv_data.get('error', "Unknown Textkernel API error") if isinstance(parsed_cv_data,
                                                                                              dict) else "Textkernel API call returned no data"
        logger.error(
            f"[TASK FAIL] Textkernel service issue for {placeholder_candidate_id} (S3: {s3_file_key}): {error_msg}. Setting status to ParsingFailed.")
        placeholder_candidate.current_status = 'ParsingFailed'
        placeholder_candidate.notes = (
                                                  placeholder_candidate.notes or "") + f"\nTextkernel Error: {str(error_msg)[:200]} ({datetime.now(dt_timezone.utc).isoformat()})"
        flag_modified(placeholder_candidate, "notes")
        db.session.commit()
        return f"Textkernel service issue for {placeholder_candidate_id}."

    # --- Email Extraction and Candidate Identification ---
    extracted_email_from_cv = None
    contact_info_cv = _extract_parsed_field(parsed_cv_data, 'ContactInformation', default_value={})
    email_list_cv = _extract_parsed_field(contact_info_cv, 'EmailAddresses', default_value=[])
    if isinstance(email_list_cv, list) and email_list_cv:
        extracted_email_from_cv = email_list_cv[0].lower().strip()  # Standardize email

    if not extracted_email_from_cv:
        logger.warning(
            f"[TASK WARN] No email found in parsed CV for placeholder {placeholder_candidate_id}. Updating placeholder directly.")
        try:
            _update_candidate_fields_from_parsed_data(placeholder_candidate, parsed_cv_data, s3_file_key,
                                                      new_cv_original_filename, is_update_for_existing=False)
            placeholder_candidate.current_status = 'NeedsReview'  # Or 'New' if you prefer initial state
            placeholder_candidate.add_history_event(
                event_type="cv_parsed_no_email",
                description=f"CV parsed, no email found. Candidate data populated.",
                actor_id=None,
                details={"cv_path": s3_file_key}
            )
            db.session.commit()
            logger.info(
                f"[TASK SUCCESS] Placeholder {placeholder_candidate_id} updated (no email in CV). Status: {placeholder_candidate.current_status}")
            return f"Updated placeholder {placeholder_candidate_id} (no email in CV)."
        except Exception as e_update_placeholder:
            db.session.rollback()
            logger.error(
                f"[TASK FAIL] Error updating placeholder {placeholder_candidate_id} (no email): {e_update_placeholder}",
                exc_info=True)
            placeholder_candidate.current_status = 'ParsingFailed'
            placeholder_candidate.notes = (
                                                      placeholder_candidate.notes or "") + f"\nDB Error (no email update): {str(e_update_placeholder)[:200]}"
            flag_modified(placeholder_candidate, "notes")
            db.session.commit()
            return f"Failed to update placeholder {placeholder_candidate_id} (no email)."

    # At this point, we have an extracted_email_from_cv.
    # Find if an existing candidate (excluding the placeholder itself, if it somehow got an email already)
    # for this company already has this email.
    existing_candidate_with_cv_email = Candidate.query.filter(
        Candidate.email == extracted_email_from_cv,  # Already lowercased and stripped
        Candidate.company_id == company_id,
        Candidate.candidate_id != placeholder_candidate.candidate_id  # Important: don't find the placeholder itself
    ).first()

    target_candidate_for_processing = None
    delete_placeholder_after_success = False

    if existing_candidate_with_cv_email:
        logger.info(
            f"[TASK] Found existing candidate (ID: {existing_candidate_with_cv_email.candidate_id}) with email {extracted_email_from_cv}. "
            f"Will merge data from placeholder {placeholder_candidate_id} into this existing candidate."
        )
        target_candidate_for_processing = existing_candidate_with_cv_email
        delete_placeholder_after_success = True

        # Merge positions from placeholder to existing candidate if they are not already associated
        if placeholder_candidate.positions:
            existing_pos_names = {p.position_name.lower().strip() for p in target_candidate_for_processing.positions}
            for p_placeholder in placeholder_candidate.positions:
                placeholder_pos_name_lower = p_placeholder.position_name.lower().strip()
                if placeholder_pos_name_lower not in existing_pos_names:
                    # Find or create the position object properly
                    position_obj = Position.query.filter(
                        func.lower(Position.position_name) == placeholder_pos_name_lower,
                        Position.company_id == company_id
                    ).first()
                    if not position_obj:  # If position doesn't exist for the company, create it
                        position_obj = Position(position_name=p_placeholder.position_name,
                                                # Use original case for creation
                                                company_id=company_id, status='Open')
                        db.session.add(position_obj)
                        logger.info(
                            f"Created new position '{p_placeholder.position_name}' for company {company_id} during merge.")

                    if position_obj not in target_candidate_for_processing.positions:  # Check association
                        target_candidate_for_processing.positions.append(position_obj)
                        logger.info(
                            f"Associated position '{p_placeholder.position_name}' from placeholder to existing candidate {target_candidate_for_processing.candidate_id}")
            flag_modified(target_candidate_for_processing, "positions")  # Mark for update if list changed

    else:  # No *other* existing candidate with this email. The placeholder is the one to update.
        logger.info(
            f"[TASK] No *other* existing candidate with email {extracted_email_from_cv}. "
            f"Updating placeholder {placeholder_candidate_id} with this email and parsed data."
        )
        target_candidate_for_processing = placeholder_candidate
        # Set the email on the placeholder if it wasn't set or was different (should be handled by _update_candidate_fields)
        if target_candidate_for_processing.email != extracted_email_from_cv:
            target_candidate_for_processing.email = extracted_email_from_cv  # Ensure placeholder gets the email

    # --- Final Update and Commit ---
    try:
        _update_candidate_fields_from_parsed_data(
            target_candidate_for_processing,
            parsed_cv_data,
            s3_file_key,  # This is the S3 key of the CV we just parsed
            new_cv_original_filename,  # This is the original filename from the placeholder
            is_update_for_existing=bool(existing_candidate_with_cv_email)
            # True if we are merging into a pre-existing record
        )

        original_status_before_update = target_candidate_for_processing.current_status
        new_status_for_candidate = 'NeedsReview'  # Default to NeedsReview after successful parsing/merge

        # If we merged into an existing candidate, their status might need resetting.
        if existing_candidate_with_cv_email:  # i.e., delete_placeholder_after_success is True
            if original_status_before_update in ['Hired', 'Rejected', 'Declined', 'ParsingFailed']:
                target_candidate_for_processing.add_history_event(
                    event_type="cv_re_submission_merge",
                    description=f"New CV uploaded and merged. Previous status was '{original_status_before_update}'. Status reset to '{new_status_for_candidate}'.",
                    actor_id=None,
                    details={"new_cv_path": s3_file_key, "previous_status": original_status_before_update,
                             "merged_from_placeholder_id": str(placeholder_candidate_id)}
                )
            elif original_status_before_update not in ['Processing', 'New']:  # If it was NeedsReview, Interview, etc.
                target_candidate_for_processing.add_history_event(
                    event_type="cv_refresh_merge",
                    description=f"CV data refreshed by new upload and merge. Previous status was '{original_status_before_update}'. Status set to '{new_status_for_candidate}'.",
                    actor_id=None,
                    details={"new_cv_path": s3_file_key, "previous_status": original_status_before_update,
                             "merged_from_placeholder_id": str(placeholder_candidate_id)}
                )
        else:  # This was the placeholder candidate being fully populated
            target_candidate_for_processing.add_history_event(
                event_type="cv_parsed_and_populated",
                description=f"CV parsed. Candidate data populated. Status set to '{new_status_for_candidate}'.",
                actor_id=None,
                details={"cv_path": s3_file_key}
            )

        target_candidate_for_processing.current_status = new_status_for_candidate

        db.session.commit()
        logger.info(
            f"[TASK SUCCESS] Candidate {target_candidate_for_processing.candidate_id} (Company: {target_candidate_for_processing.company_id}) "
            f"updated/populated. Final Status: {target_candidate_for_processing.current_status}"
        )

        if delete_placeholder_after_success:
            # Now that the main candidate is updated, delete the placeholder
            # We need to fetch it again in case session state is tricky
            placeholder_to_delete = Candidate.query.get(placeholder_candidate_id)
            if placeholder_to_delete:
                logger.info(
                    f"Deleting placeholder candidate {placeholder_candidate_id} as data was merged to {target_candidate_for_processing.candidate_id}.")
                db.session.delete(placeholder_to_delete)
                db.session.commit()
                logger.info(f"Placeholder {placeholder_candidate_id} deleted from DB.")
            else:
                logger.warning(
                    f"Could not find placeholder {placeholder_candidate_id} for deletion after merge. It might have been deleted by another process or error.")

        return f"Processed CV. Final Candidate ID: {target_candidate_for_processing.candidate_id}, Status: {target_candidate_for_processing.current_status}"

    except Exception as e_final_update:
        db.session.rollback()
        final_candidate_id_for_log = target_candidate_for_processing.candidate_id if target_candidate_for_processing else placeholder_candidate_id
        logger.error(
            f"[TASK FAIL] Error during final DB update/merge for candidate processing related to S3 key {s3_file_key} (target/placeholder ID: {final_candidate_id_for_log}): {e_final_update}",
            exc_info=True
        )

        # Re-fetch the placeholder to mark it as failed, as its state might be stale
        placeholder_to_mark_failed = Candidate.query.get(placeholder_candidate_id)
        if placeholder_to_mark_failed:
            placeholder_to_mark_failed.current_status = 'ParsingFailed'
            placeholder_to_mark_failed.notes = (
                                                           placeholder_to_mark_failed.notes or "") + f"\nDB Update/Merge Error: {str(e_final_update)[:200]} ({datetime.now(dt_timezone.utc).isoformat()})"
            flag_modified(placeholder_to_mark_failed, "notes")
            try:
                db.session.commit()
            except Exception as e_commit_fail_status:  # Nested try-except for commit
                db.session.rollback()
                logger.error(
                    f"CRITICAL: Could not even commit ParsingFailed status for placeholder {placeholder_candidate_id} after previous error: {e_commit_fail_status}")
        else:
            logger.error(
                f"CRITICAL: Placeholder {placeholder_candidate_id} not found to mark as ParsingFailed after DB Update/Merge Error.")

        # If we were attempting to merge into an existing candidate and that failed,
        # the existing candidate is NOT set to ParsingFailed, only the placeholder.
        # The S3 key (new_cv_s3_key) remains associated with the placeholder if it's not merged.
        # If merge happened but failed at commit, s3_key is now on target_candidate_for_processing.

        return f"Failed final update for CV {s3_file_key}."