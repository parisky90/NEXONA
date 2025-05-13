# backend/app/tasks/communication.py

from flask import current_app, render_template_string
from app import celery, mail, db, create_app # Import create_app
from app.models import Candidate, User # Import User model
from flask_mail import Message
import logging
import os # To construct URLs
from datetime import datetime, timezone
import uuid # Import uuid

logger = logging.getLogger(__name__)

# --- Helper function to create app context for tasks ---
# Ensure this function is suitable for your setup or use the one from celery_worker.py
def get_app_context():
    """Creates a Flask app context for the Celery task."""
    # Consider using the already configured app instance if possible,
    # otherwise create a new one based on environment config.
    app = current_app._get_current_object() if current_app else None
    if app is None:
        logger.warning("No current Flask app found, creating new one for task context.")
        app = create_app(os.getenv('FLASK_CONFIG') or 'default')
    return app.app_context()

# --- Rejection Email Task ---
@celery.task(bind=True, name='tasks.communication.send_rejection_email_task', max_retries=5)
def send_rejection_email_task(self, candidate_id):
    """Sends the standard rejection email."""
    # Get config values within the task context
    with get_app_context():
        is_debug = current_app.config.get('MAIL_DEBUG', False)
        sender_config = current_app.config.get('MAIL_SENDER', '"CV Manager App" <noreply@example.com>')
        app_name = current_app.config.get('APP_NAME', 'NEXONA')

        logger.info(f"[EMAIL TASK START] Attempting rejection email for Candidate ID: {candidate_id}. Debug mode: {is_debug}")
        try:
            candidate = Candidate.query.get(candidate_id)
            if not candidate or not candidate.email:
                logger.error(f"[EMAIL TASK FAIL] Candidate {candidate_id} not found or missing email.")
                return f"Candidate {candidate_id} invalid/missing email."

            subject = f"Ενημέρωση σχετικά με την αίτησή σας - {app_name}"; recipients = [candidate.email]
            try: sender_display_name = sender_config.split('<')[0].strip().replace('"', '') or "Η Ομάδα Προσλήψεων"
            except: sender_display_name = "Η Ομάδα Προσλήψεων"

            # Using f-string with triple quotes for multi-line body
            body_text = f"""Αγαπητέ/ή {candidate.first_name or 'Υποψήφιε/α'},

Εξετάσαμε το βιογραφικό σας σημείωμα για τη θέση εργασίας στην εταιρεία μας.

Θα θέλαμε να σας ευχαριστήσουμε θερμά για το ενδιαφέρον που δείξατε. Ωστόσο, λυπούμαστε που σας ενημερώνουμε ότι προς το παρόν δεν θα προχωρήσουμε σε περαιτέρω συνεργασία μαζί σας για την συγκεκριμένη θέση.

Το βιογραφικό σας θα παραμείνει στη βάση δεδομένων μας και θα το λάβουμε υπόψη για πιθανές μελλοντικές θέσεις εργασίας που μπορεί να ταιριάζουν με τα προσόντα σας.

Σας ευχόμαστε καλή επιτυχία στην αναζήτηση εργασίας σας.

Με εκτίμηση,
{sender_display_name}
""".strip()

            html_body = render_template_string("""
            <p>Αγαπητέ/ή {{ candidate_name }},</p>
            <p>Εξετάσαμε το βιογραφικό σας σημείωμα για τη θέση εργασίας στην εταιρεία μας.</p>
            <p>Θα θέλαμε να σας ευχαριστήσουμε θερμά για το ενδιαφέρον που δείξατε. Ωστόσο, λυπούμαστε που σας ενημερώνουμε ότι προς το παρόν δεν θα προχωρήσουμε σε περαιτέρω συνεργασία μαζί σας για την συγκεκριμένη θέση.</p>
            <p>Το βιογραφικό σας θα παραμείνει στη βάση δεδομένων μας και θα το λάβουμε υπόψη για πιθανές μελλοντικές θέσεις εργασίας που μπορεί να ταιριάζουν με τα προσόντα σας.</p>
            <p>Σας ευχόμαστε καλή επιτυχία στην αναζήτηση εργασίας σας.</p>
            <br>
            <p>Με εκτίμηση,</p>
            <p>{{ sender_display_name }}</p>
            """, candidate_name=candidate.first_name or 'Υποψήφιε/α', sender_display_name=sender_display_name)


            if is_debug:
                logger.info("--- MAIL DEBUG: Rejection Email Content Start ---"); logger.info(f"Subject: {subject}"); logger.info(f"From: {sender_config}"); logger.info(f"To: {recipients}"); logger.info("--- Body ---"); logger.info(body_text); logger.info("--- MAIL DEBUG: Email Content End ---")
                logger.info(f"[EMAIL TASK SUCCESS - DEBUG] Rejection email logged for Candidate ID: {candidate_id} to {candidate.email}")
                return f"Email logged (debug mode) for {candidate_id}."
            else:
                logger.info("[EMAIL TASK] is_debug is False, attempting rejection mail.send()")
                msg = Message(subject=subject, sender=sender_config, recipients=recipients, body=body_text, html=html_body)
                mail.send(msg)
                logger.info(f"[EMAIL TASK SUCCESS] Rejection email successfully sent for Candidate ID: {candidate_id} to {candidate.email}")
                return f"Email sent for {candidate_id}."
        except Exception as e:
            logger.error(f"[EMAIL TASK FAIL] Error during rejection email processing for {candidate_id}: {e}", exc_info=True)
            if not is_debug:
                try: countdown = 60 * (2 ** self.request.retries); logger.info(f"Retrying rejection email send for {candidate_id} in {countdown}s..."); self.retry(exc=e, countdown=countdown)
                except self.MaxRetriesExceededError: logger.critical(f"[EMAIL TASK FAIL] Max retries exceeded for rejection email, candidate {candidate_id}.");
            return f"Failed to send rejection email for {candidate_id}."

