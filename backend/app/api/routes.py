from flask import Blueprint, request, jsonify, current_app, render_template
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from app import db, s3_service_instance, celery
from app.models import (
    User, Company, Candidate, Position, CompanySettings,
    Interview, InterviewStatus, InterviewSlot # <<< ΠΡΟΣΘΗΚΗ InterviewSlot
)
from app.config import Config
from datetime import datetime, timedelta, timezone as dt_timezone # dt_timezone είναι το UTC
from zoneinfo import ZoneInfo
import uuid
from sqlalchemy import func, and_

bp = Blueprint('api', __name__, url_prefix='/api/v1')

# ... (το try-except block για το logging του blueprint παραμένει ίδιο) ...
try:
    if current_app:
        current_app.logger.info(
            f"DEBUG: Blueprint 'bp' defined in app.api.routes with url_prefix: {bp.url_prefix if bp else 'bp is None'}")
    else:
        import logging as temp_logger_routes
        temp_logger_routes.basicConfig(level=temp_logger_routes.INFO)
        temp_logger_routes.info(
            f"DEBUG: Blueprint 'bp' defined in app.api.routes (current_app not available yet). url_prefix: {bp.url_prefix if bp else 'bp is None'}")
except NameError:
    import logging as temp_logger_routes_fallback
    temp_logger_routes_fallback.basicConfig(level=temp_logger_routes_fallback.INFO)
    temp_logger_routes_fallback.warning("current_app not available at blueprint definition in routes.py")


# === Authentication Routes ===
# ... (register, login, logout, session_status παραμένουν ίδια με τον κώδικα που μου έστειλες) ...
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

# === Dashboard Summary ===
# ... (dashboard_summary παραμένει ίδιο με τον κώδικα που μου έστειλες) ...
@bp.route('/dashboard/summary', methods=['GET'])
@login_required
def dashboard_summary():
    current_app.logger.info(
        f"--- HIT /api/v1/dashboard/summary (user: {current_user.id if current_user.is_authenticated else 'Guest'}, role: {current_user.role if current_user.is_authenticated else 'N/A'}, company_id from user: {current_user.company_id if current_user.is_authenticated else 'N/A'}) ---")
    current_app.logger.info(f"Request args for summary: {request.args}")

    if current_user.role != 'superadmin' and not current_user.company_id:
        current_app.logger.warning(f"Dashboard access DENIED (not SA, no company_id) for user {current_user.id}.")
        return jsonify({"error": "User not associated with a company"}), 403

    company_id_to_filter = None
    if current_user.role == 'superadmin':
        company_id_param_str = request.args.get('company_id')
        if company_id_param_str:
            try:
                company_id_to_filter = int(company_id_param_str)
                if not db.session.get(Company, company_id_to_filter):
                    return jsonify({"error": f"Company with ID {company_id_to_filter} not found."}), 404
            except ValueError:
                return jsonify({"error": f"Invalid company_id format: {company_id_param_str}"}), 400
    else:
        company_id_to_filter = current_user.company_id

    now_utc = datetime.now(dt_timezone.utc)
    summary_data = {}

    candidate_query_base = Candidate.query
    position_query_base = Position.query
    interview_query_base = Interview.query # Αλλαγή: Δεν κάνουμε join με Candidate εδώ, θα φιλτράρουμε με το company_id του Interview

    if company_id_to_filter:
        candidate_query_base = candidate_query_base.filter(Candidate.company_id == company_id_to_filter)
        position_query_base = position_query_base.filter(Position.company_id == company_id_to_filter)
        interview_query_base = interview_query_base.filter(Interview.company_id == company_id_to_filter) # Φίλτρο στο Interview.company_id

    summary_data['total_candidates'] = candidate_query_base.count()
    summary_data['active_positions'] = position_query_base.filter(Position.status == 'Open').count()
    summary_data['upcoming_interviews'] = interview_query_base.filter(
        Interview.status == InterviewStatus.SCHEDULED,
        Interview.scheduled_start_time > now_utc
    ).count()

    stages_for_count = [
        "New", "Processing", "NeedsReview", "Accepted", "Interested",
        "Interview Proposed", "Interview Scheduled", "Interviewing", "Evaluation",
        "OfferMade", "Hired", "Rejected", "Declined", "ParsingFailed", "On Hold"
    ]
    candidates_by_stage_list = []
    for stage in stages_for_count:
        count_query = Candidate.query.filter(Candidate.current_status == stage)
        if company_id_to_filter:
            count_query = count_query.filter(Candidate.company_id == company_id_to_filter)
        count = count_query.count()
        stage_key = stage.lower().replace(" ", "") # π.χ., needsreview
        summary_data[stage_key] = count
        candidates_by_stage_list.append({"stage_name": stage, "count": count}) # Για το γράφημα
    summary_data["candidates_by_stage"] = candidates_by_stage_list


    days_stuck_threshold = 5
    stuck_in_needs_review_query = Candidate.query.filter(
        Candidate.current_status == 'NeedsReview',
        Candidate.submission_date < (now_utc - timedelta(days=days_stuck_threshold))
    )
    if company_id_to_filter:
        stuck_in_needs_review_query = stuck_in_needs_review_query.filter(Candidate.company_id == company_id_to_filter)
    summary_data['stuck_in_needs_review_X_days'] = stuck_in_needs_review_query.count()
    summary_data['stuck_in_needs_review_threshold_days'] = days_stuck_threshold

    hired_count_for_rate = summary_data.get('hired', 0)
    declined_count_for_rate = summary_data.get('declined', 0)
    total_offers_considered_actioned = hired_count_for_rate + declined_count_for_rate
    if total_offers_considered_actioned > 0:
        summary_data['offer_acceptance_rate'] = round((hired_count_for_rate / total_offers_considered_actioned) * 100, 1)
    else:
        summary_data['offer_acceptance_rate'] = "N/A"

    avg_time_in_needs_review_seconds_query = db.session.query(
        func.avg(func.extract('epoch', now_utc - Candidate.submission_date))
    ).filter(
        Candidate.current_status == 'NeedsReview'
    )
    if company_id_to_filter:
        avg_time_in_needs_review_seconds_query = avg_time_in_needs_review_seconds_query.filter(
            Candidate.company_id == company_id_to_filter)
    avg_seconds_result = avg_time_in_needs_review_seconds_query.scalar()
    if avg_seconds_result is not None:
        summary_data['avg_days_in_needs_review'] = round(avg_seconds_result / (24 * 60 * 60), 1)
    else:
        summary_data['avg_days_in_needs_review'] = "N/A"

    interview_scheduled_count = summary_data.get('interviewscheduled', 0)
    initial_pipeline_sum = (summary_data.get('new', 0) +
                            summary_data.get('processing', 0) +
                            summary_data.get('needsreview', 0) +
                            summary_data.get('accepted', 0) +
                            summary_data.get('interested', 0))
    denominator_for_interview_rate = initial_pipeline_sum + interview_scheduled_count
    if denominator_for_interview_rate > 0:
        summary_data['interview_conversion_rate'] = round((interview_scheduled_count / denominator_for_interview_rate) * 100, 1)
    else:
        summary_data['interview_conversion_rate'] = "N/A" if interview_scheduled_count == 0 else 100.0

    current_app.logger.info(
        f"Dashboard summary successfully generated for user {current_user.id}, company_filter: {company_id_to_filter}. Data: {summary_data}")
    return jsonify(summary_data), 200

