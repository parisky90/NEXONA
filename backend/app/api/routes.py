# backend/app/api/routes.py

from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
import uuid
from datetime import datetime, timezone
from dateutil import parser as dateutil_parser

# Flask-Login Imports
from flask_login import login_user, logout_user, current_user, login_required

# Database and Models
from app import db, celery
from app.models import User, Candidate, Position
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import func, case, or_ # Import 'or_'

# Services
from app.services import s3_service
import json

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

    username = data.get('username')
    password = data.get('password')
    remember = data.get('remember', False)

    user = User.query.filter(
        (User.username == username) | (User.email == username)
    ).first()

    if user and user.check_password(password):
        login_user(user, remember=remember)
        current_app.logger.info(f"User {user.username} (ID: {user.id}) logged in successfully.")
        user_data = {"id": user.id, "username": user.username, "email": user.email}
        return jsonify({"message": "Login successful", "user": user_data}), 200
    else:
        current_app.logger.warning(f"Failed login attempt for username/email: {username}")
        return jsonify({"error": "Invalid username or password"}), 401

@api_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    user_id = current_user.id
    username = current_user.username
    logout_user()
    current_app.logger.info(f"User {username} (ID: {user_id}) logged out successfully.")
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

# --- Upload Endpoint (Requires Auth) ---
@api_bp.route('/upload', methods=['POST'])
@login_required
def upload_cv():
    current_app.logger.info(f"--- Upload Request Received by User ID: {current_user.id} ({current_user.username}) ---")
    # Optional Request Detail Logging (keep if useful)
    # try: ... log request details ...
    # except Exception as log_err: current_app.logger.error(...)

    if 'cv_file' not in request.files: # Check file part
        current_app.logger.warning(f"Upload failed for user {current_user.id}: 'cv_file' key missing.")
        return jsonify({"error": "No file part named 'cv_file'"}), 400

    file = request.files['cv_file']
    position_name = request.form.get('position', None)

    if file.filename == '': # Check filename
        current_app.logger.warning(f"Upload failed for user {current_user.id}: No file selected.")
        return jsonify({"error": "No selected file"}), 400

    if not allowed_file(file.filename): # Check extension
        current_app.logger.warning(f"Upload failed for user {current_user.id}: Invalid file type '{file.filename}'.")
        return jsonify({"error": "Invalid file type. Allowed: pdf, docx"}), 400

    uploaded_key = None # Defined here for use in error handling
    try:
        file_ext = file.filename.rsplit('.', 1)[1].lower()
        original_filename = secure_filename(file.filename)
        s3_key = f"cvs/{uuid.uuid4()}.{file_ext}"

        file.seek(0)
        uploaded_key = s3_service.upload_file(file, s3_key) # Assign here
        if not uploaded_key: raise Exception("S3 upload service indicated failure.")
        current_app.logger.info(f"File uploaded successfully to S3 by user {current_user.id} with key: {uploaded_key}")

        # DB Operations
        try:
            new_candidate = Candidate(
                cv_original_filename=original_filename,
                cv_storage_path=uploaded_key,
                current_status='Processing',
            )

            if position_name and position_name.strip():
                position_name_cleaned = position_name.strip()
                position = Position.query.filter(func.lower(Position.position_name) == func.lower(position_name_cleaned)).first()
                if not position:
                    position = Position(position_name=position_name_cleaned)
                    db.session.add(position)
                    db.session.flush()
                    current_app.logger.info(f"Created new Position: {position_name_cleaned} (ID: {position.position_id}) by user {current_user.id}")
                else:
                     current_app.logger.info(f"Found existing Position: {position.position_name} (ID: {position.position_id})")
                new_candidate.positions.append(position)

            db.session.add(new_candidate)
            db.session.commit()
            candidate_id = new_candidate.candidate_id
            current_app.logger.info(f"Candidate record created: {candidate_id} by user {current_user.id}")

        except Exception as db_err: # Catch DB errors specifically
            db.session.rollback()
            current_app.logger.error(f"DB Error creating candidate record by user {current_user.id}: {db_err}", exc_info=True)
            # Attempt S3 cleanup ONLY if upload succeeded before DB error
            if uploaded_key:
                current_app.logger.warning(f"Attempting to delete orphaned S3 file due to DB error: {uploaded_key}")
                try: s3_service.delete_file(uploaded_key)
                except Exception as s3_del_err: current_app.logger.error(f"Failed during S3 deletion for {uploaded_key}: {s3_del_err}")
            raise # Re-raise the DB error to be caught by the outer handler

        # Send Celery Task (only if DB commit was successful)
        try:
            celery.send_task('tasks.parse_cv', args=[candidate_id, uploaded_key])
            current_app.logger.info(f"Sent parsing task for candidate {candidate_id} (uploaded by user {current_user.id}).")
        except Exception as celery_err:
            current_app.logger.critical(f"CRITICAL: Failed to send Celery parsing task for candidate {candidate_id} (uploaded by user {current_user.id}): {celery_err}", exc_info=True)
            # Optionally update status here to ParsingFailed? Requires another commit.
            # candidate = Candidate.query.get(candidate_id)
            # if candidate:
            #     candidate.current_status = 'ParsingFailed'
            #     candidate.notes = (candidate.notes or '') + f"\n[SYSTEM] Failed to queue parsing task: {celery_err}"
            #     db.session.commit()

        return jsonify({
            "message": "File uploaded successfully. Parsing initiated.",
            "candidate_id": candidate_id,
            "s3_key": uploaded_key # Maybe remove this from response later?
        }), 201

    except Exception as e: # Catch S3 errors or re-raised DB errors
        # Rollback potentially uncommitted changes if error happened after add() but before commit()
        db.session.rollback()
        current_app.logger.error(f"Overall Upload Error for user {current_user.id} (S3 or DB): {e}", exc_info=True)
        # Don't try S3 cleanup here if uploaded_key might not be set or if the error was S3 itself
        return jsonify({"error": "An internal error occurred during file upload process."}), 500


