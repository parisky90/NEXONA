# backend/app/tasks/communication.py
from app import celery, db, mail
from app.models import Interview, Candidate, User, Position, Company, InterviewSlot, InterviewStatus, CompanySettings
from flask_mail import Message
from flask import current_app, url_for, render_template
from zoneinfo import ZoneInfo
import logging
from datetime import datetime, timezone as dt_timezone, timedelta
from sqlalchemy.orm.attributes import flag_modified
from markupsafe import Markup
import uuid

logger = logging.getLogger(__name__)


# Helper function to render templates with fallback
def _render_email_template(template_base_name, **kwargs):
    try:
        # Ensure all necessary context variables for base templates are present
        kwargs.setdefault('app_name', current_app.config.get('APP_NAME', 'NEXONA'))
        kwargs.setdefault('app_home_url', current_app.config.get('FRONTEND_URL', '#'))
        kwargs.setdefault('now', datetime.now(dt_timezone.utc))

        html_body = render_template(f'email/{template_base_name}.html', **kwargs)
        text_body = render_template(f'email/{template_base_name}.txt', **kwargs)
        logger.info(f"Successfully rendered '{template_base_name}' email templates.")
        return html_body, text_body
    except Exception as e:
        logger.error(f"Email template rendering FAILED for '{template_base_name}': {e}", exc_info=True)
        fallback_subject = kwargs.get('subject', "Notification")
        fallback_greeting = f"Dear {kwargs.get('candidate_name', kwargs.get('user_name', kwargs.get('recruiter_name', 'User')))},"  # More robust greeting
        fallback_text_body = f"{fallback_greeting}\n\nPlease check the application for an update regarding: {fallback_subject}.\n\nThank you,\nThe Team"
        fallback_html_body = f"<p>{fallback_greeting}</p><p>Please check the application for an update regarding: {fallback_subject}.</p><p>Thank you,<br/>The Team</p>"
        return fallback_html_body, fallback_text_body


# --- TASKS ---

@celery.task(bind=True, max_retries=3, default_retry_delay=300)
def send_interview_proposal_email_task(self, interview_id_str):
    logger.info(f"--- [TASK START] send_interview_proposal_email_task for Interview ID: {interview_id_str} ---")
    try:
        interview = db.session.get(Interview, int(interview_id_str))
        if not interview or not interview.candidate or not interview.candidate.email or not interview.confirmation_token:
            missing = [item for item, val in
                       [("interview", interview), ("candidate", getattr(interview, 'candidate', None)),
                        ("candidate.email", getattr(getattr(interview, 'candidate', None), 'email', None)),
                        ("confirmation_token", getattr(interview, 'confirmation_token', None))] if not val]
            logger.error(
                f"[TASK_ERROR] Missing critical info for interview proposal {interview_id_str}: {', '.join(missing)}.")
            return f"Missing info for interview {interview_id_str}: {', '.join(missing)}"

        logger.debug(
            f"[TASK_DATA] Interview ID: {interview.id}, Candidate Email: {interview.candidate.email}, Token: {interview.confirmation_token}")
        company_name = interview.company.name if interview.company else current_app.config.get('APP_NAME',
                                                                                               "Our Company")
        processed_slots = []
        local_tz_str = current_app.config.get('LOCAL_TIMEZONE', 'UTC')
        try:
            local_tz = ZoneInfo(local_tz_str)
        except:
            local_tz = ZoneInfo("UTC"); logger.warning("Fallback to UTC for timezone.")

        for slot in interview.slots:
            confirm_url = url_for('api.confirm_interview_slot', token=interview.confirmation_token,
                                  slot_id_choice=slot.id, _external=True)
            start_display = slot.start_time.astimezone(local_tz).strftime(
                "%A, %d %B %Y at %H:%M (%Z)") if slot.start_time else "N/A"
            processed_slots.append({'id': slot.id, 'start_display': start_display, 'confirmation_url': confirm_url})

        reject_all_url = url_for('api.reject_interview_slots', token=interview.confirmation_token, _external=True)
        subject = f"Interview Proposal from {company_name}"
        email_context = {
            'subject': subject, 'candidate_name': interview.candidate.get_full_name(), 'company_name': company_name,
            'position_name_display': interview.position.position_name if interview.position else "the position",
            'recruiter_name': interview.recruiter.username if interview.recruiter else company_name,
            'notes_for_candidate': Markup(interview.notes_for_candidate) if interview.notes_for_candidate else None,
            'proposed_slots': processed_slots, 'reject_all_url': reject_all_url,
            'token_expiration_days': current_app.config.get('INTERVIEW_TOKEN_EXPIRATION_DAYS', 7)
            # 'local_timezone' and other base context vars are added by _render_email_template
        }
        logger.debug(f"[TASK_EMAIL_CTX] Proposal Context: {email_context}")
        html_body, text_body = _render_email_template('interview_proposal', **email_context)
        sender_email = current_app.config.get('MAIL_DEFAULT_SENDER')
        msg = Message(subject, sender=sender_email, recipients=[interview.candidate.email], body=text_body,
                      html=html_body)

        if current_app.config.get('MAIL_SUPPRESS_SEND'):
            logger.info(f"Mail suppressed for proposal to {interview.candidate.email}")
        else:
            mail.send(msg); logger.info(
                f"Proposal email sent to {interview.candidate.email} for interview {interview.id}.")
        return f"Proposal email processed for interview {interview.id}."
    except Exception as e:
        logger.error(f"[TASK_ERROR] Uncaught error in send_interview_proposal_email_task for {interview_id_str}: {e}",
                     exc_info=True)
        try:
            raise self.retry(exc=e)
        except self.MaxRetriesExceededError:
            return f"Failed proposal email (max retries) for {interview_id_str}."
        except Exception as retry_exc:
            return f"Failed proposal email (retry error) for {interview_id_str}: {retry_exc}"


