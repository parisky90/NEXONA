# backend/app/tasks/reminders.py
from app import celery, db
from app.models import User, Candidate, CompanySettings, Interview, \
    InterviewStatus  # Πρόσθεσα Interview, InterviewStatus
from datetime import datetime, timedelta, timezone as dt_timezone
import logging
from flask import current_app  # Για πρόσβαση στο config
from zoneinfo import ZoneInfo  # Για timezones

logger = logging.getLogger(__name__)


# Δεν χρειάζεται το TASK_TRIGGER_METHOD, θα καλούμε πάντα το task με το όνομά του
# αν δεν το κάνουμε import απευθείας (πράγμα που αποφεύγουμε για tasks που καλούν άλλα tasks)

# Αφαίρεση του name=... από το decorator
@celery.task(bind=True, max_retries=3, default_retry_delay=300)  # Πρόσθεσα bind=True και retry logic
def check_upcoming_interviews(self):  # Πρόσθεσα self
    """
    Scheduled task to find upcoming interviews and trigger notifications
    based on individual user preferences and company-level settings.
    """
    logger.info("[REMINDER TASK START] Checking for upcoming interviews...")
    try:
        now_utc = datetime.now(dt_timezone.utc)
        logger.debug(f"[REMINDER TASK] Current UTC time: {now_utc.isoformat()}")

        users_wanting_reminders = User.query.filter_by(
            enable_email_interview_reminders=True,
            is_active=True
        ).all()

        if not users_wanting_reminders:
            logger.info("[REMINDER TASK] No active users have email interview reminders enabled. Exiting.")
            return "No users opted-in for reminders or active."

        logger.info(f"[REMINDER TASK] Found {len(users_wanting_reminders)} user(s) with email reminders enabled.")
        all_company_settings = {cs.company_id: cs for cs in CompanySettings.query.all()}
        total_reminders_sent_this_run = 0

        # Νέα λογική: Βρες τις συνεντεύξεις που πλησιάζουν
        # και μετά βρες τους σχετικούς χρήστες (recruiters)

        # Θέλουμε συνεντεύξεις που είναι SCHEDULED
        upcoming_interviews_query = Interview.query.filter(
            Interview.status == InterviewStatus.SCHEDULED,
            Interview.scheduled_start_time > now_utc  # Μόνο μελλοντικές
        )

        for interview_to_check in upcoming_interviews_query.all():
            if not interview_to_check.recruiter or not interview_to_check.recruiter.is_active or \
                    not interview_to_check.recruiter.enable_email_interview_reminders or not interview_to_check.recruiter.email:
                logger.debug(
                    f"Interview {interview_to_check.id}: Recruiter inactive, has no email, or reminders disabled. Skipping.")
                continue

            recruiter = interview_to_check.recruiter
            company_setting = all_company_settings.get(recruiter.company_id)
            if recruiter.company_id and not (company_setting and company_setting.enable_reminders_feature_for_company):
                logger.info(
                    f"Reminder feature disabled at company level (ID: {recruiter.company_id}) for recruiter {recruiter.id} of interview {interview_to_check.id}. Skipping.")
                continue

            lead_time_minutes = recruiter.interview_reminder_lead_time_minutes
            # Χρησιμοποίησε τις τιμές από το Config για τα όρια
            min_lead = current_app.config.get('MIN_INTERVIEW_REMINDER_LEAD_TIME', 5)
            max_lead = current_app.config.get('MAX_INTERVIEW_REMINDER_LEAD_TIME', 2880)

            if not (isinstance(lead_time_minutes, int) and min_lead <= lead_time_minutes <= max_lead):
                logger.warning(
                    f"Recruiter {recruiter.id} for interview {interview_to_check.id} has invalid lead time ({lead_time_minutes} mins). Skipping.")
                continue

            reminder_trigger_time = interview_to_check.scheduled_start_time - timedelta(minutes=lead_time_minutes)

            # Έλεγχος αν είμαστε κοντά στην ώρα αποστολής του reminder
            # (π.χ., μέσα σε ένα παράθυρο 5 λεπτών πριν την ώρα του reminder)
            # για να μην στέλνουμε συνέχεια αν το task τρέχει συχνά.
            # Αυτό απαιτεί να ξέρουμε πότε εστάλη το τελευταίο reminder ή να έχουμε πιο έξυπνη λογική.
            # Για απλότητα τώρα: αν η τρέχουσα ώρα είναι ΠΡΙΝ την ώρα του reminder αλλά ΜΕΤΑ την ώρα του reminder μείον τη συχνότητα του beat, στείλε.
            # Αυτό θέλει προσοχή για να μην στέλνονται διπλά.
            # Μια πιο απλή προσέγγιση: αν reminder_trigger_time <= now_utc < reminder_trigger_time + (διάρκεια beat scheduler)
            # Για την ώρα, θα ελέγξουμε αν η ώρα του reminder είναι στο παρελθόν αλλά η συνέντευξη στο μέλλον.

            # Αν η ώρα που *θα έπρεπε* να σταλεί το reminder έχει περάσει,
            # αλλά δεν έχει περάσει η ώρα της συνέντευξης + ένα μικρό περιθώριο (π.χ. 15 λεπτά)
            # για να μην στέλνουμε reminder για συνέντευξη που μόλις έγινε.
            if reminder_trigger_time <= now_utc and now_utc < interview_to_check.scheduled_start_time - timedelta(
                    minutes=15):
                # Έλεγχος αν έχουμε ήδη στείλει reminder για αυτή τη συνέντευξη (πιο σύνθετο, χρειάζεται tracking)
                # Για την ώρα, υποθέτουμε ότι δεν έχουμε στείλει.

                candidate_name = interview_to_check.candidate.get_full_name() if interview_to_check.candidate else "N/A"
                position_name = interview_to_check.position.position_name if interview_to_check.position else "N/A"

                try:
                    local_tz_str = current_app.config.get('LOCAL_TIMEZONE', 'UTC')
                    local_tz = ZoneInfo(local_tz_str)
                    interview_display_time = interview_to_check.scheduled_start_time.astimezone(local_tz).strftime(
                        "%A, %d %B %Y at %H:%M (%Z)")
                except Exception:
                    interview_display_time = interview_to_check.scheduled_start_time.strftime("%Y-%m-%d %H:%M UTC")

                logger.info(f"[REMINDER TASK] Triggering reminder for Recruiter ID: {recruiter.id} ({recruiter.email}) "
                            f"about Interview ID: {interview_to_check.id} with Candidate: {candidate_name} "
                            f"Scheduled Time: {interview_display_time} "
                            f"Position: {position_name}")
                try:
                    # Το όνομα του task όπως θα το ανακαλύψει η Celery
                    task_name_to_call = 'app.tasks.communication.send_interview_reminder_email_task'
                    celery.send_task(
                        task_name_to_call,
                        args=[
                            recruiter.email,
                            recruiter.username,  # Ή first_name
                            candidate_name,
                            interview_to_check.scheduled_start_time.isoformat(),  # Στείλε πάντα UTC ISO
                            interview_to_check.location or "Not specified",
                            position_name,
                            lead_time_minutes,
                            str(interview_to_check.id)  # Πρόσθεσε το interview_id για logging/tracking στο email task
                        ]
                    )
                    total_reminders_sent_this_run += 1
                    # Εδώ θα χρειαζόταν λογική για να μην ξανασταλεί reminder για την ίδια συνέντευξη
                    # π.χ., ενημέρωση ενός πεδίου last_reminder_sent_at στο Interview model.
                except Exception as trigger_err:
                    logger.error(
                        f"[REMINDER TASK] Failed to trigger email task for recruiter {recruiter.id}, interview {interview_to_check.id}: {trigger_err}",
                        exc_info=True)

        logger.info(
            f"[REMINDER TASK END] Check complete. Total email reminders triggered in this run: {total_reminders_sent_this_run}.")
        return f"Checked reminders. Triggered emails: {total_reminders_sent_this_run}."

    except Exception as e:
        # db.session.rollback() # Δεν κάνουμε αλλαγές στη βάση εδώ, οπότε δεν χρειάζεται rollback
        logger.error(f"[REMINDER TASK FAIL] Unexpected error in check_upcoming_interviews: {e}", exc_info=True)
        return "Reminder check failed unexpectedly."