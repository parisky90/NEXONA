# backend/app/tasks/communication.py
from app import celery, db, mail # Δεν χρειάζεται το create_app εδώ πλέον
from app.models import Interview, Candidate, User, Position, Company
from flask_mail import Message
from flask import current_app, url_for, render_template # current_app για πρόσβαση στο config
from zoneinfo import ZoneInfo
import logging
# import os # Δεν χρειάζεται πλέον για FLASK_CONFIG

logger = logging.getLogger(__name__)


# Αφαίρεση του name=... από το decorator. Η Celery θα το ονομάσει app.tasks.communication.send_interview_proposal_email_task
@celery.task(bind=True, max_retries=3, default_retry_delay=300)
def send_interview_proposal_email_task(self, interview_id_str): # Το όρισμα είναι string από το send_task
    """
    Sends an interview proposal email to the candidate.
    Το app_context παρέχεται από το ContextTask.
    """
    logger.info(f"Executing send_interview_proposal_email_task for interview ID: {interview_id_str}")
    try:
        interview_id = int(interview_id_str) # Μετατροπή σε int αν το ID είναι integer
    except ValueError:
        logger.error(f"Invalid interview_id format: {interview_id_str}")
        return f"Error: Invalid interview_id format {interview_id_str}"

    # Το current_app είναι διαθέσιμο εδώ λόγω του ContextTask
    interview = db.session.get(Interview, interview_id) # Χρήση db.session.get
    if not interview:
        logger.error(f"send_interview_proposal_email_task: Interview with ID {interview_id} not found.")
        return f"Error: Interview ID {interview_id} not found."

    candidate = interview.candidate
    recruiter = interview.recruiter
    position = interview.position # Μπορεί να είναι None

    if not candidate or not candidate.email:
        logger.error(
            f"send_interview_proposal_email_task: Candidate or candidate email missing for interview ID {interview_id}.")
        return f"Error: Candidate or email missing for interview ID {interview_id}."
    if not recruiter: # Το recruiter_id μπορεί να είναι nullable
        logger.warning(f"send_interview_proposal_email_task: Recruiter not found for interview ID {interview_id}. Using default company name.")
        # Αν δεν υπάρχει recruiter, ίσως να θέλεις να πάρεις το company από το candidate ή το interview.company
        company_name_for_email = interview.company.name if interview.company else current_app.config.get('APP_NAME', "Our Company")
        recruiter_name_for_email = "Recruitment Team"
    else:
        company_name_for_email = recruiter.company.name if recruiter.company else current_app.config.get('APP_NAME', "Our Company")
        recruiter_name_for_email = recruiter.username


    try:
        # Χρησιμοποίησε το LOCAL_TIMEZONE από το config
        local_tz_str = current_app.config.get('LOCAL_TIMEZONE', 'UTC')
        local_tz = ZoneInfo(local_tz_str)
    except Exception as tz_err:
        logger.error(f"Could not load {local_tz_str} timezone in Celery task: {tz_err}")
        local_tz = ZoneInfo("UTC") # Fallback σε UTC
        logger.warning(f"Falling back to UTC for email display times for interview {interview_id}.")

    proposed_slots_for_email = []
    # Η λογική σου για τα slot_options με proposed_slot_1_start κλπ. ήταν από παλιότερη έκδοση.
    # Τώρα τα slots είναι στο interview.slots relationship.
    if interview.slots:
        for slot_obj in interview.slots.all(): # .all() αν είναι lazy='dynamic'
            if slot_obj.start_time and slot_obj.end_time:
                start_local = slot_obj.start_time.astimezone(local_tz)
                # Για το confirmation_url, το slot_choice τώρα είναι το slot_obj.id
                confirmation_url = url_for('api.confirm_interview_slot',
                                           token=interview.confirmation_token,
                                           slot_id_choice=slot_obj.id, # <--- ΑΛΛΑΓΗ: slot_id_choice αντί για slot_choice
                                           _external=True)
                proposed_slots_for_email.append({
                    "id": slot_obj.id, # Το πραγματικό ID του slot
                    "start_display": start_local.strftime("%A, %d %B %Y at %H:%M (%Z)"),
                    "confirmation_url": confirmation_url
                })

    if not proposed_slots_for_email:
        logger.error(
            f"send_interview_proposal_email_task: No valid proposed slots found for interview ID {interview_id}.")
        # Μην επιστρέφεις error εδώ, απλά στείλε ένα email που λέει ότι θα επικοινωνήσουν
        # ή χειρίσου το ανάλογα. Για την ώρα, θα στείλουμε ένα τροποποιημένο email.
        pass # Η λογική του fallback email παρακάτω θα το χειριστεί.


    reject_all_url = url_for('api.reject_interview_slots', token=interview.confirmation_token, _external=True)
    # Το cancel_by_candidate_url για την αρχική πρόταση δεν έχει νόημα, το confirmation_token είναι για επιλογή/απόρριψη.
    # Το cancellation_token δημιουργείται ΑΦΟΥ επιβεβαιωθεί ένα slot.
    # Θα μπορούσες να το αφαιρέσεις από το αρχικό proposal email.
    # cancel_by_candidate_url = url_for('api.cancel_interview_by_candidate', token=interview.confirmation_token, _external=True) # Πιθανώς λάθος token εδώ

    subject = f"Interview Invitation"
    if position: subject += f" for {position.position_name}"
    subject += f" at {company_name_for_email}"

    email_context = {
        'candidate_name': candidate.get_full_name(),
        'position_name_display': f"for the position «{position.position_name}»" if position else "for a collaboration opportunity",
        'company_name': company_name_for_email,
        'proposed_slots': proposed_slots_for_email, # Τώρα περιέχει τα σωστά δεδομένα
        'interview_type': interview.interview_type or "Not specified",
        'location': interview.location or "To be confirmed",
        'notes_for_candidate': interview.notes_for_candidate,
        'reject_all_url': reject_all_url,
        # 'cancel_by_candidate_url': cancel_by_candidate_url, # Αφαίρεσέ το ή διόρθωσε το token
        'recruiter_name': recruiter_name_for_email,
        'app_home_url': current_app.config.get('FRONTEND_URL', 'http://localhost:5173')
    }

    html_body = ""
    text_body = ""
    try:
        html_body = render_template('email/interview_proposal.html', **email_context)
        text_body = render_template('email/interview_proposal.txt', **email_context)
    except Exception as template_e:
        logger.warning(
            f"Email template rendering failed for interview_proposal (Interview ID: {interview_id}): {template_e}. Falling back to basic f-string email.")
        # ... (ο fallback κώδικας σου παραμένει ίδιος, αλλά βεβαιώσου ότι χρησιμοποιεί το διορθωμένο proposed_slots_for_email) ...
        html_body = f"<p>Dear {email_context['candidate_name']},</p>" # ... (κλπ)
        text_body = f"Dear {email_context['candidate_name']},\n\n" # ... (κλπ)

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
            # Χρησιμοποίησε το self.request.retries αντί για self.default_retry_delay * (self.request.retries + 1)
            # το default_retry_delay είναι ήδη η βάση.
            raise self.retry(exc=e_mail, countdown=int(self.default_retry_delay * (2 ** self.request.retries))) # Εκθετική αύξηση
        except self.MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for sending email for interview ID {interview_id}.")
            # Σημείωσε το πρόβλημα κάπου, π.χ. στο Interview object ή σε ένα admin log
            interview.internal_notes = (interview.internal_notes or "") + \
                                       f"\n[Email Send Failed] Max retries for proposal email to candidate. Error: {str(e_mail)[:100]}"
            flag_modified(interview, "internal_notes")
            db.session.commit()
            return f"Failed to send email for interview ID {interview_id} after max retries."
        except Exception as retry_exc: # Κάποιο άλλο σφάλμα κατά το retry
            logger.error(f"Error during retry mechanism for interview ID {interview_id}: {retry_exc}")
            return f"Failed to send email for interview ID {interview_id}, retry mechanism failed."