@celery.task(bind=True, max_retries=3, default_retry_delay=180)
def send_interview_confirmation_to_candidate_task(self, interview_id_str, selected_slot_id_str):
    logger.info(
        f"--- [TASK START] send_interview_confirmation_to_candidate_task for Interview ID: {interview_id_str} ---")
    interview = db.session.get(Interview, int(interview_id_str))
    if not interview or not interview.candidate or not interview.candidate.email:
        logger.error(f"[TASK_ERROR] Missing data for candidate confirmation email, interview {interview_id_str}.")
        return "Missing data for candidate confirmation."
    selected_slot = db.session.get(InterviewSlot, int(selected_slot_id_str))
    if not selected_slot or selected_slot.interview_id != interview.id:
        logger.error(f"[TASK_ERROR] Invalid slot {selected_slot_id_str} for interview {interview_id_str}.")
        return "Invalid slot for confirmation."

    company_name = interview.company.name if interview.company else "Our Company"
    subject = f"Interview Confirmed with {company_name}"
    local_tz_str = current_app.config.get('LOCAL_TIMEZONE', 'UTC')
    try:
        local_tz = ZoneInfo(local_tz_str)
    except:
        local_tz = ZoneInfo("UTC"); logger.warning("Fallback to UTC for timezone.")
    confirmed_time_display = selected_slot.start_time.astimezone(local_tz).strftime("%A, %d %B %Y at %H:%M (%Z)")
    cancel_url = url_for('api.cancel_interview_by_candidate', cancel_token=interview.cancellation_token,
                         _external=True) if interview.cancellation_token else "#"

    email_context = {
        'subject': subject, 'candidate_name': interview.candidate.get_full_name(), 'company_name': company_name,
        'position_name_display': interview.position.position_name if interview.position else "the position",
        'confirmed_time_display': confirmed_time_display,
        'location': interview.location or "Details to be confirmed",
        'interview_type': interview.interview_type,
        'notes_for_candidate': Markup(interview.notes_for_candidate) if interview.notes_for_candidate else None,
        'cancel_url': cancel_url,
        'config': current_app.config
        # Pass entire config if template needs specific values like CANCELLATION_THRESHOLD_HOURS
    }
    html_body, text_body = _render_email_template('interview_confirmation_candidate', **email_context)
    sender_email = current_app.config.get('MAIL_DEFAULT_SENDER')
    msg = Message(subject, sender=sender_email, recipients=[interview.candidate.email], body=text_body, html=html_body)
    try:
        if current_app.config.get('MAIL_SUPPRESS_SEND'):
            logger.info(f"Mail suppressed for candidate confirmation {interview_id_str}")
        else:
            mail.send(msg); logger.info(f"Candidate confirmation email sent for interview {interview_id_str}")
        return f"Candidate confirmation email sent for {interview_id_str}"
    except Exception as e:
        logger.error(f"Failed to send candidate confirmation email {interview_id_str}: {e}",
                     exc_info=True); raise self.retry(exc=e)


