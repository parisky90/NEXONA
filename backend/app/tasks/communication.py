# backend/app/tasks/communication.py
from app import celery, db, mail
from app.models import Interview, Candidate, User, Position, Company, InterviewSlot  # Προσθήκη InterviewSlot
from flask_mail import Message
from flask import current_app, url_for, render_template
from zoneinfo import ZoneInfo
import logging
from datetime import datetime
from sqlalchemy.orm.attributes import flag_modified
from markupsafe import Markup

logger = logging.getLogger(__name__)


@celery.task(bind=True, max_retries=3, default_retry_delay=300)
def send_interview_proposal_email_task(self, interview_id_str):
    """
    Sends an interview proposal email to the candidate.
    """
    logger.info(f"Executing send_interview_proposal_email_task for interview ID: {interview_id_str}")
    try:
        interview_id = int(interview_id_str)
    except ValueError:
        logger.error(f"Invalid interview_id format: {interview_id_str}")
        return f"Error: Invalid interview_id format {interview_id_str}"

    interview = db.session.get(Interview, interview_id)
    if not interview:
        logger.error(f"send_interview_proposal_email_task: Interview with ID {interview_id} not found.")
        return f"Error: Interview ID {interview_id} not found."

    candidate = interview.candidate
    recruiter = interview.recruiter
    position = interview.position

    if not candidate or not candidate.email:
        logger.error(
            f"send_interview_proposal_email_task: Candidate or candidate email missing for interview ID {interview_id}.")
        return f"Error: Candidate or email missing for interview ID {interview_id}."

    company_name_for_email = current_app.config.get('APP_NAME', "Our Company")
    if interview.company:
        company_name_for_email = interview.company.name
    elif candidate.company:
        company_name_for_email = candidate.company.name
    elif recruiter and recruiter.company:
        company_name_for_email = recruiter.company.name

    recruiter_name_for_email = "Recruitment Team"
    if recruiter:
        recruiter_name_for_email = recruiter.username

    try:
        local_tz_str = current_app.config.get('LOCAL_TIMEZONE', 'UTC')
        local_tz = ZoneInfo(local_tz_str)
    except Exception as tz_err:
        logger.error(f"Could not load {local_tz_str} timezone in Celery task: {tz_err}", exc_info=True)
        local_tz = ZoneInfo("UTC")
        logger.warning(f"Falling back to UTC for email display times for interview {interview_id}.")

    proposed_slots_for_email = []
    logger.info(f"--- URLs for Interview ID: {interview_id} (Token: {interview.confirmation_token}) ---")
    if interview.slots:
        for slot_obj in interview.slots.all():
            if slot_obj.start_time and slot_obj.end_time:
                start_local = slot_obj.start_time.astimezone(local_tz)
                confirmation_url = url_for('api.confirm_interview_slot',
                                           token=interview.confirmation_token,
                                           slot_id_choice=slot_obj.id,
                                           _external=True)
                logger.info(f"  Slot ID {slot_obj.id} Confirmation URL: {confirmation_url}")
                proposed_slots_for_email.append({
                    "id": slot_obj.id,
                    "start_display": start_local.strftime("%A, %d %B %Y at %H:%M (%Z)"),
                    "confirmation_url": confirmation_url
                })

    reject_all_url = url_for('api.reject_interview_slots', token=interview.confirmation_token, _external=True)
    logger.info(f"  Reject All Slots URL: {reject_all_url}")
    logger.info(f"--- End of URLs for Interview ID: {interview_id} ---")

    if not proposed_slots_for_email:
        logger.warning(
            f"send_interview_proposal_email_task: No valid proposed slots found for interview ID {interview_id}. Email will indicate this.")

    subject = f"Interview Invitation"
    if position:
        subject += f" for {position.position_name}"
    subject += f" at {company_name_for_email}"

    processed_notes_for_candidate = ""
    if interview.notes_for_candidate:
        processed_notes_for_candidate = Markup.escape(interview.notes_for_candidate).replace('\n', Markup('<br>'))

    email_context = {
        'candidate_name': candidate.get_full_name(),
        'position_name_display': f"for the position «{position.position_name}»" if position else "for a collaboration opportunity",
        'company_name': company_name_for_email,
        'proposed_slots': proposed_slots_for_email,
        'interview_type': interview.interview_type or "Not specified",
        'location': interview.location or "To be confirmed",
        'notes_for_candidate': processed_notes_for_candidate,
        'reject_all_url': reject_all_url,
        'recruiter_name': recruiter_name_for_email,
        'now': datetime.utcnow(),
        'app_home_url': current_app.config.get('FRONTEND_URL', 'http://localhost:5173')
    }

    html_body = ""
    text_body = ""
    try:
        html_body = render_template('email/interview_proposal.html', **email_context)
        text_body = render_template('email/interview_proposal.txt', **email_context)
        logger.info(f"Successfully rendered email templates for interview ID {interview_id}.")
    except Exception as template_e:
        logger.error(
            f"Email template rendering FAILED for interview_proposal (Interview ID: {interview_id}): {template_e}. Falling back to basic f-string email.",
            exc_info=True)
        html_body = f"""<p>Dear {email_context['candidate_name']},</p><p>We would like to invite you for an interview {email_context['position_name_display']} at {email_context['company_name']}.</p><p>Please visit the link below to select a time or indicate if no times are suitable.</p><p>Available slots:</p>"""
        if email_context['proposed_slots']:
            for slot in email_context['proposed_slots']:
                html_body += f"<p>- {slot['start_display']}: <a href='{slot['confirmation_url']}'>Confirm</a></p>"
        else:
            html_body += "<p>No specific slots proposed at this time. We will contact you.</p>"
        html_body += f"<p>If no slots work: <a href='{email_context['reject_all_url']}'>Reject all slots</a></p><p>Thank you,<br>The {email_context['company_name']} Team</p>"
        text_body = f"""Dear {email_context['candidate_name']},\n\nWe would like to invite you for an interview {email_context['position_name_display']} at {email_context['company_name']}.\nPlease visit the link below to select a time or indicate if no times are suitable.\n\nAvailable slots:\n"""
        if email_context['proposed_slots']:
            for slot in email_context['proposed_slots']:
                text_body += f"- {slot['start_display']}: Confirm at {slot['confirmation_url']}\n"
        else:
            text_body += "No specific slots proposed at this time. We will contact you.\n"
        text_body += f"If no slots work, please visit: {email_context['reject_all_url']}\n\nThank you,\nThe {email_context['company_name']} Team"

    sender_email = current_app.config.get('MAIL_DEFAULT_SENDER')
    msg = Message(subject, sender=sender_email, recipients=[candidate.email])
    msg.body = text_body
    msg.html = html_body

    try:
        if current_app.config.get('MAIL_SUPPRESS_SEND', False):
            logger.info(
                f"MAIL_SUPPRESS_SEND is True. Email to {candidate.email} for interview {interview_id} NOT sent but task executed.")
        else:
            mail.send(msg)
            logger.info(f"Interview proposal email sent to {candidate.email} for interview ID {interview_id}.")
        return f"Email processed for interview ID {interview_id}."
    except Exception as e_mail:
        logger.error(f"Failed to send interview proposal email for interview ID {interview_id}: {e_mail}",
                     exc_info=True)
        try:
            raise self.retry(exc=e_mail, countdown=int(self.default_retry_delay * (2 ** self.request.retries)))
        except self.MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for sending email for interview ID {interview_id}.")
            if interview:
                interview.internal_notes = (interview.internal_notes or "") + \
                                           f"\n[Email Send Failed] Max retries for proposal email to candidate. Error: {str(e_mail)[:100]}"
                flag_modified(interview, "internal_notes")
                try:
                    db.session.commit()
                except Exception as db_exc:
                    logger.error(
                        f"Failed to commit internal_notes update after email send failure for interview {interview_id}: {db_exc}",
                        exc_info=True)
                    db.session.rollback()
            return f"Failed to send email for interview ID {interview_id} after max retries."
        except Exception as retry_exc:
            logger.error(f"Error during retry mechanism for interview ID {interview_id}: {retry_exc}", exc_info=True)
            return f"Failed to send email for interview ID {interview_id}, retry mechanism failed."