# === Candidate Routes ===
# ... (upload_cv, get_candidates, get_candidate_detail, update_candidate_detail, delete_candidate παραμένουν ίδια με τον κώδικα που μου έστειλες) ...
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
            return jsonify({'error': 'Superadmin must specify a target company ID for upload.'}), 400
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

            placeholder_email = f"placeholder-{uuid.uuid4()}@example.com"
            new_candidate = Candidate(company_id=target_company_id, cv_original_filename=filename,
                                      cv_storage_path=file_key, current_status='Processing', email=placeholder_email)
            db.session.add(new_candidate)
            db.session.flush()

            if position_name_from_form and position_name_from_form.strip():
                position = Position.query.filter_by(company_id=target_company_id,
                                                    position_name=position_name_from_form.strip()).first()
                if not position:
                    position = Position(company_id=target_company_id, position_name=position_name_from_form.strip(),
                                        status="Open")
                    db.session.add(position)
                if position not in new_candidate.positions:
                    new_candidate.positions.append(position)

            new_candidate.add_history_event(event_type="CV_UPLOADED",
                                            description=f"CV '{filename}' uploaded.",
                                            details={"s3_key": file_key,
                                                     "position_applied": position_name_from_form or "N/A"})
            db.session.commit()

            if Config.TEXTKERNEL_ENABLED:
                celery.send_task('tasks.parsing.parse_cv_task',
                                 args=[str(new_candidate.candidate_id), file_key, target_company_id])
            else:
                new_candidate.current_status = 'NeedsReview'
                new_candidate.add_history_event(event_type="PARSING_SKIPPED",
                                                description="Textkernel parsing is disabled. Manual review needed.")
                db.session.commit()
            return jsonify({'message': 'CV uploaded successfully. Parsing in progress if enabled.',
                            'candidate_id': str(new_candidate.candidate_id)}), 201
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error during CV upload or candidate creation: {e}", exc_info=True)
            return jsonify({'error': f'Failed to upload CV: {str(e)}'}), 500
    return jsonify({'error': 'File processing error.'}), 400