@celery.task(bind=True, max_retries=3, default_retry_delay=180)
def send_interview_confirmation_to_recruiter_task(self, interview_id_str, selected_slot_id_str):
    logger.info(
        f"--- [TASK START] send_interview_confirmation_to_recruiter_task for Interview ID: {interview_id_str} ---")
    interview = db.session.get(Interview, int(interview_id_str))
    if not interview or not interview.recruiter or not interview.recruiter.email or not interview.candidate:
        logger.error(f"[TASK_ERROR] Missing data for recruiter confirmation email, interview {interview_id_str}.")
        return "Missing data for recruiter confirmation."
    selected_slot = db.session.get(InterviewSlot, int(selected_slot_id_str))
    if not selected_slot or selected_slot.interview_id != interview.id:
        logger.error(
            f"[TASK_ERROR] Invalid slot {selected_slot_id_str} for interview {interview_id_str} (recruiter mail).")
        return "Invalid slot for recruiter confirmation."

    candidate_name = interview.candidate.get_full_name()
    subject = f"Interview Scheduled: {candidate_name}"
    local_tz_str = current_app.config.get('LOCAL_TIMEZONE', 'UTC')
    try:
        local_tz = ZoneInfo(local_tz_str)
    except:
        local_tz = ZoneInfo("UTC"); logger.warning("Fallback to UTC for timezone.")
    confirmed_time_display = selected_slot.start_time.astimezone(local_tz).strftime("%A, %d %B %Y at %H:%M (%Z)")
    view_candidate_url = f"{current_app.config.get('FRONTEND_URL', '')}/candidate/{str(interview.candidate_id)}" if interview.candidate_id else "#"

    email_context = {
        'subject': subject, 'recruiter_name': interview.recruiter.username, 'candidate_name': candidate_name,
        'position_name_display': interview.position.position_name if interview.position else "the position",
        'confirmed_time_display': confirmed_time_display,
        'location': interview.location or "Details to be confirmed",
        'interview_type': interview.interview_type,
        'view_interview_url': view_candidate_url
        # Changed from view_candidate_url to view_interview_url for consistency with template
    }
    html_body, text_body = _render_email_template('interview_confirmation_recruiter', **email_context)
    sender_email = current_app.config.get('MAIL_DEFAULT_SENDER')
    msg = Message(subject, sender=sender_email, recipients=[interview.recruiter.email], body=text_body, html=html_body)
    try:
        if current_app.config.get('MAIL_SUPPRESS_SEND'):
            logger.info(f"Mail suppressed for recruiter confirmation {interview_id_str}")
        else:
            mail.send(msg); logger.info(f"Recruiter confirmation email sent for interview {interview_id_str}")
        return f"Recruiter confirmation email sent for {interview_id_str}"
    except Exception as e:
        logger.error(f"Failed to send recruiter confirmation email {interview_id_str}: {e}",
                     exc_info=True); raise self.retry(exc=e)


@celery.task(bind=True, max_retries=3, default_retry_delay=180)
def send_interview_rejection_to_recruiter_task(self, interview_id_str):
    logger.info(f"--- [TASK START] send_interview_rejection_to_recruiter_task for Interview ID: {interview_id_str} ---")
    interview = db.session.get(Interview, int(interview_id_str))
    if not interview or not interview.recruiter or not interview.recruiter.email or not interview.candidate:
        logger.error(f"[TASK_ERROR] Missing data for slot rejection notification, interview {interview_id_str}.")
        return "Missing data for slot rejection notification."

    candidate_name = interview.candidate.get_full_name()
    subject = f"Interview Slots Rejected by {candidate_name}"
    view_candidate_url = f"{current_app.config.get('FRONTEND_URL', '')}/candidate/{str(interview.candidate_id)}" if interview.candidate_id else "#"
    email_context = {
        'subject': subject, 'recruiter_name': interview.recruiter.username, 'candidate_name': candidate_name,
        'position_name_display': interview.position.position_name if interview.position else "the position",
        'interview_id': interview.id, 'view_candidate_url': view_candidate_url
    }
    html_body, text_body = _render_email_template('interview_slots_rejected_recruiter', **email_context)
    sender_email = current_app.config.get('MAIL_DEFAULT_SENDER')
    msg = Message(subject, sender=sender_email, recipients=[interview.recruiter.email], body=text_body, html=html_body)
    try:
        if current_app.config.get('MAIL_SUPPRESS_SEND'):
            logger.info(f"Mail suppressed for slot rejection notification {interview_id_str}")
        else:
            mail.send(msg); logger.info(f"Slot rejection notification sent for interview {interview_id_str}")
        return f"Slot rejection notification sent for {interview_id_str}"
    except Exception as e:
        logger.error(f"Failed to send slot rejection notification {interview_id_str}: {e}",
                     exc_info=True); raise self.retry(exc=e)