@celery.task(bind=True, max_retries=3, default_retry_delay=180)
def send_interview_confirmation_to_candidate_task(self, interview_id_str, selected_slot_id_str):
    logger.info(
        f"Executing send_interview_confirmation_to_candidate_task for interview ID: {interview_id_str}, slot ID: {selected_slot_id_str}")
    try:
        interview_id = int(interview_id_str)
        selected_slot_id = int(selected_slot_id_str)
    except ValueError:
        logger.error(
            f"Invalid ID format for interview or slot: interview_id='{interview_id_str}', slot_id='{selected_slot_id_str}'")
        return "Error: Invalid ID format."

    interview = db.session.get(Interview, interview_id)
    if not interview:
        logger.error(f"send_interview_confirmation_to_candidate_task: Interview {interview_id} not found.")
        return f"Error: Interview {interview_id} not found."

    selected_slot = db.session.get(InterviewSlot, selected_slot_id)
    if not selected_slot or selected_slot.interview_id != interview_id:
        logger.error(
            f"send_interview_confirmation_to_candidate_task: Slot {selected_slot_id} not found or doesn't belong to interview {interview_id}.")
        return f"Error: Slot {selected_slot_id} invalid for interview {interview_id}."

    candidate = interview.candidate
    if not candidate or not candidate.email:
        logger.error(
            f"send_interview_confirmation_to_candidate_task: Candidate or email missing for interview {interview_id}.")
        return f"Error: Candidate or email missing for interview {interview_id}."

    company_name_for_email = interview.company.name if interview.company else current_app.config.get('APP_NAME',
                                                                                                     "Our Company")
    position_name_display = f"for the position «{interview.position.position_name}»" if interview.position else "regarding your application"

    try:
        local_tz_str = current_app.config.get('LOCAL_TIMEZONE', 'UTC')
        local_tz = ZoneInfo(local_tz_str)
    except Exception as tz_err:
        logger.error(f"Could not load {local_tz_str} timezone in Celery task: {tz_err}", exc_info=True)
        local_tz = ZoneInfo("UTC")
        logger.warning(f"Falling back to UTC for email display times for interview {interview_id}.")

    confirmed_time_display = selected_slot.start_time.astimezone(local_tz).strftime("%A, %d %B %Y at %H:%M (%Z)")
    cancel_url = None
    if interview.cancellation_token:
        cancel_url = url_for('api.cancel_interview_by_candidate', cancel_token=interview.cancellation_token,
                             _external=True)

    logger.info(f"--- Candidate Confirmation Email URLs for Interview ID: {interview_id} ---")
    logger.info(f"  Cancel URL: {cancel_url}")
    logger.info(f"--- End of Candidate Confirmation Email URLs ---")

    processed_notes_for_candidate_confirmation = ""
    if interview.notes_for_candidate:
        processed_notes_for_candidate_confirmation = Markup.escape(interview.notes_for_candidate).replace('\n', Markup(
            '<br>'))

    subject = f"Interview Confirmed {position_name_display} at {company_name_for_email}"
    email_context = {
        'candidate_name': candidate.get_full_name(),
        'company_name': company_name_for_email,
        'position_name_display': position_name_display,
        'confirmed_time_display': confirmed_time_display,
        'location': interview.location or "To be confirmed",
        'interview_type': interview.interview_type or "Not specified",
        'notes_for_candidate': processed_notes_for_candidate_confirmation,
        'cancel_url': cancel_url,
        'now': datetime.utcnow(),
        'app_home_url': current_app.config.get('FRONTEND_URL')
    }

    html_body = ""
    text_body = ""
    try:
        # ΝΕΑ ΟΝΟΜΑΤΑ TEMPLATES (πρέπει να δημιουργηθούν):
        html_body = render_template('email/interview_confirmation_candidate.html', **email_context)
        text_body = render_template('email/interview_confirmation_candidate.txt', **email_context)
        logger.info(f"Successfully rendered candidate confirmation email templates for interview {interview_id}.")
    except Exception as template_e:
        logger.error(
            f"Candidate confirmation email template rendering FAILED for interview {interview_id}: {template_e}",
            exc_info=True)
        html_body = f"<p>Dear {email_context['candidate_name']},</p><p>Your interview {email_context['position_name_display']} with {email_context['company_name']} is confirmed for <strong>{email_context['confirmed_time_display']}</strong>.</p>"
        if email_context['location'] != "To be confirmed": html_body += f"<p>Location: {email_context['location']}</p>"
        if email_context[
            'cancel_url']: html_body += f"<p>If you need to cancel or reschedule, please use this link: <a href='{email_context['cancel_url']}'>Manage Interview</a></p>"
        html_body += f"<p>Thank you.</p>"
        text_body = f"Dear {email_context['candidate_name']},\n\nYour interview {email_context['position_name_display']} with {email_context['company_name']} is confirmed for {email_context['confirmed_time_display']}.\n"
        if email_context['location'] != "To be confirmed": text_body += f"Location: {email_context['location']}\n"
        if email_context[
            'cancel_url']: text_body += f"If you need to cancel or reschedule, please use this link: {email_context['cancel_url']}\n"
        text_body += f"\nThank you."

    sender_email = current_app.config.get('MAIL_DEFAULT_SENDER')
    msg = Message(subject, sender=sender_email, recipients=[candidate.email])
    msg.body = text_body
    msg.html = html_body

    try:
        if current_app.config.get('MAIL_SUPPRESS_SEND', False):
            logger.info(
                f"MAIL_SUPPRESS_SEND is True. Candidate confirmation email to {candidate.email} for interview {interview_id} NOT sent.")
        else:
            mail.send(msg)
            logger.info(f"Candidate confirmation email sent to {candidate.email} for interview {interview_id}.")
        return f"Candidate confirmation email processed for interview {interview_id}."
    except Exception as e_mail:
        logger.error(f"Failed to send candidate confirmation email for interview {interview_id}: {e_mail}",
                     exc_info=True)
        try:
            raise self.retry(exc=e_mail, countdown=int(self.default_retry_delay * (2 ** self.request.retries)))
        except self.MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for candidate confirmation email, interview {interview_id}.")
            return f"Failed candidate confirmation email (max retries) for interview {interview_id}."
        except Exception as retry_exc:
            logger.error(
                f"Retry mechanism failed for candidate confirmation email, interview {interview_id}: {retry_exc}",
                exc_info=True)
            return f"Failed candidate confirmation email (retry mechanism error) for interview {interview_id}."