@bp.route('/candidates', methods=['GET'], endpoint='get_all_candidates_main')
@bp.route('/candidates/<string:status_in_path>', methods=['GET'], endpoint='get_candidates_by_status_main')
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
                                    Candidate.email.ilike(search_ilike), Candidate.skills_summary.ilike(search_ilike),
                                    Candidate.notes.ilike(search_ilike),
                                    Candidate.hr_comments.ilike(search_ilike)))

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
        'evaluation_rating', 'candidate_confirmation_status'
    ]
    updated_fields_log = {}
    status_changed = False
    old_status_for_log = candidate.current_status
    new_status_from_payload = data.get('current_status')

    if new_status_from_payload == 'NeedsReview' and old_status_for_log in ['Declined', 'Rejected', 'ParsingFailed']:
        candidate.evaluation_rating = None
        candidate.candidate_confirmation_status = None
        # Καθαρισμός παλιών πεδίων συνέντευξης (αν υπάρχουν στο candidate model)
        if hasattr(candidate, 'interview_datetime'): candidate.interview_datetime = None
        if hasattr(candidate, 'interview_location'): candidate.interview_location = None
        if hasattr(candidate, 'interview_type'): candidate.interview_type = None
        # Καθαρισμός ενεργών συνεντεύξεων (Interview model) - Πιο σύνθετο, ίσως να γίνει χειροκίνητα ή με task
        active_interviews = Interview.query.filter_by(candidate_id=candidate.candidate_id).filter(
            Interview.status.in_([InterviewStatus.PROPOSED, InterviewStatus.SCHEDULED, InterviewStatus.COMPLETED, InterviewStatus.EVALUATION_POSITIVE, InterviewStatus.EVALUATION_NEGATIVE])
        ).all()
        for inv in active_interviews:
            inv.status = InterviewStatus.CANCELLED_BY_RECRUITER # ή ένα νέο status "CANCELLED_DUE_TO_REEVALUATION"
            inv.internal_notes = (inv.internal_notes or "") + "\nCancelled due to candidate re-evaluation."
        updated_fields_log['re_evaluation_reset'] = {
            'evaluation_rating': 'cleared', 'candidate_confirmation_status': 'cleared',
            'active_interviews_cancelled': len(active_interviews)
        }
        current_app.logger.info(
            f"Candidate {candidate.candidate_id} re-evaluated. Resetting fields and cancelling {len(active_interviews)} active interviews.")


    for field in allowed_fields:
        if field in data:
            old_value = getattr(candidate, field, None)
            new_value = data[field]
            if field == 'email' and new_value is not None: new_value = new_value.lower().strip()
            if field == 'age':
                if new_value == '' or new_value is None: new_value = None
                else:
                    try: new_value = int(new_value)
                    except ValueError: return jsonify({'error': f'Invalid value for age: {data[field]} must be a number.'}), 400
            if old_value != new_value:
                setattr(candidate, field, new_value)
                updated_fields_log[field] = {'old': str(old_value), 'new': str(new_value)}
                if field == 'current_status': status_changed = True

    if 'positions' in data and isinstance(data['positions'], list):
        current_position_names = {pos.position_name for pos in candidate.positions}
        new_position_names_from_data = {p_name.strip() for p_name in data['positions'] if isinstance(p_name, str) and p_name.strip()}
        if current_position_names != new_position_names_from_data:
            updated_fields_log['positions'] = {'old': list(current_position_names), 'new': list(new_position_names_from_data)}
            new_positions_for_candidate = []
            for pos_name in new_position_names_from_data:
                position = Position.query.filter_by(company_id=candidate.company_id, position_name=pos_name).first()
                if not position:
                    position = Position(company_id=candidate.company_id, position_name=pos_name, status="Open")
                    db.session.add(position)
                new_positions_for_candidate.append(position)
            candidate.positions = new_positions_for_candidate

    if 'offers' in data and isinstance(data['offers'], list):
        old_offers_for_log = candidate.offers if candidate.offers else []
        new_offers_for_db = []
        for offer_data_from_frontend in data['offers']:
            if not isinstance(offer_data_from_frontend, dict): continue
            processed_offer_for_db = {}
            offer_amount_val = offer_data_from_frontend.get('offer_amount')
            if offer_amount_val == '' or offer_amount_val is None: processed_offer_for_db['offer_amount'] = None
            else:
                try: processed_offer_for_db['offer_amount'] = float(offer_amount_val)
                except (ValueError, TypeError): processed_offer_for_db['offer_amount'] = None
            processed_offer_for_db['offer_notes'] = offer_data_from_frontend.get('offer_notes', '').strip()
            offer_date_str = offer_data_from_frontend.get('offer_date')
            if offer_date_str:
                try:
                    dt_obj = datetime.fromisoformat(offer_date_str.replace('Z', '+00:00'))
                    processed_offer_for_db['offer_date'] = dt_obj.isoformat()
                except ValueError: processed_offer_for_db['offer_date'] = None
            else: processed_offer_for_db['offer_date'] = None
            if processed_offer_for_db['offer_amount'] is not None or processed_offer_for_db['offer_notes']:
                new_offers_for_db.append(processed_offer_for_db)
        if old_offers_for_log != new_offers_for_db:
            updated_fields_log['offers'] = {'old': old_offers_for_log, 'new': new_offers_for_db}
        candidate.offers = new_offers_for_db

    if not updated_fields_log: return jsonify({'message': 'No changes detected or no updatable fields provided.'}), 200

    history_description = f"Candidate details manually updated."
    if status_changed:
        history_description = f"Status changed from '{old_status_for_log}' to '{candidate.current_status}'."
        if len(updated_fields_log) > 1: history_description += " Other fields also updated."
    elif updated_fields_log:
        history_description = f"Candidate details updated (status remained '{candidate.current_status}')."

    candidate.add_history_event(event_type="CANDIDATE_MANUALLY_UPDATED", description=history_description, details={'updated_fields': updated_fields_log})
    candidate.updated_at = datetime.now(dt_timezone.utc)
    try:
        db.session.commit()
        updated_candidate = db.session.get(Candidate, candidate_id_obj)
        cv_url_after_update = None
        if updated_candidate.cv_storage_path:
            try: cv_url_after_update = s3_service_instance.create_presigned_url(updated_candidate.cv_storage_path)
            except Exception: pass
        candidate_data_to_return = updated_candidate.to_dict(include_cv_url=True, cv_url=cv_url_after_update)
        return jsonify(candidate_data_to_return), 200
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

    can_delete = False
    if current_user.role == 'superadmin': can_delete = True
    elif current_user.role == 'company_admin' and current_user.company_id == candidate.company_id: can_delete = True

    if not can_delete:
        current_app.logger.warning(
            f"User {current_user.username} (Role: {current_user.role}, Company: {current_user.company_id}) "
            f"attempted to delete candidate {candidate.candidate_id} (Company: {candidate.company_id}) without permission.")
        return jsonify({'error': 'Forbidden: You do not have permission to delete this candidate'}), 403

    s3_path_to_delete = candidate.cv_storage_path
    candidate_full_name_for_log = candidate.full_name

    try:
        db.session.delete(candidate) # Οι συνεντεύξεις και τα slots θα διαγραφούν μέσω cascade delete
        db.session.commit()
        current_app.logger.info(
            f"Candidate {candidate_uuid} ('{candidate_full_name_for_log}') deleted by user {current_user.username} (ID: {current_user.id}).")
        if s3_path_to_delete:
            try:
                s3_service_instance.delete_file(s3_path_to_delete)
                current_app.logger.info(
                    f"Successfully deleted CV {s3_path_to_delete} from S3 for deleted candidate {candidate_uuid}")
            except Exception as s3_e:
                current_app.logger.error(
                    f"Failed to delete CV {s3_path_to_delete} from S3 for candidate {candidate_uuid}: {s3_e}",
                    exc_info=True)
        return jsonify({'message': f"Candidate '{candidate_full_name_for_log}' deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting candidate {candidate_uuid}: {e}", exc_info=True)
        return jsonify({'error': f'Failed to delete candidate: {str(e)}'}), 500


# --- ΕΝΗΜΕΡΩΜΕΝΗ ΣΥΝΑΡΤΗΣΗ propose_interview ---
@bp.route('/candidates/<string:candidate_uuid>/propose-interview', methods=['POST'])
@login_required
def propose_interview(candidate_uuid):
    current_app.logger.info(f"Propose interview called by user {current_user.id} (Role: {current_user.role}) for candidate {candidate_uuid}")
    # Επιτρέπουμε σε company_admin, superadmin (και user αν το επιθυμείς)
    if current_user.role not in ['company_admin', 'superadmin', 'user']:
        current_app.logger.warning(f"User {current_user.id} with role {current_user.role} tried to propose interview (Permission Denied).")
        return jsonify({'error': 'Forbidden: User does not have permission to propose interviews'}), 403
    try:
        candidate_id_obj = uuid.UUID(candidate_uuid)
    except ValueError:
        current_app.logger.error(f"Invalid candidate UUID format: {candidate_uuid}")
        return jsonify({'error': 'Invalid candidate UUID format'}), 400

    candidate = db.session.get(Candidate, candidate_id_obj)
    if not candidate:
        current_app.logger.error(f"Candidate not found for UUID: {candidate_uuid} during propose interview.")
        return jsonify({'error': 'Candidate not found'}), 404

    # Έλεγχος αν ο χρήστης (αν δεν είναι superadmin) ανήκει στην ίδια εταιρεία με τον υποψήφιο
    if current_user.role != 'superadmin' and current_user.company_id != candidate.company_id:
        current_app.logger.warning(
            f"User {current_user.id} (company {current_user.company_id}) "
            f"tried to propose interview for candidate {candidate.candidate_id} (company {candidate.company_id}) - Mismatched company."
        )
        return jsonify({'error': 'Forbidden: User cannot manage interviews for this candidate'}), 403

    data = request.get_json()
    if not data:
        current_app.logger.error(f"No data provided for propose interview for candidate {candidate_uuid}.")
        return jsonify({'error': 'No data provided'}), 400

    current_app.logger.debug(f"Received payload for propose interview (candidate {candidate_uuid}): {data}")

    proposed_slots_data = data.get('proposed_slots')
    location = data.get('location')
    interview_type = data.get('interview_type')
    notes_for_candidate = data.get('notes_for_candidate', '')
    internal_notes = data.get('internal_notes', '')
    position_id_str = data.get('position_id')
    position_id = None

    if position_id_str and position_id_str.strip() != "":
        try:
            position_id = int(position_id_str)
            if position_id == 0: # Αν 0 σημαίνει "χωρίς συγκεκριμένη θέση"
                position_id = None
            elif position_id is not None:
                 pos_obj = db.session.get(Position, position_id)
                 if not pos_obj:
                    current_app.logger.error(f"Propose Interview: Position with ID {position_id} not found for candidate {candidate_uuid}.")
                    return jsonify({'error': f'Position with ID {position_id} not found.'}), 404
                 if pos_obj.company_id != candidate.company_id: # Έλεγχος αν η θέση ανήκει στην εταιρεία του υποψηφίου
                    current_app.logger.error(
                        f"Propose Interview: Position {position_id} (company {pos_obj.company_id}) "
                        f"does not belong to candidate's company {candidate.company_id}."
                    )
                    return jsonify({'error': 'Selected position does not belong to the candidate\'s company.'}), 400
        except ValueError:
            current_app.logger.error(f"Propose Interview: Invalid position_id format: {position_id_str} for candidate {candidate_uuid}")
            return jsonify({'error': 'Invalid position_id format.'}), 400

    if not proposed_slots_data or not isinstance(proposed_slots_data, list) or not (1 <= len(proposed_slots_data) <= 3):
        current_app.logger.error(f"Invalid proposed_slots data for candidate {candidate_uuid}: {proposed_slots_data}")
        return jsonify({'error': 'Proposed slots are required (1 to 3 slots as a list of {start_time, end_time})'}), 400

    try:
        greece_tz = ZoneInfo("Europe/Athens")
    except Exception as tz_err:
        current_app.logger.critical(f"Could not load Europe/Athens timezone: {tz_err}", exc_info=True)
        return jsonify({'error': 'Server timezone configuration error.'}), 500

    interview = Interview(
        candidate_id=candidate.candidate_id,
        company_id=candidate.company_id, # ΣΗΜΑΝΤΙΚΟ: Το company_id της συνέντευξης
        recruiter_id=current_user.id,
        position_id=position_id,
        location=location,
        interview_type=interview_type,
        notes_for_candidate=notes_for_candidate,
        internal_notes=internal_notes,
        status=InterviewStatus.PROPOSED
    )
    interview.generate_confirmation_token()
    db.session.add(interview)

    try:
        db.session.flush() # Για να πάρουμε το interview.id για τα slots
        current_app.logger.info(f"Interview object (ID: {interview.id}) created and flushed for candidate {candidate_uuid}.")
    except Exception as e_flush:
        db.session.rollback()
        current_app.logger.error(f"Error flushing session for new interview for candidate {candidate_uuid}: {e_flush}", exc_info=True)
        return jsonify({'error': 'Database error during interview creation (flush).'}), 500

    created_interview_slots = []
    for i, slot_data in enumerate(proposed_slots_data):
        start_time_str = slot_data.get('start_time')
        end_time_str = slot_data.get('end_time')

        if not start_time_str or not end_time_str:
            current_app.logger.error(f"Slot {i + 1} for interview {interview.id} (candidate {candidate_uuid}) is missing start_time or end_time.")
            db.session.rollback()
            return jsonify({'error': f'Slot {i + 1} is missing start_time or end_time'}), 400
        try:
            # Το frontend στέλνει "YYYY-MM-DD HH:MM:SS"
            naive_start_dt = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
            naive_end_dt = datetime.strptime(end_time_str, "%Y-%m-%d %H:%M:%S")

            # Κάνουμε τα naive datetimes "aware" με την τοπική ζώνη (greece_tz)
            local_aware_start_dt = naive_start_dt.replace(tzinfo=greece_tz)
            local_aware_end_dt = naive_end_dt.replace(tzinfo=greece_tz)
            current_app.logger.debug(f"Slot {i+1} (Interview {interview.id}) - Naive: {naive_start_dt} to {naive_end_dt}, Local Aware (Athens): {local_aware_start_dt} to {local_aware_end_dt}")

            if local_aware_end_dt <= local_aware_start_dt:
                current_app.logger.error(f"Slot {i + 1} (Interview {interview.id}) end_time must be after start_time.")
                db.session.rollback()
                return jsonify({'error': f'Slot {i + 1} end_time must be after start_time'}), 400

            # Μετατροπή σε UTC για αποθήκευση στη βάση
            utc_start_dt = local_aware_start_dt.astimezone(dt_timezone.utc)
            utc_end_dt = local_aware_end_dt.astimezone(dt_timezone.utc)
            current_app.logger.debug(f"Slot {i+1} (Interview {interview.id}) - UTC for DB: {utc_start_dt} to {utc_end_dt}")

            interview_slot = InterviewSlot(
                interview_id=interview.id,
                start_time=utc_start_dt,
                end_time=utc_end_dt,
                is_selected=False
            )
            db.session.add(interview_slot)
            created_interview_slots.append(interview_slot)

        except ValueError as ve:
            current_app.logger.error(
                f"Invalid datetime format for slot {i + 1} (Interview {interview.id}, candidate {candidate_uuid}): Start='{start_time_str}', End='{end_time_str}'. Error: {ve}",
                exc_info=True)
            db.session.rollback()
            return jsonify({
                               'error': f'Invalid datetime format for slot {i + 1}. Expected YYYY-MM-DD HH:MM:SS in local time (Europe/Athens). Input was Start: "{start_time_str}", End: "{end_time_str}"'}), 400
        except Exception as e_dt:
            current_app.logger.error(f"Unexpected error processing slot {i + 1} (Interview {interview.id}, candidate {candidate_uuid}) datetime: {e_dt}", exc_info=True)
            db.session.rollback()
            return jsonify({'error': f'Error processing datetime for slot {i + 1}: {str(e_dt)}'}), 500

    try:
        candidate.add_history_event(
            event_type="INTERVIEW_PROPOSED",
            description=f"Interview proposed by {current_user.username}. Awaiting candidate's response.",
            actor_id=current_user.id,
            details={
                'interview_id': interview.id, 'location': location or "N/A", 'type': interview_type or "N/A",
                'position_id': position_id, 'proposed_slots_count': len(created_interview_slots)
            }
        )
        if candidate.current_status in ['Interested', 'Accepted', 'NeedsReview', 'New', 'Processing']:
            candidate.current_status = "Interview Proposed"

        db.session.commit()
        current_app.logger.info(f"Interview {interview.id} and {len(created_interview_slots)} slots proposed successfully for candidate {candidate_uuid} by user {current_user.id}.")
        try:
            task_name = 'tasks.communication.send_interview_proposal_email_task'
            celery.send_task(task_name, args=[interview.id])
            current_app.logger.info(f"Celery task '{task_name}' dispatched for interview {interview.id}")
        except Exception as celery_e:
            current_app.logger.error(
                f"Error dispatching Celery task '{task_name}' for interview {interview.id}: {celery_e}", exc_info=True)
        return jsonify(interview.to_dict(include_slots=True)), 201 # Επιστροφή του interview με τα slots
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error committing interview proposal for candidate {candidate_uuid}: {e}",
                                 exc_info=True)
        return jsonify({'error': 'An unexpected error occurred while proposing the interview.'}), 500