@celery.task(bind=True, max_retries=3, default_retry_delay=180)
def send_interview_cancellation_to_recruiter_task(self, interview_id_str, reason=None, reschedule_preference=None):
    logger.info(
        f"--- [TASK START] send_interview_cancellation_to_recruiter_task (by candidate) for Interview ID: {interview_id_str} ---")
    interview = db.session.get(Interview, int(interview_id_str))
    if not interview or not interview.recruiter or not interview.recruiter.email or not interview.candidate:
        logger.error(
            f"[TASK_ERROR] Missing data for candidate cancellation notification, interview {interview_id_str}.")
        return "Missing data for cancellation (recruiter) notification."

    candidate_name = interview.candidate.get_full_name()
    subject = f"Interview Cancelled by Candidate: {candidate_name}"
    view_candidate_url = f"{current_app.config.get('FRONTEND_URL', '')}/candidate/{str(interview.candidate_id)}" if interview.candidate_id else "#"

    reschedule_message = "Not specified"
    if reschedule_preference == 'request_reschedule':
        reschedule_message = "Yes, requested reschedule."
    elif reschedule_preference == 'no_reschedule':
        reschedule_message = "No, does not wish to reschedule."

    email_context = {
        'subject': subject, 'recruiter_name': interview.recruiter.username, 'candidate_name': candidate_name,
        'position_name_display': interview.position.position_name if interview.position else "the position",
        'interview_id': interview.id, 'cancellation_reason': reason or "No reason provided.",
        'reschedule_message': reschedule_message, 'view_candidate_url': view_candidate_url
    }
    html_body, text_body = _render_email_template('interview_cancelled_by_candidate_recruiter', **email_context)
    sender_email = current_app.config.get('MAIL_DEFAULT_SENDER')
    msg = Message(subject, sender=sender_email, recipients=[interview.recruiter.email], body=text_body, html=html_body)
    try:
        if current_app.config.get('MAIL_SUPPRESS_SEND'):
            logger.info(f"Mail suppressed for candidate cancellation notification {interview_id_str}")
        else:
            mail.send(msg); logger.info(f"Candidate cancellation notification sent for interview {interview_id_str}")
        return f"Candidate cancellation notification sent for {interview_id_str}"
    except Exception as e:
        logger.error(f"Failed to send candidate cancellation notification {interview_id_str}: {e}",
                     exc_info=True); raise self.retry(exc=e)


