# backend/app/api/routes.py

from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
import uuid
from datetime import datetime, timezone
from dateutil import parser as dateutil_parser  # For flexible date parsing

# Flask-Login Imports
from flask_login import login_user, logout_user, current_user, login_required

# Database and Models
from app import db, celery
from app.models import User, Candidate, Position
from sqlalchemy.orm.attributes import flag_modified  # Import flag_modified
from sqlalchemy import func, case, or_  # Import 'or_'

# Services
from app.services import s3_service

# import json # Not strictly needed here if not using json.loads/dumps

api_bp = Blueprint('api', __name__, url_prefix='/api/v1')

ALLOWED_EXTENSIONS = {'pdf', 'docx'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# --- Authentication Routes ---

@api_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({"error": "Username and password required"}), 400
    username = data.get('username');
    password = data.get('password');
    remember = data.get('remember', False)
    user = User.query.filter((User.username == username) | (User.email == username)).first()
    if user and user.check_password(password):
        login_user(user, remember=remember);
        current_app.logger.info(f"User {user.username} logged in.");
        user_data = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "enable_interview_reminders": user.enable_interview_reminders,
            "reminder_lead_time_minutes": user.reminder_lead_time_minutes,
            "email_interview_reminders": user.email_interview_reminders,
        }
        return jsonify({"message": "Login successful", "user": user_data}), 200
    else:
        current_app.logger.warning(f"Failed login attempt for: {username}")
        return jsonify({"error": "Invalid username or password"}), 401


@api_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    user_id = current_user.id;
    username = current_user.username;
    logout_user()
    current_app.logger.info(f"User {username} (ID: {user_id}) logged out.");
    return jsonify({"message": "Logout successful"}), 200


@api_bp.route('/session', methods=['GET'])
def check_session():
    if current_user.is_authenticated:
        user_data = {
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "enable_interview_reminders": current_user.enable_interview_reminders,
            "reminder_lead_time_minutes": current_user.reminder_lead_time_minutes,
            "email_interview_reminders": current_user.email_interview_reminders,
        }
        return jsonify({"authenticated": True, "user": user_data}), 200
    else:
        return jsonify({"authenticated": False}), 200


# --- Upload Endpoint ---
@api_bp.route('/upload', methods=['POST'])
@login_required
def upload_cv():
    current_app.logger.info(f"--- Upload Request Received by User ID: {current_user.id} ({current_user.username}) ---")
    if 'cv_file' not in request.files:
        current_app.logger.warning(f"Upload failed user {current_user.id}: 'cv_file' missing.")
        return jsonify({"error": "No file part named 'cv_file'"}), 400
    file = request.files['cv_file'];
    position_name = request.form.get('position', None)
    if file.filename == '':
        current_app.logger.warning(f"Upload failed user {current_user.id}: No file selected.")
        return jsonify({"error": "No selected file"}), 400
    if not allowed_file(file.filename):
        current_app.logger.warning(f"Upload failed user {current_user.id}: Invalid file type '{file.filename}'.")
        return jsonify({"error": "Invalid file type. Allowed: pdf, docx"}), 400

    uploaded_key = None
    try:
        file_ext = file.filename.rsplit('.', 1)[1].lower();
        original_filename = secure_filename(file.filename)
        s3_key = f"cvs/{uuid.uuid4()}.{file_ext}";
        file.seek(0);
        uploaded_key = s3_service.upload_file(file, s3_key)
        if not uploaded_key: raise Exception("S3 upload service indicated failure.")
        current_app.logger.info(f"S3 Upload OK: {uploaded_key} by User {current_user.id}")

        # DB Block
        new_candidate = Candidate(
            cv_original_filename=original_filename,
            cv_storage_path=uploaded_key,
            current_status='Processing',
            confirmation_uuid=str(uuid.uuid4())  # Generate UUID on creation
        )
        if position_name and position_name.strip():
            pos_name_cleaned = position_name.strip();
            position = Position.query.filter(func.lower(Position.position_name) == func.lower(pos_name_cleaned)).first()
            if not position:
                position = Position(position_name=pos_name_cleaned);
                db.session.add(position);
                db.session.flush()
                current_app.logger.info(f"Created Position: {pos_name_cleaned} by user {current_user.id}")
            new_candidate.positions.append(position)
        db.session.add(new_candidate);
        db.session.commit();
        candidate_id = new_candidate.candidate_id
        current_app.logger.info(f"Candidate record created: {candidate_id} by user {current_user.id}")

        # Celery Task Trigger
        celery.send_task('tasks.parse_cv', args=[candidate_id, uploaded_key])
        current_app.logger.info(f"Sent parsing task for {candidate_id}.")
        return jsonify(new_candidate.to_dict()), 201

    except Exception as e:  # General Error (S3 or DB)
        db.session.rollback()  # Rollback in case of any error after potential DB interaction start
        current_app.logger.error(f"Overall Upload Error user {current_user.id}: {e}", exc_info=True)
        if uploaded_key:  # S3 Cleanup if file was uploaded but something else failed
            try:
                s3_service.delete_file(uploaded_key)
                current_app.logger.warning(f"S3 cleanup attempted for {uploaded_key} after error.")
            except Exception as s3_del_err:
                current_app.logger.error(f"S3 cleanup FAILED for {uploaded_key}: {s3_del_err}")
        return jsonify({"error": "Internal upload error."}), 500


