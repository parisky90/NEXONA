# backend/app/api/routes.py

from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
import uuid
from datetime import datetime, timezone
from dateutil import parser as dateutil_parser
from flask_login import login_user, logout_user, current_user, login_required
from app import db, celery
# --- ΔΙΟΡΘΩΣΗ 1: Προσθήκη CompanySettings στο import ---
from app.models import User, Candidate, Position, Company, CompanySettings
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import func, case, or_
from app.services import s3_service

api_bp = Blueprint('api', __name__)

ALLOWED_EXTENSIONS = {'pdf', 'docx'}
def allowed_file(filename): return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_current_user_company_id():
    if not current_user.is_authenticated:
        return None
    if current_user.role == 'superadmin':
        return None
    if not current_user.company_id:
        current_app.logger.error(f"User {current_user.id} ({current_user.username}) with role {current_user.role} has no company_id.")
        return None
    return current_user.company_id

@api_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data: return jsonify({"error": "Request must be JSON"}), 400
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    if not username or not email or not password:
        return jsonify({"error": "Username, email, and password are required"}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters long"}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username already exists"}), 409
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email address already registered"}), 409
    new_user = User(
        username=username, email=email, role='user', is_active=False
    )
    new_user.set_password(password)
    try:
        db.session.add(new_user)
        db.session.commit()
        current_app.logger.info(f"New user registered: {username} ({email}). Awaiting activation.")
        # celery.send_task('app.tasks.communication_tasks.send_account_confirmation_email', args=[new_user.id])
        return jsonify({"message": "Registration successful. Account activation pending."}), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error during user registration for {username}: {e}", exc_info=True)
        return jsonify({"error": "Registration failed due to an internal error."}), 500

@api_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or not data.get('login_identifier') or not data.get('password'):
        return jsonify({"error": "Login identifier and password required"}), 400
    login_identifier = data.get('login_identifier')
    password = data.get('password')
    remember = data.get('remember', False)
    user = User.query.filter((User.username == login_identifier) | (User.email == login_identifier)).first()
    if user and user.check_password(password):
        if not user.is_active:
            current_app.logger.warning(f"Login attempt by inactive user: {login_identifier}")
            return jsonify({"error": "Account not active. Please check your email or contact an administrator."}), 403
        if user.role != 'superadmin' and not user.company_id:
            current_app.logger.warning(f"Login attempt by user {user.username} not assigned to any company.")
            return jsonify({"error": "Account not yet assigned to a company by an administrator."}), 403
        login_user(user, remember=remember)
        current_app.logger.info(f"User {user.username} (Role: {user.role}, CompanyID: {user.company_id}) logged in.")
        user_data = {
            "id": user.id, "username": user.username, "email": user.email,
            "role": user.role, "company_id": user.company_id,
        }
        if user.company_id and user.role != 'superadmin':
            # --- Εδώ χρησιμοποιείται το CompanySettings ---
            company_settings = CompanySettings.query.filter_by(company_id=user.company_id).first()
            if company_settings:
                user_data["company_settings"] = {
                    "rejection_email_template": company_settings.rejection_email_template,
                    "reminder_email_template": company_settings.reminder_email_template,
                    "interview_invitation_email_template": company_settings.interview_invitation_email_template,
                    "interview_reminder_timing_minutes": company_settings.interview_reminder_timing_minutes
                }
        return jsonify({"message": "Login successful", "user": user_data}), 200
    else:
        current_app.logger.warning(f"Failed login attempt for: {login_identifier}")
        return jsonify({"error": "Invalid login identifier or password"}), 401

@api_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    user_id = current_user.id; username = current_user.username
    logout_user()
    current_app.logger.info(f"User {username} (ID: {user_id}) logged out.")
    return jsonify({"message": "Logout successful"}), 200

@api_bp.route('/session', methods=['GET'])
def check_session():
    if current_user.is_authenticated:
        user_data = {
            "id": current_user.id, "username": current_user.username, "email": current_user.email,
            "role": current_user.role, "company_id": current_user.company_id
        }
        if current_user.company_id and current_user.role != 'superadmin':
            company_settings = CompanySettings.query.filter_by(company_id=current_user.company_id).first()
            if company_settings:
                user_data["company_settings"] = {
                    "interview_reminder_timing_minutes": company_settings.interview_reminder_timing_minutes
                }
        return jsonify({"authenticated": True, "user": user_data}), 200
    else:
        return jsonify({"authenticated": False}), 200