@celery.task(bind=True, max_retries=3, default_retry_delay=180)
def send_interview_confirmation_to_recruiter_task(self, interview_id_str, selected_slot_id_str):
    logger.info(
        f"Executing send_interview_confirmation_to_recruiter_task for interview ID: {interview_id_str}, slot ID: {selected_slot_id_str}")
    try:
        interview_id = int(interview_id_str)
        selected_slot_id = int(selected_slot_id_str)
    except ValueError:
        logger.error(
            f"Invalid ID format for recruiter confirmation: interview_id='{interview_id_str}', slot_id='{selected_slot_id_str}'")
        return "Error: Invalid ID format."

    interview = db.session.get(Interview, interview_id)
    if not interview:
        logger.error(f"Recruiter confirmation: Interview {interview_id} not found.")
        return f"Error: Interview {interview_id} not found."

    selected_slot = db.session.get(InterviewSlot, selected_slot_id)
    if not selected_slot or selected_slot.interview_id != interview_id:
        logger.error(f"Recruiter confirmation: Slot {selected_slot_id} invalid for interview {interview_id}.")
        return f"Error: Slot {selected_slot_id} invalid for interview {interview_id}."

    recruiter = interview.recruiter
    if not recruiter or not recruiter.email:
        logger.warning(
            f"Recruiter confirmation: Recruiter or email missing for interview {interview_id}. Cannot send email.")
        return f"Warning: Recruiter or email missing for interview {interview_id}."

    candidate = interview.candidate
    candidate_name = candidate.get_full_name() if candidate else "N/A"
    company_name_for_email = recruiter.company.name if recruiter.company else current_app.config.get('APP_NAME',
                                                                                                     "The Company")
    position_name_display = f"for position «{interview.position.position_name}»" if interview.position else "for an interview"

    try:
        local_tz_str = current_app.config.get('LOCAL_TIMEZONE', 'UTC')
        local_tz = ZoneInfo(local_tz_str)
    except Exception as tz_err:
        logger.error(f"Could not load {local_tz_str} timezone in Celery task: {tz_err}", exc_info=True)
        local_tz = ZoneInfo("UTC")
        logger.warning(f"Falling back to UTC for email display times for interview {interview_id}.")

    confirmed_time_display = selected_slot.start_time.astimezone(local_tz).strftime("%A, %d %B %Y at %H:%M (%Z)")

    view_interview_url = "#"
    if interview.candidate_id:
        view_interview_url = f"{current_app.config.get('FRONTEND_URL', '')}/candidate/{str(interview.candidate_id)}?tab=interviews"

    subject = f"Interview Scheduled: {candidate_name} {position_name_display}"
    email_context = {
        'recruiter_name': recruiter.username,
        'candidate_name': candidate_name,
        'company_name': company_name_for_email,
        'position_name_display': position_name_display,
        'confirmed_time_display': confirmed_time_display,
        'location': interview.location or "To be confirmed",
        'interview_type': interview.interview_type or "Not specified",
        'view_interview_url': view_interview_url,
        'now': datetime.utcnow(),
        'app_home_url': current_app.config.get('FRONTEND_URL')
    }

    html_body = ""
    text_body = ""
    try:
        # ΝΕΑ ΟΝΟΜΑΤΑ TEMPLATES (πρέπει να δημιουργηθούν):
        html_body = render_template('email/interview_confirmation_recruiter.html', **email_context)
        text_body = render_template('email/interview_confirmation_recruiter.txt', **email_context)
        logger.info(f"Successfully rendered recruiter confirmation email templates for interview {interview_id}.")
    except Exception as template_e:
        logger.error(
            f"Recruiter confirmation email template rendering FAILED for interview {interview_id}: {template_e}",
            exc_info=True)
        html_body = f"<p>Hello {email_context['recruiter_name']},</p><p>The interview with {email_context['candidate_name']} {email_context['position_name_display']} has been scheduled for <strong>{email_context['confirmed_time_display']}</strong>.</p>"
        if email_context['location'] != "To be confirmed": html_body += f"<p>Location: {email_context['location']}</p>"
        if email_context[
            'view_interview_url'] != "#": html_body += f"<p>You can view the details here: <a href='{email_context['view_interview_url']}'>Interview Details</a></p>"
        text_body = f"Hello {email_context['recruiter_name']},\n\nThe interview with {email_context['candidate_name']} {email_context['position_name_display']} has been scheduled for {email_context['confirmed_time_display']}.\n"
        if email_context['location'] != "To be confirmed": text_body += f"Location: {email_context['location']}\n"
        if email_context[
            'view_interview_url'] != "#": text_body += f"You can view the details here: {email_context['view_interview_url']}\n"

    sender_email = current_app.config.get('MAIL_DEFAULT_SENDER')
    msg = Message(subject, sender=sender_email, recipients=[recruiter.email])
    msg.body = text_body
    msg.html = html_body

    try:
        if current_app.config.get('MAIL_SUPPRESS_SEND', False):
            logger.info(
                f"MAIL_SUPPRESS_SEND is True. Recruiter confirmation email to {recruiter.email} for interview {interview_id} NOT sent.")
        else:
            mail.send(msg)
            logger.info(f"Recruiter confirmation email sent to {recruiter.email} for interview {interview_id}.")
        return f"Recruiter confirmation email processed for interview {interview_id}."
    except Exception as e_mail:
        logger.error(f"Failed to send recruiter confirmation email for interview {interview_id}: {e_mail}",
                     exc_info=True)
        try:
            raise self.retry(exc=e_mail, countdown=int(self.default_retry_delay * (2 ** self.request.retries)))
        except self.MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for recruiter confirmation email, interview {interview_id}.")
            return f"Failed recruiter confirmation email (max retries) for interview {interview_id}."
        except Exception as retry_exc:
            logger.error(
                f"Retry mechanism failed for recruiter confirmation email, interview {interview_id}: {retry_exc}",
                exc_info=True)
            return f"Failed recruiter confirmation email (retry mechanism error) for interview {interview_id}."


