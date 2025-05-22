# backend/app/api/routes.py
from flask import Blueprint, request, jsonify, current_app, render_template, redirect
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from app import db, s3_service_instance, celery
from app.models import (
    User, Company, Candidate, Position, CompanySettings,
    Interview, InterviewStatus, InterviewSlot, Branch
)
from datetime import datetime, timezone as dt_timezone, timedelta
from zoneinfo import ZoneInfo
import uuid
import secrets
from sqlalchemy import func, exc
from sqlalchemy.orm.attributes import flag_modified
from markupsafe import escape

from app.tasks.conversion import convert_docx_to_pdf_task  # Import the new task

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
    user = User.query.filter(
        (User.username == login_identifier) | (User.email == login_identifier.lower().strip())).first()
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
    user_id_for_log = current_user.id
    username_for_log = current_user.username
    logout_user()
    current_app.logger.info(f"User '{username_for_log}' (ID: {user_id_for_log}) logged out.")
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
        f"--- HIT /api/v1/dashboard/summary (user: {current_user.id if current_user.is_authenticated else 'Guest'}, role: {current_user.role if current_user.is_authenticated else 'N/A'}, company_id from user: {current_user.company_id if current_user.is_authenticated else 'N/A'}) ---")
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
    interview_query_base = Interview.query
    if company_id_to_filter:
        candidate_query_base = candidate_query_base.filter(Candidate.company_id == company_id_to_filter)
        position_query_base = position_query_base.filter(Position.company_id == company_id_to_filter)
        interview_query_base = interview_query_base.filter(Interview.company_id == company_id_to_filter)
    summary_data['total_candidates'] = candidate_query_base.count()
    summary_data['active_positions'] = position_query_base.filter(Position.status == 'Open').count()
    summary_data['upcoming_interviews'] = interview_query_base.filter(
        Interview.status == InterviewStatus.SCHEDULED,
        Interview.scheduled_start_time > now_utc
    ).count()
    stages_for_count = ["New", "Processing", "NeedsReview", "Accepted", "Interested", "Interview Proposed",
                        "Interview Scheduled", "Interviewing", "Evaluation", "OfferMade", "Hired", "Rejected",
                        "Declined", "ParsingFailed", "On Hold"]
    candidates_by_stage_list_for_chart = []
    for stage in stages_for_count:
        count_query = Candidate.query.filter(Candidate.current_status == stage)
        if company_id_to_filter:
            count_query = count_query.filter(Candidate.company_id == company_id_to_filter)
        count = count_query.count()
        stage_key_for_summary = stage.lower().replace(" ", "")
        summary_data[stage_key_for_summary] = count
        candidates_by_stage_list_for_chart.append({"stage_name": stage, "count": count})

    summary_data["candidates_by_stage"] = candidates_by_stage_list_for_chart
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
        summary_data['offer_acceptance_rate'] = round((hired_count_for_rate / total_offers_considered_actioned) * 100,
                                                      1)
    else:
        summary_data['offer_acceptance_rate'] = "N/A"
    avg_time_in_needs_review_seconds_query = db.session.query(
        func.avg(func.extract('epoch', now_utc - Candidate.status_last_changed_date))).filter(
        Candidate.current_status == 'NeedsReview')
    if company_id_to_filter:
        avg_time_in_needs_review_seconds_query = avg_time_in_needs_review_seconds_query.filter(
            Candidate.company_id == company_id_to_filter)
    avg_seconds_result = avg_time_in_needs_review_seconds_query.scalar()
    if avg_seconds_result is not None:
        summary_data['avg_days_in_needs_review'] = round(avg_seconds_result / (24 * 60 * 60), 1)
    else:
        summary_data['avg_days_in_needs_review'] = "N/A"
    interview_scheduled_count = summary_data.get('interviewscheduled', 0)
    initial_pipeline_sum = (
            summary_data.get('new', 0) + summary_data.get('processing', 0) + summary_data.get('needsreview', 0) +
            summary_data.get('accepted', 0) + summary_data.get('interested', 0))
    denominator_for_interview_rate = initial_pipeline_sum + interview_scheduled_count
    if denominator_for_interview_rate > 0:
        summary_data['interview_conversion_rate'] = round(
            (interview_scheduled_count / denominator_for_interview_rate) * 100, 1)
    else:
        summary_data['interview_conversion_rate'] = "N/A" if interview_scheduled_count == 0 else 100.0
    current_app.logger.info(
        f"Dashboard summary successfully generated for user {current_user.id}, company_filter: {company_id_to_filter}.")
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
            return jsonify({'error': 'Superadmin must specify a target company ID for upload.'}), 400
    else:
        target_company_id = current_user.company_id

    if not target_company_id:
        current_app.logger.error(f"Could not determine target_company_id for CV upload by user {current_user.id}")
        return jsonify({'error': 'Target company could not be determined for CV upload.'}), 500

    if file:
        filename = secure_filename(file.filename)
        file_content_bytes = file.read()
        file.seek(0)

        original_content_type = file.content_type
        current_app.logger.debug(
            f"CV Upload: Original filename: '{filename}', Content-Type from request: '{original_content_type}'")

        position_name_from_form = request.form.get('position', None)
        branch_ids_str = request.form.get('branch_ids', '')
        position_ids_str = request.form.get('position_ids', '')

        branch_ids_int = []
        if branch_ids_str:
            try:
                branch_ids_int = [int(b_id.strip()) for b_id in branch_ids_str.split(',') if b_id.strip().isdigit()]
            except ValueError:
                current_app.logger.warning(f"Invalid branch_ids format received: {branch_ids_str}")

        position_ids_int = []
        if position_ids_str:
            try:
                position_ids_int = [int(p_id.strip()) for p_id in position_ids_str.split(',') if p_id.strip().isdigit()]
            except ValueError:
                current_app.logger.warning(f"Invalid position_ids format received: {position_ids_str}")

        try:
            file_key = f"cvs/{target_company_id}/{uuid.uuid4()}_{filename}"

            upload_success_key = s3_service_instance.upload_file_obj(
                file_obj_content_bytes=file_content_bytes,
                object_name=file_key,
                ContentType=original_content_type
            )

            if not upload_success_key:
                current_app.logger.error(
                    f"S3 upload failed for {filename} by user {current_user.id} for company {target_company_id}.")
                return jsonify({'error': 'Failed to upload file to S3 storage.'}), 500

            placeholder_email = f"placeholder-{uuid.uuid4()}@example.com"

            new_candidate = Candidate(
                company_id=target_company_id,
                cv_original_filename=filename,
                cv_storage_path=upload_success_key,
                cv_content_type=original_content_type,
                current_status='Processing',
                email=placeholder_email
            )
            db.session.add(new_candidate)
            db.session.flush()

            assigned_position_names_log = []
            if position_ids_int:
                positions_to_assign = Position.query.filter(Position.position_id.in_(position_ids_int),
                                                            Position.company_id == target_company_id).all()
                for pos in positions_to_assign:
                    if pos not in new_candidate.positions: new_candidate.positions.append(
                        pos); assigned_position_names_log.append(pos.position_name)
            elif position_name_from_form and position_name_from_form.strip():
                position_obj = Position.query.filter_by(company_id=target_company_id,
                                                        position_name=position_name_from_form.strip()).first()
                if not position_obj:
                    position_obj = Position(company_id=target_company_id, position_name=position_name_from_form.strip(),
                                            status="Open")
                    db.session.add(position_obj)
                if position_obj not in new_candidate.positions: new_candidate.positions.append(
                    position_obj); assigned_position_names_log.append(position_obj.position_name)

            assigned_branch_names_log = []
            if branch_ids_int:
                branches_to_assign = Branch.query.filter(Branch.id.in_(branch_ids_int),
                                                         Branch.company_id == target_company_id).all()
                for branch in branches_to_assign:
                    if branch not in new_candidate.branches: new_candidate.branches.append(
                        branch); assigned_branch_names_log.append(branch.name)

            history_details = {
                "s3_key": upload_success_key,
                "original_filename": filename,
                "content_type": original_content_type,
                "branch_ids_applied": branch_ids_int,
                "branches_applied_names": assigned_branch_names_log,
                "position_ids_applied": position_ids_int,
                "positions_applied_names": assigned_position_names_log,
                "ad_hoc_position_name_given": position_name_from_form if not position_ids_int and position_name_from_form else None
            }
            new_candidate.add_history_event(event_type="CV_UPLOADED",
                                            description=f"CV '{filename}' uploaded by {current_user.username}.",
                                            actor_id=current_user.id, details=history_details)
            db.session.commit()

            # --- DEBUGGING ΓΙΑ DOCX CONVERSION ---
            current_app.logger.info(f"[UPLOAD_CV_DEBUG] Candidate ID: {new_candidate.candidate_id}")
            current_app.logger.info(f"[UPLOAD_CV_DEBUG] Original Filename: {new_candidate.cv_original_filename}")
            current_app.logger.info(f"[UPLOAD_CV_DEBUG] Content-Type from model: {new_candidate.cv_content_type}")
            current_app.logger.info(f"[UPLOAD_CV_DEBUG] Is DOCX property: {new_candidate.is_docx}")
            # --- ΤΕΛΟΣ DEBUGGING ---

            if new_candidate.is_docx:
                current_app.logger.info(
                    f"CV for candidate {new_candidate.candidate_id} IS DOCX. Scheduling conversion task.")
                convert_docx_to_pdf_task.delay(
                    str(new_candidate.candidate_id),
                    new_candidate.cv_storage_path,
                    new_candidate.cv_original_filename
                )
            else:
                current_app.logger.info(
                    f"CV for candidate {new_candidate.candidate_id} is NOT DOCX (type from model: {new_candidate.cv_content_type}, filename: {new_candidate.cv_original_filename}). Skipping conversion task.")

            if current_app.config.get('TEXTKERNEL_ENABLED', False):
                celery.send_task('app.tasks.parsing.parse_cv_task',
                                 args=[str(new_candidate.candidate_id), upload_success_key, target_company_id])
            else:
                if new_candidate.current_status == 'Processing':
                    new_candidate.current_status = 'NeedsReview'
                    new_candidate.add_history_event(event_type="PARSING_SKIPPED",
                                                    description="Textkernel parsing is disabled. Manual review needed.")
                    db.session.commit()

            return jsonify({'message': 'CV uploaded successfully. Processing...',
                            'candidate_id': str(new_candidate.candidate_id)}), 201
        except exc.IntegrityError as ie:
            db.session.rollback();
            current_app.logger.error(f"Integrity error during CV upload: {ie}",
                                     exc_info=True);
            return jsonify(
                {'error': 'A database conflict occurred. Please try again.'}), 409
        except Exception as e:
            db.session.rollback();
            current_app.logger.error(f"Error during CV upload or candidate creation: {e}",
                                     exc_info=True);
            return jsonify(
                {'error': f'Failed to upload CV: {str(e)}'}), 500

    return jsonify({'error': 'File processing error.'}), 400


