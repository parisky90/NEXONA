# backend/app/api/routes.py
from flask import Blueprint, request, jsonify, current_app, render_template
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from app import db, s3_service_instance, celery  # Προστέθηκε το celery instance
from app.models import (
    User, Company, Candidate, Position, CompanySettings,
    Interview, InterviewStatus
)
from app.config import Config
from datetime import datetime, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo
import uuid

# import logging # Δεν χρησιμοποιείται απευθείας, το current_app.logger είναι διαθέσιμο

bp = Blueprint('api', __name__, url_prefix='/api/v1')


# === Authentication Routes ===
@bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request must be JSON'}), 400

    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    company_name = data.get('company_name')

    if not all([username, email, password, company_name]):
        return jsonify(
            {'error': 'Missing data for registration (username, email, password, company_name required)'}), 400

    if User.query.filter((User.username == username) | (User.email == email.lower().strip())).first():
        return jsonify({'error': 'User with this username or email already exists'}), 409

    new_company = Company(name=company_name.strip())
    db.session.add(new_company)
    try:
        db.session.flush()

        company_settings = CompanySettings(company_id=new_company.id)
        db.session.add(company_settings)

        new_user = User(
            username=username.strip(),
            email=email.strip().lower(),
            role='company_admin',
            company_id=new_company.id,
            is_active=True,
            confirmed_on=datetime.now(dt_timezone.utc)
        )
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.flush()

        new_company.owner_user_id = new_user.id

        db.session.commit()
        login_user(new_user, remember=True)
        user_info = new_user.to_dict(include_company_info=True)

        current_app.logger.info(
            f"User '{new_user.username}' and Company '{new_company.name}' registered. User logged in.")
        return jsonify({
            'message': 'User and company registered successfully. User logged in.',
            'user': user_info
        }), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error during registration for user '{username}' or company '{company_name}': {e}",
                                 exc_info=True)
        return jsonify({'error': f'Could not register: {str(e)}'}), 500


@bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data: return jsonify({'error': 'Request must be JSON'}), 400
    login_identifier = data.get('login_identifier')
    password = data.get('password')
    if not login_identifier or not password: return jsonify({'error': 'Username/Email and password are required'}), 400
    user = User.query.filter((User.username == login_identifier) | (User.email == login_identifier.lower())).first()
    if user and user.check_password(password):
        if not user.is_active:
            current_app.logger.warning(f"Login attempt for inactive account: {login_identifier}")
            return jsonify({'error': 'Account is inactive. Please contact support.'}), 403
        login_user(user, remember=True)
        user_info = user.to_dict(include_company_info=True)
        current_app.logger.info(f"User '{user.username}' (ID: {user.id}) logged in successfully.")
        return jsonify({'message': 'Logged in successfully', 'user': user_info}), 200
    current_app.logger.warning(f"Failed login attempt for identifier: {login_identifier}")
    return jsonify({'error': 'Invalid username/email or password'}), 401


@bp.route('/logout', methods=['POST'])
@login_required
def logout():
    user_id = current_user.id
    username = current_user.username
    logout_user()
    current_app.logger.info(f"User '{username}' (ID: {user_id}) logged out.")
    return jsonify({'message': 'Logged out successfully'}), 200


@bp.route('/session', methods=['GET'])
@login_required
def session_status():
    user_info = current_user.to_dict(include_company_info=True)
    return jsonify({'is_authenticated': True, 'user': user_info}), 200


@bp.route('/dashboard/summary', methods=['GET'])
@login_required
def dashboard_summary():
    current_app.logger.info(
        f"--- dashboard_summary endpoint CALLED by user: {current_user.id if current_user.is_authenticated else 'Anonymous'}, Role: {current_user.role if current_user.is_authenticated else 'N/A'} ---")
    if current_user.role != 'superadmin' and not current_user.company_id:
        current_app.logger.warning(
            f"Dashboard access denied for user {current_user.id} (no company_id and not superadmin).")
        return jsonify({"error": "User not associated with a company"}), 403
    company_id_to_filter = None
    if current_user.role == 'superadmin':
        company_id_param = request.args.get('company_id', type=int)
        if company_id_param:
            company_id_to_filter = company_id_param
            if not db.session.get(Company, company_id_to_filter):
                current_app.logger.warning(
                    f"Superadmin requested dashboard for non-existent company ID: {company_id_to_filter}")
                return jsonify({"error": f"Company with ID {company_id_to_filter} not found."}), 404
    else:
        company_id_to_filter = current_user.company_id
    now_utc = datetime.now(dt_timezone.utc)
    if company_id_to_filter:
        total_candidates = Candidate.query.filter_by(company_id=company_id_to_filter).count()
        active_positions = Position.query.filter_by(company_id=company_id_to_filter, status='Open').count()
        upcoming_interviews_count = Interview.query.join(Candidate).filter(
            Candidate.company_id == company_id_to_filter, Interview.status == InterviewStatus.SCHEDULED,
            Interview.scheduled_start_time > now_utc).count()
    else:
        total_candidates = Candidate.query.count()
        active_positions = Position.query.filter_by(status='Open').count()
        upcoming_interviews_count = Interview.query.filter(
            Interview.status == InterviewStatus.SCHEDULED, Interview.scheduled_start_time > now_utc).count()
    stages = ["New", "Processing", "NeedsReview", "Accepted", "Interested", "Interview Scheduled", "Interviewing",
              "Evaluation", "OfferMade", "Hired", "Rejected", "Declined", "ParsingFailed", "On Hold"]
    candidates_by_stage = []
    for stage in stages:
        query = Candidate.query.filter(Candidate.current_status == stage)
        if company_id_to_filter: query = query.filter(Candidate.company_id == company_id_to_filter)
        count = query.count()
        candidates_by_stage.append({"stage_name": stage, "count": count})
    summary_data = {
        "total_candidates": total_candidates, "active_positions": active_positions,
        "upcoming_interviews": upcoming_interviews_count, "candidates_by_stage": candidates_by_stage
    }
    for item in candidates_by_stage:
        key_name = item['stage_name'].lower().replace(" ", "") + "_count"
        summary_data[key_name] = item['count']
        summary_data[item['stage_name'].lower().replace(" ", "")] = item['count']
    current_app.logger.info(
        f"Dashboard summary generated for user {current_user.id}, company_filter: {company_id_to_filter}")
    return jsonify(summary_data), 200


