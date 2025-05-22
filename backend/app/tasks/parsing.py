# backend/app/tasks/parsing.py
from flask import current_app
from app import celery, db, s3_service_instance
from app.models import Candidate, Position
from app.services import textkernel_service
import logging
from datetime import datetime, timezone as dt_timezone
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import func
import uuid

logger = logging.getLogger(__name__)


def _extract_parsed_field(data_dict, primary_key, secondary_key=None, default_value=None):
    if not isinstance(data_dict, dict):
        return default_value
    value = data_dict.get(primary_key)
    if secondary_key and isinstance(value, dict):
        return value.get(secondary_key, default_value)
    return value if value is not None else default_value


def _update_candidate_fields_from_parsed_data(candidate_to_update: Candidate, parsed_cv_data: dict, new_cv_s3_key: str,
                                              new_cv_original_filename: str, new_cv_content_type: str,
                                              is_update_for_existing: bool,
                                              placeholder_cv_pdf_key: str = None):  # Νέα παράμετρος
    logger.debug(
        f"Updating fields for candidate ID: {candidate_to_update.candidate_id} with data from S3 key: {new_cv_s3_key}")

    contact_info = _extract_parsed_field(parsed_cv_data, 'ContactInformation', default_value={})
    person_names = _extract_parsed_field(contact_info, 'CandidateName', default_value={})
    personal_attrs = _extract_parsed_field(parsed_cv_data, 'PersonalAttributes', default_value={})

    candidate_to_update.first_name = _extract_parsed_field(person_names, 'GivenName') or candidate_to_update.first_name
    candidate_to_update.last_name = _extract_parsed_field(person_names, 'FamilyName') or candidate_to_update.last_name

    email_list_cv = _extract_parsed_field(contact_info, 'EmailAddresses', default_value=[])
    parsed_email_from_cv = None
    if isinstance(email_list_cv, list) and email_list_cv:
        parsed_email_from_cv = email_list_cv[0].lower().strip()

    if parsed_email_from_cv:
        if not candidate_to_update.email or candidate_to_update.email.startswith("placeholder-"):
            candidate_to_update.email = parsed_email_from_cv
            logger.info(
                f"Candidate {candidate_to_update.candidate_id}: Email set to '{parsed_email_from_cv}' from CV (was placeholder/empty).")
        elif is_update_for_existing and candidate_to_update.email.lower().strip() != parsed_email_from_cv:
            existing_other_candidate_with_new_email = Candidate.query.filter(
                Candidate.email == parsed_email_from_cv,
                Candidate.company_id == candidate_to_update.company_id,
                Candidate.candidate_id != candidate_to_update.candidate_id
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
                    actor_id=None,
                    details={"cv_email": parsed_email_from_cv, "record_email": candidate_to_update.email,
                             "conflicting_candidate_id": str(existing_other_candidate_with_new_email.candidate_id)}
                )
            else:
                old_email_for_history = candidate_to_update.email
                candidate_to_update.email = parsed_email_from_cv
                logger.info(
                    f"Candidate {candidate_to_update.candidate_id}: Email updated from '{old_email_for_history}' to '{parsed_email_from_cv}' based on new CV."
                )
                candidate_to_update.add_history_event(
                    event_type="email_updated_from_cv",
                    description=f"Email updated from '{old_email_for_history}' to '{parsed_email_from_cv}' based on new CV.",
                    actor_id=None,
                    details={"old_email": old_email_for_history, "new_email": parsed_email_from_cv}
                )

    phone_list = _extract_parsed_field(contact_info, 'Telephones', default_value=[])
    if isinstance(phone_list, list) and phone_list:
        first_phone_obj = phone_list[0]
        if isinstance(first_phone_obj, dict):
            phone_to_set = _extract_parsed_field(first_phone_obj, 'Normalized')
            if not phone_to_set:
                phone_to_set = _extract_parsed_field(first_phone_obj, 'Raw')
            candidate_to_update.phone_number = phone_to_set or candidate_to_update.phone_number

    dob_str = _extract_parsed_field(_extract_parsed_field(personal_attrs, 'DateOfBirth', default_value={}), 'Date')
    if dob_str:
        try:
            birth_date = datetime.strptime(dob_str, "%Y-%m-%d").date()
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
        for edu_entry in education_section:
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
            start_date = _extract_parsed_field(start_date_obj, 'Date', '')
            end_date_obj = _extract_parsed_field(dates_of_attendance, 'EndDate', default_value={})
            end_date_str_from_parser = _extract_parsed_field(end_date_obj, 'StringDate', '')
            end_date = _extract_parsed_field(end_date_obj, 'Date', '')
            if end_date_str_from_parser and 'current' in end_date_str_from_parser.lower():
                end_date_display = 'Present'
            elif end_date:
                end_date_display = end_date
            else:
                end_date_display = 'N/A'
            start_date_display = start_date if start_date else 'N/A'
            edu_texts.append(
                f"School: {school}, Degree: {degree_name}, Dates: {start_date_display} - {end_date_display}")
        candidate_to_update.education_summary = "\n---\n".join(
            edu_texts) if edu_texts else candidate_to_update.education_summary

    experience_section = _extract_parsed_field(
        _extract_parsed_field(parsed_cv_data, 'EmploymentHistory', default_value={}), 'Positions', default_value=[])
    if isinstance(experience_section, list) and experience_section:
        exp_texts = []
        for exp_entry in experience_section:
            if not isinstance(exp_entry, dict): continue
            employer_name_obj = _extract_parsed_field(exp_entry, 'Employer', default_value={})
            employer_name_data = _extract_parsed_field(employer_name_obj, 'Name', default_value={})
            employer = _extract_parsed_field(employer_name_data, 'Normalized') or _extract_parsed_field(
                employer_name_data, 'Raw', 'N/A')
            title_obj = _extract_parsed_field(exp_entry, 'JobTitle', default_value={})
            title = _extract_parsed_field(title_obj, 'Normalized') or _extract_parsed_field(title_obj, 'Raw', 'N/A')
            description = _extract_parsed_field(exp_entry, 'Description', '')
            exp_texts.append(f"Employer: {employer}, Title: {title}\n   Description: {description.strip()}")
        candidate_to_update.experience_summary = "\n------\n".join(
            exp_texts) if exp_texts else candidate_to_update.experience_summary

    skills_data = _extract_parsed_field(parsed_cv_data, 'Skills', default_value={})
    raw_skills_list = _extract_parsed_field(skills_data, 'Raw', default_value=[])
    if isinstance(raw_skills_list, list) and raw_skills_list:
        skills_names = [_extract_parsed_field(s, 'Name') for s in raw_skills_list if
                        isinstance(s, dict) and _extract_parsed_field(s, 'Name')]
        candidate_to_update.skills_summary = ", ".join(
            filter(None, skills_names)) if skills_names else candidate_to_update.skills_summary
    else:
        skills_text_blob = _extract_parsed_field(skills_data, 'Text')
        if skills_text_blob and (not candidate_to_update.skills_summary or is_update_for_existing):
            candidate_to_update.skills_summary = skills_text_blob

    languages_section = _extract_parsed_field(parsed_cv_data, 'LanguageCompetencies', default_value=[])
    if isinstance(languages_section, list) and languages_section:
        lang_list = [_extract_parsed_field(lang, 'Language') for lang in languages_section if
                     isinstance(lang, dict) and _extract_parsed_field(lang, 'Language')]
        candidate_to_update.languages = ", ".join(
            filter(None, lang_list)) if lang_list else candidate_to_update.languages

    seminar_section = _extract_parsed_field(_extract_parsed_field(parsed_cv_data, 'Training', default_value={}),
                                            'TrainingDetails', default_value=[])
    if isinstance(seminar_section, list) and seminar_section:
        seminar_texts = []
        for sem_entry in seminar_section:
            if not isinstance(sem_entry, dict): continue
            name = _extract_parsed_field(sem_entry, 'Name', 'N/A')
            date_obj = _extract_parsed_field(sem_entry, 'Date', default_value={})
            date_str = ''
            if isinstance(date_obj, dict):
                date_str = _extract_parsed_field(date_obj, 'Date', '')
            elif isinstance(date_obj, str):
                date_str = date_obj
            seminar_texts.append(f"Seminar: {name} ({date_str.strip()})")
        candidate_to_update.seminars = "\n---\n".join(seminar_texts) if seminar_texts else candidate_to_update.seminars

    old_cv_path_for_history = candidate_to_update.cv_storage_path
    old_cv_filename_for_history = candidate_to_update.cv_original_filename
    old_cv_pdf_key_for_history = candidate_to_update.cv_pdf_storage_key  # Για διαγραφή παλιού PDF

    if old_cv_path_for_history and old_cv_path_for_history != new_cv_s3_key:
        logger.info(
            f"Candidate {candidate_to_update.candidate_id} has old CV {old_cv_path_for_history}. Replacing with {new_cv_s3_key}.")
        candidate_to_update.add_history_event(
            event_type="cv_replaced",
            description=f"New CV uploaded ('{new_cv_original_filename}'), replacing old one ('{old_cv_filename_for_history or 'Unknown old name'}').",
            actor_id=None,
            details={"old_cv_path": old_cv_path_for_history, "new_cv_path": new_cv_s3_key,
                     "old_filename": old_cv_filename_for_history, "new_filename": new_cv_original_filename}
        )
        try:
            logger.info(f"Attempting to delete old S3 file (original): {old_cv_path_for_history}")
            if hasattr(s3_service_instance, 'delete_file') and callable(getattr(s3_service_instance, 'delete_file')):
                s3_service_instance.delete_file(old_cv_path_for_history)
                logger.info(f"Successfully deleted old S3 file (original): {old_cv_path_for_history}")
            else:
                logger.warning(
                    f"s3_service_instance does not have a 'delete_file' method. Old CV {old_cv_path_for_history} not deleted from S3.")

            # Διαγραφή και του παλιού PDF αν υπάρχει και είναι διαφορετικό από το νέο (αν το νέο είναι ήδη PDF)
            if old_cv_pdf_key_for_history and old_cv_pdf_key_for_history != placeholder_cv_pdf_key:
                logger.info(f"Attempting to delete old S3 file (PDF): {old_cv_pdf_key_for_history}")
                if hasattr(s3_service_instance, 'delete_file') and callable(
                        getattr(s3_service_instance, 'delete_file')):
                    s3_service_instance.delete_file(old_cv_pdf_key_for_history)
                    logger.info(f"Successfully deleted old S3 file (PDF): {old_cv_pdf_key_for_history}")
        except Exception as s3_del_err:
            logger.error(f"Failed to delete old S3 file(s) for {old_cv_path_for_history}: {s3_del_err}")
    elif not old_cv_path_for_history and new_cv_s3_key:
        candidate_to_update.add_history_event(
            event_type="cv_added",
            description=f"CV ('{new_cv_original_filename}') added.",
            actor_id=None,
            details={"new_cv_path": new_cv_s3_key, "new_filename": new_cv_original_filename}
        )

    candidate_to_update.cv_storage_path = new_cv_s3_key
    candidate_to_update.cv_original_filename = new_cv_original_filename
    candidate_to_update.cv_content_type = new_cv_content_type  # Ενημέρωση με το content type του νέου αρχείου

    # Ενημέρωση του cv_pdf_storage_key αν μας δόθηκε (π.χ. από το placeholder)
    if placeholder_cv_pdf_key:
        candidate_to_update.cv_pdf_storage_key = placeholder_cv_pdf_key
    elif not candidate_to_update.is_docx:  # Αν το νέο αρχείο δεν είναι docx (π.χ. είναι PDF), καθαρίζουμε το pdf key
        candidate_to_update.cv_pdf_storage_key = None

    parsed_note = f"CV data extracted/updated from '{new_cv_original_filename}' on {datetime.now(dt_timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}."
    if candidate_to_update.notes:
        if parsed_note not in candidate_to_update.notes:
            candidate_to_update.notes += f"\n{parsed_note}"
    else:
        candidate_to_update.notes = parsed_note
    flag_modified(candidate_to_update, "notes")

    candidate_to_update.updated_at = datetime.now(dt_timezone.utc)
    logger.debug(f"Candidate {candidate_to_update.candidate_id} fields prepared for database commit.")


