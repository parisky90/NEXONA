from app import celery, db, mail, create_app  # Προστέθηκε create_app για πιθανή χρήση app_context
from app.models import Interview, Candidate, User, Position, Company  # Προστέθηκε Company
from flask_mail import Message
from flask import current_app, url_for, render_template  # Προστέθηκε render_template για μελλοντική χρήση
from datetime import datetime
from zoneinfo import ZoneInfo
import logging

logger = logging.getLogger(__name__)


# Παράδειγμα υπάρχοντος task (αν υπάρχει, παραμένει)
# @celery.task(name='app.tasks.communication.send_example_email')
# def send_example_email(recipient, subject, body):
#     app = create_app(os.getenv('FLASK_CONFIG') or 'default') # Δημιουργία app instance
#     with app.app_context(): # Δημιουργία application context
#         msg = Message(subject, sender=current_app.config['MAIL_DEFAULT_SENDER'], recipients=[recipient])
#         msg.body = body
#         try:
#             mail.send(msg)
#             logger.info(f"Example email sent to {recipient}")
#             return f"Email sent to {recipient}"
#         except Exception as e:
#             logger.error(f"Failed to send example email to {recipient}: {e}", exc_info=True)
#             # Εδώ μπορείς να προσθέσεις self.retry(exc=e) αν το task είναι bind=True
#             raise


@celery.task(bind=True, name='app.tasks.communication.send_interview_proposal_email_task', max_retries=3,
             default_retry_delay=300)  # Προσθήκη retries