# === Candidate Routes ===
@bp.route('/upload', methods=['POST'])
@login_required
def upload_cv():
    if 'cv_file' not in request.files: return jsonify({'error': 'No "cv_file" part in the request'}), 400
    file = request.files['cv_file']
    if file.filename == '': return jsonify({'error': 'No selected file'}), 400
    if current_user.role != 'superadmin' and not current_user.company_id:
        current_app.logger.warning(f"User {current_user.id} without company_id tried to upload CV.")
        return jsonify({'error': 'User not associated with a company, cannot upload CVs'}), 403
    target_company_id = None
    if current_user.role == 'superadmin':
        company_id_for_upload_str = request.form.get('company_id_for_upload')
        if company_id_for_upload_str:
            try:
                target_company_id = int(company_id_for_upload_str)
                if not db.session.get(Company, target_company_id): return jsonify(
                    {'error': f'Target company ID {target_company_id} not found.'}), 404
            except ValueError:
                return jsonify({'error': 'Invalid company_id_for_upload format.'}), 400
        else:
            if not current_user.company_id: return jsonify(
                {'error': 'Superadmin must specify a target company ID for upload or be associated with one.'}), 400
            target_company_id = current_user.company_id
    else:
        target_company_id = current_user.company_id
    if not target_company_id:
        current_app.logger.error(f"Could not determine target_company_id for CV upload by user {current_user.id}")
        return jsonify({'error': 'Target company could not be determined for CV upload.'}), 500
    if file:
        filename = secure_filename(file.filename)
        file_content_bytes = file.read()
        position_name_from_form = request.form.get('position', None)
        try:
            file_key = f"cvs/{target_company_id}/{uuid.uuid4()}_{filename}"
            upload_success_key = s3_service_instance.upload_file_obj(file_obj_content_bytes=file_content_bytes,
                                                                     object_name=file_key,
                                                                     ContentType=file.content_type)
            if not upload_success_key:
                current_app.logger.error(
                    f"S3 upload failed for {filename} by user {current_user.id} for company {target_company_id}.")
                return jsonify({'error': 'Failed to upload file to S3 storage.'}), 500
            current_app.logger.info(
                f"CV '{filename}' uploaded to S3 at {file_key} by user {current_user.id} for company {target_company_id}")
            placeholder_email = f"placeholder-{uuid.uuid4()}@example.com"
            new_candidate = Candidate(company_id=target_company_id, cv_original_filename=filename,
                                      cv_storage_path=file_key, current_status='Processing', email=placeholder_email)
            db.session.add(new_candidate)
            db.session.flush()
            if position_name_from_form:
                position = Position.query.filter_by(company_id=target_company_id,
                                                    position_name=position_name_from_form).first()
                if not position:
                    position = Position(company_id=target_company_id, position_name=position_name_from_form,
                                        status="Open")
                    db.session.add(position)
                    current_app.logger.info(
                        f"Created new position '{position_name_from_form}' for company {target_company_id} during CV upload.")
                if position not in new_candidate.positions:
                    new_candidate.positions.append(position)
                    current_app.logger.info(
                        f"Associated candidate {new_candidate.candidate_id} with position '{position_name_from_form}'.")
            new_candidate.add_history_event(event_type="CV_UPLOADED",
                                            description=f"CV '{filename}' uploaded by {current_user.username}.",
                                            actor_id=current_user.id, actor_username=current_user.username,
                                            details={"s3_key": file_key,
                                                     "position_applied": position_name_from_form or "N/A"})
            db.session.commit()
            current_app.logger.info(
                f"Candidate record created with ID {new_candidate.candidate_id} and placeholder email {placeholder_email}")
            if Config.TEXTKERNEL_ENABLED:
                try:
                    # ΣΩΣΤΟΣ ΤΡΟΠΟΣ ΚΛΗΣΗΣ TASK (με βάση το όνομα που ορίζεται στο decorator του task)
                    # Υποθέτουμε ότι το task ονομάζεται 'tasks.parsing.parse_cv_task'
                    celery.send_task('tasks.parsing.parse_cv_task',
                                     args=[str(new_candidate.candidate_id), file_key, target_company_id])
                    current_app.logger.info(
                        f"Celery task 'tasks.parsing.parse_cv_task' dispatched for candidate {new_candidate.candidate_id}, S3 key {file_key}, company {target_company_id}")
                except Exception as celery_e:
                    current_app.logger.error(f"Error dispatching Celery task for CV parsing: {celery_e}", exc_info=True)
            else:
                new_candidate.current_status = 'NeedsReview'
                new_candidate.add_history_event(event_type="PARSING_SKIPPED",
                                                description="Textkernel parsing is disabled. Manual review needed.",
                                                actor_username="System")
                db.session.commit()
                current_app.logger.info(
                    f"Textkernel disabled. Candidate {new_candidate.candidate_id} status set to {new_candidate.current_status}.")
            return jsonify({'message': 'CV uploaded successfully. Parsing in progress if enabled.',
                            'candidate_id': str(new_candidate.candidate_id), 'filename': filename,
                            's3_key': file_key}), 201
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error during CV upload or candidate creation: {e}", exc_info=True)
            return jsonify({'error': f'Failed to upload CV: {str(e)}'}), 500
    return jsonify({'error': 'File processing error.'}), 400