# --- Dashboard Summary Endpoint ---
@api_bp.route('/dashboard/summary', methods=['GET'])
@login_required
def get_dashboard_summary():
    try:
        relevant_statuses = ['Processing', 'ParsingFailed', 'NeedsReview', 'New', 'Accepted', 'Rejected', 'Interested',
                             'Interview', 'Declined', 'Evaluation', 'OfferMade', 'Hired']
        status_aggregations = [func.sum(case((Candidate.current_status == status, 1), else_=0)).label(status) for status
                               in relevant_statuses]
        q = db.session.query(func.count(Candidate.candidate_id).label("total_cvs"), *status_aggregations).first()
        summary = {"total_cvs": 0};
        [summary.update({s: 0}) for s in relevant_statuses];
        if q: summary.update({k: v or 0 for k, v in q._asdict().items()})
        return jsonify(summary), 200
    except Exception as e:
        current_app.logger.error(f"Summary Error: {e}", exc_info=True); return jsonify({"error": "Summary failed"}), 500


# --- Get Candidates by Status Endpoint ---
@api_bp.route('/candidates/<string:status>', methods=['GET'])
@login_required
def get_candidates_by_status(status):
    valid_statuses = ['Processing', 'ParsingFailed', 'NeedsReview', 'New', 'Accepted', 'Rejected', 'Interested',
                      'Interview', 'Declined', 'Evaluation', 'OfferMade', 'Hired']
    if status not in valid_statuses: return jsonify({"error": f"Invalid status: {status}"}), 400
    try:
        candidates_query = Candidate.query.filter_by(current_status=status).order_by(
            Candidate.submission_date.desc()).all()
        candidates_list = [cand.to_dict() for cand in candidates_query]
        return jsonify(candidates_list), 200
    except Exception as e:
        current_app.logger.error(f"Candidates list '{status}' Error: {e}"); return jsonify(
            {"error": "List failed"}), 500