@celery.task(bind=True, max_retries=3, default_retry_delay=180)
def send_interview_rejection_to_recruiter_task(self, interview_id_str):
    logger.info(f"Executing send_interview_rejection_to_recruiter_task for interview ID: {interview_id_str}")
    try:
        interview_id = int(interview_id_str)
    except ValueError:
        logger.error(f"Invalid ID format for interview rejection: interview_id='{interview_id_str}'")
        return "Error: Invalid ID format."

    interview = db.session.get(Interview, interview_id)
    if not interview:
        logger.error(f"Interview rejection: Interview {interview_id} not found.")
        return f"Error: Interview {interview_id} not found."

    recruiter = interview.recruiter
    if not recruiter or not recruiter.email:
        logger.warning(
            f"Interview rejection: Recruiter or email missing for interview {interview_id}. Cannot send email.")
        return f"Warning: Recruiter or email missing for interview {interview_id}."

    candidate = interview.candidate
    candidate_name = candidate.get_full_name() if candidate else "N/A"
    company_name_for_email = recruiter.company.name if recruiter.company else current_app.config.get('APP_NAME',
                                                                                                     "The Company")
    position_name_display = f"for position «{interview.position.position_name}»" if interview.position else "for an interview"

    view_candidate_url = "#"
    if interview.candidate_id:
        view_candidate_url = f"{current_app.config.get('FRONTEND_URL', '')}/candidate/{str(interview.candidate_id)}"

    subject = f"Interview Slots Declined: {candidate_name} {position_name_display}"
    email_context = {
        'recruiter_name': recruiter.username,
        'candidate_name': candidate_name,
        'company_name': company_name_for_email,
        'position_name_display': position_name_display,
        'reason_message': "The candidate has indicated that none of the proposed interview slots are suitable.",
        'view_candidate_url': view_candidate_url,
        'now': datetime.utcnow(),
        'app_home_url': current_app.config.get('FRONTEND_URL')
    }

    html_body = ""
    text_body = ""
    try:
        # ΝΕΑ ΟΝΟΜΑΤΑ TEMPLATES (πρέπει να δημιουργηθούν):
        html_body = render_template('email/interview_slots_rejected_recruiter.html', **email_context)
        text_body = render_template('email/interview_slots_rejected_recruiter.txt', **email_context)
        logger.info(
            f"Successfully rendered recruiter rejection notification email templates for interview {interview_id}.")
    except Exception as template_e:
        logger.error(
            f"Recruiter rejection notification email template rendering FAILED for interview {interview_id}: {template_e}",
            exc_info=True)
        html_body = f"<p>Hello {email_context['recruiter_name']},</p><p>The candidate {email_context['candidate_name']} has declined all proposed interview slots for {email_context['position_name_display']}.</p>"
        if email_context[
            'view_candidate_url'] != "#": html_body += f"<p>You can view the candidate's profile here: <a href='{email_context['view_candidate_url']}'>Candidate Details</a></p>"
        text_body = f"Hello {email_context['recruiter_name']},\n\nThe candidate {email_context['candidate_name']} has declined all proposed interview slots for {email_context['position_name_display']}.\n"
        if email_context[
            'view_candidate_url'] != "#": text_body += f"You can view the candidate's profile here: {email_context['view_candidate_url']}\n"

    sender_email = current_app.config.get('MAIL_DEFAULT_SENDER')
    msg = Message(subject, sender=sender_email, recipients=[recruiter.email])
    msg.body = text_body
    msg.html = html_body

    try:
        if current_app.config.get('MAIL_SUPPRESS_SEND', False):
            logger.info(
                f"MAIL_SUPPRESS_SEND is True. Recruiter rejection notification to {recruiter.email} for interview {interview_id} NOT sent.")
        else:
            mail.send(msg)
            logger.info(f"Recruiter rejection notification sent to {recruiter.email} for interview {interview_id}.")
        return f"Recruiter rejection notification email processed for interview {interview_id}."
    except Exception as e_mail:
        logger.error(f"Failed to send recruiter rejection notification for interview {interview_id}: {e_mail}",
                     exc_info=True)
        try:
            raise self.retry(exc=e_mail, countdown=int(self.default_retry_delay * (2 ** self.request.retries)))
        except self.MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for recruiter rejection notification, interview {interview_id}.")
            return f"Failed recruiter rejection notification (max retries) for interview {interview_id}."
        except Exception as retry_exc:
            logger.error(
                f"Retry mechanism failed for recruiter rejection notification, interview {interview_id}: {retry_exc}",
                exc_info=True)
            return f"Failed recruiter rejection notification (retry mechanism error) for interview {interview_id}."