@bp.route('/candidates', methods=['GET'], endpoint='get_all_candidates')
@bp.route('/candidates/<string:status_in_path>', methods=['GET'], endpoint='get_candidates_by_status')
@login_required
def get_candidates(status_in_path=None):
    if current_user.role != 'superadmin' and not current_user.company_id: return jsonify(
        {'error': 'User not associated with a company'}), 403
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    status_filter = status_in_path or request.args.get('status', None, type=str)
    search_term = request.args.get('search', None, type=str)
    query = Candidate.query
    if current_user.role == 'superadmin':
        company_id_param = request.args.get('company_id', type=int)
        if company_id_param:
            if not db.session.get(Company, company_id_param): return jsonify(
                {"error": f"Company with ID {company_id_param} not found."}), 404
            query = query.filter(Candidate.company_id == company_id_param)
    else:
        query = query.filter(Candidate.company_id == current_user.company_id)
    if status_filter and status_filter.lower() != 'all': query = query.filter(Candidate.current_status == status_filter)
    if search_term:
        search_ilike = f"%{search_term}%"
        query = query.filter(db.or_(Candidate.first_name.ilike(search_ilike), Candidate.last_name.ilike(search_ilike),
                                    Candidate.email.ilike(search_ilike), Candidate.skills_summary.ilike(search_ilike)))
    query = query.order_by(Candidate.submission_date.desc())
    try:
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        candidates_data = [candidate_obj.to_dict() for candidate_obj in pagination.items]
        total_results = pagination.total
        total_pages = pagination.pages
    except Exception as e:
        current_app.logger.error(f"Error during candidate pagination: {e}", exc_info=True)
        return jsonify({'error': 'Error fetching candidates list.'}), 500
    return jsonify({'candidates': candidates_data, 'total_results': total_results, 'total_pages': total_pages,
                    'current_page': pagination.page, 'has_next': pagination.has_next,
                    'has_prev': pagination.has_prev}), 200


@bp.route('/candidate/<string:candidate_uuid>', methods=['GET'])
@login_required
def get_candidate_detail(candidate_uuid):
    try:
        candidate_id_obj = uuid.UUID(candidate_uuid)
    except ValueError:
        return jsonify({'error': 'Invalid candidate UUID format'}), 400
    candidate = db.session.get(Candidate, candidate_id_obj)
    if not candidate: return jsonify({'error': 'Candidate not found'}), 404
    if current_user.role != 'superadmin' and current_user.company_id != candidate.company_id:
        current_app.logger.warning(
            f"User {current_user.id} (Company: {current_user.company_id}) attempted to access candidate {candidate.candidate_id} (Company: {candidate.company_id}) without permission.")
        return jsonify({'error': 'Forbidden: You do not have permission to view this candidate'}), 403
    cv_url = None
    if candidate.cv_storage_path:
        try:
            cv_url = s3_service_instance.create_presigned_url(candidate.cv_storage_path)
        except Exception as e:
            current_app.logger.error(
                f"Failed to generate presigned URL for CV {candidate.cv_storage_path} of candidate {candidate.candidate_id}: {e}",
                exc_info=True)
    return jsonify(candidate.to_dict(include_cv_url=True, cv_url=cv_url)), 200