# --- Πρόσθεσε και τα άλλα tasks εδώ με τον ίδιο τρόπο (αφαίρεση του name=...) ---

@celery.task(bind=True, max_retries=3, default_retry_delay=180)
def send_interview_confirmation_to_candidate_task(self, interview_id_str, selected_slot_id_str):
    logger.info(f"Executing send_interview_confirmation_to_candidate_task for interview ID: {interview_id_str}, slot ID: {selected_slot_id_str}")
    # ... (Υλοποίησε τη λογική σου εδώ, παρόμοια με το παραπάνω task) ...
    # Βρες το interview, candidate, selected_slot.
    # Φτιάξε το email_context.
    # Render τα templates.
    # Στείλε το email.
    # Κάνε logging.
    # Handle errors και retries.
    pass

@celery.task(bind=True, max_retries=3, default_retry_delay=180)
def send_interview_confirmation_to_recruiter_task(self, interview_id_str, selected_slot_id_str):
    logger.info(f"Executing send_interview_confirmation_to_recruiter_task for interview ID: {interview_id_str}, slot ID: {selected_slot_id_str}")
    # ... (Υλοποίησε τη λογική σου εδώ) ...
    pass

@celery.task(bind=True, max_retries=3, default_retry_delay=180)
def send_interview_rejection_to_recruiter_task(self, interview_id_str):
    logger.info(f"Executing send_interview_rejection_to_recruiter_task for interview ID: {interview_id_str}")
    # ... (Υλοποίησε τη λογική σου εδώ) ...
    pass

@celery.task(bind=True, max_retries=3, default_retry_delay=180)
def send_interview_cancellation_to_recruiter_task(self, interview_id_str, reason=None, reschedule_preference=None):
    logger.info(f"Executing send_interview_cancellation_to_recruiter_task for interview ID: {interview_id_str}. Reason: {reason or 'N/A'}, Reschedule: {reschedule_preference or 'N/A'}")
    # ... (Υλοποίησε τη λογική σου εδώ) ...
    pass

# Αν έχεις και το send_interview_reminder_email_task εδώ:
@celery.task(bind=True, max_retries=3, default_retry_delay=60)
def send_interview_reminder_email_task(self, user_email, user_first_name, candidate_name, interview_datetime_iso, interview_location, position_names, lead_time_minutes):
    logger.info(f"Executing send_interview_reminder_email_task to {user_email} for candidate {candidate_name}")
    # ... (Υλοποίησε τη λογική σου εδώ) ...
    pass