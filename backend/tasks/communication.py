# backend/tasks/communication.py
from app import celery, db, mail, \
    create_app  # Βεβαιώσου ότι το create_app είναι εδώ αν το χρειάζεσαι για context σε άλλα tasks
from app.models import Interview, Candidate, User, Position, Company
from flask_mail import Message
from flask import current_app, url_for, render_template
from datetime import datetime  # Δεν χρειάζεται το datetime από εδώ, το παίρνουμε από το interview object
from zoneinfo import ZoneInfo  # Για την μετατροπή της ώρας
import logging
import os  # Για το FLASK_CONFIG

logger = logging.getLogger(__name__)


@celery.task(bind=True, name='tasks.communication.send_interview_proposal_email_task', max_retries=3,
             default_retry_delay=300)
def send_interview_proposal_email_task(self, interview_id):
    """
    Sends an interview proposal email to the candidate.
    """
    # Χρησιμοποίησε το app context που παρέχεται από την Celery ή δημιούργησε ένα νέο.
    # Αν το task είναι bind=True και το celery instance έχει ρυθμιστεί με app (όπως στο make_celery),
    # τότε το self.app είναι διαθέσιμο. Αλλιώς, δημιούργησε νέο app context.
    app_instance = self.app if hasattr(self, 'app') and self.app else None
    if not app_instance:
        # Fallback: Δημιούργησε μια νέα app instance αν το self.app δεν είναι διαθέσιμο.
        # Αυτό είναι σημαντικό αν το task καλείται από σημεία όπου το app context μπορεί να μην υπάρχει.
        # Ωστόσο, με τη ρύθμιση ContextTask, το app_context θα έπρεπε να είναι pushed.
        # Αυτό το fallback είναι για επιπλέον ασφάλεια.
        current_app_config = os.getenv('FLASK_ENV') or 'development'  # Ή 'default'
        app_instance = create_app(current_app_config)
        logger.info(f"Created new Flask app instance in task with config: {current_app_config}")

    with app_instance.app_context():
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
        if not recruiter:
            logger.error(f"send_interview_proposal_email_task: Recruiter not found for interview ID {interview_id}.")
            return f"Error: Recruiter not found for interview ID {interview_id}."

        company = recruiter.company
        company_name_for_email = company.name if company else "Our Company"  # Default αν δεν βρεθεί εταιρεία

        try:
            greece_tz = ZoneInfo("Europe/Athens")  # Η ζώνη ώρας για εμφάνιση
        except Exception as tz_err:
            logger.error(f"Could not load Europe/Athens timezone in Celery task: {tz_err}")
            # Χρησιμοποίησε UTC ως fallback αν η ζώνη ώρας δεν φορτωθεί
            greece_tz = ZoneInfo("UTC")
            logger.warning("Falling back to UTC for email display times.")

        proposed_slots_for_email = []
        slot_options = [
            (interview.proposed_slot_1_start, interview.proposed_slot_1_end, 1),
            (interview.proposed_slot_2_start, interview.proposed_slot_2_end, 2),
            (interview.proposed_slot_3_start, interview.proposed_slot_3_end, 3),
        ]

        for start_utc, end_utc, slot_num in slot_options:
            if start_utc and end_utc:  # Βεβαιώσου ότι και τα δύο υπάρχουν
                start_local = start_utc.astimezone(greece_tz)  # Μετατροπή σε τοπική ώρα για εμφάνιση
                proposed_slots_for_email.append({
                    "id": slot_num,
                    "start_display": start_local.strftime("%A, %d %B %Y at %H:%M (%Z)"),
                    "confirmation_url": url_for('api.confirm_interview_slot', token=interview.confirmation_token,
                                                slot_choice=slot_num, _external=True)
                })

        if not proposed_slots_for_email:  # Έλεγχος αν υπάρχουν επεξεργασμένα slots
            logger.error(
                f"send_interview_proposal_email_task: No valid proposed slots to email for interview ID {interview_id}.")
            return f"Error: No valid proposed slots for interview ID {interview_id}."

        reject_all_url = url_for('api.reject_interview_slots', token=interview.confirmation_token, _external=True)
        cancel_by_candidate_url = url_for('api.cancel_interview_by_candidate', token=interview.confirmation_token,
                                          _external=True)

        subject = f"Interview Invitation"
        if position: subject += f" for {position.position_name}"
        subject += f" at {company_name_for_email}"

        email_context = {
            'candidate_name': candidate.get_full_name(),
            'position_name_display': f"for the position «{position.position_name}»" if position else "for a collaboration opportunity",
            'company_name': company_name_for_email,
            'proposed_slots': proposed_slots_for_email,
            'interview_type': interview.interview_type or "Not specified",
            'location': interview.location or "To be confirmed",
            'notes_for_candidate': interview.notes_for_candidate,
            'reject_all_url': reject_all_url,
            'cancel_by_candidate_url': cancel_by_candidate_url,
            'recruiter_name': recruiter.username,
            'app_home_url': current_app.config.get('FRONTEND_URL', 'http://localhost:5173')
        }

        html_body = ""
        text_body = ""
        try:
            # Βεβαιώσου ότι τα templates υπάρχουν στο backend/templates/email/
            html_body = render_template('email/interview_proposal.html', **email_context)
            text_body = render_template('email/interview_proposal.txt', **email_context)
        except Exception as template_e:
            logger.warning(
                f"Email template rendering failed for interview_proposal: {template_e}. Falling back to basic f-string email.")
            # Απλό Fallback HTML
            html_body = f"""
            <p>Dear {email_context['candidate_name']},</p>
            <p>Thank you for your interest {email_context['position_name_display']} at {email_context['company_name']}.</p>
            <p>We would like to invite you for an interview. Please find below some proposed date(s) and time(s) (Local Time):</p>
            """
            if email_context['proposed_slots']:
                html_body += "<ul>"
                for slot in email_context['proposed_slots']:
                    html_body += f"<li>{slot['start_display']} - <a href='{slot['confirmation_url']}'>Select this slot</a></li>"
                html_body += "</ul>"
            else:
                html_body += "<p>No proposed slots are currently defined. We will contact you shortly.</p>"

            html_body += f"<p><strong>Interview Type:</strong> {email_context['interview_type']}</p>"
            html_body += f"<p><strong>Location/Link:</strong> {email_context['location']}</p>"
            if email_context['notes_for_candidate']:
                html_body += f"<p><strong>Notes:</strong><br/>{email_context['notes_for_candidate'].replace(chr(10), '<br/>')}</p>"
            html_body += f"""
            <p>Please select the slot that works best for you by clicking the corresponding link.</p>
            <p>If none of the above slots are suitable, please let us know by clicking here: <a href='{email_context['reject_all_url']}'>None of these slots work for me</a>.</p>
            <p>If you wish to cancel this invitation, you can do so here: <a href='{email_context['cancel_by_candidate_url']}'>Cancel invitation</a>.</p>
            <p>We look forward to speaking with you!</p>
            <p>Sincerely,<br/>The {email_context['company_name']} Recruitment Team</p>
            """
            # Απλό Fallback TEXT
            text_body = f"Dear {email_context['candidate_name']},\n\nThank you for your interest {email_context['position_name_display']} at {email_context['company_name']}.\nWe would like to invite you for an interview. Please find below some proposed date(s) and time(s) (Local Time):\n"
            if email_context['proposed_slots']:
                for slot in email_context['proposed_slots']:
                    text_body += f"- {slot['start_display']} (Confirm: {slot['confirmation_url']})\n"
            else:
                text_body += "No proposed slots are currently defined. We will contact you shortly.\n"
            text_body += f"\nInterview Type: {email_context['interview_type']}\nLocation/Link: {email_context['location']}\n"
            if email_context['notes_for_candidate']: text_body += f"\nNotes:\n{email_context['notes_for_candidate']}\n"
            text_body += f"\nPlease select the slot that works best for you by visiting the corresponding link.\nIf none of these slots work, please click here: {email_context['reject_all_url']}\nIf you wish to cancel this invitation: {email_context['cancel_by_candidate_url']}\n\nWe look forward to speaking with you!\n\nSincerely,\nThe {email_context['company_name']} Recruitment Team"

        sender_email = current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@example.com')
        msg = Message(subject, sender=sender_email, recipients=[candidate.email])
        msg.body = text_body
        msg.html = html_body

        try:
            if current_app.config.get('MAIL_SUPPRESS_SEND', False):
                logger.info(
                    f"MAIL_SUPPRESS_SEND is True. Email to {candidate.email} for interview {interview_id} NOT sent but task executed.")
            else:
                mail.send(msg)  # Το mail instance είναι ήδη αρχικοποιημένο με την app
                logger.info(f"Interview proposal email sent to {candidate.email} for interview ID {interview_id}.")
            return f"Email processed for interview ID {interview_id}."
        except Exception as e_mail:
            logger.error(f"Failed to send interview proposal email for interview ID {interview_id}: {e_mail}",
                         exc_info=True)
            try:
                raise self.retry(exc=e_mail, countdown=int(self.default_retry_delay * (self.request.retries + 1)))
            except self.MaxRetriesExceededError:
                logger.error(f"Max retries exceeded for sending email for interview ID {interview_id}.")
                return f"Failed to send email for interview ID {interview_id} after max retries."
            except Exception as retry_exc:
                logger.error(f"Error during retry mechanism for interview ID {interview_id}: {retry_exc}")
                return f"Failed to send email for interview ID {interview_id}, retry mechanism failed."