# --- Candidate Detail Endpoint (GET, PUT, DELETE) ---
@api_bp.route('/candidate/<string:candidate_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def handle_candidate(candidate_id):
    candidate = Candidate.query.get_or_404(candidate_id, description=f"Candidate {candidate_id} not found.")
    user_id = current_user.id

    if request.method == 'GET':
        try:
            return jsonify(candidate.to_dict()), 200
        except Exception as e:
            current_app.logger.error(f"GET {candidate_id} Error: {e}"); return jsonify(
                {"error": "Details failed."}), 500

    elif request.method == 'PUT':
        current_app.logger.info(f"PUT {candidate_id} by User {user_id}")
        data = request.get_json()
        if not data: return jsonify({"error": "No input data"}), 400

        allowed_updates = [
            'first_name', 'last_name', 'age', 'phone_number', 'email',
            'current_status', 'notes', 'education', 'work_experience',
            'languages', 'seminars', 'interview_datetime', 'interview_location',
            'evaluation_rating',
            'offers',  # Επιτρέπουμε την ενημέρωση της λίστας προσφορών
            'candidate_confirmation_status'
        ]
        updated = False
        original_status = candidate.current_status
        notes_before_this_update_cycle = candidate.notes  # Πάρε τις σημειώσεις ΠΡΙΝ τις αλλαγές
        new_status = data.get('current_status', original_status)
        original_interview_time = candidate.interview_datetime
        interview_time_changed = False

        for key, value in data.items():
            if key in allowed_updates:
                if key == 'interview_datetime':
                    new_dt_value = None
                    if value:
                        try:
                            parsed_dt = dateutil_parser.isoparse(value); new_dt_value = parsed_dt.astimezone(
                                timezone.utc) if parsed_dt.tzinfo else parsed_dt.replace(tzinfo=timezone.utc)
                        except (ValueError, TypeError):
                            new_dt_value = original_interview_time
                    else:
                        new_dt_value = None
                    if new_dt_value != original_interview_time: setattr(candidate, key,
                                                                        new_dt_value); interview_time_changed = True; updated = True
                elif key == 'age':
                    current_val = getattr(candidate, key);
                    new_val = int(value) if str(value).strip().isdigit() else None
                    if current_val != new_val: setattr(candidate, key, new_val); updated = True
                elif key == 'offers':
                    if isinstance(value, list):
                        setattr(candidate, key, value); flag_modified(candidate, "offers"); updated = True
                    else:
                        current_app.logger.warning(
                            f"Invalid data type for 'offers' for candidate {candidate_id}. Expected list, got {type(value)}")
                else:
                    current_val = getattr(candidate, key)
                    if current_val != value: setattr(candidate, key, value); updated = True
            elif key == 'positions' and isinstance(value, list):
                current_pos = {p.position_name for p in candidate.positions};
                target_pos = set(p for p in value if p)
                positions_to_remove = [p for p in candidate.positions if p.position_name not in target_pos]
                if positions_to_remove:
                    for pos_obj in positions_to_remove: candidate.positions.remove(pos_obj); updated = True
                for pos_name in target_pos:
                    if pos_name not in current_pos:
                        position = Position.query.filter(
                            func.lower(Position.position_name) == func.lower(pos_name)).first()
                        if not position: position = Position(position_name=pos_name); db.session.add(position)
                        if position not in candidate.positions: candidate.positions.append(position)
                        updated = True

        if interview_time_changed and candidate.interview_datetime:
            candidate.candidate_confirmation_status = 'Pending';
            candidate.confirmation_uuid = str(uuid.uuid4());
            flag_modified(candidate, "candidate_confirmation_status");
            flag_modified(candidate, "confirmation_uuid");
            updated = True
        elif interview_time_changed and not candidate.interview_datetime:
            candidate.candidate_confirmation_status = None;
            flag_modified(candidate, "candidate_confirmation_status");
            updated = True

        if new_status != original_status:
            candidate.current_status = new_status;
            updated = True
            notes_for_history = notes_before_this_update_cycle
            history_entry = {"status": new_status, "previous_status": original_status,
                             "timestamp": datetime.now(timezone.utc).isoformat(), "updated_by": user_id,
                             "notes_at_this_stage": notes_for_history or ""}
            current_history = candidate.history if isinstance(candidate.history, list) else [];
            current_history.append(history_entry);
            candidate.history = current_history;
            flag_modified(candidate, "history")
            if original_status == 'Interview' and new_status not in ['Evaluation', 'Interview', 'OfferMade']:
                candidate.interview_datetime = None;
                candidate.interview_location = None;
                candidate.candidate_confirmation_status = None;
                flag_modified(candidate, "candidate_confirmation_status")

        if not updated: return jsonify({"message": "No changes detected"}), 304
        try:
            db.session.commit()
            current_app.logger.info(f"Candidate {candidate_id} updated successfully by user {user_id}.")
            if interview_time_changed and candidate.interview_datetime:
                celery.send_task('tasks.communication.send_interview_invitation_email',
                                 args=[str(candidate.candidate_id)])
            if new_status != original_status and new_status in ['Rejected', 'Declined']:
                celery.send_task('tasks.communication.send_rejection_email_task', args=[str(candidate.candidate_id)])
            return jsonify(candidate.to_dict()), 200
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating {candidate_id} by user {user_id}: {e}", exc_info=True)
            return jsonify({"error": "Failed to update candidate"}), 500

    elif request.method == 'DELETE':
        current_app.logger.info(f"DELETE {candidate_id} by User {user_id}")
        s3_key = candidate.cv_storage_path
        name = candidate.get_full_name()
        try:
            db.session.delete(candidate)
            db.session.commit()
            current_app.logger.info(f"DELETE {candidate_id} ({name}) DB OK by {user_id}.")
            if s3_key:
                try:
                    deleted = s3_service.delete_file(s3_key)
                    current_app.logger.info(f"S3 Delete {'OK' if deleted else 'Failed'} for key: {s3_key}")
                except Exception as s3_e:
                    current_app.logger.error(f"S3 Delete Error for key {s3_key}: {s3_e}")
            return jsonify({"message": f"Candidate {name} deleted successfully."}), 200
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"DELETE {candidate_id} DB Error: {e}", exc_info=True)
            return jsonify({"error": "Failed to delete candidate"}), 500