# --- ΕΝΗΜΕΡΩΜΕΝΗ ΣΥΝΑΡΤΗΣΗ confirm_interview_slot ---
@bp.route('/interviews/confirm/<string:token>/<int:slot_id_choice>', methods=['GET']) # slot_id_choice αντί για slot_choice
def confirm_interview_slot(token, slot_id_choice):
    interview = Interview.query.filter_by(confirmation_token=token).first()
    company_name_for_page = "Our Company" # Default
    if interview and interview.candidate and interview.candidate.company:
        company_name_for_page = interview.candidate.company.name
    elif interview and interview.recruiter and interview.recruiter.company: # Fallback
        company_name_for_page = interview.recruiter.company.name


    if not interview:
        return render_interview_action_page("Error", "Invalid or expired confirmation link.", "is-danger", company_name_for_page), 404

    if not interview.is_token_valid() or interview.status != InterviewStatus.PROPOSED:
        return render_interview_action_page("Error", "This link has expired or the invitation is no longer active.", "is-danger", company_name_for_page), 400

    selected_slot = InterviewSlot.query.filter_by(id=slot_id_choice, interview_id=interview.id).first()

    if not selected_slot:
        return render_interview_action_page("Error", "Invalid slot selection for this interview.", "is-danger", company_name_for_page), 400

    # Έλεγχος αν το slot έχει ήδη επιλεγεί (αν και δεν θα έπρεπε να είναι δυνατό με το token)
    if selected_slot.is_selected:
         return render_interview_action_page("Information", "This slot has already been confirmed.", "is-info", company_name_for_page), 400


    # Ενημέρωση του interview με το επιλεγμένο slot
    interview.scheduled_start_time = selected_slot.start_time
    interview.scheduled_end_time = selected_slot.end_time
    interview.status = InterviewStatus.SCHEDULED
    interview.confirmation_token = None # Καθαρισμός token
    interview.token_expiration = None

    # Μαρκάρισμα του επιλεγμένου slot και απο-μαρκάρισμα των άλλων (αν και δεν θα έπρεπε να υπάρχουν άλλα επιλεγμένα)
    for slot_in_interview in interview.slots:
        slot_in_interview.is_selected = (slot_in_interview.id == selected_slot.id)

    candidate = interview.candidate
    if candidate:
        candidate.current_status = "Interview Scheduled"
        candidate.candidate_confirmation_status = "Confirmed" # Ενημέρωση του γενικού status του υποψηφίου
        candidate.add_history_event(
            event_type="INTERVIEW_SCHEDULED_BY_CANDIDATE",
            description=f"Candidate confirmed interview for slot ID {selected_slot.id} ({selected_slot.start_time.strftime('%Y-%m-%d %H:%M UTC')}).",
            actor_username=candidate.get_full_name() or "Candidate", # Ή το email του αν δεν έχει όνομα
            details={'interview_id': interview.id, 'selected_slot_id': selected_slot.id,
                     'scheduled_time_utc': selected_slot.start_time.isoformat(),
                     'location': interview.location or "N/A", 'type': interview.interview_type or "N/A"}
        )
    try:
        db.session.commit()
        greece_tz = ZoneInfo("Europe/Athens")
        confirmed_time_display = selected_slot.start_time.astimezone(greece_tz).strftime(
            "%A, %d %B %Y at %H:%M (%Z)")
        # celery.send_task('tasks.communication.send_interview_confirmation_to_candidate_task', args=[interview.id, selected_slot.id])
        # celery.send_task('tasks.communication.send_interview_confirmation_to_recruiter_task', args=[interview.id, selected_slot.id])
        return render_interview_action_page("Interview Confirmed",
                                            f"Thank you! Your interview has been scheduled for: <strong>{confirmed_time_display}</strong>. You will receive a confirmation email shortly.",
                                            company_name_for_link=company_name_for_page)
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error confirming interview slot ID {slot_id_choice} for token {token}: {e}", exc_info=True)
        return render_interview_action_page("System Error",
                                            "An error occurred while confirming your selection. Please try again later or contact us.",
                                            "is-danger", company_name_for_page), 500