@celery.task(bind=True, max_retries=3, default_retry_delay=180)
def send_interview_cancellation_to_candidate_task(self, interview_id_str, reason=None):
    logger.info(
        f"--- [TASK START] send_interview_cancellation_to_candidate_task (by recruiter) for Interview ID: {interview_id_str} ---")
    interview = db.session.get(Interview, int(interview_id_str))
    if not interview or not interview.candidate or not interview.candidate.email:
        logger.error(
            f"[TASK_ERROR] Missing data for recruiter cancellation notification, interview {interview_id_str}.")
        return "Missing data for cancellation (candidate) notification."

    company_name = interview.company.name if interview.company else "Our Company"
    subject = f"Interview Cancellation by {company_name}"
    # Προσπάθησε να πάρεις την αρχική ώρα αν είναι διαθέσιμη (π.χ. από το scheduled_start_time πριν την ακύρωση)
    # Αυτό το πεδίο δεν υπάρχει στο model του Interview, οπότε πρέπει να το πάρεις από κάπου αλλού ή να το παραλείψεις.
    # Για την ώρα, θα το αφήσω ως έχει και θα πρέπει να το προσθέσεις στο context αν το έχεις.
    originally_scheduled_time_display = "previously scheduled time"  # Placeholder
    if interview.scheduled_start_time:  # Αν η συνέντευξη *ήταν* προγραμματισμένη
        try:
            local_tz = ZoneInfo(current_app.config.get('LOCAL_TIMEZONE', 'UTC'))
            originally_scheduled_time_display = interview.scheduled_start_time.astimezone(local_tz).strftime(
                "%A, %d %B %Y at %H:%M (%Z)")
        except:
            originally_scheduled_time_display = interview.scheduled_start_time.strftime("%Y-%m-%d %H:%M UTC")

    email_context = {
        'subject': subject, 'candidate_name': interview.candidate.get_full_name(), 'company_name': company_name,
        'position_name_display': interview.position.position_name if interview.position else "your interview",
        'interview_id': interview.id,
        'cancellation_reason_by_recruiter': reason or "The company has cancelled this interview.",
        # Άλλαξα το όνομα της μεταβλητής για συνέπεια με το template
        'originally_scheduled_time': originally_scheduled_time_display
    }
    html_body, text_body = _render_email_template('interview_cancelled_by_recruiter_candidate', **email_context)
    sender_email = current_app.config.get('MAIL_DEFAULT_SENDER')
    msg = Message(subject, sender=sender_email, recipients=[interview.candidate.email], body=text_body, html=html_body)
    try:
        if current_app.config.get('MAIL_SUPPRESS_SEND'):
            logger.info(f"Mail suppressed for recruiter cancellation notification {interview_id_str}")
        else:
            mail.send(msg); logger.info(f"Recruiter cancellation notification sent for interview {interview_id_str}")
        return f"Recruiter cancellation notification sent for {interview_id_str}"
    except Exception as e:
        logger.error(f"Failed to send recruiter cancellation notification {interview_id_str}: {e}",
                     exc_info=True); raise self.retry(exc=e)


# --- OFFER/HIRED/DECLINED TASKS ---
@celery.task(bind=True, max_retries=3, default_retry_delay=300)
def send_offer_made_email_to_candidate_task(self, candidate_id_str, offer_details_dict=None):
    logger.info(f"--- [TASK START] send_offer_made_email_to_candidate_task for Candidate ID: {candidate_id_str} ---")
    if offer_details_dict is None: offer_details_dict = {}
    try:
        candidate_id_obj = uuid.UUID(candidate_id_str)
    except ValueError:
        logger.error(
            f"[TASK_ERROR] Invalid candidate_id format: {candidate_id_str}"); return f"Error: Invalid candidate_id format {candidate_id_str}"
    candidate = db.session.get(Candidate, candidate_id_obj)
    if not candidate: logger.error(
        f"[TASK_ERROR] Candidate ID {candidate_id_str} not found."); return f"Error: Candidate ID {candidate_id_str} not found."
    if not candidate.email: logger.error(
        f"[TASK_ERROR] Candidate email missing for ID {candidate_id_str}."); return f"Error: Candidate email missing for ID {candidate_id_str}."
    if not candidate.offer_acceptance_token: logger.error(
        f"[TASK_ERROR] Offer acceptance token missing for candidate {candidate_id_str}."); return f"Error: Offer token missing for {candidate_id_str}."

    company_name = candidate.company.name if candidate.company else current_app.config.get('APP_NAME', "Our Company")
    accept_url = url_for('api.accept_offer', token=candidate.offer_acceptance_token, _external=True)
    reject_url = url_for('api.reject_offer', token=candidate.offer_acceptance_token, _external=True)
    subject = f"Job Offer from {company_name}"
    email_context = {
        'subject': subject, 'candidate_name': candidate.get_full_name(), 'company_name': company_name,
        'offer_amount': offer_details_dict.get('offer_amount'),
        'offer_notes': Markup(offer_details_dict.get('offer_notes')) if offer_details_dict.get('offer_notes') else None,
        'offer_date': offer_details_dict.get('offer_date'), 'accept_url': accept_url, 'reject_url': reject_url,
    }
    html_body, text_body = _render_email_template('offer_made_candidate', **email_context)
    sender_email = current_app.config.get('MAIL_DEFAULT_SENDER')
    msg = Message(subject, sender=sender_email, recipients=[candidate.email], body=text_body, html=html_body)
    try:
        if current_app.config.get('MAIL_SUPPRESS_SEND'):
            logger.info(f"Mail suppressed for offer email to {candidate.email}")
        else:
            mail.send(msg); logger.info(f"Offer email sent to {candidate.email}.")
        return f"Offer email processed for candidate {candidate_id_str}."
    except Exception as e_mail:
        logger.error(f"Failed to send offer email for {candidate_id_str}: {e_mail}", exc_info=True); raise self.retry(
            exc=e_mail)