@celery.task(bind=True, max_retries=3, default_retry_delay=180)
def send_interview_cancellation_to_recruiter_task(self, interview_id_str, reason=None, reschedule_preference=None):
    logger.info(
        f"Executing send_interview_cancellation_to_recruiter_task for interview ID: {interview_id_str}. Reason: {reason or 'N/A'}, Reschedule: {reschedule_preference or 'N/A'}")
    try:
        interview_id = int(interview_id_str)
    except ValueError:
        logger.error(f"Invalid ID format for interview cancellation: interview_id='{interview_id_str}'")
        return "Error: Invalid ID format."

    interview = db.session.get(Interview, interview_id)
    if not interview:
        logger.error(f"Interview cancellation: Interview {interview_id} not found.")
        return f"Error: Interview {interview_id} not found."

    recruiter = interview.recruiter
    if not recruiter or not recruiter.email:
        logger.warning(
            f"Interview cancellation: Recruiter or email missing for interview {interview_id}. Cannot send email.")
        return f"Warning: Recruiter or email missing for interview {interview_id}."

    candidate = interview.candidate
    candidate_name = candidate.get_full_name() if candidate else "N/A"
    company_name_for_email = recruiter.company.name if recruiter.company else current_app.config.get('APP_NAME',
                                                                                                     "The Company")
    position_name_display = f"for position «{interview.position.position_name}»" if interview.position else "for an interview"

    view_candidate_url = "#"
    if interview.candidate_id:
        view_candidate_url = f"{current_app.config.get('FRONTEND_URL', '')}/candidate/{str(interview.candidate_id)}"

    subject = f"Interview Cancelled by Candidate: {candidate_name} {position_name_display}"
    email_context = {
        'recruiter_name': recruiter.username,
        'candidate_name': candidate_name,
        'company_name': company_name_for_email,
        'position_name_display': position_name_display,
        'cancellation_reason': reason or "No specific reason provided.",
        'reschedule_preference_text': reschedule_preference,
        'view_candidate_url': view_candidate_url,
        'now': datetime.utcnow(),
        'app_home_url': current_app.config.get('FRONTEND_URL')
    }

    if reschedule_preference == 'request_reschedule':
        reschedule_message = "The candidate has requested to reschedule."
    elif reschedule_preference == 'no_reschedule':
        reschedule_message = "The candidate does not wish to reschedule at this time."
    else:
        reschedule_message = "The candidate's preference for rescheduling is not specified or they are unsure."
    email_context['reschedule_message'] = reschedule_message

    html_body = ""
    text_body = ""
    try:
        # ΝΕΑ ΟΝΟΜΑΤΑ TEMPLATES (πρέπει να δημιουργηθούν):
        html_body = render_template('email/interview_cancelled_by_candidate_recruiter.html', **email_context)
        text_body = render_template('email/interview_cancelled_by_candidate_recruiter.txt', **email_context)
        logger.info(
            f"Successfully rendered recruiter cancellation notification email templates for interview {interview_id}.")
    except Exception as template_e:
        logger.error(
            f"Recruiter cancellation notification email template rendering FAILED for interview {interview_id}: {template_e}",
            exc_info=True)
        html_body = f"<p>Hello {email_context['recruiter_name']},</p><p>The candidate {email_context['candidate_name']} has cancelled their interview {email_context['position_name_display']}.</p>"
        if email_context[
            'cancellation_reason'] != "No specific reason provided.": html_body += f"<p>Reason provided: {email_context['cancellation_reason']}</p>"
        html_body += f"<p>{email_context['reschedule_message']}</p>"
        if email_context[
            'view_candidate_url'] != "#": html_body += f"<p>You can view the candidate's profile here: <a href='{email_context['view_candidate_url']}'>Candidate Details</a></p>"
        text_body = f"Hello {email_context['recruiter_name']},\n\nThe candidate {email_context['candidate_name']} has cancelled their interview {email_context['position_name_display']}.\n"
        if email_context[
            'cancellation_reason'] != "No specific reason provided.": text_body += f"Reason provided: {email_context['cancellation_reason']}\n"
        text_body += f"{email_context['reschedule_message']}\n"
        if email_context[
            'view_candidate_url'] != "#": text_body += f"You can view the candidate's profile here: {email_context['view_candidate_url']}\n"

    sender_email = current_app.config.get('MAIL_DEFAULT_SENDER')
    msg = Message(subject, sender=sender_email, recipients=[recruiter.email])
    msg.body = text_body
    msg.html = html_body

    try:
        if current_app.config.get('MAIL_SUPPRESS_SEND', False):
            logger.info(
                f"MAIL_SUPPRESS_SEND is True. Recruiter cancellation notification to {recruiter.email} for interview {interview_id} NOT sent.")
        else:
            mail.send(msg)
            logger.info(f"Recruiter cancellation notification sent to {recruiter.email} for interview {interview_id}.")
        return f"Recruiter cancellation notification email processed for interview {interview_id}."
    except Exception as e_mail:
        logger.error(f"Failed to send recruiter cancellation notification for interview {interview_id}: {e_mail}",
                     exc_info=True)
        try:
            raise self.retry(exc=e_mail, countdown=int(self.default_retry_delay * (2 ** self.request.retries)))
        except self.MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for recruiter cancellation notification, interview {interview_id}.")
            return f"Failed recruiter cancellation notification (max retries) for interview {interview_id}."
        except Exception as retry_exc:
            logger.error(
                f"Retry mechanism failed for recruiter cancellation notification, interview {interview_id}: {retry_exc}",
                exc_info=True)
            return f"Failed recruiter cancellation notification (retry mechanism error) for interview {interview_id}."