# --- Dashboard Summary Endpoint ---
@api_bp.route('/dashboard/summary', methods=['GET'])
# @login_required # Add later
def get_dashboard_summary():
    try:
        relevant_statuses = [ 'Processing', 'ParsingFailed', 'NeedsReview', 'New', 'Accepted', 'Rejected', 'Interested', 'Interview', 'Declined', 'Evaluation', 'OfferMade', 'Hired' ]
        status_aggregations = [ func.sum(case((Candidate.current_status == status, 1), else_=0)).label(status) for status in relevant_statuses ]
        status_counts_query = db.session.query(func.count(Candidate.candidate_id).label("total_cvs"), *status_aggregations).first()
        if not status_counts_query:
            summary_data = {"total_cvs": 0}
            for status in relevant_statuses: summary_data[status] = 0
        else:
            summary_data = dict(status_counts_query._asdict())
            for status in relevant_statuses: summary_data[status] = summary_data.get(status, 0) or 0
        return jsonify(summary_data), 200
    except Exception as e:
        current_app.logger.error(f"Error generating dashboard summary: {e}", exc_info=True)
        return jsonify({"error": "Failed to generate dashboard summary"}), 500

# --- Get Candidates by Status Endpoint ---
@api_bp.route('/candidates/<string:status>', methods=['GET'])
# @login_required # Add later
def get_candidates_by_status(status):
    valid_statuses = [ 'Processing', 'ParsingFailed', 'NeedsReview', 'New', 'Accepted', 'Rejected', 'Interested', 'Interview', 'Declined', 'Evaluation', 'OfferMade', 'Hired' ]
    if status not in valid_statuses: return jsonify({"error": f"Invalid status: {status}"}), 400
    try:
        candidates = Candidate.query.filter_by(current_status=status).order_by(Candidate.submission_date.desc()).all()
        candidates_list = [ { "candidate_id": c.candidate_id, "full_name": c.get_full_name(), "positions": c.get_position_names(), "submission_date": c.submission_date.isoformat() if c.submission_date else None, "interview_date": c.interview_datetime.isoformat() if c.interview_datetime else None, "current_status": c.current_status } for c in candidates ]
        return jsonify(candidates_list), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching candidates with status '{status}': {e}", exc_info=True)
        return jsonify({"error": "Failed to retrieve candidates"}), 500


