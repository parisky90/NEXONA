# backend/app/tasks/communication.py
from app import celery, db, mail
from app.models import Interview, Candidate, User, Position, Company, InterviewSlot, InterviewStatus
from flask_mail import Message
from flask import current_app, url_for, render_template
from zoneinfo import ZoneInfo
import logging
from datetime import datetime, timedelta  # Πρόσθεσε timedelta αν χρειάζεται
from sqlalchemy.orm.attributes import flag_modified
from markupsafe import Markup

logger = logging.getLogger(__name__)


# ... (send_interview_proposal_email_task, send_interview_confirmation_to_candidate_task,
#      send_interview_confirmation_to_recruiter_task, send_interview_rejection_to_recruiter_task,
#      send_interview_cancellation_to_recruiter_task, send_interview_cancellation_to_candidate_task,
#      send_interview_reminder_email_task ΠΑΡΑΜΕΝΟΥΝ ΙΔΙΑ ΜΕ ΤΗΝ ΤΕΛΕΥΤΑΙΑ ΠΛΗΡΗ ΕΚΔΟΣΗ ΠΟΥ ΣΟΥ ΕΣΤΕΙΛΑ) ...

# --- ΝΕΑ TASKS ΓΙΑ OFFER/HIRED/DECLINED ---

@celery.task(bind=True, max_retries=3, default_retry_delay=300)
def send_offer_made_email_to_candidate_task(self, candidate_id_str, offer_details_dict=None):
    logger.info(f"Executing send_offer_made_email_to_candidate_task for Candidate ID: {candidate_id_str}")
    if offer_details_dict is None:
        offer_details_dict = {}
    try:
        candidate_id_obj = uuid.UUID(candidate_id_str)
        candidate = db.session.get(Candidate, candidate_id_obj)
    except ValueError:
        logger.error(f"Invalid candidate_id format: {candidate_id_str}")
        return f"Error: Invalid candidate_id format {candidate_id_str}"

    if not candidate:
        logger.error(f"send_offer_made_email_task: Candidate with ID {candidate_id_str} not found.")
        return f"Error: Candidate ID {candidate_id_str} not found."
    if not candidate.email:
        logger.error(f"send_offer_made_email_task: Candidate email missing for ID {candidate_id_str}.")
        return f"Error: Candidate email missing for ID {candidate_id_str}."
    if not candidate.offer_acceptance_token:
        logger.error(f"send_offer_made_email_task: Offer acceptance token missing for candidate {candidate_id_str}.")
        # Αυτό δεν θα έπρεπε να συμβεί αν το token δημιουργείται σωστά στο route
        return f"Error: Offer acceptance token missing for candidate {candidate_id_str}."

    company_name = candidate.company.name if candidate.company else current_app.config.get('APP_NAME', "Our Company")

    accept_url = url_for('api.accept_offer', token=candidate.offer_acceptance_token, _external=True)
    reject_url = url_for('api.reject_offer', token=candidate.offer_acceptance_token, _external=True)

    subject = f"Job Offer from {company_name}"
    email_context = {
        'candidate_name': candidate.get_full_name(),
        'company_name': company_name,
        'offer_amount': offer_details_dict.get('offer_amount'),  # Μπορεί να είναι None
        'offer_notes': offer_details_dict.get('offer_notes'),  # Μπορεί να είναι None
        'offer_date': offer_details_dict.get('offer_date'),  # Μπορεί να είναι None (ISO string)
        'accept_url': accept_url,
        'reject_url': reject_url,
        'now': datetime.utcnow(),
        'app_home_url': current_app.config.get('FRONTEND_URL')
    }

    html_body = ""
    text_body = ""
    try:
        # Χρειάζονται νέα templates: email/offer_made_candidate.html και .txt
        html_body = render_template('email/offer_made_candidate.html', **email_context)
        text_body = render_template('email/offer_made_candidate.txt', **email_context)
        logger.info(f"Successfully rendered 'Offer Made' email templates for candidate {candidate_id_str}.")
    except Exception as template_e:
        logger.error(f"'Offer Made' email template rendering FAILED for candidate {candidate_id_str}: {template_e}",
                     exc_info=True)
        # Fallback
        html_body = f"<p>Dear {candidate.get_full_name()},</p><p>We are pleased to extend an offer of employment from {company_name}.</p>"
        if offer_details_dict.get(
            'offer_amount'): html_body += f"<p>Offered Salary: {offer_details_dict.get('offer_amount')}</p>"
        if offer_details_dict.get('offer_notes'): html_body += f"<p>Notes: {offer_details_dict.get('offer_notes')}</p>"
        html_body += f"<p>To accept this offer, please click here: <a href='{accept_url}'>Accept Offer</a></p>"
        html_body += f"<p>If you wish to decline, please click here: <a href='{reject_url}'>Decline Offer</a></p>"
        text_body = f"Dear {candidate.get_full_name()},\n\nWe are pleased to extend an offer of employment from {company_name}.\n"
        if offer_details_dict.get(
            'offer_amount'): text_body += f"Offered Salary: {offer_details_dict.get('offer_amount')}\n"
        if offer_details_dict.get('offer_notes'): text_body += f"Notes: {offer_details_dict.get('offer_notes')}\n"
        text_body += f"To accept this offer, please visit: {accept_url}\n"
        text_body += f"If you wish to decline, please visit: {reject_url}\n"

    sender_email = current_app.config.get('MAIL_DEFAULT_SENDER')
    msg = Message(subject, sender=sender_email, recipients=[candidate.email])
    msg.body = text_body
    msg.html = html_body

    try:
        if current_app.config.get('MAIL_SUPPRESS_SEND', False):
            logger.info(f"MAIL_SUPPRESS_SEND is True. Offer email to {candidate.email} NOT sent.")
        else:
            mail.send(msg)
            logger.info(f"Offer email sent to {candidate.email}.")
        return f"Offer email processed for candidate {candidate_id_str}."
    except Exception as e_mail:
        logger.error(f"Failed to send offer email for candidate {candidate_id_str}: {e_mail}", exc_info=True)
        # Retry logic (παρόμοια με τα άλλα tasks)
        try:
            raise self.retry(exc=e_mail, countdown=int(self.default_retry_delay * (2 ** self.request.retries)))
        except self.MaxRetriesExceededError:
            logger.error(f"Max retries for offer email, candidate {candidate_id_str}.")
            return f"Failed offer email (max retries) for candidate {candidate_id_str}."
        except Exception as retry_exc:
            logger.error(f"Retry mechanism failed for offer email, candidate {candidate_id_str}: {retry_exc}",
                         exc_info=True)
            return f"Failed offer email (retry mechanism error) for candidate {candidate_id_str}."