# --- ΕΝΗΜΕΡΩΜΕΝΗ ΣΥΝΑΡΤΗΣΗ reject_interview_slots ---
@bp.route('/interviews/reject/<string:token>', methods=['GET'])
def reject_interview_slots(token):
    interview = Interview.query.filter_by(confirmation_token=token).first()
    company_name_for_page = "Our Company"
    if interview and interview.candidate and interview.candidate.company:
        company_name_for_page = interview.candidate.company.name
    elif interview and interview.recruiter and interview.recruiter.company:
        company_name_for_page = interview.recruiter.company.name

    if not interview: return render_interview_action_page("Error", "Invalid or expired link.", "is-danger", company_name_for_page), 404

    if not interview.is_token_valid() or interview.status != InterviewStatus.PROPOSED:
        return render_interview_action_page("Error", "This link has expired or the invitation is no longer active.", "is-danger", company_name_for_page), 400

    interview.status = InterviewStatus.CANDIDATE_REJECTED_ALL
    interview.confirmation_token = None
    interview.token_expiration = None
    # Δεν χρειάζεται να αλλάξουμε is_selected στα slots, αφού κανένα δεν επιλέχθηκε.

    candidate = interview.candidate
    if candidate:
        candidate.candidate_confirmation_status = "Declined" # Ενημέρωση γενικού status
        candidate.add_history_event(event_type="INTERVIEW_SLOTS_REJECTED_BY_CANDIDATE",
                                    description="Candidate indicated no proposed slots are suitable.",
                                    actor_username=candidate.get_full_name() or "Candidate",
                                    details={'interview_id': interview.id})
        # Μπορεί να θέλεις να αλλάξεις το candidate.current_status πίσω σε 'Interested' ή 'Accepted'
        # if candidate.current_status == "Interview Proposed":
        #    candidate.current_status = "Interested" # ή το προηγούμενο status του
    try:
        db.session.commit()
        # celery.send_task('tasks.communication.send_interview_rejection_to_recruiter_task', args=[interview.id])
        return render_interview_action_page("Interview Slots Declined",
                                            "Thank you for your response. Your preference has been recorded. A recruiter may contact you if further discussion is needed.",
                                            company_name_for_link=company_name_for_page)
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error rejecting interview slots for token {token}: {e}", exc_info=True)
        return render_interview_action_page("System Error", "An error occurred. Please try again later.", "is-danger", company_name_for_page), 500