@celery.task(bind=True, max_retries=3, default_retry_delay=60)
def send_interview_reminder_email_task(self, user_email, user_name, candidate_name, interview_datetime_iso,
                                       interview_location, position_name, lead_time_minutes, interview_id_str):
    logger.info(
        f"Executing send_interview_reminder_email_task to {user_email} for candidate {candidate_name}, interview ID: {interview_id_str}")

    try:
        interview_datetime_utc = datetime.fromisoformat(interview_datetime_iso)
        if interview_datetime_utc.tzinfo is None:
            interview_datetime_utc = interview_datetime_utc.replace(tzinfo=ZoneInfo("UTC"))
    except ValueError:
        logger.error(
            f"Invalid interview_datetime_iso format: {interview_datetime_iso} for interview {interview_id_str}")
        return "Error: Invalid datetime format for reminder."

    try:
        local_tz_str = current_app.config.get('LOCAL_TIMEZONE', 'UTC')
        local_tz = ZoneInfo(local_tz_str)
    except Exception as tz_err:
        logger.error(f"Could not load {local_tz_str} timezone in reminder task: {tz_err}", exc_info=True)
        local_tz = ZoneInfo("UTC")
        logger.warning(f"Falling back to UTC for reminder email display times for interview {interview_id_str}.")

    interview_display_time_local = interview_datetime_utc.astimezone(local_tz).strftime("%A, %d %B %Y at %H:%M (%Z)")

    candidate_uuid_for_url = None
    try:
        interview_obj_for_url = db.session.get(Interview, int(interview_id_str))
        if interview_obj_for_url and interview_obj_for_url.candidate_id:
            candidate_uuid_for_url = str(interview_obj_for_url.candidate_id)
    except Exception as e_get_cand_id:
        logger.warning(
            f"Could not retrieve candidate_id for interview {interview_id_str} for URL generation: {e_get_cand_id}",
            exc_info=True)

    view_interview_url = "#"
    if candidate_uuid_for_url:
        view_interview_url = f"{current_app.config.get('FRONTEND_URL', '')}/candidate/{candidate_uuid_for_url}?tab=interviews"

    subject = f"Reminder: Upcoming Interview with {candidate_name}"
    email_context = {
        'user_name': user_name,
        'candidate_name': candidate_name,
        'interview_time_display': interview_display_time_local,
        'location': interview_location,
        'position_name': position_name,
        'lead_time_minutes': lead_time_minutes,
        'view_interview_url': view_interview_url,
        'now': datetime.utcnow(),
        'app_home_url': current_app.config.get('FRONTEND_URL')
    }

    html_body = ""
    text_body = ""
    try:
        # ΝΕΑ ΟΝΟΜΑΤΑ TEMPLATES (πρέπει να δημιουργηθούν):
        html_body = render_template('email/interview_reminder_recruiter.html', **email_context)
        text_body = render_template('email/interview_reminder_recruiter.txt', **email_context)
        logger.info(f"Successfully rendered reminder email templates for interview {interview_id_str} to {user_email}.")
    except Exception as template_e:
        logger.error(
            f"Reminder email template rendering FAILED for interview {interview_id_str} to {user_email}: {template_e}",
            exc_info=True)
        html_body = f"<p>Hello {email_context['user_name']},</p><p>This is a reminder for your upcoming interview with {email_context['candidate_name']} for the position of {email_context['position_name']}.</p><p><strong>Time:</strong> {email_context['interview_time_display']}</p>"
        if email_context['location']: html_body += f"<p><strong>Location:</strong> {email_context['location']}</p>"
        if email_context[
            'view_interview_url'] != "#": html_body += f"<p>You can view more details here: <a href='{email_context['view_interview_url']}'>Interview Details</a></p>"
        text_body = f"Hello {email_context['user_name']},\n\nThis is a reminder for your upcoming interview with {email_context['candidate_name']} for the position of {email_context['position_name']}.\nTime: {email_context['interview_time_display']}\n"
        if email_context['location']: text_body += f"Location: {email_context['location']}\n"
        if email_context[
            'view_interview_url'] != "#": text_body += f"You can view more details here: {email_context['view_interview_url']}\n"

    sender_email = current_app.config.get('MAIL_DEFAULT_SENDER')
    msg = Message(subject, sender=sender_email, recipients=[user_email])
    msg.body = text_body
    msg.html = html_body

    try:
        if current_app.config.get('MAIL_SUPPRESS_SEND', False):
            logger.info(
                f"MAIL_SUPPRESS_SEND is True. Reminder email to {user_email} for interview {interview_id_str} NOT sent.")
        else:
            mail.send(msg)
            logger.info(f"Reminder email sent to {user_email} for interview {interview_id_str}.")
        return f"Reminder email processed for interview {interview_id_str} to {user_email}."
    except Exception as e_mail:
        logger.error(f"Failed to send reminder email for interview {interview_id_str} to {user_email}: {e_mail}",
                     exc_info=True)
        try:
            raise self.retry(exc=e_mail, countdown=int(self.default_retry_delay * (2 ** self.request.retries)))
        except self.MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for reminder email, interview {interview_id_str} to {user_email}.")
            return f"Failed reminder email (max retries) for interview {interview_id_str}."
        except Exception as retry_exc:
            logger.error(
                f"Retry mechanism failed for reminder email, interview {interview_id_str} to {user_email}: {retry_exc}",
                exc_info=True)
            return f"Failed reminder email (retry mechanism error) for interview {interview_id_str}."