# --- CV URL Generation Endpoint ---
@api_bp.route('/candidate/<string:candidate_id>/cv_url', methods=['GET'])
@login_required
def get_candidate_cv_url(candidate_id):
    candidate = Candidate.query.get_or_404(candidate_id)
    if not candidate.cv_storage_path: return jsonify({"error": "No CV file associated"}), 404
    try:
        cv_url = s3_service.generate_presigned_url(candidate.cv_storage_path, expiration=900)
        if cv_url:
            return jsonify({"cv_url": cv_url}), 200
        else:
            current_app.logger.error(f"S3 service failed to generate URL for {candidate_id}"); return jsonify(
                {"error": "Could not generate CV URL."}), 500
    except Exception as e:
        current_app.logger.error(f"CV URL Error {candidate_id}: {e}", exc_info=True); return jsonify(
            {"error": "URL gen failed"}), 500


# --- Search Endpoint ---
@api_bp.route('/search', methods=['GET'])
@login_required
def search_candidates():
    query = request.args.get('q', '');
    status_filter = request.args.get('status', None)
    try:
        q = Candidate.query
        if query:
            search_term = f"%{query}%"
            search_filters = [
                Candidate.first_name.ilike(search_term),
                Candidate.last_name.ilike(search_term),
                Candidate.email.ilike(search_term),
                Candidate.phone_number.ilike(search_term),
                Position.position_name.ilike(search_term)
            ]
            q = q.outerjoin(Candidate.positions).filter(or_(*search_filters))
        if status_filter:
            valid = ['Processing', 'ParsingFailed', 'NeedsReview', 'New', 'Accepted', 'Rejected', 'Interested',
                     'Interview', 'Declined', 'Evaluation', 'OfferMade', 'Hired']
            if status_filter in valid:
                q = q.filter(Candidate.current_status == status_filter)
            else:
                current_app.logger.warning(f"Invalid status filter ignored: {status_filter}")
        candidates_query = q.distinct().order_by(Candidate.submission_date.desc()).all()
        return jsonify([cand.to_dict() for cand in candidates_query]), 200
    except Exception as e:
        current_app.logger.error(f"Search Error q='{query}' s='{status_filter}': {e}", exc_info=True); return jsonify(
            {"error": "Search failed"}), 500


# --- Settings Endpoint ---
@api_bp.route('/settings', methods=['GET', 'PUT'])
@login_required
def handle_settings():
    if request.method == 'GET':
        s = {"username": current_user.username, "email": current_user.email,
             "enable_interview_reminders": current_user.enable_interview_reminders,
             "reminder_lead_time_minutes": current_user.reminder_lead_time_minutes,
             "email_interview_reminders": current_user.email_interview_reminders, }
        return jsonify(s), 200
    elif request.method == 'PUT':
        data = request.get_json();
        if not data: return jsonify({"error": "No settings data"}), 400
        updated = False;
        allowed = {'enable_interview_reminders': bool, 'reminder_lead_time_minutes': int,
                   'email_interview_reminders': bool}
        for k, v in data.items():
            if k in allowed:
                try:
                    t = allowed[k];
                    casted = t(v)
                    if k == 'reminder_lead_time_minutes' and not (5 <= casted <= 1440): raise ValueError("Range error.")
                    if getattr(current_user, k) != casted: setattr(current_user, k, casted); updated = True
                except (ValueError, TypeError) as e:
                    current_app.logger.warning(f"Invalid value for setting '{k}': {v}. Error: {e}"); return jsonify(
                        {"error": f"Invalid value for setting '{k}'"}), 400
        if not updated: return jsonify({"message": "No changes detected"}), 304
        try:
            db.session.commit()
            s = {"enable_interview_reminders": current_user.enable_interview_reminders,
                 "reminder_lead_time_minutes": current_user.reminder_lead_time_minutes,
                 "email_interview_reminders": current_user.email_interview_reminders, }
            return jsonify({"message": "Settings updated", "settings": s}), 200
        except Exception as e:
            db.session.rollback(); current_app.logger.error(f"Settings update error {current_user.id}: {e}",
                                                            exc_info=True); return jsonify(
                {"error": "Save failed"}), 500