@api_bp.route('/upload', methods=['POST'])
@login_required
def upload_cv():
    current_app.logger.info(f"--- Upload Request Received by User ID: {current_user.id} ({current_user.username}) ---")
    user_company_id = get_current_user_company_id()
    if current_user.role != 'superadmin' and not user_company_id:
        return jsonify({"error": "User not associated with a company."}), 403
    target_company_id = user_company_id
    if current_user.role == 'superadmin':
        target_company_id_from_form = request.form.get('company_id_for_upload', type=int)
        if not target_company_id_from_form:
            first_company = Company.query.first()
            if not first_company:
                return jsonify({"error": "No companies exist in the system for superadmin upload."}), 400
            target_company_id = first_company.id
            current_app.logger.warning(f"Superadmin uploading CV, no target company specified, defaulting to Company ID: {target_company_id}")
        else:
            target_company_id = target_company_id_from_form
    if 'cv_file' not in request.files: return jsonify({"error": "No file part named 'cv_file'"}), 400
    file = request.files['cv_file']
    position_name_from_form = request.form.get('position', None)
    if file.filename == '': return jsonify({"error": "No selected file"}), 400
    if not allowed_file(file.filename): return jsonify({"error": "Invalid file type. Allowed: pdf, docx"}), 400
    uploaded_key = None
    try:
        file_ext = file.filename.rsplit('.', 1)[1].lower()
        original_filename = secure_filename(file.filename)
        s3_key = f"company_{target_company_id}/cvs/{uuid.uuid4()}.{file_ext}"
        file.seek(0)
        uploaded_key = s3_service.upload_file(file, s3_key)
        if not uploaded_key: raise Exception("S3 upload service indicated failure.")
        new_candidate = Candidate(
            cv_original_filename=original_filename, cv_storage_path=uploaded_key,
            current_status='Processing', confirmation_uuid=str(uuid.uuid4()),
            company_id=target_company_id
        )
        if position_name_from_form and position_name_from_form.strip():
            pos_name_cleaned = position_name_from_form.strip()
            position = Position.query.filter(
                func.lower(Position.position_name) == func.lower(pos_name_cleaned),
                Position.company_id == target_company_id
            ).first()
            if not position:
                position = Position(position_name=pos_name_cleaned, company_id=target_company_id)
                db.session.add(position)
            new_candidate.positions.append(position)
        db.session.add(new_candidate); db.session.commit()
        candidate_id_val = new_candidate.candidate_id
        celery.send_task('app.tasks.parsing_tasks.parse_cv_task', args=[candidate_id_val, uploaded_key, target_company_id])
        return jsonify(new_candidate.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Overall Upload Error user {current_user.id} (Company: {target_company_id}) during upload: {e}", exc_info=True)
        if uploaded_key:
            try: s3_service.delete_file(uploaded_key)
            except Exception as s3_del_err: current_app.logger.error(f"S3 cleanup FAILED for {uploaded_key}: {s3_del_err}")
        return jsonify({"error": "Internal upload error."}), 500

@api_bp.route('/dashboard/summary', methods=['GET'])
@login_required
def get_dashboard_summary():
    user_company_id = get_current_user_company_id()
    query_company_id = None
    if current_user.role == 'superadmin':
        company_id_filter = request.args.get('company_id', type=int)
        if company_id_filter: query_company_id = company_id_filter
    elif user_company_id: query_company_id = user_company_id
    else: return jsonify({"error": "User not associated with a company or not authorized."}), 403
    try:
        relevant_statuses = [ 'Processing', 'ParsingFailed', 'NeedsReview', 'New', 'Accepted', 'Rejected', 'Interested', 'Interview', 'Declined', 'Evaluation', 'OfferMade', 'Hired' ]
        status_aggregations = [ func.sum(case((Candidate.current_status == status, 1), else_=0)).label(status) for status in relevant_statuses ]
        query_obj = db.session.query(func.count(Candidate.candidate_id).label("total_cvs"), *status_aggregations)
        if query_company_id: query_obj = query_obj.filter(Candidate.company_id == query_company_id)
        q_result = query_obj.first()
        summary = {"total_cvs": 0}; [summary.update({s: 0}) for s in relevant_statuses];
        if q_result: summary.update({k: v or 0 for k, v in q_result._asdict().items()})
        return jsonify(summary), 200
    except Exception as e:
        current_app.logger.error(f"Dashboard Summary Error (User: {current_user.id}, Company Filter: {query_company_id}): {e}", exc_info=True)
        return jsonify({"error": "Failed to retrieve dashboard summary."}), 500

@api_bp.route('/candidates/<string:status>', methods=['GET'])
@login_required
def get_candidates_by_status(status):
    valid_statuses = [ 'Processing', 'ParsingFailed', 'NeedsReview', 'New', 'Accepted', 'Rejected', 'Interested', 'Interview', 'Declined', 'Evaluation', 'OfferMade', 'Hired', 'All' ]
    if status not in valid_statuses: return jsonify({"error": f"Invalid status: {status}"}), 400
    user_company_id = get_current_user_company_id()
    query_company_id = None
    if current_user.role == 'superadmin':
        company_id_filter = request.args.get('company_id', type=int)
        if company_id_filter: query_company_id = company_id_filter
    elif user_company_id: query_company_id = user_company_id
    else: return jsonify({"error": "User not associated with a company or not authorized."}), 403
    try:
        candidates_query_obj = Candidate.query
        if query_company_id: candidates_query_obj = candidates_query_obj.filter(Candidate.company_id == query_company_id)
        if status != 'All': candidates_query_obj = candidates_query_obj.filter(Candidate.current_status == status)
        candidates_result = candidates_query_obj.order_by(Candidate.submission_date.desc()).all()
        return jsonify([cand.to_dict() for cand in candidates_result]), 200
    except Exception as e:
        current_app.logger.error(f"Error listing candidates (Status: {status}, User: {current_user.id}, Company Filter: {query_company_id}): {e}", exc_info=True)
        return jsonify({"error": "Failed to retrieve candidate list."}), 500

# --- ΔΙΟΡΘΩΣΗ 2: Άλλαξε το όνομα της παραμέτρου εδώ ---
@api_bp.route('/candidate/<string:candidate_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def handle_candidate(candidate_id): # <--- ΑΛΛΑΓΗ ΕΔΩ
    user_company_id = get_current_user_company_id()
    # Χρησιμοποίησε το candidate_id (που έρχεται από το URL) για το query
    candidate = Candidate.query.get_or_404(candidate_id, description=f"Candidate {candidate_id} not found.")
    if current_user.role != 'superadmin':
        if not user_company_id or candidate.company_id != user_company_id:
            current_app.logger.warning(f"Access denied for user {current_user.id} to candidate {candidate.candidate_id}")
            return jsonify({"error": "Access denied to this candidate."}), 403
    user_id_for_logs = current_user.id
    if request.method == 'GET':
        try:
            cv_url_val = None
            if candidate.cv_storage_path:
                cv_url_val = s3_service.generate_presigned_url(candidate.cv_storage_path, expiration=900)
            return jsonify(candidate.to_dict(include_cv_url=True, cv_url=cv_url_val)), 200
        except Exception as e:
            current_app.logger.error(f"GET Candidate {candidate.candidate_id} Error: {e}", exc_info=True)
            return jsonify({"error": "Failed to retrieve candidate details."}), 500
    elif request.method == 'PUT':
        current_app.logger.info(f"PUT Candidate {candidate.candidate_id} by User {user_id_for_logs}")
        data = request.get_json();
        if not data: return jsonify({"error": "No input data provided."}), 400
        allowed_updates = [
            'first_name', 'last_name', 'age', 'phone_number', 'email',
            'current_status', 'notes', 'education', 'work_experience',
            'languages', 'seminars', 'interview_datetime', 'interview_location',
            'evaluation_rating', 'offers', 'candidate_confirmation_status'
        ]
        updated = False; original_status = candidate.current_status; notes_before_this_update_cycle = candidate.notes
        new_status = data.get('current_status', original_status); original_interview_time = candidate.interview_datetime
        interview_time_changed = False
        for key, value in data.items():
            if key in allowed_updates:
                if key == 'interview_datetime':
                    new_dt_value = None
                    if value:
                        try: parsed_dt = dateutil_parser.isoparse(value); new_dt_value = parsed_dt.astimezone(timezone.utc) if parsed_dt.tzinfo else parsed_dt.replace(tzinfo=timezone.utc)
                        except (ValueError, TypeError): new_dt_value = original_interview_time
                    else: new_dt_value = None
                    if new_dt_value != original_interview_time: setattr(candidate, key, new_dt_value); interview_time_changed = True; updated = True
                elif key == 'age':
                     current_val = getattr(candidate, key); new_val = int(value) if value is not None and str(value).strip().isdigit() else None
                     if current_val != new_val: setattr(candidate, key, new_val); updated = True
                elif key == 'offers':
                    if isinstance(value, list): setattr(candidate, key, value); flag_modified(candidate, "offers"); updated = True
                    else: current_app.logger.warning(f"Invalid data type for 'offers' for candidate {candidate.candidate_id}")
                else:
                     current_val = getattr(candidate, key)
                     if current_val != value: setattr(candidate, key, value); updated = True
            elif key == 'positions' and isinstance(value, list):
                current_pos_names = {p.position_name for p in candidate.positions}; target_pos_names = set(p_name for p_name in value if isinstance(p_name, str) and p_name.strip())
                positions_to_remove = [p for p in candidate.positions if p.position_name not in target_pos_names]
                if positions_to_remove:
                    for pos_obj in positions_to_remove: candidate.positions.remove(pos_obj)
                    updated = True
                for pos_name in target_pos_names:
                    if pos_name not in current_pos_names:
                        position = Position.query.filter(
                            func.lower(Position.position_name) == func.lower(pos_name),
                            Position.company_id == candidate.company_id
                        ).first()
                        if not position:
                            position = Position(position_name=pos_name, company_id=candidate.company_id)
                            db.session.add(position)
                        if position not in candidate.positions: candidate.positions.append(position)
                        updated = True
        if interview_time_changed:
            if candidate.interview_datetime:
                candidate.candidate_confirmation_status = 'Pending'
                candidate.confirmation_uuid = str(uuid.uuid4())
                flag_modified(candidate, "candidate_confirmation_status"); flag_modified(candidate, "confirmation_uuid")
            else:
                candidate.candidate_confirmation_status = None
                flag_modified(candidate, "candidate_confirmation_status")
            updated = True
        if new_status != original_status:
            candidate.current_status = new_status; updated = True
            history_entry = {
                "status": new_status, "previous_status": original_status,
                "timestamp": datetime.now(timezone.utc).isoformat(), "updated_by": user_id_for_logs,
                "notes_at_this_stage": data.get('notes', candidate.notes)
            }
            current_history = candidate.history if isinstance(candidate.history, list) else []; current_history.append(history_entry)
            candidate.history = current_history; flag_modified(candidate, "history")
            if original_status == 'Interview' and new_status not in ['Evaluation', 'Interview', 'OfferMade', 'Hired']:
                candidate.interview_datetime = None; candidate.interview_location = None
                candidate.candidate_confirmation_status = None
                flag_modified(candidate, "candidate_confirmation_status")
        if not updated: return jsonify({"message": "No changes detected"}), 304
        try:
            db.session.commit()
            current_app.logger.info(f"Candidate {candidate.candidate_id} updated by {user_id_for_logs}.")
            if interview_time_changed and candidate.interview_datetime:
                celery.send_task('app.tasks.communication_tasks.send_interview_invitation_email_task', args=[str(candidate.candidate_id)])
            if new_status != original_status and new_status in ['Rejected', 'Declined']:
                celery.send_task('app.tasks.communication_tasks.send_rejection_email_task', args=[str(candidate.candidate_id)])
            return jsonify(candidate.to_dict()), 200
        except Exception as e: db.session.rollback(); current_app.logger.error(f"Error updating candidate {candidate.candidate_id}: {e}", exc_info=True); return jsonify({"error": "Failed to update candidate details."}), 500
    elif request.method == 'DELETE':
        current_app.logger.info(f"DELETE Candidate {candidate.candidate_id} by User {user_id_for_logs}")
        s3_key_to_delete = candidate.cv_storage_path
        candidate_name_for_log = candidate.get_full_name()
        try:
            db.session.delete(candidate); db.session.commit()
            current_app.logger.info(f"Candidate {candidate.candidate_id} ({candidate_name_for_log}) deleted from DB by {user_id_for_logs}.")
            if s3_key_to_delete:
                try: s3_service.delete_file(s3_key_to_delete)
                except Exception as s3_e: current_app.logger.error(f"S3 Delete error for key {s3_key_to_delete}: {s3_e}", exc_info=True)
            return jsonify({"message": f"Candidate {candidate_name_for_log} deleted successfully."}), 200
        except Exception as e:
            db.session.rollback(); current_app.logger.error(f"Error deleting candidate {candidate.candidate_id} from DB: {e}", exc_info=True)
            return jsonify({"error": "Failed to delete candidate."}), 500

@api_bp.route('/candidate/<string:candidate_id>/cv_url', methods=['GET']) # <--- ΑΛΛΑΓΗ ΕΔΩ
@login_required
def get_candidate_cv_url(candidate_id): # <--- ΑΛΛΑΓΗ ΕΔΩ
    user_company_id = get_current_user_company_id()
    # Χρησιμοποίησε το candidate_id (που έρχεται από το URL) για το query
    candidate = Candidate.query.get_or_404(candidate_id)
    if current_user.role != 'superadmin':
        if not user_company_id or candidate.company_id != user_company_id:
            return jsonify({"error": "Access denied to this candidate's CV."}), 403
    if not candidate.cv_storage_path: return jsonify({"error": "No CV file associated"}), 404
    try:
        cv_url = s3_service.generate_presigned_url(candidate.cv_storage_path, expiration=900)
        if cv_url: return jsonify({"cv_url": cv_url}), 200
        else: current_app.logger.error(f"S3 service failed to generate URL for candidate {candidate.candidate_id}"); return jsonify({"error": "Could not generate CV URL."}), 500
    except Exception as e: current_app.logger.error(f"Error generating CV URL for candidate {candidate.candidate_id}: {e}", exc_info=True); return jsonify({"error": "Failed to generate CV URL"}), 500

@api_bp.route('/search', methods=['GET'])
@login_required
def search_candidates():
    query_term = request.args.get('q', ''); status_filter_term = request.args.get('status', None)
    user_company_id = get_current_user_company_id(); query_target_company_id = None
    if current_user.role == 'superadmin':
        company_id_param = request.args.get('company_id', type=int)
        if company_id_param: query_target_company_id = company_id_param
    elif user_company_id: query_target_company_id = user_company_id
    else: return jsonify({"error": "User not associated with a company or not authorized."}), 403
    try:
        query_builder = Candidate.query
        if query_target_company_id: query_builder = query_builder.filter(Candidate.company_id == query_target_company_id)
        if query_term:
            search_pattern = f"%{query_term}%"
            search_conditions = [ Candidate.first_name.ilike(search_pattern), Candidate.last_name.ilike(search_pattern), Candidate.email.ilike(search_pattern), Candidate.phone_number.ilike(search_pattern) ]
            if any(term in query_term.lower() for term in ["position", "role", "title"]):
                 query_builder = query_builder.outerjoin(Candidate.positions).filter(or_(*search_conditions, Position.position_name.ilike(search_pattern)))
            else: query_builder = query_builder.filter(or_(*search_conditions))
        if status_filter_term:
            valid_statuses = [ 'Processing', 'ParsingFailed', 'NeedsReview', 'New', 'Accepted', 'Rejected', 'Interested', 'Interview', 'Declined', 'Evaluation', 'OfferMade', 'Hired' ]
            if status_filter_term in valid_statuses: query_builder = query_builder.filter(Candidate.current_status == status_filter_term)
        candidates_result = query_builder.distinct().order_by(Candidate.submission_date.desc()).all()
        return jsonify([cand.to_dict() for cand in candidates_result]), 200
    except Exception as e:
        current_app.logger.error(f"Search Error (Query: '{query_term}', User: {current_user.id}, Company: {query_target_company_id}): {e}", exc_info=True)
        return jsonify({"error": "Search operation failed."}), 500

@api_bp.route('/settings', methods=['GET', 'PUT'])
@login_required
def handle_settings():
    user_company_id = get_current_user_company_id()
    company_settings_obj = None # Initialize
    if current_user.role == 'superadmin':
        target_company_id_for_superadmin = request.args.get('company_id', type=int)
        if not target_company_id_for_superadmin and request.method == 'PUT':
             return jsonify({"error": "Superadmin must specify a company_id to update settings."}), 400
        if not target_company_id_for_superadmin and request.method == 'GET':
             return jsonify({"message": "Superadmin: Specify company_id to view company settings."}), 400
        if target_company_id_for_superadmin:
            company_settings_obj = CompanySettings.query.filter_by(company_id=target_company_id_for_superadmin).first_or_404()
    elif user_company_id:
        company_settings_obj = CompanySettings.query.filter_by(company_id=user_company_id).first()
        if not company_settings_obj:
            try:
                company_settings_obj = CompanySettings(company_id=user_company_id); db.session.add(company_settings_obj); db.session.commit()
                current_app.logger.info(f"Dynamically created CompanySettings for company_id {user_company_id}.")
            except Exception as cs_create_err:
                db.session.rollback(); current_app.logger.error(f"Failed to create CompanySettings for {user_company_id}: {cs_create_err}", exc_info=True)
                return jsonify({"error": "Company settings missing and could not be initialized."}), 500
    else: return jsonify({"error": "User not associated with a company."}), 403
    if request.method == 'PUT' and current_user.role not in ['company_admin', 'superadmin']:
        return jsonify({"error": "You do not have permission to modify company settings."}), 403
    if request.method == 'GET':
        return jsonify({
            "company_id": company_settings_obj.company_id,
            "rejection_email_template": company_settings_obj.rejection_email_template,
            "reminder_email_template": company_settings_obj.reminder_email_template,
            "interview_invitation_email_template": company_settings_obj.interview_invitation_email_template,
            "interview_reminder_timing_minutes": company_settings_obj.interview_reminder_timing_minutes
        }), 200
    elif request.method == 'PUT':
        data = request.get_json();
        if not data: return jsonify({"error": "No settings data provided."}), 400
        updated_fields = False; allowed_company_settings = {
            'rejection_email_template': str, 'reminder_email_template': str,
            'interview_invitation_email_template': str, 'interview_reminder_timing_minutes': int
        }
        for key, value in data.items():
            if key in allowed_company_settings:
                expected_type = allowed_company_settings[key]
                try:
                    casted_value = None
                    if value is not None:
                        casted_value = expected_type(value)
                        if key == 'interview_reminder_timing_minutes' and not (5 <= casted_value <= 2880):
                            raise ValueError("Interview reminder lead time out of range (5-2880 minutes).")
                    if getattr(company_settings_obj, key) != casted_value:
                        setattr(company_settings_obj, key, casted_value); updated_fields = True
                except (ValueError, TypeError) as e:
                    current_app.logger.warning(f"Invalid value for company setting '{key}': {value}. Error: {e}")
                    return jsonify({"error": f"Invalid value or type for setting '{key}'."}), 400
        if not updated_fields: return jsonify({"message": "No changes detected"}), 304
        try:
            db.session.commit()
            current_app.logger.info(f"Company settings for {company_settings_obj.company_id} updated by {current_user.id}.")
            return jsonify({
                "message": "Company settings updated.", "settings": {
                    "company_id": company_settings_obj.company_id,
                    "rejection_email_template": company_settings_obj.rejection_email_template,
                    "reminder_email_template": company_settings_obj.reminder_email_template,
                    "interview_invitation_email_template": company_settings_obj.interview_invitation_email_template,
                    "interview_reminder_timing_minutes": company_settings_obj.interview_reminder_timing_minutes
            }}), 200
        except Exception as e:
            db.session.rollback(); current_app.logger.error(f"Error saving company settings for {company_settings_obj.company_id}: {e}", exc_info=True)
            return jsonify({"error": "Failed to save company settings."}), 500

@api_bp.route('/interviews/confirm/<string:confirmation_uuid>', methods=['GET'])
def confirm_interview(confirmation_uuid):
    try:
        candidate = Candidate.query.filter_by(confirmation_uuid=confirmation_uuid).first()
        if not candidate: return "<h1>Σφάλμα</h1><p>Ο σύνδεσμος επιβεβαίωσης δεν είναι έγκυρος ή έχει λήξει.</p>", 404
        if not candidate.interview_datetime: return "<h1>Σφάλμα</h1><p>Δεν υπάρχει προγραμματισμένη συνέντευξη.</p>", 400
        response_message, status_code = "", 200
        if candidate.candidate_confirmation_status == 'Confirmed':
            response_message = f"<h1>Ήδη Επιβεβαιωμένο</h1><p>Η συνέντευξη στις {candidate.interview_datetime.strftime('%d/%m/%Y %H:%M')} έχει ήδη επιβεβαιωθεί.</p>"
        elif candidate.candidate_confirmation_status in ['Pending', 'Declined']:
            candidate.candidate_confirmation_status = 'Confirmed'; db.session.commit()
            try: celery.send_task('app.tasks.communication_tasks.notify_recruiter_interview_confirmed_task', args=[str(candidate.candidate_id), candidate.company_id])
            except Exception as celery_err: current_app.logger.error(f"Failed to send celery task for interview confirmation: {celery_err}", exc_info=True)
            response_message = f"<h1>Επιβεβαίωση Επιτυχής</h1><p>Ευχαριστούμε, {candidate.get_full_name()}! Η συνέντευξη στις {candidate.interview_datetime.strftime('%d/%m/%Y %H:%M')} έχει επιβεβαιωθεί.</p>"
        else: response_message = "<h1>Σφάλμα</h1><p>Αυτή η ενέργεια δεν είναι δυνατή.</p>"; status_code = 400
        return response_message, status_code
    except Exception as e:
        db.session.rollback(); current_app.logger.error(f"Error confirming interview (UUID: {confirmation_uuid}): {e}", exc_info=True)
        return "<h1>Σφάλμα Συστήματος</h1><p>Παρουσιάστηκε σφάλμα.</p>", 500

@api_bp.route('/interviews/decline/<string:confirmation_uuid>', methods=['GET'])
def decline_interview(confirmation_uuid):
    try:
        candidate = Candidate.query.filter_by(confirmation_uuid=confirmation_uuid).first()
        if not candidate: return "<h1>Σφάλμα</h1><p>Ο σύνδεσμος δεν είναι έγκυρος ή έχει λήξει.</p>", 404
        if not candidate.interview_datetime: return "<h1>Σφάλμα</h1><p>Δεν υπάρχει προγραμματισμένη συνέντευξη.</p>", 400
        response_message, status_code = "", 200
        if candidate.candidate_confirmation_status == 'Declined':
            response_message = f"<h1>Ήδη Δηλωμένο</h1><p>Έχετε ήδη δηλώσει αδυναμία για τη συνέντευξη στις {candidate.interview_datetime.strftime('%d/%m/%Y %H:%M')}.</p>"
        elif candidate.candidate_confirmation_status in ['Pending', 'Confirmed']:
            candidate.candidate_confirmation_status = 'Declined'; db.session.commit()
            try: celery.send_task('app.tasks.communication_tasks.notify_recruiter_interview_declined_task', args=[str(candidate.candidate_id), candidate.company_id])
            except Exception as celery_err: current_app.logger.error(f"Failed to send celery task for interview declination: {celery_err}", exc_info=True)
            response_message = f"<h1>Επιβεβαίωση Λήφθηκε</h1><p>Λάβαμε το αίτημά σας για τη συνέντευξη στις {candidate.interview_datetime.strftime('%d/%m/%Y %H:%M')}.</p>"
        else: response_message = "<h1>Σφάλμα</h1><p>Αυτή η ενέργεια δεν είναι δυνατή.</p>"; status_code = 400
        return response_message, status_code
    except Exception as e:
        db.session.rollback(); current_app.logger.error(f"Error declining interview (UUID: {confirmation_uuid}): {e}", exc_info=True)
        return "<h1>Σφάλμα Συστήματος</h1><p>Παρουσιάστηκε σφάλμα.</p>", 500