# --- Υπόλοιπα Tasks (προς υλοποίηση) ---

# @celery.task(name='tasks.communication.send_interview_confirmation_to_candidate_task')
# def send_interview_confirmation_to_candidate_task(interview_id):
#     # Λογική για αποστολή email επιβεβαίωσης στον υποψήφιο
#     logger.info(f"TODO: Send interview confirmation to candidate for interview ID: {interview_id}")
#     pass

# @celery.task(name='tasks.communication.send_interview_confirmation_to_recruiter_task')
# def send_interview_confirmation_to_recruiter_task(interview_id):
#     # Λογική για αποστολή email επιβεβαίωσης στον recruiter
#     logger.info(f"TODO: Send interview confirmation to recruiter for interview ID: {interview_id}")
#     pass

# @celery.task(name='tasks.communication.send_interview_rejection_to_recruiter_task')
# def send_interview_rejection_to_recruiter_task(interview_id):
#     # Λογική για ειδοποίηση του recruiter ότι ο υποψήφιος απέρριψε τα slots
#     logger.info(f"TODO: Send interview slot rejection notification to recruiter for interview ID: {interview_id}")
#     pass

# @celery.task(name='tasks.communication.send_interview_cancellation_to_recruiter_task')
# def send_interview_cancellation_to_recruiter_task(interview_id, reason=None):
#     # Λογική για ειδοποίηση του recruiter ότι ο υποψήφιος ακύρωσε τη συνέντευξη
#     logger.info(f"TODO: Send interview cancellation by candidate notification to recruiter for interview ID: {interview_id}. Reason: {reason or 'N/A'}")
#     pass