# --- Interview Confirmation/Declination Endpoints ---
@api_bp.route('/interviews/confirm/<string:confirmation_uuid>', methods=['GET'])
def confirm_interview(confirmation_uuid):
    try:
        candidate = Candidate.query.filter_by(confirmation_uuid=confirmation_uuid).first()
        if not candidate: return "<h1>Σφάλμα</h1><p>Ο σύνδεσμος επιβεβαίωσης δεν είναι έγκυρος ή έχει λήξει.</p>", 404
        if not candidate.interview_datetime: return "<h1>Σφάλμα</h1><p>Δεν υπάρχει προγραμματισμένη συνέντευξη για αυτόν τον σύνδεσμο.</p>", 400
        response_message, status_code = "", 200
        if candidate.candidate_confirmation_status == 'Confirmed':
            response_message = f"<h1>Ήδη Επιβεβαιωμένο</h1><p>Η παρουσία σας στη συνέντευξη στις {candidate.interview_datetime.strftime('%d/%m/%Y %H:%M')} έχει ήδη επιβεβαιωθεί.</p>"
        elif candidate.candidate_confirmation_status in ['Pending', 'Declined']:
            candidate.candidate_confirmation_status = 'Confirmed';
            db.session.commit()
            try:
                celery.send_task('tasks.communication.notify_recruiter_interview_confirmed',
                                 args=[str(candidate.candidate_id)])
            except Exception as celery_err:
                current_app.logger.error(f"Failed to send task: {celery_err}")
            response_message = f"<h1>Επιβεβαίωση Επιτυχής</h1><p>Ευχαριστούμε, {candidate.get_full_name()}! Η παρουσία σας στη συνέντευξη στις {candidate.interview_datetime.strftime('%d/%m/%Y %H:%M')} έχει επιβεβαιωθεί.</p>"
        else:
            response_message = "<h1>Σφάλμα</h1><p>Αυτή η ενέργεια δεν είναι δυνατή αυτή τη στιγμή.</p>"; status_code = 400
        return response_message, status_code
    except Exception as e:
        db.session.rollback(); current_app.logger.error(f"Error confirming interview: {e}",
                                                        exc_info=True); return "<h1>Σφάλμα Συστήματος</h1><p>Παρουσιάστηκε σφάλμα.</p>", 500


@api_bp.route('/interviews/decline/<string:confirmation_uuid>', methods=['GET'])
def decline_interview(confirmation_uuid):
    try:
        candidate = Candidate.query.filter_by(confirmation_uuid=confirmation_uuid).first()
        if not candidate: return "<h1>Σφάλμα</h1><p>Ο σύνδεσμος ακύρωσης/αλλαγής δεν είναι έγκυρος ή έχει λήξει.</p>", 404
        if not candidate.interview_datetime: return "<h1>Σφάλμα</h1><p>Δεν υπάρχει προγραμματισμένη συνέντευξη.</p>", 400
        response_message, status_code = "", 200
        if candidate.candidate_confirmation_status == 'Declined':
            response_message = f"<h1>Ήδη Δηλωμένο</h1><p>Έχετε ήδη δηλώσει αδυναμία για τη συνέντευξη στις {candidate.interview_datetime.strftime('%d/%m/%Y %H:%M')}.</p>"
        elif candidate.candidate_confirmation_status in ['Pending', 'Confirmed']:
            candidate.candidate_confirmation_status = 'Declined';
            db.session.commit()
            try:
                celery.send_task('tasks.communication.notify_recruiter_interview_declined',
                                 args=[str(candidate.candidate_id)])
            except Exception as celery_err:
                current_app.logger.error(f"Failed to send task: {celery_err}")
            response_message = f"<h1>Επιβεβαίωση Λήφθηκε</h1><p>Λάβαμε το αίτημά σας για τη συνέντευξη στις {candidate.interview_datetime.strftime('%d/%m/%Y %H:%M')}.</p>"
        else:
            response_message = "<h1>Σφάλμα</h1><p>Αυτή η ενέργεια δεν είναι δυνατή.</p>"; status_code = 400
        return response_message, status_code
    except Exception as e:
        db.session.rollback(); current_app.logger.error(f"Error declining interview: {e}",
                                                        exc_info=True); return "<h1>Σφάλμα Συστήματος</h1><p>Παρουσιάστηκε σφάλμα.</p>", 500