@celery.task(bind=True, max_retries=3, default_retry_delay=180)
def send_hired_confirmation_email_to_candidate_task(self, candidate_id_str):
    logger.info(f"Executing send_hired_confirmation_email_to_candidate_task for Candidate ID: {candidate_id_str}")
    try:
        candidate_id_obj = uuid.UUID(candidate_id_str)
        candidate = db.session.get(Candidate, candidate_id_obj)
    except ValueError:
        logger.error(f"Invalid candidate_id format for hired email: {candidate_id_str}")
        return "Error: Invalid ID format."

    if not candidate or not candidate.email:
        logger.error(f"Hired email: Candidate or email missing for ID {candidate_id_str}.")
        return f"Error: Candidate or email missing for ID {candidate_id_str}."

    company_name = candidate.company.name if candidate.company else current_app.config.get('APP_NAME', "Our Company")
    # Εδώ θα μπορούσες να φορτώσεις παραμετροποιήσιμο περιεχόμενο από το CompanySettings
    # welcome_message_template = candidate.company.settings.welcome_email_template or "Welcome aboard!"
    # Για τώρα, ένα γενικό μήνυμα:
    welcome_message_body = f"We are thrilled to welcome you to the team at {company_name}! We will be in touch shortly with details about your onboarding process."

    subject = f"Welcome to {company_name}!"
    email_context = {
        'candidate_name': candidate.get_full_name(),
        'company_name': company_name,
        'welcome_message_body': welcome_message_body,  # Αυτό θα μπορούσε να είναι πιο πλούσιο
        'now': datetime.utcnow(),
        'app_home_url': current_app.config.get('FRONTEND_URL')
    }

    html_body = ""
    text_body = ""
    try:
        # Χρειάζονται νέα templates: email/hired_confirmation_candidate.html και .txt
        html_body = render_template('email/hired_confirmation_candidate.html', **email_context)
        text_body = render_template('email/hired_confirmation_candidate.txt', **email_context)
        logger.info(f"Successfully rendered 'Hired Confirmation' email templates for candidate {candidate_id_str}.")
    except Exception as template_e:
        logger.error(
            f"'Hired Confirmation' email template rendering FAILED for candidate {candidate_id_str}: {template_e}",
            exc_info=True)
        html_body = f"<p>Dear {candidate.get_full_name()},</p><p>Congratulations and welcome to {company_name}!</p><p>{welcome_message_body}</p>"
        text_body = f"Dear {candidate.get_full_name()},\n\nCongratulations and welcome to {company_name}!\n{welcome_message_body}\n"

    sender_email = current_app.config.get('MAIL_DEFAULT_SENDER')
    msg = Message(subject, sender=sender_email, recipients=[candidate.email])
    msg.body = text_body
    msg.html = html_body

    try:
        if current_app.config.get('MAIL_SUPPRESS_SEND', False):
            logger.info(f"MAIL_SUPPRESS_SEND is True. Hired email to {candidate.email} NOT sent.")
        else:
            mail.send(msg)
            logger.info(f"Hired email sent to {candidate.email}.")
        return f"Hired email processed for candidate {candidate_id_str}."
    except Exception as e_mail:
        logger.error(f"Failed to send hired email for candidate {candidate_id_str}: {e_mail}", exc_info=True)
        # Retry logic
        try:
            raise self.retry(exc=e_mail, countdown=int(self.default_retry_delay * (2 ** self.request.retries)))
        except self.MaxRetriesExceededError:
            logger.error(f"Max retries for hired email, candidate {candidate_id_str}.")
            return f"Failed hired email (max retries) for candidate {candidate_id_str}."
        except Exception as retry_exc:
            logger.error(f"Retry mechanism failed for hired email, candidate {candidate_id_str}: {retry_exc}",
                         exc_info=True)
            return f"Failed hired email (retry mechanism error) for candidate {candidate_id_str}."