# --- Interview Reminder Email Task (to Recruiter/User) ---
@celery.task(bind=True, name='tasks.communication.send_interview_reminder_email_task', max_retries=3)
def send_interview_reminder_email_task(self, user_email, candidate_name, interview_datetime_iso, interview_location):
    """Sends an interview reminder email to a user (HR personnel)."""
    with get_app_context():
        is_debug = current_app.config.get('MAIL_DEBUG', False)
        sender_config = current_app.config.get('MAIL_SENDER', '"CV Manager App" <noreply@example.com>')
        app_name = current_app.config.get('APP_NAME', 'NEXONA')

        logger.info(f"[REMINDER EMAIL TASK START] Attempting reminder to User: {user_email} for Candidate: {candidate_name}")
        try:
            if not user_email:
                logger.error("[REMINDER EMAIL TASK FAIL] No user email provided.")
                return "User email missing."

            try:
                interview_dt = datetime.fromisoformat(interview_datetime_iso).astimezone(timezone.utc) # Ensure UTC for consistency if needed
                formatted_time = interview_dt.strftime("%d/%m/%Y %H:%M UTC") # Example format
            except Exception as format_err:
                logger.warning(f"Could not format interview datetime {interview_datetime_iso}: {format_err}")
                formatted_time = interview_datetime_iso # Fallback

            subject = f"Υπενθύμιση Συνέντευξης: {candidate_name or 'Υποψήφιος'}"
            recipients = [user_email]
            body_text = f"""
Γεια σας,

Αυτό είναι μια υπενθύμιση για την επερχόμενη συνέντευξή σας:

Υποψήφιος: {candidate_name or 'N/A'}
Ημερομηνία & Ώρα: {formatted_time}
Τοποθεσία: {interview_location or 'N/A'}

- Σύστημα {app_name}
""".strip()

            html_body = render_template_string("""
            <p>Γεια σας,</p>
            <p>Αυτό είναι μια υπενθύμιση για την επερχόμενη συνέντευξή σας:</p>
            <ul>
                <li><strong>Υποψήφιος:</strong> {{ candidate_name }}</li>
                <li><strong>Ημερομηνία & Ώρα:</strong> {{ formatted_time }}</li>
                <li><strong>Τοποθεσία:</strong> {{ interview_location }}</li>
            </ul>
            <p>- Σύστημα {{ app_name }}</p>
            """, candidate_name=candidate_name or 'N/A', formatted_time=formatted_time, interview_location=interview_location or 'N/A', app_name=app_name)

            if is_debug:
                logger.info("--- MAIL DEBUG: Interview Reminder Email Content Start ---")
                logger.info(f"Subject: {subject}"); logger.info(f"From: {sender_config}"); logger.info(f"To: {recipients}"); logger.info("--- Body ---"); logger.info(body_text); logger.info("--- MAIL DEBUG: Email Content End ---")
                logger.info(f"[REMINDER EMAIL SUCCESS - DEBUG] Logged for User: {user_email}, Candidate: {candidate_name}")
                return "Reminder email logged (debug)."
            else:
                logger.info("[REMINDER EMAIL TASK] is_debug is False, attempting reminder mail.send()")
                msg = Message(subject=subject, sender=sender_config, recipients=recipients, body=body_text, html=html_body)
                mail.send(msg)
                logger.info(f"[REMINDER EMAIL SUCCESS] Sent to User: {user_email}, Candidate: {candidate_name}")
                return "Reminder email sent."

        except Exception as e:
            logger.error(f"[REMINDER EMAIL FAIL] Error sending reminder to {user_email} for {candidate_name}: {e}", exc_info=True)
            if not is_debug:
                try:
                    countdown = 30 * (2 ** self.request.retries)
                    logger.info(f"Retrying reminder email send for {user_email} in {countdown}s...")
                    self.retry(exc=e, countdown=countdown)
                except self.MaxRetriesExceededError:
                    logger.critical(f"[REMINDER EMAIL FAIL] Max retries exceeded for reminder email to {user_email} for {candidate_name}.")
            return f"Failed to send reminder email to {user_email}."


