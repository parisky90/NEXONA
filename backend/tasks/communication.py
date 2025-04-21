# backend/tasks/communication.py

from flask import current_app
from app import celery, mail, db
from app.models import Candidate, User # Import User model
from flask_mail import Message
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# --- Rejection Email Task ---
@celery.task(bind=True, name='tasks.communication.send_rejection_email', max_retries=5)
def send_rejection_email_task(self, candidate_id, is_debug, sender_config):
    """Sends the standard rejection email or logs it if is_debug is True."""
    logger.info(f"[EMAIL TASK START] Attempting rejection email for Candidate ID: {candidate_id}. Passed Debug mode: {is_debug}")
    try:
        candidate = Candidate.query.get(candidate_id)
        if not candidate or not candidate.email:
            logger.error(f"[EMAIL TASK FAIL] Candidate {candidate_id} not found or missing email.")
            return f"Candidate {candidate_id} invalid/missing email."

        subject = "Σχετικά με την αίτησή σας"; recipients = [candidate.email]
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

        if is_debug:
            logger.info("--- MAIL DEBUG: Rejection Email Content Start ---"); logger.info(f"Subject: {subject}"); logger.info(f"From: {sender_config}"); logger.info(f"To: {recipients}"); logger.info("--- Body ---"); logger.info(body_text); logger.info("--- MAIL DEBUG: Email Content End ---")
            logger.info(f"[EMAIL TASK SUCCESS - DEBUG] Rejection email logged for Candidate ID: {candidate_id} to {candidate.email}")
            return f"Email logged (debug mode) for {candidate_id}."
        else:
            logger.info("[EMAIL TASK] is_debug is False, attempting rejection mail.send()")
            msg = Message(subject=subject, sender=sender_config, recipients=recipients, body=body_text)
            mail.send(msg)
            logger.info(f"[EMAIL TASK SUCCESS] Rejection email successfully sent for Candidate ID: {candidate_id} to {candidate.email}")
            return f"Email sent for {candidate_id}."
    except Exception as e:
        logger.error(f"[EMAIL TASK FAIL] Error during rejection email processing for {candidate_id}: {e}", exc_info=True)
        if not is_debug:
            try: countdown = 60 * (2 ** self.request.retries); logger.info(f"Retrying rejection email send for {candidate_id} in {countdown}s..."); self.retry(exc=e, countdown=countdown, args=[candidate_id, is_debug, sender_config])
            except self.MaxRetriesExceededError: logger.critical(f"[EMAIL TASK FAIL] Max retries exceeded for rejection email, candidate {candidate_id}."); # Try update notes ...
        return f"Failed to send rejection email for {candidate_id}."


# --- NEW Interview Reminder Email Task ---
@celery.task(bind=True, name='tasks.communication.send_interview_reminder_email', max_retries=3)
def send_interview_reminder_email_task(self, user_email, candidate_name, interview_datetime_iso, interview_location):
    """Sends an interview reminder email to a user (HR personnel)."""
    logger.info(f"[REMINDER EMAIL TASK START] Attempting reminder to User: {user_email} for Candidate: {candidate_name}")
    # Use config value loaded by the worker context
    is_debug = current_app.config.get('MAIL_DEBUG', False)
    sender_config = current_app.config.get('MAIL_SENDER', '"CV Manager App" <noreply@example.com>')

    try:
        if not user_email:
            logger.error("[REMINDER EMAIL TASK FAIL] No user email provided.")
            return "User email missing."

        # Format datetime for display
        try:
            interview_dt = datetime.fromisoformat(interview_datetime_iso)
            # Consider user's timezone preference later? For now, show as parsed (likely UTC or with offset)
            formatted_time = interview_dt.strftime("%Y-%m-%d %H:%M %Z%z") # ISO-like with timezone
            # Or more friendly:
            # formatted_time = interview_dt.strftime("%A, %B %d, %Y at %I:%M %p %Z")
        except Exception as format_err:
            logger.warning(f"Could not format interview datetime {interview_datetime_iso}: {format_err}")
            formatted_time = interview_datetime_iso # Fallback

        subject = f"Interview Reminder: {candidate_name or 'Candidate'}"
        recipients = [user_email]
        body_text = f"""
Hi,

This is a reminder for your upcoming interview:

Candidate: {candidate_name or 'N/A'}
Date & Time: {formatted_time}
Location: {interview_location or 'N/A'}

- CV Manager System
""".strip()

        # --- Conditional Send or Log ---
        if is_debug:
            logger.info("--- MAIL DEBUG: Interview Reminder Email Content Start ---")
            logger.info(f"Subject: {subject}"); logger.info(f"From: {sender_config}"); logger.info(f"To: {recipients}"); logger.info("--- Body ---"); logger.info(body_text); logger.info("--- MAIL DEBUG: Email Content End ---")
            logger.info(f"[REMINDER EMAIL SUCCESS - DEBUG] Logged for User: {user_email}, Candidate: {candidate_name}")
            return "Reminder email logged (debug)."
        else:
            logger.info("[REMINDER EMAIL TASK] is_debug is False, attempting reminder mail.send()")
            msg = Message(subject=subject, sender=sender_config, recipients=recipients, body=body_text)
            mail.send(msg)
            logger.info(f"[REMINDER EMAIL SUCCESS] Sent to User: {user_email}, Candidate: {candidate_name}")
            return "Reminder email sent."

    except Exception as e:
        logger.error(f"[REMINDER EMAIL FAIL] Error sending reminder to {user_email} for {candidate_name}: {e}", exc_info=True)
        if not is_debug:
            try:
                countdown = 30 * (2 ** self.request.retries) # Shorter retry for reminders
                logger.info(f"Retrying reminder email send for {user_email} in {countdown}s...")
                # Pass original args on retry
                self.retry(exc=e, countdown=countdown, args=[user_email, candidate_name, interview_datetime_iso, interview_location])
            except self.MaxRetriesExceededError:
                logger.critical(f"[REMINDER EMAIL FAIL] Max retries exceeded for reminder email to {user_email} for {candidate_name}.")
        return f"Failed to send reminder email to {user_email}."