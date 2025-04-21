# backend/tasks/reminders.py

# --- Corrected Imports ---
from flask import current_app # Import from Flask ONLY if needed inside task (currently not used directly)
from app import celery, db    # Import celery & db from app package

# Using direct import assuming structure allows it
try:
    from .communication import send_interview_reminder_email_task
    TASK_TRIGGER_METHOD = 'direct'
except ImportError as e:
    TASK_TRIGGER_METHOD = 'by_name'
    pass # Continue, will use send_task by name

from app.models import User, Candidate
from datetime import datetime, timedelta, timezone
import logging

logger = logging.getLogger(__name__)
# --- End Corrected Imports ---


@celery.task(name='tasks.reminders.check_upcoming_interviews')
def check_upcoming_interviews():
    """
    Scheduled task to find upcoming interviews and trigger notifications.
    App context is provided by ContextTask.
    """
    logger.info("[REMINDER TASK START] Checking for upcoming interviews...")

    try:
        users_to_notify = User.query.filter_by(enable_interview_reminders=True).all()

        if not users_to_notify:
            logger.info("[REMINDER TASK] No users have reminders enabled.")
            return "No users opted-in for reminders."

        now_utc = datetime.now(timezone.utc)
        logger.debug(f"[REMINDER TASK] Current UTC time: {now_utc.isoformat()}")

        total_reminders_sent = 0
        processed_interviews = set()

        for user in users_to_notify:
            lead_time_minutes = user.reminder_lead_time_minutes
            email_reminders_enabled = user.email_interview_reminders # Get pref from user object

            logger.debug(f"[REMINDER TASK] Processing User ID: {user.id} ({user.username}). Lead Time: {lead_time_minutes} mins, Email Enabled: {email_reminders_enabled}")

            if not (isinstance(lead_time_minutes, int) and 5 <= lead_time_minutes <= 1440):
                logger.warning(f"[REMINDER TASK] User {user.id} has invalid lead time ({lead_time_minutes}), skipping.")
                continue

            reminder_target_time_start = now_utc + timedelta(minutes=lead_time_minutes)

            # --- Using NARROW WINDOW (+/- 1 min) ---
            window_minutes = 1
            window_start = reminder_target_time_start - timedelta(minutes=window_minutes)
            window_end = reminder_target_time_start + timedelta(minutes=window_minutes)
            # --- END NARROW WINDOW ---

            logger.debug(f"[REMINDER TASK] Query Window (UTC): {window_start.isoformat()} to {window_end.isoformat()}")

            interviews_in_window = Candidate.query.filter(
                Candidate.current_status == 'Interview',
                Candidate.interview_datetime > window_start,
                Candidate.interview_datetime <= window_end
            ).all()

            # Log if candidates were found by the query, BEFORE checking email prefs
            if interviews_in_window:
                logger.info(f"[REMINDER TASK] Found {len(interviews_in_window)} upcoming interview(s) for user {user.id} within the time window.")
                for cand in interviews_in_window:
                     logger.debug(f"  - Candidate ID: {cand.candidate_id}, Interview Time (UTC): {cand.interview_datetime.isoformat() if cand.interview_datetime else 'NULL'}")
            else:
                 logger.debug(f"[REMINDER TASK] No interviews found within the calculated {window_minutes*2} min window for user {user.id}.")
                 continue # Go to next user if no interviews found for this one


            # --- START: ADDED DEBUG LOGGING FOR EMAIL CHECK ---
            # Process reminders only if email is enabled AND user has email
            if email_reminders_enabled and user.email:
                # Log that the condition passed
                logger.info(f"[REMINDER TASK EMAIL CHECK - PASSED] Will attempt trigger: email_reminders_enabled={email_reminders_enabled}, user.email='{user.email}'")
                for candidate in interviews_in_window:
                    interview_key = (candidate.candidate_id, candidate.interview_datetime)
                    if interview_key in processed_interviews:
                        logger.debug(f"Skipping already processed interview in this run: {candidate.candidate_id}")
                        continue

                    try:
                        candidate_name = candidate.get_full_name()
                        interview_dt_iso = candidate.interview_datetime.isoformat() if candidate.interview_datetime else None
                        interview_loc = candidate.interview_location or "Not specified"

                        if not interview_dt_iso:
                            logger.warning(f"Skipping reminder: Candidate {candidate.candidate_id} missing interview datetime.")
                            continue

                        logger.info(f"[REMINDER TASK] Triggering reminder email task for {user.email} about candidate {candidate.candidate_id} ({candidate_name})")

                        if TASK_TRIGGER_METHOD == 'direct':
                             send_interview_reminder_email_task.delay(
                                 user_email=user.email, candidate_name=candidate_name,
                                 interview_datetime_iso=interview_dt_iso, interview_location=interview_loc
                             )
                        else: # Fallback by name
                             celery.send_task(
                                 'tasks.communication.send_interview_reminder_email',
                                 args=[user.email, candidate_name, interview_dt_iso, interview_loc]
                             )

                        processed_interviews.add(interview_key)
                        total_reminders_sent += 1

                    except Exception as trigger_err:
                        logger.error(f"[REMINDER TASK] Failed trigger email task for user {user.id}, candidate {candidate.candidate_id}: {trigger_err}", exc_info=True)
            else:
                 # Log that the condition failed IF interviews were found
                 if interviews_in_window:
                     logger.warning(f"[REMINDER TASK EMAIL CHECK - FAILED] Condition not met: email_reminders_enabled={email_reminders_enabled}, user.email='{user.email}'. No email will be triggered.")
                     # Log specific reason (optional but helpful)
                     if not email_reminders_enabled: logger.warning(f"[REMINDER TASK] Detail: Email reminders explicitly disabled for user {user.id}.")
                     if not user.email: logger.warning(f"[REMINDER TASK] Detail: User {user.id} has no email address.")

            # --- END: ADDED DEBUG LOGGING FOR EMAIL CHECK ---


        logger.info(f"[REMINDER TASK END] Check complete. Found candidates matching window: {len(processed_interviews)}. Email reminders triggered: {total_reminders_sent}.") # Updated log
        return f"Checked reminders. Matched interviews: {len(processed_interviews)}. Triggered emails: {total_reminders_sent}."

    except Exception as e:
        logger.error(f"[REMINDER TASK FAIL] Unexpected error in check_upcoming_interviews: {e}", exc_info=True)
        return "Reminder check failed unexpectedly."