# --- ΝΕΟ TASK: Αποστολή Πρόσκλησης Συνέντευξης στον Υποψήφιο ---
@celery.task(bind=True, name='tasks.communication.send_interview_invitation_email_task', max_retries=3, default_retry_delay=120)
def send_interview_invitation_email(self, candidate_id):
    """Sends an interview invitation email to the candidate with confirmation links."""
    with get_app_context():
        is_debug = current_app.config.get('MAIL_DEBUG', False)
        sender_config = current_app.config.get('MAIL_SENDER', '"CV Manager App" <noreply@example.com>')
        app_name = current_app.config.get('APP_NAME', 'NEXONA')
        # IMPORTANT: Set APP_BASE_URL in .env or config (e.g., http://yourdomain.com or http://localhost:5000)
        base_url = current_app.config.get('APP_BASE_URL', 'http://localhost:5000') # Default for safety

        logger.info(f"[INVITATION EMAIL TASK START] Attempting invitation email for Candidate ID: {candidate_id}. Debug: {is_debug}")
        try:
            candidate = Candidate.query.get(candidate_id)
            if not candidate:
                logger.error(f"[INVITATION EMAIL TASK FAIL] Candidate {candidate_id} not found.")
                return f"Candidate {candidate_id} not found."
            if not candidate.email:
                logger.warning(f"[INVITATION EMAIL TASK FAIL] Candidate {candidate_id} has no email address.")
                return f"Candidate {candidate_id} missing email."
            if not candidate.interview_datetime:
                logger.warning(f"[INVITATION EMAIL TASK FAIL] Candidate {candidate_id} has no interview scheduled.")
                return f"Candidate {candidate_id} no interview."
            if not candidate.confirmation_uuid:
                 logger.error(f"[INVITATION EMAIL TASK FAIL] Candidate {candidate_id} is missing confirmation_uuid.")
                 return f"Candidate {candidate_id} missing UUID."

            # Construct Confirmation URLs
            confirm_url = f"{base_url}/api/v1/interviews/confirm/{candidate.confirmation_uuid}"
            decline_url = f"{base_url}/api/v1/interviews/decline/{candidate.confirmation_uuid}"

            # Compose Email
            subject = f"Πρόσκληση Συνέντευξης - {app_name}"
            recipients = [candidate.email]
            interview_dt_formatted = candidate.interview_datetime.strftime('%d/%m/%Y στις %H:%M')

            # Basic HTML Email Template
            html_body = render_template_string("""
            <p>Αγαπητέ/ή {{ candidate_name }},</p>
            <p>Θα θέλαμε να σας προσκαλέσουμε σε συνέντευξη για τη θέση που αιτηθήκατε στην εταιρεία μας.</p>
            <p><strong>Στοιχεία Συνέντευξης:</strong></p>
            <ul>
                <li><strong>Ημερομηνία & Ώρα:</strong> {{ interview_datetime }}</li>
                {% if interview_location %}
                <li><strong>Τοποθεσία:</strong> {{ interview_location }}</li>
                {% endif %}
                {# Add description if you add it to the model/form #}
                {# {% if interview_description %}
                <li><strong>Περιγραφή/Σημειώσεις:</strong> {{ interview_description }}</li>
                {% endif %} #}
            </ul>
            <p>Παρακαλούμε επιβεβαιώστε την παρουσία σας κάνοντας κλικ στον παρακάτω σύνδεσμο:</p>
            <p style="margin: 20px 0;">
                <a href="{{ confirm_url }}" style="display: inline-block; padding: 12px 20px; background-color: #28a745; color: white; text-decoration: none; border-radius: 5px; font-weight: bold;">
                    Επιβεβαίωση Παρουσίας
                </a>
            </p>
            <p>Αν δεν μπορείτε να παρευρεθείτε την προγραμματισμένη ώρα ή χρειάζεστε αλλαγή, παρακαλούμε ενημερώστε μας κάνοντας κλικ εδώ:</p>
            <p style="margin: 20px 0;">
                <a href="{{ decline_url }}" style="display: inline-block; padding: 12px 20px; background-color: #dc3545; color: white; text-decoration: none; border-radius: 5px; font-weight: bold;">
                    Αδυναμία Παρουσίας / Αίτημα Αλλαγής
                </a>
            </p>
            <br>
            <p>Με εκτίμηση,</p>
            <p>Η Ομάδα Προσλήψεων</p>
            <p>{{ app_name }}</p>
            """,
            candidate_name=candidate.get_full_name(),
            interview_datetime=interview_dt_formatted,
            interview_location=candidate.interview_location,
            # interview_description=getattr(candidate, 'description', None), # Uncomment if description added
            confirm_url=confirm_url,
            decline_url=decline_url,
            app_name=app_name
            )

            # Create message with HTML body
            msg = Message(subject, sender=sender_config, recipients=recipients)
            msg.html = html_body
            # Optional: Add a plain text version too
            # msg.body = f"..."

            # Send Email or Log
            if is_debug:
                logger.info("--- MAIL DEBUG: Interview Invitation Email Content Start ---")
                logger.info(f"Subject: {subject}"); logger.info(f"From: {sender_config}"); logger.info(f"To: {recipients}"); logger.info("--- HTML Body ---"); logger.info(html_body); logger.info("--- MAIL DEBUG: Email Content End ---")
                logger.info(f"[INVITATION EMAIL SUCCESS - DEBUG] Logged for Candidate ID: {candidate_id} to {candidate.email}")
                return f"Invitation email logged (debug) for {candidate_id}."
            else:
                logger.info("[INVITATION EMAIL TASK] is_debug is False, attempting invitation mail.send()")
                mail.send(msg)
                logger.info(f"[INVITATION EMAIL SUCCESS] Invitation sent successfully to {candidate.email} for candidate {candidate_id}.")
                return f"Invitation email sent for {candidate_id}."

        except Exception as e:
            logger.error(f"[INVITATION EMAIL FAIL] Error during invitation email processing for {candidate_id}: {e}", exc_info=True)
            if not is_debug:
                try:
                    countdown = 120 * (2 ** self.request.retries) # Longer retry for invitations
                    logger.info(f"Retrying invitation email send for {candidate_id} in {countdown}s...")
                    self.retry(exc=e, countdown=countdown)
                except self.MaxRetriesExceededError:
                    logger.critical(f"[INVITATION EMAIL FAIL] Max retries exceeded for invitation email, candidate {candidate_id}.")
            return f"Failed to send invitation email for {candidate_id}."


