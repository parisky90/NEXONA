# backend/tasks/reminders.py
from app import celery, db  # Import celery & db from app package
from app.models import User, Candidate, CompanySettings  # Import your models
from datetime import datetime, timedelta, timezone as dt_timezone  # Renamed to avoid conflict
import logging

# It's good practice to get the logger for the current module
logger = logging.getLogger(__name__)

# Attempt to import the email sending task directly for type hinting and direct calls
# Fallback to send_task by name if direct import fails (e.g., circular dependency if not careful)
try:
    from .communication import send_interview_reminder_email_task  # Assuming this task exists

    TASK_TRIGGER_METHOD = 'direct'
except ImportError:
    logger.warning("Could not import 'send_interview_reminder_email_task' directly. Will use celery.send_task by name.")
    TASK_TRIGGER_METHOD = 'by_name'
    send_interview_reminder_email_task = None  # To satisfy linters if direct call is attempted


@celery.task(name='tasks.reminders.check_upcoming_interviews')
def check_upcoming_interviews():
    """
    Scheduled task to find upcoming interviews and trigger notifications
    based on individual user preferences and company-level settings.
    App context is provided by ContextTask in app/__init__.py.
    """
    logger.info("[REMINDER TASK START] Checking for upcoming interviews...")

    try:
        now_utc = datetime.now(dt_timezone.utc)
        logger.debug(f"[REMINDER TASK] Current UTC time: {now_utc.isoformat()}")

        # Fetch all users who have email reminders enabled at the user level
        # and are active.
        users_wanting_reminders = User.query.filter_by(
            enable_email_interview_reminders=True,
            is_active=True
        ).all()

        if not users_wanting_reminders:
            logger.info("[REMINDER TASK] No active users have email interview reminders enabled. Exiting.")
            return "No users opted-in for reminders or active."

        logger.info(f"[REMINDER TASK] Found {len(users_wanting_reminders)} user(s) with email reminders enabled.")

        # Fetch company settings to check if the reminder feature is enabled for their company
        # We can optimize this by fetching only for companies of the users found, if many companies exist.
        all_company_settings = {cs.company_id: cs for cs in CompanySettings.query.all()}

        total_reminders_sent_this_run = 0
        processed_interview_user_pairs = set()  # To avoid sending multiple reminders for the same interview to the same user in one run

        for user in users_wanting_reminders:
            if not user.email:
                logger.warning(
                    f"[REMINDER TASK] User ID {user.id} ({user.username}) has reminders enabled but no email address. Skipping.")
                continue

            if user.company_id:
                company_setting = all_company_settings.get(user.company_id)
                if not (company_setting and company_setting.enable_reminders_feature_for_company):
                    logger.info(
                        f"[REMINDER TASK] Reminder feature disabled at company level (ID: {user.company_id}) for user {user.id}. Skipping.")
                    continue
            # If user has no company_id (e.g. superadmin), they can still get reminders if they are interviewers.

            lead_time_minutes = user.interview_reminder_lead_time_minutes
            if not (isinstance(lead_time_minutes, int) and 1 <= lead_time_minutes <= 2880):  # e.g., 1 min to 2 days
                logger.warning(
                    f"[REMINDER TASK] User {user.id} has invalid lead time ({lead_time_minutes} mins). Using company default or global default if applicable, or skipping.")
                # Optionally, use company_setting.default_interview_reminder_timing_minutes or a global default.
                # For now, we'll skip if user's setting is invalid.
                continue

            # Calculate the target time window for interviews
            # The interview should be scheduled around (now_utc + lead_time_minutes)
            # We create a small window around this target to catch interviews scheduled exactly at that time.
            reminder_target_time = now_utc + timedelta(minutes=lead_time_minutes)

            # Define a small window (e.g., +/- 1 minute of the scheduler's run frequency)
            # to ensure we catch interviews that fall exactly on the minute.
            # Celery beat might not run at the *exact* second every time.
            window_start = reminder_target_time - timedelta(minutes=1)  # Check 1 minute before target
            window_end = reminder_target_time + timedelta(minutes=1)  # Check 1 minute after target

            logger.debug(
                f"[REMINDER TASK] User {user.id}: Lead time {lead_time_minutes} mins. Target window (UTC): {window_start.isoformat()} to {window_end.isoformat()}")

            # Find candidates with interviews in this window.
            # This query assumes the user (recruiter/admin) wants reminders for *any* interview
            # in their company scheduled around their preferred lead time.
            # If reminders are only for interviews where they are listed as an interviewer,
            # the query needs to be more specific (joining with Candidate.interviewers JSONB field).
            # For now, let's assume they get reminders for candidates in their company_id (if set)
            # OR if they are superadmin, for any candidate.

            query = Candidate.query.filter(
                Candidate.interview_datetime >= window_start,
                Candidate.interview_datetime <= window_end,
                Candidate.current_status.ilike('%Interview%')  # Or a more specific status like 'Interview Scheduled'
            )

            if user.company_id and user.role != 'superadmin':  # Scope to user's company if not superadmin
                query = query.filter(Candidate.company_id == user.company_id)

            # Further refinement: Check if user.id is in Candidate.interviewers list
            # This requires JSONB query capabilities if interviewers are stored as a list of user IDs.
            # For simplicity now, we'll notify if the interview is in their company (or any for superadmin).
            # A more robust solution would be:
            # from sqlalchemy.dialects.postgresql import JSONB
            # query = query.filter(Candidate.interviewers.contains(db.cast([user.id], JSONB)))

            candidates_for_reminder = query.all()

            if not candidates_for_reminder:
                logger.debug(f"[REMINDER TASK] No interviews found for user {user.id} in their target window.")
                continue

            logger.info(
                f"[REMINDER TASK] Found {len(candidates_for_reminder)} interview(s) for user {user.id} in window.")

            for candidate in candidates_for_reminder:
                interview_user_key = (candidate.candidate_id, user.id)
                if interview_user_key in processed_interview_user_pairs:
                    logger.debug(
                        f"User {user.id} already processed for interview with {candidate.candidate_id} in this run. Skipping.")
                    continue

                candidate_name = candidate.get_full_name()
                interview_dt_iso = candidate.interview_datetime.isoformat()
                interview_loc = candidate.interview_location or "Not specified"
                position_names = ", ".join(candidate.get_position_names()) or "N/A"

                logger.info(f"[REMINDER TASK] Triggering reminder for User ID: {user.id} ({user.email}) "
                            f"about Candidate: {candidate.candidate_id} ({candidate_name}) "
                            f"Interview Time: {interview_dt_iso} "
                            f"Position(s): {position_names}")
                try:
                    if TASK_TRIGGER_METHOD == 'direct' and send_interview_reminder_email_task:
                        send_interview_reminder_email_task.delay(
                            user_email=user.email,
                            user_first_name=user.username,  # Or a first_name field if you add it
                            candidate_name=candidate_name,
                            interview_datetime_iso=interview_dt_iso,
                            interview_location=interview_loc,
                            position_names=position_names,
                            lead_time_minutes=lead_time_minutes
                        )
                    else:  # Fallback by name
                        celery.send_task(
                            'tasks.communication.send_interview_reminder_email_task',
                            # Ensure this name matches the task in communication.py
                            args=[
                                user.email,
                                user.username,  # Or a first_name field
                                candidate_name,
                                interview_dt_iso,
                                interview_loc,
                                position_names,
                                lead_time_minutes
                            ]
                        )
                    processed_interview_user_pairs.add(interview_user_key)
                    total_reminders_sent_this_run += 1
                except Exception as trigger_err:
                    logger.error(
                        f"[REMINDER TASK] Failed to trigger email task for user {user.id}, candidate {candidate.candidate_id}: {trigger_err}",
                        exc_info=True)

        logger.info(
            f"[REMINDER TASK END] Check complete. Total email reminders triggered in this run: {total_reminders_sent_this_run}.")
        return f"Checked reminders. Triggered emails: {total_reminders_sent_this_run}."

    except Exception as e:
        db.session.rollback()  # Rollback in case of any db error during query
        logger.error(f"[REMINDER TASK FAIL] Unexpected error in check_upcoming_interviews: {e}", exc_info=True)
        # Consider re-raising or specific retry logic if needed
        return "Reminder check failed unexpectedly."