def send_interview_proposal_email_task(self, interview_id):
    """
    Sends an interview proposal email to the candidate.
    """
    # Χρησιμοποιούμε το app context που παρέχεται από την Celery task (μέσω της ρύθμισης στο app/__init__.py)
    # ή μπορούμε να δημιουργήσουμε ένα ρητά αν χρειαστεί για κάποιο λόγο.
    # Η Flask-SQLAlchemy και η Flask-Mail συνήθως λειτουργούν σωστά μέσα σε tasks
    # που έχουν το app context pushed από την Celery.

    # Για να είμαστε απόλυτα σίγουροι ότι έχουμε το σωστό current_app context, ειδικά για το url_for
    # που εξαρτάται από το request context (αν και το _external=True μπορεί να το παρακάμψει)
    # και για τις ρυθμίσεις της εφαρμογής:
    app = self.app if hasattr(self, 'app') else current_app  # Προτιμάμε το self.app αν το task είναι bound και έχει app
    if not app:  # Fallback αν το self.app δεν είναι διαθέσιμο
        from app import create_app as create_flask_app  # Μετονομασία για αποφυγή σύγκρουσης
        import os
        app = create_flask_app(os.getenv('FLASK_CONFIG') or 'development')  # ή 'default'

    with app.app_context():  # Εξασφάλιση του app context
        interview = db.session.get(Interview, interview_id)
        if not interview:
            logger.error(f"send_interview_proposal_email_task: Interview with ID {interview_id} not found.")
            return f"Error: Interview ID {interview_id} not found."

        candidate = interview.candidate
        recruiter = interview.recruiter  # Αυτός είναι ο User object του recruiter
        position = interview.position

        if not candidate or not candidate.email:
            logger.error(
                f"send_interview_proposal_email_task: Candidate or candidate email missing for interview ID {interview_id}.")
            return f"Error: Candidate or email missing for interview ID {interview_id}."

        if not recruiter:
            logger.error(f"send_interview_proposal_email_task: Recruiter not found for interview ID {interview_id}.")
            # Ίσως θέλουμε να στείλουμε το email ακόμα κι αν ο recruiter έχει διαγραφεί; Ή να αποτύχει το task;
            # Για τώρα, ας υποθέσουμε ότι χρειαζόμαστε τον recruiter για το όνομα της εταιρείας.
            return f"Error: Recruiter not found for interview ID {interview_id}."

        company = recruiter.company  # Παίρνουμε την εταιρεία μέσω του recruiter
        if not company:
            logger.warning(
                f"send_interview_proposal_email_task: Company not found for recruiter {recruiter.id} of interview ID {interview_id}. Using generic company name.")
            company_name_for_email = "την εταιρεία μας"
        else:
            company_name_for_email = company.name

        # Timezone για εμφάνιση (Ώρα Ελλάδος)
        greece_tz = ZoneInfo("Europe/Athens")

        proposed_slots_for_email = []
        slot_options = [
            (interview.proposed_slot_1_start, interview.proposed_slot_1_end, 1),
            (interview.proposed_slot_2_start, interview.proposed_slot_2_end, 2),
            (interview.proposed_slot_3_start, interview.proposed_slot_3_end, 3),
        ]

        for start_utc, end_utc, slot_num in slot_options:
            if start_utc and end_utc:
                start_gr = start_utc.astimezone(greece_tz)
                # end_gr = end_utc.astimezone(greece_tz) # Δεν χρησιμοποιείται στο display string
                proposed_slots_for_email.append({
                    "id": slot_num,
                    "start_display": start_gr.strftime("%A, %d %B %Y στις %H:%M (%Z)"),
                    "confirmation_url": url_for('api.confirm_interview_slot',  # Θα οριστεί στο routes.py
                                                token=interview.confirmation_token,
                                                slot_choice=slot_num,
                                                _external=True)
                })

        if not proposed_slots_for_email:
            logger.error(
                f"send_interview_proposal_email_task: No proposed slots found for interview ID {interview_id}.")
            return f"Error: No proposed slots for interview ID {interview_id}."

        reject_all_url = url_for('api.reject_interview_slots',  # Θα οριστεί στο routes.py
                                 token=interview.confirmation_token,
                                 _external=True)
        cancel_by_candidate_url = url_for('api.cancel_interview_by_candidate',  # Θα οριστεί στο routes.py
                                          token=interview.confirmation_token,
                                          _external=True)

        subject = f"Πρόσκληση για Συνέντευξη"
        if position:
            subject += f" για τη θέση {position.position_name}"
        subject += f" στην εταιρεία {company_name_for_email}"

        # Χρήση render_template για το email body (καλύτερη πρακτική)
        # Δημιούργησε αρχεία:
        # templates/email/interview_proposal.html
        # templates/email/interview_proposal.txt
        # Αν δεν υπάρχουν templates, θα χρησιμοποιηθούν τα παρακάτω f-strings.

        email_context = {
            'candidate_name': candidate.get_full_name(),
            'position_name_display': f"για τη θέση «{position.position_name}»" if position else "για μια ευκαιρία συνεργασίας",
            'company_name': company_name_for_email,
            'proposed_slots': proposed_slots_for_email,
            'interview_type': interview.interview_type,
            'location': interview.location,
            'notes_for_candidate': interview.notes_for_candidate,
            'reject_all_url': reject_all_url,
            'cancel_by_candidate_url': cancel_by_candidate_url
        }

        try:
            html_body = render_template('email/interview_proposal.html', **email_context)
            text_body = render_template('email/interview_proposal.txt', **email_context)
        except Exception as template_e:  # Αν τα templates δεν βρεθούν ή έχουν σφάλμα
            logger.warning(f"Email template rendering failed: {template_e}. Falling back to f-string emails.")
            # Fallback σε f-strings (όπως είχαμε πριν)
            html_body = f"""
            <p>Αγαπητέ/ή {email_context['candidate_name']},</p>
            <p>Σας ευχαριστούμε για το ενδιαφέρον σας {email_context['position_name_display']} στην εταιρεία {email_context['company_name']}.</p>
            <p>Θα θέλαμε να σας προσκαλέσουμε σε μια συνέντευξη. Παρακάτω θα βρείτε μερικές προτεινόμενες ημερομηνίες και ώρες (Ώρα Ελλάδος):</p>
            """
            if email_context['proposed_slots']:
                html_body += "<ul>"
                for slot in email_context['proposed_slots']:
                    html_body += f"<li>{slot['start_display']} - <a href='{slot['confirmation_url']}'>Επιλογή αυτού του slot</a></li>"
                html_body += "</ul>"
            else:  # Αυτό δεν θα έπρεπε να συμβεί αν έχουμε τον έλεγχο παραπάνω
                html_body += "<p>Δεν έχουν οριστεί προτεινόμενα slots αυτή τη στιγμή. Θα επικοινωνήσουμε σύντομα μαζί σας.</p>"

            html_body += f"<p><strong>Τύπος Συνέντευξης:</strong> {email_context['interview_type']}</p>"
            html_body += f"<p><strong>Τοποθεσία/Link:</strong> {email_context['location']}</p>"
            if email_context['notes_for_candidate']:
                html_body += f"<p><strong>Σημειώσεις:</strong><br/>{email_context['notes_for_candidate'].replace(chr(10), '<br/>')}</p>"

            html_body += f"""
            <p>Παρακαλούμε επιλέξτε το slot που σας εξυπηρετεί καλύτερα κάνοντας κλικ στον αντίστοιχο σύνδεσμο.</p>
            <p>Εάν κανένα από τα παραπάνω slots δεν σας βολεύει, παρακαλούμε ενημερώστε μας πατώντας εδώ: <a href='{email_context['reject_all_url']}'>Κανένα slot δεν με βολεύει</a>.</p>
            <p>Εάν επιθυμείτε να ακυρώσετε αυτή την πρόσκληση, μπορείτε να το κάνετε εδώ: <a href='{email_context['cancel_by_candidate_url']}'>Ακύρωση πρόσκλησης</a>.</p>
            <p>Ανυπομονούμε να σας μιλήσουμε!</p>
            <p>Με εκτίμηση,<br/>Η ομάδα προσλήψεων της {email_context['company_name']}</p>
            """
            # Fallback για text body
            text_body = f"Αγαπητέ/ή {email_context['candidate_name']}...\n (Full text body omitted for brevity, similar to HTML fallback)"

        sender_email = app.config.get('MAIL_DEFAULT_SENDER', 'noreply@example.com')
        # Εδώ θα μπορούσαμε να έχουμε μια πιο έξυπνη λογική για τον sender, π.χ., από τις ρυθμίσεις της εταιρείας.

        msg = Message(subject,
                      sender=sender_email,
                      recipients=[candidate.email])
        msg.body = text_body
        msg.html = html_body

        try:
            mail.send(msg)  # Το mail instance είναι ήδη αρχικοποιημένο με το app
            logger.info(f"Interview proposal email sent to {candidate.email} for interview ID {interview_id}.")

            # Ενημέρωση ιστορικού υποψηφίου (προαιρετικά, αν θέλουμε να καταγράφεται η αποστολή email)
            # Καλύτερα να γίνεται στο ίδιο session με τη δημιουργία του interview αν είναι κρίσιμο.
            # Εδώ είμαστε σε ξεχωριστό task, οπότε χρειαζόμαστε νέο session/commit.
            # candidate.add_history_event(...) # Αν το κάνουμε εδώ, θέλει db.session.commit()

            # Ας ενημερώσουμε το status του interview ότι το email στάλθηκε (αν έχουμε τέτοιο status)
            # interview.email_sent_at = datetime.now(ZoneInfo("UTC"))
            # db.session.commit()

            return f"Email sent successfully for interview ID {interview_id}."

        except Exception as e:
            logger.error(f"Failed to send interview proposal email for interview ID {interview_id}: {e}", exc_info=True)
            try:
                # Προσπάθεια retry για το task
                raise self.retry(exc=e, countdown=int(self.default_retry_delay * (self.request.retries + 1)))
            except self.MaxRetriesExceededError:
                logger.error(f"Max retries exceeded for sending email for interview ID {interview_id}.")
                # Εδώ θα μπορούσαμε να στείλουμε μια ειδοποίηση στον admin ή κάτι παρόμοιο.
                return f"Failed to send email for interview ID {interview_id} after max retries."
            except Exception as retry_exc:  # Άλλο σφάλμα κατά το retry
                logger.error(f"Error during retry mechanism for interview ID {interview_id}: {retry_exc}")
                return f"Failed to send email for interview ID {interview_id}, retry mechanism failed."