# --- Placeholders for Recruiter Notification Tasks ---

@celery.task(bind=True, name='tasks.communication.notify_recruiter_interview_confirmed', max_retries=3)
def notify_recruiter_interview_confirmed(self, candidate_id):
     with get_app_context():
         # TODO: Implement logic to find the relevant recruiter(s)
         # e.g., User who created the interview, or users associated with the position
         candidate = Candidate.query.get(candidate_id)
         recruiter_email = "recruiter@example.com" # Placeholder
         logger.info(f"[RECRUITER NOTIFY TASK] Candidate {candidate_id} ({candidate.get_full_name() if candidate else 'N/A'}) confirmed interview. Notifying {recruiter_email}.")
         # Send email or create in-app notification
         # ... implementation needed ...

@celery.task(bind=True, name='tasks.communication.notify_recruiter_interview_declined', max_retries=3)
def notify_recruiter_interview_declined(self, candidate_id):
     with get_app_context():
         # TODO: Implement logic to find the relevant recruiter(s)
         candidate = Candidate.query.get(candidate_id)
         recruiter_email = "recruiter@example.com" # Placeholder
         logger.info(f"[RECRUITER NOTIFY TASK] Candidate {candidate_id} ({candidate.get_full_name() if candidate else 'N/A'}) declined/requested reschedule. Notifying {recruiter_email}.")
         # Send email or create in-app notification (higher priority)
         # ... implementation needed ...