@bp.route('/candidates', methods=['GET'], endpoint='get_all_candidates_main')
@bp.route('/candidates/<string:status_in_path>', methods=['GET'], endpoint='get_candidates_by_status_main')
@login_required
def get_candidates(status_in_path=None):
    if current_user.role != 'superadmin' and not current_user.company_id: return jsonify(
        {'error': 'User not associated with a company'}), 403
    page = request.args.get('page', 1, type=int);
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
                                    Candidate.notes.ilike(search_ilike), Candidate.hr_comments.ilike(search_ilike),
                                    Candidate.positions.any(Position.position_name.ilike(search_ilike))))
    query = query.order_by(Candidate.submission_date.desc())
    try:
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        candidates_data = [
            candidate_obj.to_dict(include_history=True, include_interviews=True, include_cv_url=True, cv_url_param=None,
                                  include_branches=True) for candidate_obj in pagination.items]
        return jsonify(
            {'candidates': candidates_data, 'total_results': pagination.total, 'total_pages': pagination.pages,
             'current_page': pagination.page, 'has_next': pagination.has_next, 'has_prev': pagination.has_prev}), 200
    except Exception as e:
        current_app.logger.error(f"Error during candidate pagination: {e}", exc_info=True);
        return jsonify(
            {'error': 'Error fetching candidates list.'}), 500


@bp.route('/candidate/<string:candidate_uuid>', methods=['GET'])
@login_required
def get_candidate_detail(candidate_uuid):
    try:
        candidate_id_obj = uuid.UUID(candidate_uuid)
    except ValueError:
        return jsonify({'error': 'Invalid candidate UUID format'}), 400
    candidate = db.session.get(Candidate, candidate_id_obj)
    if not candidate: return jsonify({'error': 'Candidate not found'}), 404
    if current_user.role != 'superadmin' and current_user.company_id != candidate.company_id: return jsonify(
        {'error': 'Forbidden: You do not have permission to view this candidate'}), 403
    return jsonify(
        candidate.to_dict(include_history=True, include_interviews=True, include_cv_url=True, cv_url_param=None,
                          include_branches=True)), 200