# --- Candidate Detail Endpoint (GET, PUT, DELETE) ---
@api_bp.route('/candidate/<string:candidate_id>', methods=['GET', 'PUT', 'DELETE'])
# @login_required # Add later (at least for PUT/DELETE)
def handle_candidate(candidate_id):
    candidate = Candidate.query.get_or_404(candidate_id, description=f"Candidate {candidate_id} not found.")
    user_id = current_user.id if current_user.is_authenticated else 'Anonymous' # Log user if available

    # --- GET ---
    if request.method == 'GET':
        try: return jsonify(candidate.to_dict()), 200
        except Exception as e: current_app.logger.error(f"Error serializing candidate {candidate_id} for GET: {e}"); return jsonify({"error": "Failed candidate details."}), 500

    # --- PUT ---
    elif request.method == 'PUT':
        current_app.logger.info(f"Attempting update on candidate {candidate_id} by user {user_id}")
        data = request.get_json();
        if not data: return jsonify({"error": "No input data"}), 400
        allowed_updates = ['first_name', 'last_name', 'age', 'phone_number', 'email', 'current_status', 'notes', 'education', 'work_experience', 'languages', 'seminars', 'interview_datetime', 'interview_location', 'evaluation_rating', 'offer_details', 'offer_response_date'] # Added offer_response_date
        updated = False; original_status = candidate.current_status; new_status = data.get('current_status', original_status)

        for key, value in data.items():
            if key in allowed_updates:
                if key == 'interview_datetime' or key == 'offer_response_date': # Handle date parsing
                    if value:
                        try:
                            parsed_dt = dateutil_parser.isoparse(value)
                            if parsed_dt.tzinfo is None: parsed_dt = parsed_dt.replace(tzinfo=timezone.utc)
                            setattr(candidate, key, parsed_dt)
                        except (ValueError, TypeError) as dt_err: current_app.logger.warning(f"Could not parse {key} '{value}': {dt_err}. Setting to None."); setattr(candidate, key, None)
                    else: setattr(candidate, key, None)
                elif key == 'age': # Handle potential empty string for age
                     setattr(candidate, key, int(value) if value else None)
                else: setattr(candidate, key, value)
                updated = True
            elif key == 'positions' and isinstance(value, list): # Handle positions
                 current_positions = {p.position_name for p in candidate.positions}; target_positions_set = set(value)
                 positions_to_remove = [p for p in candidate.positions if p.position_name not in target_positions_set]
                 for pos_obj in positions_to_remove: candidate.positions.remove(pos_obj); updated = True
                 for pos_name in target_positions_set:
                     if pos_name not in current_positions:
                         position = Position.query.filter(func.lower(Position.position_name) == func.lower(pos_name)).first()
                         if not position: position = Position(position_name=pos_name); db.session.add(position); db.session.flush()
                         candidate.positions.append(position); updated = True

        if new_status != original_status: # Handle status change & history
            candidate.current_status = new_status; updated = True;
            history_entry = {"status": new_status, "timestamp": datetime.now(timezone.utc).isoformat(), "updated_by": user_id } # Add user_id to history
            current_history = candidate.history if isinstance(candidate.history, list) else []; current_history.append(history_entry); candidate.history = current_history; flag_modified(candidate, "history")
            if new_status in ['Rejected', 'Declined']: # Trigger email
                current_app.logger.info(f"Candidate {candidate_id} status changed to {new_status}, triggering rejection email.")
                try: celery.send_task('tasks.communication.send_rejection_email', args=[str(candidate.candidate_id), bool(current_app.config.get('MAIL_DEBUG', False)), str(current_app.config.get('MAIL_SENDER'))])
                except Exception as celery_err: current_app.logger.error(f"Failed send email task: {celery_err}")
            if new_status != 'Interview': # Clear interview details if moved away from Interview status (unless staying in Evaluation?)
                 if original_status == 'Interview' and new_status != 'Evaluation':
                      candidate.interview_datetime = None
                      candidate.interview_location = None
                      current_app.logger.info(f"Cleared interview details for {candidate_id} due to status change from Interview to {new_status}.")

        if not updated: return jsonify({"message": "No changes detected"}), 304
        try: db.session.commit(); current_app.logger.info(f"Candidate {candidate_id} updated successfully by user {user_id}."); return jsonify(candidate.to_dict()), 200
        except Exception as e: db.session.rollback(); current_app.logger.error(f"Error updating {candidate_id} by user {user_id}: {e}"); return jsonify({"error": "Failed to update candidate"}), 500

    # --- DELETE ---
    elif request.method == 'DELETE':
        current_app.logger.info(f"Attempting delete on candidate {candidate_id} by user {user_id}")
        s3_key_to_delete = candidate.cv_storage_path; candidate_display_name = candidate.get_full_name()
        try:
            db.session.delete(candidate); db.session.commit()
            current_app.logger.info(f"Candidate record {candidate_id} ({candidate_display_name}) deleted from DB by user {user_id}.")
            if s3_key_to_delete:
                current_app.logger.info(f"Attempting S3 deletion for {s3_key_to_delete}...")
                try:
                    deleted = s3_service.delete_file(s3_key_to_delete)
                    if deleted: current_app.logger.info(f"S3 file {s3_key_to_delete} deleted successfully.")
                    else: current_app.logger.warning(f"S3 delete indicated failure for {s3_key_to_delete}.")
                except Exception as s3_e: current_app.logger.error(f"Error during S3 deletion {s3_key_to_delete}: {s3_e}")
            return jsonify({"message": f"Candidate {candidate_id} deleted successfully."}), 200
        except Exception as e: db.session.rollback(); current_app.logger.error(f"Error deleting {candidate_id} by user {user_id}: {e}"); return jsonify({"error": "Failed to delete candidate"}), 500