@bp.route('/candidate/<string:candidate_uuid>', methods=['PUT'])
@login_required
def update_candidate_detail(candidate_uuid):
    try:
        candidate_id_obj = uuid.UUID(candidate_uuid)
    except ValueError:
        return jsonify({'error': 'Invalid candidate UUID format'}), 400
    candidate = db.session.get(Candidate, candidate_id_obj)
    if not candidate: return jsonify({'error': 'Candidate not found'}), 404
    if current_user.role != 'superadmin' and current_user.company_id != candidate.company_id:
        return jsonify({'error': 'Forbidden: You do not have permission to update this candidate'}), 403
    data = request.get_json()
    if not data: return jsonify({'error': 'No data provided for update'}), 400
    allowed_fields = [
        'first_name', 'last_name', 'email', 'phone_number', 'age',
        'education_summary', 'experience_summary', 'skills_summary',
        'languages', 'seminars', 'current_status', 'notes', 'hr_comments',
        'evaluation_rating', 'interview_datetime', 'interview_location', 'interview_type',
        'candidate_confirmation_status']
    updated_fields_log = {}
    for field in allowed_fields:
        if field in data:
            old_value = getattr(candidate, field, None)
            new_value = data[field]
            if field == 'email' and new_value is not None:
                new_value = new_value.lower().strip()
                if new_value == '': new_value = None
            if field == 'interview_datetime':
                if new_value == '' or new_value is None:
                    new_value = None
                elif isinstance(new_value, str):
                    try:
                        new_value = datetime.fromisoformat(new_value.replace('Z', '+00:00'))
                        if new_value.tzinfo is None: new_value = new_value.replace(tzinfo=dt_timezone.utc)
                    except ValueError:
                        return jsonify({'error': f'Invalid ISO format for interview_datetime: {data[field]}'}), 400
            if field == 'age':
                if new_value == '' or new_value is None:
                    new_value = None
                else:
                    try:
                        new_value = int(new_value)
                    except ValueError:
                        return jsonify({'error': f'Invalid value for age: {data[field]} must be a number.'}), 400
            if old_value != new_value:
                setattr(candidate, field, new_value)
                updated_fields_log[field] = {'old': str(old_value), 'new': str(new_value)}
    if 'positions' in data and isinstance(data['positions'], list):
        current_position_names = {pos.position_name for pos in candidate.positions}
        new_position_names = set(data['positions'])
        if current_position_names != new_position_names:
            updated_fields_log['positions'] = {'old': list(current_position_names), 'new': list(new_position_names)}
            candidate.positions = []
            for pos_name in new_position_names:
                if not pos_name.strip(): continue
                position = Position.query.filter_by(company_id=candidate.company_id,
                                                    position_name=pos_name.strip()).first()
                if not position:
                    position = Position(company_id=candidate.company_id, position_name=pos_name.strip(), status="Open")
                    db.session.add(position)
                candidate.positions.append(position)
    if 'offers' in data and isinstance(data['offers'], list):
        old_offers_for_log = candidate.offers if candidate.offers else []
        new_offers_for_db = []
        for offer_data_from_frontend in data['offers']:
            if not isinstance(offer_data_from_frontend, dict): continue
            processed_offer_for_db = {}
            offer_amount_val = offer_data_from_frontend.get('offer_amount')
            if offer_amount_val == '' or offer_amount_val is None:
                processed_offer_for_db['offer_amount'] = None
            else:
                try:
                    processed_offer_for_db['offer_amount'] = float(offer_amount_val)
                except (ValueError, TypeError):
                    current_app.logger.warning(
                        f"Invalid offer_amount '{offer_amount_val}' for candidate {candidate.candidate_id}. Setting to None.")
                    processed_offer_for_db['offer_amount'] = None
            processed_offer_for_db['offer_notes'] = offer_data_from_frontend.get('offer_notes', '').strip()
            offer_date_str_from_frontend = offer_data_from_frontend.get('offer_date')
            if offer_date_str_from_frontend:
                try:
                    if isinstance(offer_date_str_from_frontend, str):
                        dt_obj = datetime.fromisoformat(offer_date_str_from_frontend.replace('Z', '+00:00'))
                        processed_offer_for_db['offer_date'] = dt_obj.isoformat()
                    elif isinstance(offer_date_str_from_frontend, datetime):
                        processed_offer_for_db['offer_date'] = offer_date_str_from_frontend.isoformat()
                    else:
                        processed_offer_for_db['offer_date'] = None
                except ValueError:
                    current_app.logger.warning(
                        f"Invalid offer_date format '{offer_date_str_from_frontend}' for candidate {candidate.candidate_id}. Setting to None.")
                    processed_offer_for_db['offer_date'] = None
            else:
                processed_offer_for_db['offer_date'] = None
            if processed_offer_for_db['offer_amount'] is not None or processed_offer_for_db['offer_notes']:
                new_offers_for_db.append(processed_offer_for_db)
        if old_offers_for_log != new_offers_for_db:
            updated_fields_log['offers'] = {'old': old_offers_for_log, 'new': new_offers_for_db}
        candidate.offers = new_offers_for_db
    if not updated_fields_log: return jsonify({'message': 'No changes detected or no updatable fields provided.'}), 200
    candidate.add_history_event(event_type="CANDIDATE_MANUALLY_UPDATED",
                                description=f"Candidate details manually updated by {current_user.username}.",
                                actor_id=current_user.id, actor_username=current_user.username,
                                details={'updated_fields': updated_fields_log})
    candidate.updated_at = datetime.now(dt_timezone.utc)
    try:
        db.session.commit()
        updated_candidate = db.session.get(Candidate, candidate_id_obj)
        cv_url_after_update = None
        if updated_candidate.cv_storage_path:
            try:
                cv_url_after_update = s3_service_instance.create_presigned_url(updated_candidate.cv_storage_path)
            except Exception:
                pass
        return jsonify(updated_candidate.to_dict(include_cv_url=True, cv_url=cv_url_after_update)), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating candidate {candidate_uuid}: {e}", exc_info=True)
        return jsonify({'error': f'Failed to update candidate: {str(e)}'}), 500