@bp.route('/candidate/<string:candidate_uuid>', methods=['PUT'])
@login_required
def update_candidate_detail(candidate_uuid):
    try:
        candidate_id_obj = uuid.UUID(candidate_uuid)
    except ValueError:
        return jsonify({'error': 'Invalid candidate UUID format'}), 400

    candidate = db.session.get(Candidate, candidate_id_obj)
    if not candidate:
        return jsonify({'error': 'Candidate not found'}), 404

    if current_user.role != 'superadmin' and current_user.company_id != candidate.company_id:
        return jsonify({'error': 'Forbidden: You do not have permission to update this candidate'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided for update'}), 400

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
    offer_made_in_this_update = False

    current_app.logger.debug(f"Updating candidate {candidate_uuid}. Received data: {data}")
    current_app.logger.debug(f"Old status: {old_status_for_log}, New status from payload: {new_status_from_payload}")

    if new_status_from_payload == 'OfferMade' and old_status_for_log != 'OfferMade':
        if candidate.current_status not in ['Hired', 'Declined']:
            offer_made_in_this_update = True
            candidate.offer_acceptance_token = secrets.token_urlsafe(32)
            candidate.offer_acceptance_token_expiration = datetime.now(dt_timezone.utc) + timedelta(
                days=current_app.config.get('INTERVIEW_TOKEN_EXPIRATION_DAYS', 7))
            updated_fields_log['offer_acceptance_token'] = {'old': candidate.offer_acceptance_token, 'new': 'generated'}
            current_app.logger.info(
                f"Offer token generated for candidate {candidate.candidate_id} upon status change to OfferMade.")
        else:
            current_app.logger.info(
                f"Candidate {candidate.candidate_id} moved to OfferMade, but was previously {candidate.current_status}. Offer token not regenerated/email not re-sent for this specific action.")

    if new_status_from_payload == 'NeedsReview' and old_status_for_log in ['Declined', 'Rejected', 'ParsingFailed',
                                                                           'Hired', 'OfferMade']:
        current_app.logger.info(f"Re-evaluating candidate {candidate.candidate_id}. Old status: {old_status_for_log}")
        candidate.evaluation_rating = None
        candidate.candidate_confirmation_status = None
        candidate.offer_acceptance_token = None
        candidate.offer_acceptance_token_expiration = None

        interview_statuses_to_cancel_on_reevaluate = [InterviewStatus.PROPOSED, InterviewStatus.SCHEDULED]
        active_interviews_to_cancel = Interview.query.filter(
            Interview.candidate_id == candidate.candidate_id,
            Interview.status.in_(interview_statuses_to_cancel_on_reevaluate)
        ).all()
        re_evaluation_details_for_log = {
            'evaluation_rating_cleared': True, 'candidate_confirmation_status_cleared': True,
            'offer_acceptance_token_cleared': True
        }
        cancelled_interview_ids = []
        if active_interviews_to_cancel:
            for inv in active_interviews_to_cancel:
                inv.status = InterviewStatus.CANCELLED_DUE_TO_REEVALUATION
                inv.internal_notes = (inv.internal_notes or "") + \
                                     f"\n[System] Cancelled on {datetime.now(dt_timezone.utc).strftime('%Y-%m-%d')} due to re-evaluation to 'NeedsReview'."
                cancelled_interview_ids.append(str(inv.id))
            current_app.logger.info(
                f"Cancelled {len(cancelled_interview_ids)} interviews for candidate {candidate.candidate_id} due to re-evaluation.")
        re_evaluation_details_for_log['active_interviews_cancelled_count'] = len(cancelled_interview_ids)
        re_evaluation_details_for_log['cancelled_interview_ids'] = cancelled_interview_ids
        if hasattr(candidate, 'offers') and isinstance(candidate.offers, list) and candidate.offers:
            candidate.offers = []
            flag_modified(candidate, "offers")
            re_evaluation_details_for_log['offers_cleared'] = True
            current_app.logger.info(f"Cleared offers for candidate {candidate.candidate_id} due to re-evaluation.")
        updated_fields_log['re_evaluation_specific_resets'] = re_evaluation_details_for_log

    for field in allowed_fields:
        if field in data:
            if new_status_from_payload == 'NeedsReview' and \
                    old_status_for_log in ['Declined', 'Rejected', 'ParsingFailed', 'Hired', 'OfferMade'] and \
                    field in ['notes', 'hr_comments'] and \
                    field not in data:
                current_app.logger.debug(
                    f"Re-evaluation: Skipping update for '{field}' as it was not in payload, retaining existing value.")
                continue
            old_value = getattr(candidate, field, None)
            new_value = data[field]
            if field == 'email' and new_value is not None: new_value = new_value.lower().strip()
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
                if field == 'current_status': status_changed = True

    if 'positions' in data and isinstance(data['positions'], list):
        current_position_names = {pos.position_name for pos in candidate.positions}
        new_position_names_from_data = {p_name.strip() for p_name in data['positions'] if
                                        isinstance(p_name, str) and p_name.strip()}
        if current_position_names != new_position_names_from_data:
            updated_fields_log['positions'] = {'old': sorted(list(current_position_names)),
                                               'new': sorted(list(new_position_names_from_data))}
            new_positions_for_candidate = []
            for pos_name in new_position_names_from_data:
                position = Position.query.filter_by(company_id=candidate.company_id, position_name=pos_name).first()
                if not position: position = Position(company_id=candidate.company_id, position_name=pos_name,
                                                     status="Open"); db.session.add(position)
                new_positions_for_candidate.append(position)
            candidate.positions = new_positions_for_candidate

    if 'offers' in data and isinstance(data['offers'], list) and hasattr(candidate, 'offers'):
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
                    processed_offer_for_db['offer_amount'] = None
            processed_offer_for_db['offer_notes'] = offer_data_from_frontend.get('offer_notes', '').strip()
            offer_date_str = offer_data_from_frontend.get('offer_date')
            if offer_date_str:
                try:
                    if 'T' in offer_date_str:
                        standardized_date_str = offer_date_str.split('.')[0]
                        if 'Z' in standardized_date_str:
                            dt_obj_utc = datetime.fromisoformat(standardized_date_str.replace('Z', '+00:00'))
                        elif '+' in standardized_date_str[10:] or '-' in standardized_date_str[10:]:
                            dt_obj_utc = datetime.fromisoformat(standardized_date_str)
                        else:
                            try:
                                dt_obj_naive = datetime.strptime(standardized_date_str, "%Y-%m-%dT%H:%M:%S")
                            except ValueError:
                                dt_obj_naive = datetime.strptime(standardized_date_str, "%Y-%m-%dT%H:%M")
                            if dt_obj_naive.tzinfo is None:
                                dt_obj_utc = dt_obj_naive.replace(tzinfo=dt_timezone.utc)
                            else:
                                dt_obj_utc = dt_obj_naive.astimezone(dt_timezone.utc)
                    else:
                        dt_obj_naive = datetime.strptime(offer_date_str, "%Y-%m-%d")
                        dt_obj_utc = dt_obj_naive.replace(tzinfo=dt_timezone.utc)
                    processed_offer_for_db['offer_date'] = dt_obj_utc.isoformat()
                except ValueError as ve:
                    current_app.logger.warning(
                        f"Could not parse offer_date_str: '{offer_date_str}'. Error: {ve}. Setting to None.");
                    processed_offer_for_db['offer_date'] = None
            else:
                processed_offer_for_db['offer_date'] = None
            if processed_offer_for_db['offer_amount'] is not None or (
                    processed_offer_for_db.get('offer_notes') and processed_offer_for_db['offer_notes'].strip()):
                new_offers_for_db.append(processed_offer_for_db)
        if old_offers_for_log != new_offers_for_db: updated_fields_log['offers'] = {'old': old_offers_for_log,
                                                                                    'new': new_offers_for_db}
        candidate.offers = new_offers_for_db
        flag_modified(candidate, "offers")

    if 'branch_ids' in data and isinstance(data['branch_ids'], list):
        current_branch_ids = {branch.id for branch in candidate.branches}
        new_branch_ids_from_data = set()
        for b_id in data['branch_ids']:
            try:
                new_branch_ids_from_data.add(int(b_id))
            except (ValueError, TypeError):
                current_app.logger.warning(f"Invalid branch ID '{b_id}' for candidate {candidate_uuid}.")
        if current_branch_ids != new_branch_ids_from_data:
            updated_fields_log['branches'] = {'old_ids': sorted(list(current_branch_ids)),
                                              'new_ids': sorted(list(new_branch_ids_from_data))}
            new_branches_for_candidate = []
            if new_branch_ids_from_data:
                valid_branches = Branch.query.filter(Branch.id.in_(list(new_branch_ids_from_data)),
                                                     Branch.company_id == candidate.company_id).all()
                new_branches_for_candidate = valid_branches
            candidate.branches = new_branches_for_candidate

    if not updated_fields_log and not offer_made_in_this_update:
        if not status_changed:
            return jsonify({'message': 'No changes detected or no updatable fields provided.'}), 200

    history_description = f"Candidate details updated by {current_user.username}."
    if status_changed:
        if new_status_from_payload == 'NeedsReview' and old_status_for_log in ['Declined', 'Rejected', 'ParsingFailed',
                                                                               'Hired', 'OfferMade']:
            history_description = f"Candidate status reset to 'NeedsReview' for re-evaluation by {current_user.username} (was '{old_status_for_log}')."
        else:
            history_description = f"Status changed by {current_user.username} from '{old_status_for_log}' to '{candidate.current_status}'."
        other_changes_keys = set(updated_fields_log.keys()) - {'current_status', 're_evaluation_specific_resets',
                                                               'offer_acceptance_token'}
        if other_changes_keys: history_description += " Other details also updated."
    elif updated_fields_log:
        history_description = f"Candidate details (non-status) updated by {current_user.username}."

    candidate.add_history_event(
        event_type="CANDIDATE_UPDATED" if status_changed else "CANDIDATE_DETAILS_UPDATED",
        description=history_description,
        actor_id=current_user.id,
        details={'updated_fields': updated_fields_log}
    )
    candidate.updated_at = datetime.now(dt_timezone.utc)
    if status_changed:
        candidate.status_last_changed_date = datetime.now(dt_timezone.utc)

    try:
        db.session.commit()
        if offer_made_in_this_update:
            last_offer_details_for_email = candidate.offers[-1] if (
                    candidate.offers and isinstance(candidate.offers, list) and len(candidate.offers) > 0) else {}
            celery.send_task('app.tasks.communication.send_offer_made_email_to_candidate_task',
                             args=[str(candidate.candidate_id), last_offer_details_for_email])
        elif status_changed and candidate.current_status == 'Hired':
            celery.send_task('app.tasks.communication.send_hired_confirmation_email_to_candidate_task',
                             args=[str(candidate.candidate_id)])
        elif status_changed and candidate.current_status == 'Declined' and old_status_for_log == 'OfferMade':
            celery.send_task('app.tasks.communication.send_offer_declined_notification_to_recruiter_task',
                             args=[str(candidate.candidate_id), "Offer marked as Declined by recruiter."])

        updated_candidate_data = db.session.get(Candidate, candidate_id_obj).to_dict(include_history=True,
                                                                                     include_interviews=True,
                                                                                     include_cv_url=True,
                                                                                     cv_url_param=None,
                                                                                     include_branches=True)
        return jsonify(updated_candidate_data), 200
    except Exception as e:
        db.session.rollback();
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
    if current_user.role == 'superadmin':
        can_delete = True
    elif current_user.role == 'company_admin' and current_user.company_id == candidate.company_id:
        can_delete = True
    if not can_delete: return jsonify(
        {'error': 'Forbidden: You do not have permission to delete this candidate'}), 403

    s3_path_to_delete = candidate.cv_storage_path
    s3_pdf_path_to_delete = candidate.cv_pdf_storage_key
    candidate_full_name_for_log = candidate.full_name

    try:
        db.session.delete(candidate)
        db.session.commit()
        current_app.logger.info(
            f"Candidate {candidate_uuid} ('{candidate_full_name_for_log}') deleted by user {current_user.username} (ID: {current_user.id}).")

        if s3_path_to_delete:
            try:
                s3_service_instance.delete_file(s3_path_to_delete)
                current_app.logger.info(
                    f"Successfully deleted original CV {s3_path_to_delete} from S3 for deleted candidate {candidate_uuid}")
            except Exception as s3_e:
                current_app.logger.error(
                    f"Failed to delete original CV {s3_path_to_delete} from S3 for candidate {candidate_uuid}: {s3_e}",
                    exc_info=True)

        if s3_pdf_path_to_delete:
            try:
                s3_service_instance.delete_file(s3_pdf_path_to_delete)
                current_app.logger.info(
                    f"Successfully deleted PDF CV {s3_pdf_path_to_delete} from S3 for deleted candidate {candidate_uuid}")
            except Exception as s3_pdf_e:
                current_app.logger.error(
                    f"Failed to delete PDF CV {s3_pdf_path_to_delete} from S3 for candidate {candidate_uuid}: {s3_pdf_e}",
                    exc_info=True)

        return jsonify({'message': f"Candidate '{candidate_full_name_for_log}' deleted successfully"}), 200
    except Exception as e:
        db.session.rollback();
        current_app.logger.error(f"Error deleting candidate {candidate_uuid}: {e}",
                                 exc_info=True);
        return jsonify(
            {'error': f'Failed to delete candidate: {str(e)}'}), 500


# --- INTERVIEW ACTION ROUTES ---
@bp.route('/candidates/<string:candidate_uuid>/propose-interview', methods=['POST'])
@login_required
def propose_interview(candidate_uuid):
    if current_user.role not in ['company_admin', 'superadmin', 'user', 'recruiter',
                                 'hiring_manager']:  # Added recruiter, hiring_manager
        return jsonify({'error': 'Forbidden: User does not have permission to propose interviews'}), 403
    try:
        candidate_id_obj = uuid.UUID(candidate_uuid)
    except ValueError:
        return jsonify({'error': 'Invalid candidate UUID format'}), 400
    candidate = db.session.get(Candidate, candidate_id_obj)
    if not candidate: return jsonify({'error': 'Candidate not found'}), 404

    # Permission check: User must be superadmin OR belong to the same company as the candidate
    if not (current_user.role == 'superadmin' or (
            current_user.company_id and current_user.company_id == candidate.company_id)):
        return jsonify({'error': 'Forbidden: User cannot manage interviews for this candidate'}), 403

    data = request.get_json();
    if not data: return jsonify({'error': 'No data provided'}), 400

    existing_proposed_interviews = Interview.query.filter_by(candidate_id=candidate.candidate_id,
                                                             status=InterviewStatus.PROPOSED).all()
    cancelled_previous_proposal_ids = []
    if existing_proposed_interviews:
        for old_interview in existing_proposed_interviews:
            old_interview.status = InterviewStatus.CANCELLED_BY_RECRUITER
            old_interview.internal_notes = (
                                                       old_interview.internal_notes or "") + f"\nSuperseded by new proposal on {datetime.now(dt_timezone.utc).strftime('%Y-%m-%d %H:%M')} by {current_user.username}."
            old_interview.updated_at = datetime.now(dt_timezone.utc)
            cancelled_previous_proposal_ids.append(str(old_interview.id))

    proposed_slots_data = data.get('proposed_slots');
    location = data.get('location');
    interview_type = data.get('interview_type')
    notes_for_candidate = data.get('notes_for_candidate', '');
    internal_notes = data.get('internal_notes', '')
    position_id_str = data.get('position_id');
    position_id = None

    if position_id_str and str(position_id_str).strip() != "" and str(position_id_str) != "0":
        try:
            position_id = int(position_id_str);
            pos_obj = db.session.get(Position, position_id)
            if not pos_obj: return jsonify(
                {'error': f'Position with ID {position_id} not found.'}), 404
            if pos_obj.company_id != candidate.company_id: return jsonify(
                {'error': 'Selected position does not belong to the candidate\'s company.'}), 400
        except ValueError:
            return jsonify({'error': 'Invalid position_id format.'}), 400
    elif str(position_id_str) == "0":
        position_id = None

    if not proposed_slots_data or not isinstance(proposed_slots_data, list) or not (
            1 <= len(proposed_slots_data) <= 3): return jsonify(
        {'error': 'Proposed slots are required (1 to 3 slots as a list of {start_time, end_time})'}), 400

    try:
        greece_tz = ZoneInfo(current_app.config.get('LOCAL_TIMEZONE', 'Europe/Athens'))
    except Exception:
        current_app.logger.error("Failed to load LOCAL_TIMEZONE for interview proposal.")
        return jsonify({'error': "Server timezone configuration error."}), 500

    interview = Interview(candidate_id=candidate.candidate_id, company_id=candidate.company_id,
                          recruiter_id=current_user.id, position_id=position_id, location=location,
                          interview_type=interview_type, notes_for_candidate=notes_for_candidate,
                          internal_notes=internal_notes, status=InterviewStatus.PROPOSED,
                          confirmation_token=secrets.token_urlsafe(32),
                          token_expiration=datetime.now(dt_timezone.utc) + timedelta(
                              days=current_app.config.get('INTERVIEW_TOKEN_EXPIRATION_DAYS', 7)))
    db.session.add(interview)
    try:
        db.session.flush()
    except Exception as e_flush:
        db.session.rollback();
        current_app.logger.error(f"DB flush error during interview proposal: {e_flush}", exc_info=True)
        return jsonify({'error': 'Database error during interview creation (flush).'}), 500

    created_interview_slots = []
    for i, slot_data in enumerate(proposed_slots_data):
        start_time_str = slot_data.get('start_time');
        end_time_str = slot_data.get('end_time')
        if not start_time_str or not end_time_str:
            db.session.rollback()
            return jsonify({'error': f'Slot {i + 1} is missing start_time or end_time'}), 400
        try:
            naive_start_dt = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S");
            naive_end_dt = datetime.strptime(end_time_str, "%Y-%m-%d %H:%M:%S")
            local_aware_start_dt = naive_start_dt.replace(tzinfo=greece_tz);
            local_aware_end_dt = naive_end_dt.replace(tzinfo=greece_tz)
            if local_aware_end_dt <= local_aware_start_dt:
                db.session.rollback()
                return jsonify({'error': f'Slot {i + 1} end_time must be after start_time'}), 400
            if local_aware_start_dt < datetime.now(greece_tz):
                db.session.rollback()
                return jsonify({'error': f'Slot {i + 1} cannot be in the past.'}), 400
            utc_start_dt = local_aware_start_dt.astimezone(dt_timezone.utc);
            utc_end_dt = local_aware_end_dt.astimezone(dt_timezone.utc)
            interview_slot = InterviewSlot(interview_id=interview.id, start_time=utc_start_dt, end_time=utc_end_dt,
                                           is_selected=False)
            db.session.add(interview_slot);
            created_interview_slots.append(interview_slot)
        except ValueError:
            db.session.rollback();
            return jsonify(
                {'error': f'Invalid datetime format for slot {i + 1}. Expected YYYY-MM-DD HH:MM:SS (local time).'}), 400
        except Exception as e_dt:
            db.session.rollback();
            current_app.logger.error(f"Error processing slot {i + 1} datetime: {e_dt}", exc_info=True)
            return jsonify(
                {'error': f"Error processing datetime for slot {i + 1}: {str(e_dt)}"}), 500
    try:
        history_event_details = {'interview_id': str(interview.id), 'location': location or "N/A",
                                 'type': interview_type or "N/A", 'position_id': position_id,
                                 'proposed_slots_count': len(created_interview_slots)}
        if cancelled_previous_proposal_ids: history_event_details[
            'cancelled_previous_proposals'] = cancelled_previous_proposal_ids
        candidate.add_history_event(event_type="INTERVIEW_PROPOSED",
                                    description=f"Interview proposed by {current_user.username}." + (
                                        f" Previous proposals ({len(cancelled_previous_proposal_ids)}) superseded." if cancelled_previous_proposal_ids else ""),
                                    actor_id=current_user.id, details=history_event_details)
        if candidate.current_status != "Interview Proposed":
            candidate.current_status = "Interview Proposed"
            candidate.status_last_changed_date = datetime.now(dt_timezone.utc)
        db.session.commit()
        celery.send_task('app.tasks.communication.send_interview_proposal_email_task', args=[str(interview.id)])
        return jsonify(interview.to_dict(include_slots=True)), 201
    except Exception as e:
        db.session.rollback();
        current_app.logger.error(f"Final commit error during interview proposal: {e}", exc_info=True)
        return jsonify(
            {'error': 'An unexpected error occurred while proposing the interview.'}), 500


@bp.route('/interviews/confirm/<string:token>/<int:slot_id_choice>', methods=['GET'])
def confirm_interview_slot(token, slot_id_choice):
    interview = Interview.query.filter_by(confirmation_token=token).first()
    company_name_for_page = "Our Company";
    if interview: company_name_for_page = interview.company.name if interview.company else (
        interview.candidate.company.name if interview.candidate and interview.candidate.company else "Our Company")
    if not interview: return render_template("interview_action_response.html", title="Error",
                                             message="Invalid or expired confirmation link.", status_class="is-danger",
                                             company_name=company_name_for_page), 404
    if not interview.is_token_valid(
            token_type='confirmation') or interview.status != InterviewStatus.PROPOSED: return render_template(
        "interview_action_response.html", title="Error",
        message="This link has expired or the invitation is no longer active.", status_class="is-danger",
        company_name=company_name_for_page), 400
    selected_slot = InterviewSlot.query.filter_by(id=slot_id_choice, interview_id=interview.id).first()
    if not selected_slot: return render_template("interview_action_response.html", title="Error",
                                                 message="Invalid slot selection for this interview.",
                                                 status_class="is-danger", company_name=company_name_for_page), 400
    if selected_slot.is_selected: return render_template("interview_action_response.html", title="Information",
                                                         message="This slot selection has already been processed.",
                                                         status_class="is-info",
                                                         company_name=company_name_for_page), 200
    interview.scheduled_start_time = selected_slot.start_time;
    interview.scheduled_end_time = selected_slot.end_time
    interview.status = InterviewStatus.SCHEDULED;
    interview.confirmation_token = None;
    interview.token_expiration = None
    interview.cancellation_token = secrets.token_urlsafe(32);
    interview.cancellation_token_expiration = datetime.now(dt_timezone.utc) + timedelta(
        days=current_app.config.get('INTERVIEW_TOKEN_EXPIRATION_DAYS', 7))
    for slot_in_interview in interview.slots: slot_in_interview.is_selected = (slot_in_interview.id == selected_slot.id)
    candidate = interview.candidate
    if candidate:
        candidate.current_status = "Interview Scheduled";
        candidate.status_last_changed_date = datetime.now(dt_timezone.utc);
        candidate.candidate_confirmation_status = "Confirmed"
        candidate.add_history_event(event_type="INTERVIEW_SCHEDULED_BY_CANDIDATE",
                                    description=f"Candidate confirmed interview for slot ID {selected_slot.id} ({selected_slot.start_time.astimezone(ZoneInfo(current_app.config.get('LOCAL_TIMEZONE', 'Europe/Athens'))).strftime('%Y-%m-%d %H:%M')}).",
                                    actor_username=candidate.get_full_name() or "Candidate",
                                    details={'interview_id': str(interview.id), 'selected_slot_id': selected_slot.id,
                                             'scheduled_time_utc': selected_slot.start_time.isoformat(),
                                             'location': interview.location or "N/A",
                                             'type': interview.interview_type or "N/A"})
        candidate.updated_at = datetime.now(dt_timezone.utc)
    interview.updated_at = datetime.now(dt_timezone.utc)
    try:
        db.session.commit()
        greece_tz = ZoneInfo(current_app.config.get('LOCAL_TIMEZONE', 'Europe/Athens'));
        confirmed_time_display = selected_slot.start_time.astimezone(greece_tz).strftime("%A, %d %B %Y at %H:%M (%Z)")
        celery.send_task('app.tasks.communication.send_interview_confirmation_to_candidate_task',
                         args=[str(interview.id), str(selected_slot.id)])
        celery.send_task('app.tasks.communication.send_interview_confirmation_to_recruiter_task',
                         args=[str(interview.id), str(selected_slot.id)])
        return render_template("interview_action_response.html", title="Interview Confirmed",
                               message=f"Thank you! Your interview has been scheduled for: <strong>{confirmed_time_display}</strong>. You will receive a confirmation email shortly.",
                               status_class="is-success", company_name=company_name_for_page)
    except Exception as e:
        db.session.rollback();
        current_app.logger.error(f"Error confirming interview slot {slot_id_choice}: {e}",
                                 exc_info=True);
        return render_template(
            "interview_action_response.html", title="System Error", message="An error occurred. Please contact us.",
            status_class="is-danger", company_name=company_name_for_page), 500


@bp.route('/interviews/reject/<string:token>', methods=['GET'])
def reject_interview_slots(token):
    interview = Interview.query.filter_by(confirmation_token=token).first()
    company_name_for_page = "Our Company";
    if interview: company_name_for_page = interview.company.name if interview.company else (
        interview.candidate.company.name if interview.candidate and interview.candidate.company else "Our Company")
    if not interview: return render_template("interview_action_response.html", title="Error",
                                             message="Invalid or expired link.", status_class="is-danger",
                                             company_name=company_name_for_page), 404
    if not interview.is_token_valid(
            token_type='confirmation') or interview.status != InterviewStatus.PROPOSED: return render_template(
        "interview_action_response.html", title="Error",
        message="This link has expired or the invitation is no longer active.", status_class="is-danger",
        company_name=company_name_for_page), 400
    interview.status = InterviewStatus.CANDIDATE_REJECTED_ALL;
    interview.confirmation_token = None;
    interview.token_expiration = None;
    interview.updated_at = datetime.now(dt_timezone.utc)
    candidate = interview.candidate
    if candidate:
        candidate.candidate_confirmation_status = "DeclinedSlots";
        history_description = "Candidate indicated no proposed slots are suitable."
        if candidate.current_status == "Interview Proposed": candidate.current_status = "Interested"; candidate.status_last_changed_date = datetime.now(
            dt_timezone.utc); history_description += " Candidate status changed to 'Interested'."
        candidate.add_history_event(event_type="INTERVIEW_SLOTS_REJECTED_BY_CANDIDATE", description=history_description,
                                    actor_username=candidate.get_full_name() or "Candidate",
                                    details={'interview_id': str(interview.id)})
        candidate.updated_at = datetime.now(dt_timezone.utc)
    try:
        db.session.commit();
        celery.send_task('app.tasks.communication.send_interview_rejection_to_recruiter_task', args=[str(interview.id)])
        return render_template("interview_action_response.html", title="Interview Slots Declined",
                               message="Thank you for your response. A recruiter may contact you.",
                               status_class="is-info", company_name=company_name_for_page)
    except Exception as e:
        db.session.rollback();
        current_app.logger.error(f"Error rejecting interview slots for token {token}: {e}",
                                 exc_info=True);
        return render_template(
            "interview_action_response.html", title="System Error", message="An error occurred.",
            status_class="is-danger", company_name=company_name_for_page), 500


@bp.route('/interviews/cancel-by-candidate/<string:cancel_token>', methods=['GET', 'POST'])
def cancel_interview_by_candidate(cancel_token):
    interview = Interview.query.filter_by(cancellation_token=cancel_token).first()
    company_name_for_page = "Our Company"
    if interview: company_name_for_page = interview.company.name if interview.company else (
        interview.candidate.company.name if interview.candidate and interview.candidate.company else "Our Company")
    if not interview: return render_template("interview_action_response.html", title="Error",
                                             message="Invalid or expired cancellation link.", status_class="is-danger",
                                             company_name=company_name_for_page), 404
    if not interview.is_token_valid(token_type='cancellation') or interview.status not in [InterviewStatus.SCHEDULED,
                                                                                           InterviewStatus.PROPOSED]: return render_template(
        "interview_action_response.html", title="Information",
        message="This interview cannot be cancelled or the link has expired.", status_class="is-warning",
        company_name=company_name_for_page), 400
    cancellation_threshold_hours = current_app.config.get('INTERVIEW_CANCELLATION_THRESHOLD_HOURS', 12)
    if interview.status == InterviewStatus.SCHEDULED and interview.scheduled_start_time and (
            interview.scheduled_start_time - datetime.now(dt_timezone.utc) < timedelta(
        hours=cancellation_threshold_hours)): return render_template("interview_action_response.html",
                                                                     title="Cancellation Not Allowed",
                                                                     message=f"Interview is too soon (within {cancellation_threshold_hours} hours) to cancel online. Please contact {company_name_for_page}.",
                                                                     status_class="is-warning",
                                                                     company_name=company_name_for_page), 400
    if request.method == 'POST':
        cancellation_reason = request.form.get('cancellation_reason', '').strip()[:500];
        reschedule_preference = request.form.get('reschedule_preference', 'unknown')
        original_interview_status_value = interview.status.value;
        candidate = interview.candidate;
        old_candidate_status_for_log = candidate.current_status if candidate else None
        interview.status = InterviewStatus.CANCELLED_BY_CANDIDATE
        if cancellation_reason: interview.cancellation_reason_candidate = cancellation_reason
        interview.cancellation_token = None;
        interview.cancellation_token_expiration = None;
        interview.updated_at = datetime.now(dt_timezone.utc)
        history_event_description = f"Candidate cancelled interview (was {original_interview_status_value}). Reason: {cancellation_reason or 'N/A'}."
        if candidate:
            candidate.candidate_confirmation_status = "CancelledByUser";
            new_candidate_status = "Interested" if candidate.current_status in ["Interview Scheduled",
                                                                                "Interview Proposed"] else candidate.current_status
            if reschedule_preference == 'no_reschedule':
                history_event_description += " No reschedule requested."
            elif reschedule_preference == 'request_reschedule':
                history_event_description += " Reschedule requested."
            candidate.notes = (
                                      candidate.notes or "") + f"\n[Interview Cancelled by User {datetime.now(dt_timezone.utc).strftime('%Y-%m-%d')}]: Reschedule: {reschedule_preference}. Reason: {cancellation_reason or 'N/A'}";
            flag_modified(candidate, "notes")
            if new_candidate_status != old_candidate_status_for_log: candidate.current_status = new_candidate_status; candidate.status_last_changed_date = datetime.now(
                dt_timezone.utc)
            candidate.updated_at = datetime.now(dt_timezone.utc)
            candidate.add_history_event(event_type="INTERVIEW_CANCELLED_BY_CANDIDATE",
                                        description=history_event_description,
                                        actor_username=candidate.get_full_name() or "Candidate",
                                        details={'interview_id': str(interview.id),
                                                 'reason': cancellation_reason or "N/A",
                                                 'previous_interview_status': original_interview_status_value,
                                                 'previous_candidate_status': old_candidate_status_for_log,
                                                 'new_candidate_status': candidate.current_status,
                                                 'reschedule_preference': reschedule_preference})
        try:
            db.session.commit();
            celery.send_task('app.tasks.communication.send_interview_cancellation_to_recruiter_task',
                             args=[str(interview.id), cancellation_reason or None, reschedule_preference])
            return render_template("interview_action_response.html", title="Interview Cancelled",
                                   message="Your interview has been cancelled.", status_class="is-success",
                                   company_name=company_name_for_page)
        except Exception as e:
            db.session.rollback();
            current_app.logger.error(
                f"Error committing candidate cancellation for interview token {cancel_token}: {e}",
                exc_info=True);
            return render_template("interview_action_response.html", title="System Error",
                                   message="An error occurred.", status_class="is-danger",
                                   company_name=company_name_for_page), 500
    return render_template("interview_cancel_form.html", interview_id=str(interview.id),
                           candidate_name=interview.candidate.get_full_name() if interview.candidate else "Candidate",
                           company_name=company_name_for_page, cancel_token=cancel_token, scheduled_time_display=(
            interview.scheduled_start_time.astimezone(
                ZoneInfo(current_app.config.get('LOCAL_TIMEZONE', 'Europe/Athens'))).strftime(
                "%A, %d %B %Y at %H:%M") if interview.scheduled_start_time else "N/A"))


@bp.route('/interviews/<int:interview_id>/cancel-by-recruiter', methods=['POST'])
@login_required
def cancel_interview_by_recruiter(interview_id):
    interview = db.session.get(Interview, interview_id);
    if not interview: return jsonify({'error': 'Interview not found'}), 404
    candidate = interview.candidate
    if not candidate: return jsonify({'error': 'Candidate for this interview not found'}), 404
    can_cancel = (current_user.role == 'superadmin') or (
            current_user.role == 'company_admin' and current_user.company_id == interview.company_id) or (
                         current_user.id == interview.recruiter_id)
    if not can_cancel: return jsonify(
        {'error': 'Forbidden: You cannot cancel this interview.'}), 403
    if interview.status not in [InterviewStatus.PROPOSED, InterviewStatus.SCHEDULED]: return jsonify(
        {'error': f'Interview cannot be cancelled in state: {interview.status.value}.'}), 400
    data = request.get_json();
    reason = data.get('reason', 'Cancelled by recruiter.') if data else 'Cancelled by recruiter.'
    original_interview_status = interview.status.value;
    old_candidate_status = candidate.current_status
    interview.status = InterviewStatus.CANCELLED_BY_RECRUITER
    interview.internal_notes = (
                                       interview.internal_notes or "") + f"\nCancelled by {current_user.username} on {datetime.now(dt_timezone.utc).strftime('%Y-%m-%d')}. Reason: {reason}"
    interview.confirmation_token = None;
    interview.token_expiration = None;
    interview.cancellation_token = None;
    interview.cancellation_token_expiration = None
    interview.updated_at = datetime.now(dt_timezone.utc)
    new_candidate_status = "Interested" if old_candidate_status in ["Interview Proposed",
                                                                    "Interview Scheduled"] else old_candidate_status
    if candidate.current_status != new_candidate_status: candidate.current_status = new_candidate_status; candidate.status_last_changed_date = datetime.now(
        dt_timezone.utc)
    candidate.candidate_confirmation_status = "RecruiterCancelled";
    candidate.updated_at = datetime.now(dt_timezone.utc)
    candidate.add_history_event(event_type="INTERVIEW_CANCELLED_BY_RECRUITER",
                                description=f"Interview (ID: {interview.id}, was {original_interview_status}) cancelled by recruiter {current_user.username}. Reason: {reason}",
                                actor_id=current_user.id, details={'interview_id': str(interview.id), 'reason': reason,
                                                                   'previous_interview_status': original_interview_status,
                                                                   'previous_candidate_status': old_candidate_status,
                                                                   'new_candidate_status': candidate.current_status})
    try:
        db.session.commit();
        celery.send_task('app.tasks.communication.send_interview_cancellation_to_candidate_task',
                         args=[str(interview.id), reason])
        return jsonify(
            {'message': 'Interview cancelled successfully.', 'interview': interview.to_dict(include_slots=True),
             'candidate_status': candidate.current_status}), 200
    except Exception as e:
        db.session.rollback();
        current_app.logger.error(f"Error cancelling interview {interview_id} by recruiter: {e}",
                                 exc_info=True);
        return jsonify(
            {'error': 'Failed to cancel interview.'}), 500


# --- OFFER ACTION ROUTES ---
@bp.route('/offer/accept/<string:token>', methods=['GET'])
def accept_offer(token):
    candidate = Candidate.query.filter_by(offer_acceptance_token=token).first()
    company_name_for_page = "Our Company"
    if candidate and candidate.company:
        company_name_for_page = candidate.company.name

    if not candidate or not candidate.is_offer_token_valid():
        current_app.logger.warning(f"Invalid or expired offer acceptance token used: {token}")
        return render_template("interview_action_response.html", title="Error",
                               message="This offer link is invalid or has expired. Please contact the company if you believe this is an error.",
                               status_class="is-danger", company_name=company_name_for_page), 404

    if candidate.current_status != 'OfferMade':
        current_app.logger.info(
            f"Offer token {token} used for candidate {candidate.candidate_id} whose status is already {candidate.current_status}.")
        message_for_processed_offer = "This offer has already been processed."
        if candidate.current_status == 'Hired':
            message_for_processed_offer = "This offer has already been accepted and your status is Hired. Welcome aboard!"
        elif candidate.current_status == 'Declined':
            message_for_processed_offer = "This offer was previously declined."
        return render_template("interview_action_response.html", title="Information",
                               message=message_for_processed_offer,
                               status_class="is-info", company_name=company_name_for_page), 400

    old_status = candidate.current_status
    candidate.current_status = 'Hired'
    candidate.status_last_changed_date = datetime.now(dt_timezone.utc)
    candidate.offer_acceptance_token = None
    candidate.offer_acceptance_token_expiration = None
    candidate.updated_at = datetime.now(dt_timezone.utc)
    candidate.add_history_event(event_type="OFFER_ACCEPTED_BY_CANDIDATE",
                                description=f"Candidate accepted offer. Status changed from '{old_status}' to 'Hired'.",
                                actor_username=candidate.get_full_name() or "Candidate",
                                details={'offer_token_used': token})
    try:
        db.session.commit()
        celery.send_task('app.tasks.communication.send_hired_confirmation_email_to_candidate_task',
                         args=[str(candidate.candidate_id)])
        current_app.logger.info(f"Candidate {candidate.candidate_id} accepted offer. Status: Hired.")
        return render_template("interview_action_response.html", title="Offer Accepted!",
                               message="Congratulations! Your offer has been accepted. We will be in touch shortly with more details.",
                               status_class="is-success", company_name=company_name_for_page)
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error processing offer acceptance for token {token}: {e}", exc_info=True)
        return render_template("interview_action_response.html", title="System Error",
                               message="An error occurred while processing your acceptance. Please contact us.",
                               status_class="is-danger", company_name=company_name_for_page), 500


@bp.route('/offer/reject/<string:token>', methods=['GET'], endpoint='reject_offer_form')
def reject_offer_form(token):
    candidate = Candidate.query.filter_by(offer_acceptance_token=token).first()
    company_name_for_page = "Our Company"
    position_name_display = "this position"
    frontend_url_for_template = current_app.config.get('FRONTEND_URL', '#')

    if candidate:
        if candidate.company: company_name_for_page = candidate.company.name
        if candidate.positions and candidate.positions.count() > 0:
            position_names = [p.position_name for p in candidate.positions.all() if p.position_name]
            if position_names:
                position_name_display = ', '.join(position_names)

    if not candidate or not candidate.is_offer_token_valid():
        current_app.logger.warning(f"Invalid or expired offer rejection token used for form: {token}")
        return render_template("interview_action_response.html", title="Error",
                               message="This offer link is invalid or has expired. Please contact the company if you believe this is an error.",
                               status_class="is-danger", company_name=company_name_for_page), 404

    if candidate.current_status != 'OfferMade':
        current_app.logger.info(
            f"Offer rejection token (form) {token} used for candidate {candidate.candidate_id} whose status is {candidate.current_status}.")
        message_for_processed_offer = "This offer has already been processed."
        if candidate.current_status == 'Hired':
            message_for_processed_offer = "This offer was previously accepted."
        elif candidate.current_status == 'Declined':
            message_for_processed_offer = "This offer was previously declined."
        return render_template("interview_action_response.html", title="Information",
                               message=message_for_processed_offer,
                               status_class="is-info", company_name=company_name_for_page), 400

    return render_template("offer_reject_form.html",
                           token=token,
                           candidate_name=candidate.get_full_name(),
                           company_name=company_name_for_page,
                           position_name_display=position_name_display,
                           frontend_url=frontend_url_for_template)


@bp.route('/offer/reject/<string:token>', methods=['POST'], endpoint='reject_offer_submit')
def reject_offer_submit(token):
    candidate = Candidate.query.filter_by(offer_acceptance_token=token).first()
    company_name_for_page = "Our Company"
    position_name_display = "this position"
    frontend_url_for_template = current_app.config.get('FRONTEND_URL', '#')

    if candidate:
        if candidate.company: company_name_for_page = candidate.company.name
        if candidate.positions and candidate.positions.count() > 0:
            position_names = [p.position_name for p in candidate.positions.all() if p.position_name]
            if position_names:
                position_name_display = ', '.join(position_names)

    if not candidate:
        current_app.logger.error(f"Offer rejection submission for non-existent token/candidate: {token}")
        return render_template("interview_action_response.html", title="Error",
                               message="Invalid request. Offer link may be incorrect or expired.",
                               status_class="is-danger", company_name=company_name_for_page), 400

    if candidate.current_status != 'OfferMade':
        return render_template("interview_action_response.html", title="Information",
                               message="This offer has already been processed.",
                               status_class="is-info", company_name=company_name_for_page), 400

    rejection_reason = request.form.get('rejection_reason', '').strip()[:1000]
    rejection_reason_provided = bool(rejection_reason)

    old_status = candidate.current_status
    candidate.current_status = 'Declined'
    candidate.status_last_changed_date = datetime.now(dt_timezone.utc)

    if rejection_reason_provided:
        timestamp_str = datetime.now(dt_timezone.utc).strftime('%Y-%m-%d %H:%M')
        reason_to_log = f"[Offer Rejected by Candidate - {timestamp_str}]: {rejection_reason}"
        candidate.hr_comments = (
                                    candidate.hr_comments + "\n\n" if candidate.hr_comments and candidate.hr_comments.strip() else "") + reason_to_log
        flag_modified(candidate, "hr_comments")

    candidate.offer_acceptance_token = None
    candidate.offer_acceptance_token_expiration = None
    candidate.updated_at = datetime.now(dt_timezone.utc)
    candidate.add_history_event(event_type="OFFER_REJECTED_BY_CANDIDATE",
                                description=f"Candidate declined offer. Status changed from '{old_status}' to 'Declined'. " + (
                                    "Reason provided." if rejection_reason_provided else "No specific reason provided."),
                                actor_username=candidate.get_full_name() or "Candidate",
                                details={'offer_token_used': token,
                                         'rejection_reason_provided': rejection_reason_provided})
    try:
        db.session.commit()
        celery.send_task('app.tasks.communication.send_offer_declined_confirmation_to_candidate_task',
                         args=[str(candidate.candidate_id), rejection_reason_provided])
        celery.send_task('app.tasks.communication.send_offer_declined_notification_to_recruiter_task',
                         args=[str(candidate.candidate_id), rejection_reason or None])
        current_app.logger.info(
            f"Candidate {candidate.candidate_id} rejected offer. Status: Declined. Reason: '{escape(rejection_reason) if rejection_reason else 'N/A'}'")
        return render_template("interview_action_response.html", title="Offer Declined",
                               message="Thank you for your response. We have recorded your decision and appreciate your feedback.",
                               status_class="is-info", company_name=company_name_for_page)
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error processing offer rejection for token {token} (submit): {e}", exc_info=True)
        return render_template("offer_reject_form.html",
                               token=token,
                               candidate_name=candidate.get_full_name(),
                               company_name=company_name_for_page,
                               position_name_display=position_name_display,
                               frontend_url=frontend_url_for_template,
                               error_message="An internal error occurred. Please try submitting again or contact us."), 500


# --- SETTINGS ROUTE ---
@bp.route('/settings', methods=['GET'])
@login_required
def get_user_settings():
    user_settings = {'username': current_user.username, 'email': current_user.email,
                     'enable_email_interview_reminders': current_user.enable_email_interview_reminders,
                     'interview_reminder_lead_time_minutes': current_user.interview_reminder_lead_time_minutes}
    return jsonify(user_settings), 200


@bp.route('/settings', methods=['PUT'])
@login_required
def update_user_settings():
    data = request.get_json();
    if not data: return jsonify({'error': 'No data provided'}), 400
    updated_fields_count = 0;
    settings_changed_details = {}
    if 'enable_email_interview_reminders' in data:
        new_val = bool(data['enable_email_interview_reminders'])
        if current_user.enable_email_interview_reminders != new_val: settings_changed_details[
            'enable_email_interview_reminders'] = {'old': current_user.enable_email_interview_reminders,
                                                   'new': new_val}; current_user.enable_email_interview_reminders = new_val; updated_fields_count += 1
    if 'interview_reminder_lead_time_minutes' in data:
        try:
            lead_time = int(data['interview_reminder_lead_time_minutes']);
            min_lead = current_app.config.get('MIN_INTERVIEW_REMINDER_LEAD_TIME', 15);
            max_lead = current_app.config.get('MAX_INTERVIEW_REMINDER_LEAD_TIME', 2 * 24 * 60)
            if not (min_lead <= lead_time <= max_lead): return jsonify(
                {'error': f'Reminder lead time must be between {min_lead} and {max_lead} minutes.'}), 400
            if current_user.interview_reminder_lead_time_minutes != lead_time: settings_changed_details[
                'interview_reminder_lead_time_minutes'] = {'old': current_user.interview_reminder_lead_time_minutes,
                                                           'new': lead_time}; current_user.interview_reminder_lead_time_minutes = lead_time; updated_fields_count += 1
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid lead time value.'}), 400
    if updated_fields_count == 0: return jsonify({'message': 'No settings were changed.'}), 200
    current_user.updated_at = datetime.now(dt_timezone.utc)
    try:
        db.session.commit();
        updated_settings_response = {'enable_email_interview_reminders': current_user.enable_email_interview_reminders,
                                     'interview_reminder_lead_time_minutes': current_user.interview_reminder_lead_time_minutes}
        current_app.logger.info(f"User {current_user.id} updated settings: {settings_changed_details}")
        return jsonify({'message': 'User settings updated successfully', 'settings': updated_settings_response}), 200
    except Exception as e:
        db.session.rollback();
        current_app.logger.error(f"Error updating user settings for user {current_user.id}: {e}",
                                 exc_info=True);
        return jsonify(
            {'error': 'Failed to update user settings.'}), 500