# --- CV URL Generation Endpoint ---
@api_bp.route('/candidate/<string:candidate_id>/cv_url', methods=['GET'])
# @login_required # Add later
def get_candidate_cv_url(candidate_id):
    candidate = Candidate.query.get_or_404(candidate_id);
    if not candidate.cv_storage_path: return jsonify({"error": "No CV file associated"}), 404
    try:
        cv_url = s3_service.generate_presigned_url(candidate.cv_storage_path, expiration=900) # 15 min expiry
        if cv_url: return jsonify({"cv_url": cv_url}), 200
        else: return jsonify({"error": "Could not generate CV URL."}), 500
    except Exception as e: current_app.logger.error(f"Error generating presigned URL for {candidate_id}: {e}"); return jsonify({"error": "Failed to generate CV URL."}), 500


# --- Search Endpoint (Includes Phone Number) ---
@api_bp.route('/search', methods=['GET'])
# @login_required # Add later
def search_candidates():
    query = request.args.get('q', '')
    status_filter = request.args.get('status', None)

    if not query: return jsonify([]), 200

    try:
        search_term = f"%{query}%"
        # Build the OR conditions for searching
        search_filters = [
            Candidate.first_name.ilike(search_term),
            Candidate.last_name.ilike(search_term),
            Position.position_name.ilike(search_term),
            Candidate.phone_number.ilike(search_term) # <<< SEARCH PHONE
        ]
        # Also allow searching by full name concatenation?
        # search_filters.append( (Candidate.first_name + ' ' + Candidate.last_name).ilike(search_term) ) # Needs DB specific concat function usually

        candidates_query = Candidate.query.join(Candidate.positions, isouter=True).filter(or_(*search_filters))

        if status_filter:
             valid_statuses = [ 'Processing', 'ParsingFailed', 'NeedsReview', 'New', 'Accepted', 'Rejected', 'Interested', 'Interview', 'Declined', 'Evaluation', 'OfferMade', 'Hired' ]
             if status_filter in valid_statuses: candidates_query = candidates_query.filter(Candidate.current_status == status_filter)
             else: current_app.logger.warning(f"Invalid status filter '{status_filter}' provided in search, ignoring.")

        candidates = candidates_query.distinct().order_by(Candidate.submission_date.desc()).all()
        candidates_list = [ { "candidate_id": c.candidate_id, "full_name": c.get_full_name(), "positions": c.get_position_names(), "submission_date": c.submission_date.isoformat() if c.submission_date else None, "interview_date": c.interview_datetime.isoformat() if c.interview_datetime else None, "current_status": c.current_status } for c in candidates ]
        return jsonify(candidates_list), 200
    except Exception as e:
        current_app.logger.error(f"Error during search query='{query}', status='{status_filter}': {e}", exc_info=True)
        return jsonify({"error": "Failed to perform search"}), 500


# --- Settings Endpoint (Requires Auth) ---
@api_bp.route('/settings', methods=['GET', 'PUT'])
@login_required
def handle_settings():
    if request.method == 'GET':
        user_settings = { "username": current_user.username, "email": current_user.email, "enable_interview_reminders": current_user.enable_interview_reminders, "reminder_lead_time_minutes": current_user.reminder_lead_time_minutes, "email_interview_reminders": current_user.email_interview_reminders, }
        return jsonify(user_settings), 200

    elif request.method == 'PUT':
        data = request.get_json();
        if not data: return jsonify({"error": "No settings data"}), 400
        updated = False; allowed_setting_updates = { 'enable_interview_reminders': bool, 'reminder_lead_time_minutes': int, 'email_interview_reminders': bool }
        for key, value in data.items():
            if key in allowed_setting_updates:
                try:
                    expected_type = allowed_setting_updates[key]; casted_value = expected_type(value)
                    if key == 'reminder_lead_time_minutes' and not (5 <= casted_value <= 1440): raise ValueError("Lead time out of range (5-1440 min).")
                    setattr(current_user, key, casted_value); updated = True
                except (ValueError, TypeError) as e: current_app.logger.warning(f"Invalid value for setting '{key}': {value}. Error: {e}"); return jsonify({"error": f"Invalid value for setting '{key}'"}), 400
        if not updated: return jsonify({"message": "No valid settings provided"}), 400
        try:
            db.session.commit(); current_app.logger.info(f"Settings updated for user ID: {current_user.id}")
            user_settings = { "enable_interview_reminders": current_user.enable_interview_reminders, "reminder_lead_time_minutes": current_user.reminder_lead_time_minutes, "email_interview_reminders": current_user.email_interview_reminders, }
            return jsonify({"message": "Settings updated", "settings": user_settings}), 200
        except Exception as e: db.session.rollback(); current_app.logger.error(f"Error updating settings for user ID {current_user.id}: {e}"); return jsonify({"error": "Failed to update settings"}), 500