# ... (cancel_interview_by_candidate, get_user_settings, update_user_settings παραμένουν ίδια με τον κώδικα που μου έστειλες) ...
@bp.route('/interviews/cancel-by-candidate/<string:token>', methods=['GET'])
def cancel_interview_by_candidate(token):
    interview = Interview.query.filter_by(confirmation_token=token).first()
    company_name_for_page = "Our Company"
    if interview and interview.candidate and interview.candidate.company:
        company_name_for_page = interview.candidate.company.name
    elif interview and interview.recruiter and interview.recruiter.company:
        company_name_for_page = interview.recruiter.company.name

    if not interview: return render_interview_action_page("Error",
                                                          "Invalid or expired cancellation link. The interview may have already been actioned or cancelled.",
                                                          "is-danger", company_name_for_page), 404

    can_cancel_via_token = (interview.status == InterviewStatus.PROPOSED and interview.is_token_valid()) or \
                           (interview.status == InterviewStatus.SCHEDULED and interview.confirmation_token == token)

    if not can_cancel_via_token:
        message = "This interview cannot be cancelled via this link. It may have already been completed, cancelled, or the link has expired."
        current_app.logger.warning(
            f"Attempt to cancel interview {interview.id} with token {token} in status {interview.status.value} denied or token invalid.")
        return render_interview_action_page("Information", message, "is-warning", company_name_for_page), 400

    cancellation_reason_from_query = request.args.get('reason', '').strip()[:500]
    original_status_before_cancel = interview.status.value
    interview.status = InterviewStatus.CANCELLED_BY_CANDIDATE
    if cancellation_reason_from_query: interview.cancellation_reason_candidate = cancellation_reason_from_query
    interview.confirmation_token = None
    interview.token_expiration = None

    candidate = interview.candidate
    if candidate:
        event_description = f"Candidate cancelled interview (was {original_status_before_cancel})."
        if cancellation_reason_from_query: event_description += f" Reason: {cancellation_reason_from_query}"
        candidate.candidate_confirmation_status = "Cancelled"
        if candidate.current_status == "Interview Scheduled" or candidate.current_status == "Interview Proposed":
            candidate.current_status = "Interested" # Ή το προηγούμενο status
        candidate.add_history_event(
            event_type="INTERVIEW_CANCELLED_BY_CANDIDATE", description=event_description,
            actor_username=candidate.get_full_name() or "Candidate",
            details={'interview_id': interview.id, 'reason': cancellation_reason_from_query or "N/A",
                     'previous_status': original_status_before_cancel}
        )
    try:
        db.session.commit()
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