@celery.task(bind=True, max_retries=3, default_retry_delay=180)
def send_hired_confirmation_email_to_candidate_task(self, candidate_id_str):
    logger.info(
        f"--- [TASK START] send_hired_confirmation_email_to_candidate_task for Candidate ID: {candidate_id_str} ---")
    try:
        candidate_id_obj = uuid.UUID(candidate_id_str)
    except ValueError:
        logger.error(
            f"[TASK_ERROR] Invalid candidate_id format for hired email: {candidate_id_str}"); return "Error: Invalid ID format."
    candidate = db.session.get(Candidate, candidate_id_obj)
    if not candidate or not candidate.email: logger.error(
        f"[TASK_ERROR] Hired email: Candidate or email missing for ID {candidate_id_str}."); return f"Error: Candidate or email missing for ID {candidate_id_str}."

    company_name = candidate.company.name if candidate.company else current_app.config.get('APP_NAME', "Our Company")
    welcome_message_body = f"We are thrilled to welcome you to the team at {company_name}! We will be in touch shortly with details about your onboarding process."  # This could come from CompanySettings
    subject = f"Welcome to {company_name}!"
    email_context = {
        'subject': subject, 'candidate_name': candidate.get_full_name(), 'company_name': company_name,
        'welcome_message_body': Markup(welcome_message_body)
    }
    html_body, text_body = _render_email_template('hired_confirmation_candidate', **email_context)
    sender_email = current_app.config.get('MAIL_DEFAULT_SENDER')
    msg = Message(subject, sender=sender_email, recipients=[candidate.email], body=text_body, html=html_body)
    try:
        if current_app.config.get('MAIL_SUPPRESS_SEND'):
            logger.info(f"Mail suppressed for hired email to {candidate.email}")
        else:
            mail.send(msg); logger.info(f"Hired email sent to {candidate.email}.")
        return f"Hired email processed for candidate {candidate_id_str}."
    except Exception as e_mail:
        logger.error(f"Failed to send hired email for {candidate_id_str}: {e_mail}", exc_info=True); raise self.retry(
            exc=e_mail)


@celery.task(bind=True, max_retries=3, default_retry_delay=180)
def send_offer_declined_notification_to_recruiter_task(self, candidate_id_str):
    logger.info(
        f"--- [TASK START] send_offer_declined_notification_to_recruiter_task for Candidate ID: {candidate_id_str} ---")
    try:
        candidate_id_obj = uuid.UUID(candidate_id_str)
    except ValueError:
        logger.error(
            f"[TASK_ERROR] Invalid candidate_id format for offer declined: {candidate_id_str}"); return "Error: Invalid ID format."
    candidate = db.session.get(Candidate, candidate_id_obj)
    if not candidate: logger.error(
        f"[TASK_ERROR] Offer declined: Candidate {candidate_id_str} not found."); return f"Error: Candidate {candidate_id_str} not found."

    recruiter_to_notify = None;
    company = candidate.company
    if company:
        if company.owner and company.owner.is_active and company.owner.email:
            recruiter_to_notify = company.owner
        else:
            active_admins_or_recruiters = User.query.filter(User.company_id == company.id, User.is_active == True,
                                                            User.email != None,
                                                            User.role.in_(['company_admin', 'recruiter'])).all()
            if active_admins_or_recruiters:
                recruiter_to_notify = active_admins_or_recruiters[0]  # Notify the first one found
            elif company.users.filter(User.is_active == True, User.email != None).first():
                recruiter_to_notify = company.users.filter(User.is_active == True, User.email != None).first()

    if not recruiter_to_notify or not recruiter_to_notify.email:
        logger.warning(
            f"[TASK_WARN] Offer declined: No active recruiter/admin with email found for company of candidate {candidate_id_str}.");
        return f"Warning: No recruiter to notify for {candidate_id_str}."

    company_name = company.name if company else current_app.config.get('APP_NAME', "The Company")
    candidate_name = candidate.get_full_name()
    view_candidate_url = f"{current_app.config.get('FRONTEND_URL', '')}/candidate/{str(candidate.candidate_id)}" if candidate.candidate_id else "#"
    subject = f"Offer Declined by Candidate: {candidate_name}"
    email_context = {
        'subject': subject, 'recruiter_name': recruiter_to_notify.username, 'candidate_name': candidate_name,
        'company_name': company_name, 'view_candidate_url': view_candidate_url
    }
    html_body, text_body = _render_email_template('offer_declined_recruiter', **email_context)
    sender_email = current_app.config.get('MAIL_DEFAULT_SENDER')
    msg = Message(subject, sender=sender_email, recipients=[recruiter_to_notify.email], body=text_body, html=html_body)
    try:
        if current_app.config.get('MAIL_SUPPRESS_SEND'):
            logger.info(f"Mail suppressed for offer declined notification to {recruiter_to_notify.email}")
        else:
            mail.send(msg); logger.info(f"Offer declined notification sent to {recruiter_to_notify.email}.")
        return f"Offer declined notification processed for candidate {candidate_id_str}."
    except Exception as e_mail:
        logger.error(f"Failed to send offer declined notification for {candidate_id_str}: {e_mail}",
                     exc_info=True); raise self.retry(exc=e_mail)