@bp.route('/candidate/<string:candidate_uuid>', methods=['DELETE'])
@login_required
def delete_candidate(candidate_uuid):
    try:
        candidate_id_obj = uuid.UUID(candidate_uuid)
    except ValueError:
        return jsonify({'error': 'Invalid candidate UUID format'}), 400
    candidate = db.session.get(Candidate, candidate_id_obj)
    if not candidate: return jsonify({'error': 'Candidate not found'}), 404
    if current_user.role != 'superadmin' and current_user.company_id != candidate.company_id:
        return jsonify({'error': 'Forbidden: You do not have permission to delete this candidate'}), 403
    s3_path_to_delete = candidate.cv_storage_path
    candidate_full_name = candidate.full_name
    try:
        db.session.delete(candidate)
        db.session.commit()
        current_app.logger.info(
            f"Candidate {candidate_uuid} ('{candidate_full_name}') deleted by user {current_user.id}.")
        if s3_path_to_delete:
            try:
                s3_service_instance.delete_file(s3_path_to_delete)
                current_app.logger.info(
                    f"Successfully deleted CV {s3_path_to_delete} from S3 for deleted candidate {candidate_uuid}")
            except Exception as s3_e:
                current_app.logger.error(
                    f"Failed to delete CV {s3_path_to_delete} from S3 for candidate {candidate_uuid}: {s3_e}",
                    exc_info=True)
        return jsonify({'message': f"Candidate '{candidate_full_name}' deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting candidate {candidate_uuid}: {e}", exc_info=True)
        return jsonify({'error': f'Failed to delete candidate: {str(e)}'}), 500


@bp.route('/candidates/<string:candidate_uuid>/propose-interview', methods=['POST'])
@login_required
def propose_interview(candidate_uuid):
    if current_user.role not in ['company_admin', 'superadmin']:
        current_app.logger.warning(f"User {current_user.id} with role {current_user.role} tried to propose interview.")
        return jsonify({'error': 'Forbidden: User does not have permission to propose interviews'}), 403
    try:
        candidate_id_obj = uuid.UUID(candidate_uuid)
    except ValueError:
        return jsonify({'error': 'Invalid candidate UUID format'}), 400
    candidate = db.session.get(Candidate, candidate_id_obj)
    if not candidate: return jsonify({'error': 'Candidate not found'}), 404
    if current_user.role != 'superadmin' and current_user.company_id != candidate.company_id:
        current_app.logger.warning(
            f"User {current_user.id} (Company: {current_user.company_id}) tried to propose interview for candidate {candidate.candidate_id} (Company: {candidate.company_id}).")
        return jsonify({'error': 'Forbidden: User cannot manage interviews for this candidate'}), 403
    data = request.get_json()
    if not data: return jsonify({'error': 'No data provided'}), 400
    proposed_slots_data = data.get('proposed_slots')
    location = data.get('location')
    interview_type = data.get('interview_type')
    notes_for_candidate = data.get('notes_for_candidate', '')
    internal_notes = data.get('internal_notes', '')
    position_id_str = data.get('position_id')
    position_id = None
    if position_id_str:
        try:
            position_id = int(position_id_str)
            if position_id != 0 and not db.session.get(Position, position_id): return jsonify(
                {'error': f'Position with ID {position_id} not found.'}), 404
            if position_id == 0: position_id = None
        except ValueError:
            return jsonify({'error': 'Invalid position_id format.'}), 400
    if not proposed_slots_data or not isinstance(proposed_slots_data, list) or not (1 <= len(proposed_slots_data) <= 3):
        return jsonify({'error': 'Proposed slots are required (1 to 3 slots as a list of {start_time, end_time})'}), 400
    try:
        greece_tz = ZoneInfo("Europe/Athens")
    except Exception as tz_err:
        current_app.logger.error(f"Could not load Europe/Athens timezone: {tz_err}")
        return jsonify({'error': 'Server timezone configuration error.'}), 500
    parsed_utc_slots = []
    for i, slot_data in enumerate(proposed_slots_data):
        start_time_str = slot_data.get('start_time')
        end_time_str = slot_data.get('end_time')
        if not start_time_str or not end_time_str: return jsonify(
            {'error': f'Slot {i + 1} is missing start_time or end_time'}), 400
        try:
            naive_start_dt = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
            naive_end_dt = datetime.strptime(end_time_str, "%Y-%m-%d %H:%M:%S")
            local_aware_start_dt = naive_start_dt.replace(tzinfo=greece_tz)
            local_aware_end_dt = naive_end_dt.replace(tzinfo=greece_tz)
            if local_aware_end_dt <= local_aware_start_dt: return jsonify(
                {'error': f'Slot {i + 1} end_time must be after start_time'}), 400
            utc_start_dt = local_aware_start_dt.astimezone(dt_timezone.utc)
            utc_end_dt = local_aware_end_dt.astimezone(dt_timezone.utc)
            parsed_utc_slots.append({'start': utc_start_dt, 'end': utc_end_dt})
        except ValueError:
            current_app.logger.error(
                f"Invalid datetime format for slot {i + 1}: Start='{start_time_str}', End='{end_time_str}'",
                exc_info=True)
            return jsonify({
                               'error': f'Invalid datetime format for slot {i + 1}. Expected YYYY-MM-DD HH:MM:SS in local time.'}), 400
        except Exception as e_dt:
            current_app.logger.error(f"Unexpected error processing slot {i + 1} datetime: {e_dt}", exc_info=True)
            return jsonify({'error': f'Error processing datetime for slot {i + 1}: {str(e_dt)}'}), 500
    interview = Interview(
        candidate_id=candidate.candidate_id, recruiter_id=current_user.id, position_id=position_id,
        location=location, interview_type=interview_type, notes_for_candidate=notes_for_candidate,
        internal_notes=internal_notes, status=InterviewStatus.PROPOSED
    )
    if len(parsed_utc_slots) >= 1:
        interview.proposed_slot_1_start = parsed_utc_slots[0]['start']
        interview.proposed_slot_1_end = parsed_utc_slots[0]['end']
    if len(parsed_utc_slots) >= 2:
        interview.proposed_slot_2_start = parsed_utc_slots[1]['start']
        interview.proposed_slot_2_end = parsed_utc_slots[1]['end']
    if len(parsed_utc_slots) >= 3:
        interview.proposed_slot_3_start = parsed_utc_slots[2]['start']
        interview.proposed_slot_3_end = parsed_utc_slots[2]['end']
    interview.generate_confirmation_token()
    try:
        db.session.add(interview)
        db.session.flush()
        candidate.add_history_event(
            event_type="INTERVIEW_PROPOSED",
            description=f"Interview proposed by {current_user.username}. Awaiting candidate's response.",
            actor_id=current_user.id, actor_username=current_user.username,
            details={
                'interview_id': interview.id, 'location': location or "N/A", 'type': interview_type or "N/A",
                'position_id': position_id, 'proposed_slots_count': len(parsed_utc_slots)
            }
        )
        if candidate.current_status in ['Interested', 'Accepted', 'NeedsReview']:
            candidate.current_status = "Interview Proposed"
            current_app.logger.info(f"Candidate {candidate.candidate_id} status updated to 'Interview Proposed'.")
        db.session.commit()
        try:
            # ΣΩΣΤΗ ΚΛΗΣΗ TASK ΜΕ ΒΑΣΗ ΤΟ ΟΝΟΜΑ ΠΟΥ ΟΡΙΖΕΤΑΙ ΣΤΟ DECORATOR ΤΟΥ TASK
            # Βεβαιώσου ότι το task στο communication.py έχει name='tasks.communication.send_interview_proposal_email_task'
            task_name = 'tasks.communication.send_interview_proposal_email_task'
            celery.send_task(task_name, args=[interview.id])
            current_app.logger.info(f"Celery task '{task_name}' dispatched for interview {interview.id}")
        except Exception as celery_e:
            current_app.logger.error(
                f"Error dispatching Celery task '{task_name}' for interview {interview.id}: {celery_e}", exc_info=True)
        return jsonify(interview.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating interview proposal for candidate {candidate_uuid}: {e}",
                                 exc_info=True)
        return jsonify({'error': 'An unexpected error occurred while proposing the interview.'}), 500


def render_interview_action_page(title, message, status_class="is-success", company_name_for_link="NEXONA"):
    app_home_url = current_app.config.get('FRONTEND_URL', 'http://localhost:5173')
    try:
        return render_template('interview_action_feedback.html',
                               title=title, message=message, status_class=status_class,
                               company_name=company_name_for_link, app_home_url=app_home_url)
    except Exception as e_render:
        current_app.logger.error(f"Failed to render interview_action_feedback.html: {e_render}", exc_info=True)
        status_code = 200 if status_class == "is-success" else 400
        html_response = f"<h1>{title}</h1><p>{message}</p>"
        if app_home_url: html_response += f"<p><a href='{app_home_url}'>Return to Homepage</a></p>"
        return html_response, status_code


@bp.route('/interviews/confirm/<string:token>/<int:slot_choice>', methods=['GET'])
def confirm_interview_slot(token, slot_choice):
    interview = Interview.query.filter_by(confirmation_token=token).first()
    company_name_for_page = "Our Company"
    if interview and interview.recruiter and interview.recruiter.company:
        company_name_for_page = interview.recruiter.company.name
    elif interview and interview.candidate and interview.candidate.company:
        company_name_for_page = interview.candidate.company.name
    if not interview:
        current_app.logger.warning(f"confirm_interview_slot: Invalid or non-existent token: {token}")
        return render_interview_action_page("Error", "Invalid or expired confirmation link.", "is-danger",
                                            company_name_for_page), 404
    if not interview.is_token_valid() or interview.status != InterviewStatus.PROPOSED:
        current_app.logger.warning(
            f"confirm_interview_slot: Token expired or interview not PROPOSED for token: {token}. Status: {interview.status.value if interview.status else 'N/A'}")
        return render_interview_action_page("Error", "This link has expired or the invitation is no longer active.",
                                            "is-danger", company_name_for_page), 400
    selected_slot_start, selected_slot_end = None, None
    slot_map = {
        1: (interview.proposed_slot_1_start, interview.proposed_slot_1_end),
        2: (interview.proposed_slot_2_start, interview.proposed_slot_2_end),
        3: (interview.proposed_slot_3_start, interview.proposed_slot_3_end),
    }
    if slot_choice in slot_map and slot_map[slot_choice][0] and slot_map[slot_choice][1]:
        selected_slot_start, selected_slot_end = slot_map[slot_choice]
    else:
        current_app.logger.warning(f"confirm_interview_slot: Invalid slot_choice {slot_choice} for token: {token}")
        return render_interview_action_page("Error", "Invalid slot selection.", "is-danger", company_name_for_page), 400
    interview.scheduled_start_time = selected_slot_start
    interview.scheduled_end_time = selected_slot_end
    interview.status = InterviewStatus.SCHEDULED
    interview.confirmation_token = None
    interview.token_expiration = None
    candidate = interview.candidate
    if candidate:
        candidate.current_status = "Interview Scheduled"
        candidate.interview_datetime = selected_slot_start
        candidate.interview_location = interview.location
        candidate.interview_type = interview.interview_type
        candidate.candidate_confirmation_status = "Confirmed"
        candidate.add_history_event(
            event_type="INTERVIEW_SCHEDULED_BY_CANDIDATE",
            description=f"Candidate confirmed interview for slot {slot_choice} ({selected_slot_start.strftime('%Y-%m-%d %H:%M UTC') if selected_slot_start else 'N/A'}).",
            actor_username=candidate.get_full_name() or "Candidate",
            details={'interview_id': interview.id,
                     'scheduled_time_utc': selected_slot_start.isoformat() if selected_slot_start else None,
                     'location': interview.location or "N/A", 'type': interview.interview_type or "N/A"}
        )
    try:
        db.session.commit()
        current_app.logger.info(f"Interview {interview.id} confirmed by candidate for slot {slot_choice}.")
        greece_tz = ZoneInfo("Europe/Athens")
        confirmed_time_display = selected_slot_start.astimezone(greece_tz).strftime(
            "%A, %d %B %Y at %H:%M (%Z)") if selected_slot_start else "N/A"
        # Εδώ θα καλούσες τα tasks για email επιβεβαίωσης
        # celery.send_task('tasks.communication.send_interview_confirmation_to_candidate_task', args=[interview.id])
        # celery.send_task('tasks.communication.send_interview_confirmation_to_recruiter_task', args=[interview.id])
        return render_interview_action_page("Interview Confirmed",
                                            f"Thank you! Your interview has been scheduled for: <strong>{confirmed_time_display}</strong>. You will receive a confirmation email shortly.",
                                            company_name_for_link=company_name_for_page)
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error confirming interview slot for token {token}: {e}", exc_info=True)
        return render_interview_action_page("System Error",
                                            "An error occurred while confirming your selection. Please try again later or contact us.",
                                            "is-danger", company_name_for_page), 500


@bp.route('/interviews/reject/<string:token>', methods=['GET'])
def reject_interview_slots(token):
    interview = Interview.query.filter_by(confirmation_token=token).first()
    company_name_for_page = "Our Company"
    if interview and interview.recruiter and interview.recruiter.company:
        company_name_for_page = interview.recruiter.company.name
    elif interview and interview.candidate and interview.candidate.company:
        company_name_for_page = interview.candidate.company.name
    if not interview: return render_interview_action_page("Error", "Invalid or expired link.", "is-danger",
                                                          company_name_for_page), 404
    if not interview.is_token_valid() or interview.status != InterviewStatus.PROPOSED:
        return render_interview_action_page("Error", "This link has expired or the invitation is no longer active.",
                                            "is-danger", company_name_for_page), 400
    interview.status = InterviewStatus.CANDIDATE_REJECTED_ALL
    interview.confirmation_token = None
    interview.token_expiration = None
    candidate = interview.candidate
    if candidate:
        candidate.candidate_confirmation_status = "Declined"
        candidate.add_history_event(event_type="INTERVIEW_SLOTS_REJECTED_BY_CANDIDATE",
                                    description="Candidate indicated no proposed slots are suitable.",
                                    actor_username=candidate.get_full_name() or "Candidate",
                                    details={'interview_id': interview.id})
    try:
        db.session.commit()
        current_app.logger.info(f"Interview {interview.id} slots rejected by candidate (token: {token}).")
        # celery.send_task('tasks.communication.send_interview_rejection_to_recruiter_task', args=[interview.id])
        return render_interview_action_page("Interview Slots Declined",
                                            "Thank you for your response. Your preference has been recorded. A recruiter may contact you if further discussion is needed.",
                                            company_name_for_link=company_name_for_page)
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error rejecting interview slots for token {token}: {e}", exc_info=True)
        return render_interview_action_page("System Error", "An error occurred. Please try again later.", "is-danger",
                                            company_name_for_page), 500


@bp.route('/interviews/cancel-by-candidate/<string:token>', methods=['GET'])
def cancel_interview_by_candidate(token):
    interview = Interview.query.filter_by(confirmation_token=token).first()
    company_name_for_page = "Our Company"
    if interview and interview.recruiter and interview.recruiter.company:
        company_name_for_page = interview.recruiter.company.name
    elif interview and interview.candidate and interview.candidate.company:
        company_name_for_page = interview.candidate.company.name
    if not interview: return render_interview_action_page("Error",
                                                          "Invalid or expired cancellation link. The interview may have already been actioned or cancelled.",
                                                          "is-danger", company_name_for_page), 404
    if interview.status not in [InterviewStatus.PROPOSED,
                                InterviewStatus.SCHEDULED] or interview.confirmation_token != token or not interview.is_token_valid():
        message = "This interview cannot be cancelled via this link. It may have already been completed, cancelled, or the link has expired."
        if interview.status == InterviewStatus.CANCELLED_BY_CANDIDATE:
            message = "This interview has already been cancelled by you."
        elif interview.status == InterviewStatus.CANCELLED_BY_RECRUITER:
            message = "This interview has been cancelled by the recruiter."
        return render_interview_action_page("Information", message, "is-warning", company_name_for_page), 400
    cancellation_reason_from_query = request.args.get('reason', '').strip()[:500]
    original_status_before_cancel = interview.status
    interview.status = InterviewStatus.CANCELLED_BY_CANDIDATE
    if cancellation_reason_from_query: interview.cancellation_reason_candidate = cancellation_reason_from_query
    interview.confirmation_token = None
    interview.token_expiration = None
    candidate = interview.candidate
    if candidate:
        event_description = f"Candidate cancelled interview (was {original_status_before_cancel.value})."
        if cancellation_reason_from_query: event_description += f" Reason: {cancellation_reason_from_query}"
        candidate.candidate_confirmation_status = "Cancelled"
        candidate.add_history_event(
            event_type="INTERVIEW_CANCELLED_BY_CANDIDATE", description=event_description,
            actor_username=candidate.get_full_name() or "Candidate",
            details={'interview_id': interview.id, 'reason': cancellation_reason_from_query or "N/A",
                     'previous_status': original_status_before_cancel.value}
        )
    try:
        db.session.commit()
        current_app.logger.info(
            f"Interview {interview.id} cancelled by candidate (token: {token}). Reason: {cancellation_reason_from_query or 'N/A'}")
        # celery.send_task('tasks.communication.send_interview_cancellation_to_recruiter_task', args=[interview.id, cancellation_reason_from_query or None])
        return render_interview_action_page("Interview Cancelled",
                                            "Your interview has been successfully cancelled. Thank you for letting us know.",
                                            company_name_for_link=company_name_for_page)
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error cancelling interview by candidate for token {token}: {e}", exc_info=True)
        return render_interview_action_page("System Error",
                                            "An error occurred while cancelling. Please try again later.", "is-danger",
                                            company_name_for_page), 500


@bp.route('/user/settings', methods=['GET'])
@login_required
def get_user_settings():
    user_settings = {
        'username': current_user.username, 'email': current_user.email,
        'enable_email_interview_reminders': current_user.enable_email_interview_reminders,
        'interview_reminder_lead_time_minutes': current_user.interview_reminder_lead_time_minutes
    }
    return jsonify(user_settings), 200


@bp.route('/user/settings', methods=['PUT'])
@login_required
def update_user_settings():
    data = request.get_json()
    if not data: return jsonify({'error': 'No data provided'}), 400
    updated_fields_count = 0
    if 'enable_email_interview_reminders' in data:
        new_val = bool(data['enable_email_interview_reminders'])
        if current_user.enable_email_interview_reminders != new_val:
            current_user.enable_email_interview_reminders = new_val
            updated_fields_count += 1
    if 'interview_reminder_lead_time_minutes' in data:
        try:
            lead_time = int(data['interview_reminder_lead_time_minutes'])
            if not (5 <= lead_time <= 2880):
                return jsonify({'error': 'Interview reminder lead time must be between 5 and 2880 minutes.'}), 400
            if current_user.interview_reminder_lead_time_minutes != lead_time:
                current_user.interview_reminder_lead_time_minutes = lead_time
                updated_fields_count += 1
        except (ValueError, TypeError):
            return jsonify(
                {'error': 'Invalid value for interview_reminder_lead_time_minutes. Must be an integer.'}), 400
    if updated_fields_count == 0: return jsonify({'message': 'No settings were changed.'}), 200
    current_user.updated_at = datetime.now(dt_timezone.utc)
    try:
        db.session.commit()
        updated_settings_response = {
            'enable_email_interview_reminders': current_user.enable_email_interview_reminders,
            'interview_reminder_lead_time_minutes': current_user.interview_reminder_lead_time_minutes
        }
        current_app.logger.info(f"User {current_user.id} updated their settings.")
        return jsonify({'message': 'User settings updated successfully', 'settings': updated_settings_response}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating user settings for user {current_user.id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to update user settings.'}), 500