@celery.task(bind=True, acks_late=True, max_retries=3, default_retry_delay=60)
def parse_cv_task(self, placeholder_candidate_id_str: str, s3_file_key: str, company_id: int):
    try:
        placeholder_candidate_uuid = uuid.UUID(placeholder_candidate_id_str)
    except ValueError:
        logger.error(
            f"[TASK FAIL] Invalid UUID format for placeholder_candidate_id: {placeholder_candidate_id_str}. Aborting.")
        try:
            if hasattr(s3_service_instance, 'delete_file') and callable(getattr(s3_service_instance, 'delete_file')):
                s3_service_instance.delete_file(s3_file_key)
                logger.info(
                    f"Deleted S3 file {s3_file_key} due to invalid placeholder ID format {placeholder_candidate_id_str}.")
        except Exception as s3_del_err_invalid_id:
            logger.error(
                f"Failed to delete S3 file {s3_file_key} for invalid placeholder ID {placeholder_candidate_id_str}: {s3_del_err_invalid_id}")
        return f"Invalid placeholder_candidate_id format: {placeholder_candidate_id_str}."

    logger.info(
        f"[TASK START] parse_cv_task for placeholder_id: {placeholder_candidate_id_str}, S3: {s3_file_key}, Company: {company_id}. Attempt: {self.request.retries + 1}")

    placeholder_candidate = db.session.get(Candidate, placeholder_candidate_uuid)
    if not placeholder_candidate:
        logger.error(f"[TASK FAIL] Placeholder candidate {placeholder_candidate_id_str} not found. Aborting.")
        try:
            if hasattr(s3_service_instance, 'delete_file') and callable(getattr(s3_service_instance, 'delete_file')):
                s3_service_instance.delete_file(s3_file_key)
                logger.info(
                    f"Deleted S3 file {s3_file_key} as placeholder {placeholder_candidate_id_str} was not found (final attempt).")
        except Exception as s3_del_err:
            logger.error(
                f"Failed to delete S3 file {s3_file_key} for non-existent placeholder {placeholder_candidate_id_str}: {s3_del_err}")
        return f"Placeholder candidate {placeholder_candidate_id_str} not found."

    new_cv_original_filename = placeholder_candidate.cv_original_filename
    new_cv_content_type = placeholder_candidate.cv_content_type  # Παίρνουμε το content type από τον placeholder
    placeholder_cv_pdf_key = placeholder_candidate.cv_pdf_storage_key  # Παίρνουμε το PDF key από τον placeholder

    logger.info(f"[TASK] Calling Textkernel for placeholder_id: {placeholder_candidate_id_str}, S3: {s3_file_key}")
    try:
        parsed_cv_data = textkernel_service.parse_cv_via_textkernel(s3_file_key)
    except Exception as tk_api_exc:
        logger.error(f"[TASK RETRY/FAIL] Textkernel API call failed critically for {s3_file_key}: {tk_api_exc}",
                     exc_info=True)
        try:
            raise self.retry(exc=tk_api_exc)
        except self.MaxRetriesExceededError:
            logger.error(f"[TASK FAIL] Max retries exceeded for Textkernel API call for {s3_file_key}.")
            placeholder_candidate.current_status = 'ParsingFailed'
            placeholder_candidate.status_last_changed_date = datetime.now(dt_timezone.utc)
            placeholder_candidate.notes = (
                                                  placeholder_candidate.notes or "") + f"\nTextkernel API Error (Max Retries): {str(tk_api_exc)[:200]} ({datetime.now(dt_timezone.utc).isoformat()})"
            flag_modified(placeholder_candidate, "notes")
            db.session.commit()
            return f"Textkernel API call failed critically after retries for {s3_file_key}."

    if parsed_cv_data is None or (isinstance(parsed_cv_data, dict) and 'error' in parsed_cv_data):
        error_msg = parsed_cv_data.get('error', "Unknown Textkernel API error") if isinstance(parsed_cv_data,
                                                                                              dict) else "Textkernel API call returned no data"
        logger.error(
            f"[TASK FAIL] Textkernel service issue for {placeholder_candidate_id_str} (S3: {s3_file_key}): {error_msg}. Setting status to ParsingFailed.")
        placeholder_candidate.current_status = 'ParsingFailed'
        placeholder_candidate.status_last_changed_date = datetime.now(dt_timezone.utc)
        placeholder_candidate.notes = (
                                              placeholder_candidate.notes or "") + f"\nTextkernel Error: {str(error_msg)[:200]} ({datetime.now(dt_timezone.utc).isoformat()})"
        flag_modified(placeholder_candidate, "notes")
        db.session.commit()
        return f"Textkernel service issue for {placeholder_candidate_id_str}."

    extracted_email_from_cv = None
    contact_info_cv = _extract_parsed_field(parsed_cv_data, 'ContactInformation', default_value={})
    email_list_cv = _extract_parsed_field(contact_info_cv, 'EmailAddresses', default_value=[])
    if isinstance(email_list_cv, list) and email_list_cv:
        extracted_email_from_cv = email_list_cv[0].lower().strip()

    if not extracted_email_from_cv:
        logger.warning(
            f"[TASK WARN] No email found in parsed CV for placeholder {placeholder_candidate_id_str}. Updating placeholder directly.")
        try:
            _update_candidate_fields_from_parsed_data(
                placeholder_candidate,
                parsed_cv_data,
                s3_file_key,
                new_cv_original_filename,
                new_cv_content_type,  # Περνάμε το content type
                is_update_for_existing=False,
                placeholder_cv_pdf_key=placeholder_cv_pdf_key  # Περνάμε το PDF key
            )
            placeholder_candidate.current_status = 'NeedsReview'
            placeholder_candidate.status_last_changed_date = datetime.now(dt_timezone.utc)
            placeholder_candidate.add_history_event(
                event_type="cv_parsed_no_email",
                description=f"CV parsed, no email found. Candidate data populated.",
                actor_id=None,
                details={"cv_path": s3_file_key}
            )
            db.session.commit()
            logger.info(
                f"[TASK SUCCESS] Placeholder {placeholder_candidate_id_str} updated (no email in CV). Status: {placeholder_candidate.current_status}")
            return f"Updated placeholder {placeholder_candidate_id_str} (no email in CV)."
        except Exception as e_update_placeholder:
            db.session.rollback()
            logger.error(
                f"[TASK FAIL] Error updating placeholder {placeholder_candidate_id_str} (no email): {e_update_placeholder}",
                exc_info=True)
            placeholder_candidate.current_status = 'ParsingFailed'
            placeholder_candidate.status_last_changed_date = datetime.now(dt_timezone.utc)
            placeholder_candidate.notes = (
                                                  placeholder_candidate.notes or "") + f"\nDB Error (no email update): {str(e_update_placeholder)[:200]}"
            flag_modified(placeholder_candidate, "notes")
            db.session.commit()
            return f"Failed to update placeholder {placeholder_candidate_id_str} (no email)."

    existing_candidate_with_cv_email = Candidate.query.filter(
        Candidate.email == extracted_email_from_cv,
        Candidate.company_id == company_id,
        Candidate.candidate_id != placeholder_candidate.candidate_id
    ).first()

    target_candidate_for_processing = None
    delete_placeholder_after_success = False

    if existing_candidate_with_cv_email:
        logger.info(
            f"[TASK] Found existing candidate (ID: {existing_candidate_with_cv_email.candidate_id}) with email {extracted_email_from_cv}. "
            f"Will merge data from placeholder {placeholder_candidate_id_str} into this existing candidate."
        )
        target_candidate_for_processing = existing_candidate_with_cv_email
        delete_placeholder_after_success = True

        placeholder_positions_to_merge = placeholder_candidate.positions.all()
        if placeholder_positions_to_merge:
            current_target_positions_ids = {p.position_id for p in target_candidate_for_processing.positions.all()}
            for p_placeholder in placeholder_positions_to_merge:
                if p_placeholder.position_id not in current_target_positions_ids:
                    target_candidate_for_processing.positions.append(p_placeholder)
                    logger.info(
                        f"Associated position '{p_placeholder.position_name}' from placeholder to existing candidate {target_candidate_for_processing.candidate_id}")
    else:
        logger.info(
            f"[TASK] No *other* existing candidate with email {extracted_email_from_cv}. "
            f"Updating placeholder {placeholder_candidate_id_str} with this email and parsed data."
        )
        target_candidate_for_processing = placeholder_candidate
        if target_candidate_for_processing.email.startswith("placeholder-"):
            target_candidate_for_processing.email = extracted_email_from_cv
            logger.info(
                f"Placeholder {target_candidate_for_processing.candidate_id} email updated to {extracted_email_from_cv}")

    try:
        _update_candidate_fields_from_parsed_data(
            target_candidate_for_processing,
            parsed_cv_data,
            s3_file_key,
            new_cv_original_filename,
            new_cv_content_type,  # Περνάμε το content type
            is_update_for_existing=bool(existing_candidate_with_cv_email),
            placeholder_cv_pdf_key=placeholder_cv_pdf_key if delete_placeholder_after_success else None
            # Περνάμε το PDF key μόνο αν κάνουμε merge
        )

        original_status_before_update = target_candidate_for_processing.current_status
        new_status_for_candidate = 'NeedsReview'

        if existing_candidate_with_cv_email:
            if original_status_before_update in ['Hired', 'Rejected', 'Declined', 'ParsingFailed']:
                target_candidate_for_processing.add_history_event(
                    event_type="cv_re_submission_merge",
                    description=f"New CV uploaded and merged. Previous status was '{original_status_before_update}'. Status reset to '{new_status_for_candidate}'.",
                    actor_id=None,
                    details={"new_cv_path": s3_file_key, "previous_status": original_status_before_update,
                             "merged_from_placeholder_id": str(placeholder_candidate_uuid)}
                )
            elif original_status_before_update not in ['Processing', 'New']:
                target_candidate_for_processing.add_history_event(
                    event_type="cv_refresh_merge",
                    description=f"CV data refreshed by new upload and merge. Previous status was '{original_status_before_update}'. Status set to '{new_status_for_candidate}'.",
                    actor_id=None,
                    details={"new_cv_path": s3_file_key, "previous_status": original_status_before_update,
                             "merged_from_placeholder_id": str(placeholder_candidate_uuid)}
                )
        else:
            target_candidate_for_processing.add_history_event(
                event_type="cv_parsed_and_populated",
                description=f"CV parsed. Candidate data populated. Status set to '{new_status_for_candidate}'.",
                actor_id=None,
                details={"cv_path": s3_file_key}
            )

        target_candidate_for_processing.current_status = new_status_for_candidate
        target_candidate_for_processing.status_last_changed_date = datetime.now(dt_timezone.utc)

        db.session.commit()
        logger.info(
            f"[TASK SUCCESS] Candidate {target_candidate_for_processing.candidate_id} (Company: {target_candidate_for_processing.company_id}) "
            f"updated/populated. Final Status: {target_candidate_for_processing.current_status}"
        )

        if delete_placeholder_after_success:
            placeholder_to_delete = db.session.get(Candidate, placeholder_candidate_uuid)
            if placeholder_to_delete:
                logger.info(
                    f"Deleting placeholder candidate {placeholder_candidate_id_str} as data was merged to {target_candidate_for_processing.candidate_id}.")
                # Πριν διαγράψουμε τον placeholder, ας βεβαιωθούμε ότι ο target έχει το PDF key αν ο placeholder το είχε
                if placeholder_to_delete.cv_pdf_storage_key and not target_candidate_for_processing.cv_pdf_storage_key:
                    logger.info(
                        f"Copying cv_pdf_storage_key '{placeholder_to_delete.cv_pdf_storage_key}' from placeholder to target {target_candidate_for_processing.candidate_id}")
                    target_candidate_for_processing.cv_pdf_storage_key = placeholder_to_delete.cv_pdf_storage_key
                    # Επίσης, το content_type του αρχικού αρχείου που οδήγησε σε αυτό το PDF
                    target_candidate_for_processing.cv_content_type = placeholder_to_delete.cv_content_type
                    db.session.add(
                        target_candidate_for_processing)  # Add to session if it wasn't already, or to mark dirty
                    db.session.commit()  # Commit the change on target before deleting placeholder

                db.session.delete(placeholder_to_delete)
                db.session.commit()
                logger.info(f"Placeholder {placeholder_candidate_id_str} deleted from DB.")
            else:
                logger.warning(
                    f"Could not find placeholder {placeholder_candidate_id_str} for deletion after merge. It might have been deleted by another process or error.")

        return f"Processed CV. Final Candidate ID: {target_candidate_for_processing.candidate_id}, Status: {target_candidate_for_processing.current_status}"

    except Exception as e_final_update:
        db.session.rollback()
        final_candidate_id_for_log = target_candidate_for_processing.candidate_id if target_candidate_for_processing else placeholder_candidate_id_str
        logger.error(
            f"[TASK FAIL] Error during final DB update/merge for candidate processing related to S3 key {s3_file_key} (target/placeholder ID: {final_candidate_id_for_log}): {e_final_update}",
            exc_info=True
        )

        candidate_to_mark_failed = db.session.get(Candidate, placeholder_candidate_uuid)
        if not candidate_to_mark_failed and existing_candidate_with_cv_email:
            candidate_to_mark_failed = db.session.get(Candidate, existing_candidate_with_cv_email.candidate_id)

        if candidate_to_mark_failed:
            candidate_to_mark_failed.current_status = 'ParsingFailed'
            candidate_to_mark_failed.status_last_changed_date = datetime.now(dt_timezone.utc)
            candidate_to_mark_failed.notes = (
                                                     candidate_to_mark_failed.notes or "") + f"\nDB Update/Merge Error: {str(e_final_update)[:200]} ({datetime.now(dt_timezone.utc).isoformat()})"
            flag_modified(candidate_to_mark_failed, "notes")
            try:
                db.session.commit()
            except Exception as e_commit_fail_status:
                db.session.rollback()
                logger.error(
                    f"CRITICAL: Could not even commit ParsingFailed status for candidate {candidate_to_mark_failed.candidate_id} after previous error: {e_commit_fail_status}")
        else:
            logger.error(
                f"CRITICAL: Candidate for S3 key {s3_file_key} not found to mark as ParsingFailed after DB Update/Merge Error.")
        return f"Failed final update for CV {s3_file_key}."