@celery.task(bind=True, max_retries=3, default_retry_delay=60)
def send_interview_reminder_email_task(self, user_email, user_name, candidate_name, interview_datetime_iso,
                                       interview_location, position_name, lead_time_minutes, interview_id_str):
    logger.info(
        f"--- [TASK START] send_interview_reminder_email_task to {user_email}, Interview: {interview_id_str} ---")
    try:
        interview_datetime_utc = datetime.fromisoformat(interview_datetime_iso)
        if interview_datetime_utc.tzinfo is None: interview_datetime_utc = interview_datetime_utc.replace(
            tzinfo=dt_timezone.utc)
    except ValueError:
        logger.error(
            f"[TASK_ERROR] Invalid datetime format for reminder: {interview_datetime_iso}"); return "Error: Invalid datetime format."

    local_tz_str = current_app.config.get('LOCAL_TIMEZONE', 'UTC')
    try:
        local_tz = ZoneInfo(local_tz_str)
    except Exception as tz_err:
        logger.error(f"[TASK_ERROR] Timezone error in reminder: {tz_err}"); local_tz = ZoneInfo("UTC")
    interview_display_time_local = interview_datetime_utc.astimezone(local_tz).strftime("%A, %d %B %Y at %H:%M (%Z)")

    candidate_uuid_for_url = None
    try:
        interview_obj = db.session.get(Interview, int(interview_id_str))
        if interview_obj and interview_obj.candidate_id: candidate_uuid_for_url = str(interview_obj.candidate_id)
    except Exception:
        logger.warning(f"Could not get candidate_id for interview {interview_id_str} for reminder URL.")

    view_interview_url = f"{current_app.config.get('FRONTEND_URL', '')}/candidate/{candidate_uuid_for_url}?tab=interviews" if candidate_uuid_for_url else current_app.config.get(
        'FRONTEND_URL', '#')  # Fallback to frontend URL
    subject = f"Reminder: Upcoming Interview with {candidate_name}"
    email_context = {
        'subject': subject, 'user_name': user_name, 'candidate_name': candidate_name,
        'interview_time_display': interview_display_time_local, 'location': interview_location or "Not specified",
        'position_name': position_name or "the position", 'lead_time_minutes': lead_time_minutes,
        'view_interview_url': view_interview_url
    }
    html_body, text_body = _render_email_template('interview_reminder_recruiter',
                                                  **email_context)  # Assuming reminder is for recruiter
    sender_email = current_app.config.get('MAIL_DEFAULT_SENDER')
    msg = Message(subject, sender=sender_email, recipients=[user_email], body=text_body, html=html_body)
    try:
        if current_app.config.get('MAIL_SUPPRESS_SEND'):
            logger.info(f"Mail suppressed for reminder email to {user_email}")
        else:
            mail.send(msg); logger.info(f"Reminder email sent to {user_email} for interview {interview_id_str}.")
        return f"Reminder email processed for {interview_id_str}."
    except Exception as e:
        logger.error(f"Failed to send reminder email {interview_id_str}: {e}", exc_info=True); raise self.retry(exc=e)