@celery.task(bind=True, max_retries=3, default_retry_delay=180)
def send_offer_declined_notification_to_recruiter_task(self, candidate_id_str):
    logger.info(f"Executing send_offer_declined_notification_to_recruiter_task for Candidate ID: {candidate_id_str}")
    try:
        candidate_id_obj = uuid.UUID(candidate_id_str)
        candidate = db.session.get(Candidate, candidate_id_obj)
    except ValueError:
        logger.error(f"Invalid candidate_id format for offer declined email: {candidate_id_str}")
        return "Error: Invalid ID format."

    if not candidate:
        logger.error(f"Offer declined email: Candidate {candidate_id_str} not found.")
        return f"Error: Candidate {candidate_id_str} not found."

    # Βρες τον recruiter. Αν η εταιρεία έχει πολλούς, ίσως να θες να στείλεις σε όλους τους company admins
    # ή στον recruiter που έκανε την τελευταία ενέργεια. Για τώρα, στέλνουμε στον owner της εταιρείας ή σε έναν admin.
    recruiter_to_notify = None
    company = candidate.company
    if company:
        if company.owner:
            recruiter_to_notify = company.owner
        elif company.users.first():  # Πάρε τον πρώτο χρήστη της εταιρείας αν δεν υπάρχει owner
            recruiter_to_notify = company.users.first()

    if not recruiter_to_notify or not recruiter_to_notify.email:
        logger.warning(
            f"Offer declined email: No recruiter/admin found or email missing for company of candidate {candidate_id_str}. Cannot send notification.")
        return f"Warning: No recruiter/admin to notify for candidate {candidate_id_str}."

    company_name = company.name if company else current_app.config.get('APP_NAME', "The Company")
    candidate_name = candidate.get_full_name()

    # Link στο προφίλ του υποψηφίου
    view_candidate_url = "#"
    if candidate.candidate_id:
        view_candidate_url = f"{current_app.config.get('FRONTEND_URL', '')}/candidate/{str(candidate.candidate_id)}"

    subject = f"Offer Declined by Candidate: {candidate_name}"
    email_context = {
        'recruiter_name': recruiter_to_notify.username,
        'candidate_name': candidate_name,
        'company_name': company_name,
        'view_candidate_url': view_candidate_url,
        'now': datetime.utcnow(),
        'app_home_url': current_app.config.get('FRONTEND_URL')
    }

    html_body = ""
    text_body = ""
    try:
        # Χρειάζονται νέα templates: email/offer_declined_recruiter.html και .txt
        html_body = render_template('email/offer_declined_recruiter.html', **email_context)
        text_body = render_template('email/offer_declined_recruiter.txt', **email_context)
        logger.info(
            f"Successfully rendered 'Offer Declined' notification email templates for candidate {candidate_id_str}.")
    except Exception as template_e:
        logger.error(
            f"'Offer Declined' notification email template rendering FAILED for candidate {candidate_id_str}: {template_e}",
            exc_info=True)
        html_body = f"<p>Hello {recruiter_to_notify.username},</p><p>The candidate {candidate_name} has declined the job offer.</p>"
        if view_candidate_url != "#": html_body += f"<p>You can view the candidate's profile here: <a href='{view_candidate_url}'>Candidate Details</a></p>"
        text_body = f"Hello {recruiter_to_notify.username},\n\nThe candidate {candidate_name} has declined the job offer.\n"
        if view_candidate_url != "#": text_body += f"You can view the candidate's profile here: {view_candidate_url}\n"

    sender_email = current_app.config.get('MAIL_DEFAULT_SENDER')
    msg = Message(subject, sender=sender_email, recipients=[recruiter_to_notify.email])
    msg.body = text_body
    msg.html = html_body

    try:
        if current_app.config.get('MAIL_SUPPRESS_SEND', False):
            logger.info(
                f"MAIL_SUPPRESS_SEND is True. Offer declined notification to {recruiter_to_notify.email} NOT sent.")
        else:
            mail.send(msg)
            logger.info(f"Offer declined notification sent to {recruiter_to_notify.email}.")
        return f"Offer declined notification email processed for candidate {candidate_id_str}."
    except Exception as e_mail:
        logger.error(f"Failed to send offer declined notification for candidate {candidate_id_str}: {e_mail}",
                     exc_info=True)
        # Retry logic
        try:
            raise self.retry(exc=e_mail, countdown=int(self.default_retry_delay * (2 ** self.request.retries)))
        except self.MaxRetriesExceededError:
            logger.error(f"Max retries for offer declined notification, candidate {candidate_id_str}.")
            return f"Failed offer declined notification (max retries) for candidate {candidate_id_str}."
        except Exception as retry_exc:
            logger.error(
                f"Retry mechanism failed for offer declined notification, candidate {candidate_id_str}: {retry_exc}",
                exc_info=True)
            return f"Failed offer declined notification (retry mechanism error) for candidate {candidate_id_str}."


# --- ΤΕΛΟΣ ΝΕΩΝ TASKS ---

# --- Υπόλοιπα tasks (send_interview_reminder_email_task) παραμένουν ίδια ---
@celery.task(bind=True, max_retries=3, default_retry_delay=60)
def send_interview_reminder_email_task(self, user_email, user_name, candidate_name, interview_datetime_iso,
                                       interview_location, position_name, lead_time_minutes, interview_id_str):
    # ... (ίδιο με την τελευταία πλήρη έκδοση που σου έστειλα) ...
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