@bp.route('/settings', methods=['GET'])
@login_required
def get_user_settings():
    user_settings = {
        'username': current_user.username,
        'email': current_user.email,
        'enable_email_interview_reminders': current_user.enable_email_interview_reminders,
        'interview_reminder_lead_time_minutes': current_user.interview_reminder_lead_time_minutes
    }
    return jsonify(user_settings), 200


@bp.route('/settings', methods=['PUT'])
@login_required
def update_user_settings():
    data = request.get_json()
    if not data: return jsonify({'error': 'No data provided'}), 400

    updated_fields_count = 0
    settings_changed_details = {}

    if 'enable_email_interview_reminders' in data:
        new_val = bool(data['enable_email_interview_reminders'])
        if current_user.enable_email_interview_reminders != new_val:
            settings_changed_details['enable_email_interview_reminders'] = {
                'old': current_user.enable_email_interview_reminders, 'new': new_val}
            current_user.enable_email_interview_reminders = new_val
            updated_fields_count += 1

    if 'interview_reminder_lead_time_minutes' in data:
        try:
            lead_time = int(data['interview_reminder_lead_time_minutes'])
            if not (5 <= lead_time <= 2 * 24 * 60):
                return jsonify({'error': 'Interview reminder lead time must be between 5 and 2880 minutes.'}), 400
            if current_user.interview_reminder_lead_time_minutes != lead_time:
                settings_changed_details['interview_reminder_lead_time_minutes'] = {
                    'old': current_user.interview_reminder_lead_time_minutes, 'new': lead_time}
                current_user.interview_reminder_lead_time_minutes = lead_time
                updated_fields_count += 1
        except (ValueError, TypeError):
            return jsonify(
                {'error': 'Invalid value for interview_reminder_lead_time_minutes. Must be an integer.'}), 400

    if updated_fields_count == 0:
        return jsonify({'message': 'No settings were changed.'}), 200

    current_user.updated_at = datetime.now(dt_timezone.utc)
    try:
        db.session.commit()
        updated_settings_response = {
            'enable_email_interview_reminders': current_user.enable_email_interview_reminders,
            'interview_reminder_lead_time_minutes': current_user.interview_reminder_lead_time_minutes
        }
        current_app.logger.info(f"User {current_user.id} updated their settings: {settings_changed_details}")
        return jsonify({'message': 'User settings updated successfully', 'settings': updated_settings_response}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating user settings for user {current_user.id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to update user settings.'}), 500