# backend/app/api/routes.py

from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
import uuid
from datetime import datetime, timezone as dt_timezone
from dateutil import parser as dateutil_parser
from flask_login import login_user, logout_user, current_user, login_required
from app import db, celery
from app.models import User, Candidate, Position, Company, CompanySettings
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import func, case, or_, extract, DECIMAL  # Προσθήκη DECIMAL για το avg_days_to_interview
from app.services import s3_service

bp = Blueprint('api', __name__)

ALLOWED_EXTENSIONS = {'pdf', 'docx'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_current_user_company_id():
    if not current_user.is_authenticated:
        return None
    if current_user.role == 'superadmin':
        return None
    if not current_user.company_id:
        current_app.logger.error(
            f"User {current_user.id} ({current_user.username}) with role {current_user.role} has no company_id.")
        return None
    return current_user.company_id


# --- Login/Register/Session Routes ---
@bp.route('/register', methods=['POST'])
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

    new_user = User(username=username, email=email, role='user', is_active=False)
    new_user.set_password(password)
    try:
        db.session.add(new_user)
        db.session.commit()
        current_app.logger.info(f"New user registered: {username} ({email}). Awaiting activation/assignment.")
        return jsonify({
            "message": "Registration successful. Account activation and company assignment pending administrator review."}), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error during user registration for {username}: {e}", exc_info=True)
        return jsonify({"error": "Registration failed due to an internal error."}), 500


@bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data: return jsonify({"error": "Invalid JSON format"}), 400
    login_identifier = data.get('login_identifier')
    password = data.get('password')
    if not login_identifier or not password:
        return jsonify({"error": "Login identifier and password required"}), 400
    remember = data.get('remember', False)
    user = User.query.filter((User.username == login_identifier) | (User.email == login_identifier)).first()
    if user and user.check_password(password):
        if not user.is_active:
            return jsonify({"error": "Account not active. Please check your email or contact an administrator."}), 403
        if user.role != 'superadmin' and not user.company_id:
            return jsonify({"error": "Account not yet assigned to a company by an administrator."}), 403
        login_user(user, remember=remember)
        user_data = user.to_dict(include_company_info=True)
        current_app.logger.info(f"User {user.username} (Role: {user.role}, CompanyID: {user.company_id}) logged in.")
        return jsonify({"message": "Login successful", "user": user_data}), 200
    return jsonify({"error": "Invalid login identifier or password"}), 401


@bp.route('/logout', methods=['POST'])
@login_required
def logout():
    user_id_log = current_user.id
    username_log = current_user.username
    logout_user()
    current_app.logger.info(f"User {username_log} (ID: {user_id_log}) logged out.")
    return jsonify({"message": "Logout successful"}), 200


@bp.route('/session', methods=['GET'])
def check_session():
    if current_user.is_authenticated:
        user_data = current_user.to_dict(include_company_info=True)
        return jsonify({"authenticated": True, "user": user_data}), 200
    return jsonify({"authenticated": False}), 200


@bp.route('/upload', methods=['POST'])
@login_required
def upload_cv():
    current_app.logger.info(f"--- Upload Request Received by User ID: {current_user.id} ({current_user.username}) ---")
    user_company_id_for_context = get_current_user_company_id()
    target_company_id_for_candidate = None

    if current_user.role == 'superadmin':
        target_company_id_from_form = request.form.get('company_id_for_upload', type=int)
        if not target_company_id_from_form:
            return jsonify({"error": "Superadmin must specify a target company_id for the candidate."}), 400
        company_exists = Company.query.get(target_company_id_from_form)
        if not company_exists:
            return jsonify({"error": f"Target company with ID {target_company_id_from_form} not found."}), 404
        target_company_id_for_candidate = target_company_id_from_form
    elif user_company_id_for_context:
        target_company_id_for_candidate = user_company_id_for_context
    else:
        return jsonify({"error": "User not associated with a company or unauthorized."}), 403

    if 'cv_file' not in request.files:
        return jsonify({"error": "No file part named 'cv_file'"}), 400
    file = request.files['cv_file']
    position_name_from_form = request.form.get('position', None)

    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if not allowed_file(file.filename):
        return jsonify({"error": f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"}), 400

    uploaded_s3_key = None
    try:
        file_ext = file.filename.rsplit('.', 1)[1].lower()
        original_filename = secure_filename(file.filename)
        s3_key = f"company_{target_company_id_for_candidate}/cvs/{uuid.uuid4()}.{file_ext}"

        file.seek(0)
        uploaded_s3_key = s3_service.upload_file(file, s3_key)
        if not uploaded_s3_key:
            raise Exception("S3 upload service indicated failure without raising an exception.")

        new_candidate = Candidate(
            cv_original_filename=original_filename,
            cv_storage_path=uploaded_s3_key,
            current_status='Processing',
            confirmation_uuid=uuid.uuid4(),
            company_id=target_company_id_for_candidate
        )

        if position_name_from_form and position_name_from_form.strip():
            pos_name_cleaned = position_name_from_form.strip()
            position = Position.query.filter(
                func.lower(Position.position_name) == func.lower(pos_name_cleaned),
                Position.company_id == target_company_id_for_candidate
            ).first()
            if not position:
                position = Position(position_name=pos_name_cleaned,
                                    company_id=target_company_id_for_candidate,
                                    status='Open')
                db.session.add(position)
            new_candidate.positions.append(position)

        db.session.add(new_candidate)
        db.session.commit()
        candidate_id_for_task = str(new_candidate.candidate_id)

        celery.send_task('tasks.parsing.parse_cv_task',
                         args=[candidate_id_for_task, uploaded_s3_key, target_company_id_for_candidate])
        current_app.logger.info(
            f"CV uploaded (S3 Key: {uploaded_s3_key}), Placeholder Candidate ID: {candidate_id_for_task} created for Company {target_company_id_for_candidate}. Parsing task queued.")
        return jsonify(new_candidate.to_dict()), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            f"Upload Error (User: {current_user.id}, TargetCompany: {target_company_id_for_candidate}): {e}",
            exc_info=True)
        if uploaded_s3_key:
            try:
                s3_service.delete_file(uploaded_s3_key)
                current_app.logger.info(f"S3 file {uploaded_s3_key} deleted due to subsequent error.")
            except Exception as s3_del_err:
                current_app.logger.error(
                    f"S3 cleanup FAILED for key {uploaded_s3_key} after upload error: {s3_del_err}")
        return jsonify({"error": "Internal server error during CV upload."}), 500


# --- Dashboard Routes ---
@bp.route('/dashboard/summary', methods=['GET'])
@login_required
def get_dashboard_summary():
    user_company_id_context = get_current_user_company_id()
    query_target_company_id = None

    if current_user.role == 'superadmin':
        company_id_filter_param = request.args.get('company_id', type=int)
        if company_id_filter_param:
            query_target_company_id = company_id_filter_param
    elif user_company_id_context:
        query_target_company_id = user_company_id_context
    else:
        return jsonify({"error": "User not associated with a company or not authorized."}), 403

    try:
        relevant_statuses = [
            'New', 'Processing', 'NeedsReview', 'Interview', 'OfferMade', 'Hired',
            'Rejected', 'ParsingFailed', 'Accepted', 'Declined', 'Interested',
            'Evaluation', 'On Hold'
        ]

        # Function to generate keys exactly as seen in your logs
        def generate_key_from_log_format(status_string):
            # Based on your logs: 'needsreview', 'offermade', 'parsingfailed'
            # This implies removing spaces and hyphens, then lowercasing.
            return status_string.replace(" ", "").replace("-", "").lower()

        status_keys_for_dict = {status: generate_key_from_log_format(status) for status in relevant_statuses}

        status_aggregations = [
            func.sum(case((Candidate.current_status == status, 1), else_=0)).label(
                status_keys_for_dict[status]
            )
            for status in relevant_statuses
        ]

        query_obj = db.session.query(func.count(Candidate.candidate_id).label("total_candidates"), *status_aggregations)

        if query_target_company_id:
            query_obj = query_obj.filter(Candidate.company_id == query_target_company_id)

        q_result = query_obj.first()

        summary = {"total_candidates": 0}
        for status in relevant_statuses:
            summary[status_keys_for_dict[status]] = 0

        if q_result:
            summary.update({k: (v or 0) for k, v in q_result._asdict().items()})

        current_app.logger.info(
            f"CORRECTED Dashboard Summary for company {query_target_company_id if query_target_company_id else 'ALL'}: {summary}")
        return jsonify(summary), 200
    except Exception as e:
        current_app.logger.error(
            f"Dashboard Summary Error (User: {current_user.id}, Company Filter: {query_target_company_id}): {e}",
            exc_info=True)
        return jsonify({"error": "Failed to retrieve dashboard summary."}), 500


@bp.route('/dashboard/statistics', methods=['GET'])
@login_required
def get_dashboard_statistics():
    user_company_id_context = get_current_user_company_id()
    query_target_company_id = None

    if current_user.role == 'superadmin':
        company_id_filter_param = request.args.get('company_id', type=int)
        if company_id_filter_param:
            query_target_company_id = company_id_filter_param
    elif user_company_id_context:
        query_target_company_id = user_company_id_context
    else:
        return jsonify({"error": "User not associated with a company or not authorized."}), 403

    stats = {}
    try:
        base_query_candidate = Candidate.query
        base_query_position = Position.query

        if query_target_company_id:
            base_query_candidate = base_query_candidate.filter(Candidate.company_id == query_target_company_id)
            base_query_position = base_query_position.filter(Position.company_id == query_target_company_id)

        total_candidates_for_company = base_query_candidate.count()

        reached_interview_statuses = ['Interview', 'Evaluation', 'OfferMade', 'Hired']
        reached_interview_count = base_query_candidate.filter(
            Candidate.current_status.in_(reached_interview_statuses)
        ).count()

        stats['interview_reach_percentage'] = round(
            (reached_interview_count / total_candidates_for_company) * 100, 1
        ) if total_candidates_for_company > 0 else 0.0

        # avg_days_to_interview might return Decimal, ensure it's serializable
        avg_time_subquery_result = db.session.query(
            func.avg(
                extract('epoch', Candidate.interview_datetime) - extract('epoch', Candidate.submission_date)
            ).label('avg_duration_seconds')
        ).filter(
            Candidate.submission_date.isnot(None),
            Candidate.interview_datetime.isnot(None),
            Candidate.interview_datetime > Candidate.submission_date,
            Candidate.current_status.in_(['Interview', 'Evaluation', 'OfferMade', 'Hired'])
        )
        if query_target_company_id:
            avg_time_subquery_result = avg_time_subquery_result.filter(Candidate.company_id == query_target_company_id)

        avg_result = avg_time_subquery_result.scalar()  # Use scalar to get single value or None

        if avg_result is not None:  # avg_result could be Decimal
            stats['avg_days_to_interview'] = round(float(avg_result) / (60 * 60 * 24), 1)
        else:
            stats['avg_days_to_interview'] = "N/A"

        stats['open_positions_count'] = base_query_position.filter(Position.status == 'Open').count()

        pipeline_status_order = [
            'NeedsReview', 'Accepted', 'Interested', 'Interview', 'Evaluation', 'OfferMade', 'Hired'
        ]
        other_statuses_to_count = ['Processing', 'ParsingFailed', 'New', 'On Hold', 'Rejected', 'Declined']
        all_statuses_for_query = pipeline_status_order + other_statuses_to_count

        candidates_by_stage_query = db.session.query(
            Candidate.current_status,
            func.count(Candidate.candidate_id).label('count')
        ).filter(Candidate.current_status.in_(all_statuses_for_query))

        if query_target_company_id:
            candidates_by_stage_query = candidates_by_stage_query.filter(
                Candidate.company_id == query_target_company_id)

        candidates_by_stage_results = candidates_by_stage_query.group_by(Candidate.current_status).all()

        stats_by_stage_dict = {status: 0 for status in all_statuses_for_query}

        for status_value, count in candidates_by_stage_results:
            if status_value in stats_by_stage_dict:
                stats_by_stage_dict[status_value] = count

        stats['candidates_by_stage'] = []
        for status_val_in_pipeline in pipeline_status_order:
            stage_name_display = status_val_in_pipeline.replace("NeedsReview", "Needs Review").replace("OfferMade",
                                                                                                       "Offer Made").replace(
                "ParsingFailed", "Parsing Failed")

            stats['candidates_by_stage'].append({
                "stage_name": stage_name_display,
                "stage_value": status_val_in_pipeline,
                "count": stats_by_stage_dict.get(status_val_in_pipeline, 0)
            })
        current_app.logger.info(
            f"Generated candidates_by_stage for chart (Company {query_target_company_id if query_target_company_id else 'ALL'}): {stats['candidates_by_stage']}")

        current_app.logger.info(
            f"Returning statistics for company {query_target_company_id if query_target_company_id else 'ALL'}: {stats}")
        return jsonify(stats), 200
    except Exception as e:
        current_app.logger.error(
            f"Dashboard Statistics Error (User: {current_user.id}, Company Filter: {query_target_company_id}): {e}",
            exc_info=True)
        return jsonify({"error": "Failed to retrieve dashboard statistics."}), 500


# ... (Ο υπόλοιπος κώδικας για /candidates, /candidate/<id>, /search, /settings, /interviews παραμένει ο ίδιος με πριν)

@bp.route('/candidates/<string:status_param>', methods=['GET'])
@login_required
def get_candidates_by_status(status_param):
    valid_statuses = [
        'New', 'Processing', 'NeedsReview', 'Interview', 'OfferMade', 'Hired',
        'Rejected', 'ParsingFailed', 'Accepted', 'Declined', 'Interested',
        'Evaluation', 'On Hold', 'All'
    ]
    if status_param not in valid_statuses:
        return jsonify({"error": f"Invalid status filter: {status_param}."}), 400

    user_company_id_context = get_current_user_company_id()
    query_target_company_id = None
    if current_user.role == 'superadmin':
        company_id_filter_param = request.args.get('company_id', type=int)
        if company_id_filter_param:
            query_target_company_id = company_id_filter_param
    elif user_company_id_context:
        query_target_company_id = user_company_id_context
    else:
        return jsonify({"error": "User not associated with a company or unauthorized."}), 403

    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 15, type=int)

        query_obj = Candidate.query
        if query_target_company_id:
            query_obj = query_obj.filter(Candidate.company_id == query_target_company_id)

        if status_param != 'All':
            query_obj = query_obj.filter(Candidate.current_status == status_param)

        pagination = query_obj.order_by(Candidate.submission_date.desc().nullslast()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        candidates_data = []
        for cand in pagination.items:
            cv_url_val = s3_service.generate_presigned_url(cand.cv_storage_path) if cand.cv_storage_path else None
            candidates_data.append(cand.to_dict(include_cv_url=True, cv_url=cv_url_val))

        return jsonify({
            "candidates": candidates_data,
            "total_results": pagination.total,
            "current_page": pagination.page,
            "per_page": pagination.per_page,
            "total_pages": pagination.pages
        }), 200
    except Exception as e:
        current_app.logger.error(
            f"Error listing candidates (Status: {status_param}, User: {current_user.id}, Company: {query_target_company_id}): {e}",
            exc_info=True)
        return jsonify({"error": "Failed to retrieve candidate list."}), 500


@bp.route('/candidate/<string:candidate_id_url>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def handle_candidate(candidate_id_url):
    try:
        candidate_uuid = uuid.UUID(candidate_id_url)
    except ValueError:
        return jsonify({"error": "Invalid candidate ID format."}), 400

    candidate = Candidate.query.get_or_404(candidate_uuid,
                                           description=f"Candidate with ID {candidate_id_url} not found.")
    user_company_id_context = get_current_user_company_id()
    user_id_for_logs = current_user.id
    user_username_for_logs = current_user.username

    if current_user.role != 'superadmin':
        if not user_company_id_context or candidate.company_id != user_company_id_context:
            current_app.logger.warning(
                f"Access denied for user {user_id_for_logs} (Company: {user_company_id_context}) to candidate {candidate.candidate_id} (Company: {candidate.company_id})")
            return jsonify({"error": "Access denied to this candidate."}), 403

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
        current_app.logger.info(
            f"PUT Candidate {candidate.candidate_id} by User {user_id_for_logs} ({user_username_for_logs}). Payload (first 500 chars): {str(request.data)[:500]}")
        data = request.get_json()
        if not data:
            return jsonify({"error": "No input data provided. Request body must be JSON."}), 400

        updated_fields_tracker = False
        original_status = candidate.current_status
        original_interview_time = candidate.interview_datetime
        interview_time_changed_flag = False

        allowed_direct_updates = [
            'first_name', 'last_name', 'email', 'phone_number', 'age',
            'education_summary', 'experience_summary', 'skills_summary',
            'languages', 'seminars', 'notes', 'evaluation_rating',
            'interview_location', 'interview_type',
            'hr_comments'
        ]

        for key, value_from_payload in data.items():
            if key in allowed_direct_updates:
                current_value_on_candidate = getattr(candidate, key, None)
                new_value = value_from_payload

                if key == 'age':
                    if value_from_payload is None or str(value_from_payload).strip() == '':
                        new_value = None
                    else:
                        try:
                            new_value = int(value_from_payload)
                            if not (0 <= new_value <= 120):
                                new_value = None
                                current_app.logger.warning(f"Invalid age value: {value_from_payload}. Set to None.")
                        except ValueError:
                            current_app.logger.warning(
                                f"Invalid value for age: {value_from_payload}. Skipping update for age.")
                            continue

                if key == 'email' and value_from_payload:
                    new_value = value_from_payload.lower().strip()
                    if new_value != candidate.email:
                        existing_with_new_email = Candidate.query.filter(
                            Candidate.email == new_value,
                            Candidate.company_id == candidate.company_id,
                            Candidate.candidate_id != candidate.candidate_id
                        ).first()
                        if existing_with_new_email:
                            current_app.logger.warning(
                                f"Attempt to update email for candidate {candidate.candidate_id} to '{new_value}', which already exists for company {candidate.company_id}.")
                            return jsonify({
                                "error": f"Email '{new_value}' is already in use by another candidate in this company."}), 409

                if current_value_on_candidate != new_value:
                    setattr(candidate, key, new_value)
                    updated_fields_tracker = True
                    current_app.logger.debug(
                        f"Candidate {candidate.candidate_id}: Field '{key}' changed from '{current_value_on_candidate}' to '{new_value}'")

            elif key == 'interview_datetime':
                new_dt_value_utc = None
                if value_from_payload:
                    try:
                        parsed_dt = dateutil_parser.isoparse(value_from_payload)
                        new_dt_value_utc = parsed_dt.astimezone(
                            dt_timezone.utc) if parsed_dt.tzinfo else parsed_dt.replace(tzinfo=dt_timezone.utc)
                    except (ValueError, TypeError) as date_parse_err:
                        current_app.logger.warning(
                            f"Invalid date format for interview_datetime ('{value_from_payload}'). Error: {date_parse_err}. Skipping update.")
                        continue

                if (original_interview_time and new_dt_value_utc != original_interview_time) or \
                        (not original_interview_time and new_dt_value_utc is not None) or \
                        (original_interview_time and new_dt_value_utc is None):
                    candidate.interview_datetime = new_dt_value_utc
                    interview_time_changed_flag = True
                    updated_fields_tracker = True
                    current_app.logger.debug(
                        f"Candidate {candidate.candidate_id}: Field 'interview_datetime' changed from '{original_interview_time}' to '{new_dt_value_utc}'")

            elif key == 'positions' and isinstance(value_from_payload, list):
                current_candidate_pos_names_lower = {p.position_name.lower().strip() for p in candidate.positions}
                target_pos_names_from_payload_lower = {p_name.strip().lower() for p_name in value_from_payload if
                                                       isinstance(p_name, str) and p_name.strip()}

                positions_to_disassociate_objs = [p for p in candidate.positions if
                                                  p.position_name.lower().strip() not in target_pos_names_from_payload_lower]
                if positions_to_disassociate_objs:
                    for pos_obj_to_remove in positions_to_disassociate_objs:
                        candidate.positions.remove(pos_obj_to_remove)
                    updated_fields_tracker = True
                    current_app.logger.debug(
                        f"Candidate {candidate.candidate_id}: Disassociated positions: {[p.position_name for p in positions_to_disassociate_objs]}")

                for pos_name_target_lower in target_pos_names_from_payload_lower:
                    if pos_name_target_lower not in current_candidate_pos_names_lower:
                        original_case_pos_name = next((p_name_orig for p_name_orig in value_from_payload if
                                                       p_name_orig.strip().lower() == pos_name_target_lower),
                                                      pos_name_target_lower.title())

                        position_obj_to_add = Position.query.filter(
                            func.lower(Position.position_name) == pos_name_target_lower,
                            Position.company_id == candidate.company_id
                        ).first()
                        if not position_obj_to_add:
                            position_obj_to_add = Position(position_name=original_case_pos_name,
                                                           company_id=candidate.company_id, status='Open')
                            db.session.add(position_obj_to_add)
                            current_app.logger.debug(
                                f"Candidate {candidate.candidate_id}: Created new position '{original_case_pos_name}' during update.")

                        if position_obj_to_add not in candidate.positions:
                            candidate.positions.append(position_obj_to_add)
                            updated_fields_tracker = True
                            current_app.logger.debug(
                                f"Candidate {candidate.candidate_id}: Associated with position '{position_obj_to_add.position_name}'")

            elif key == 'offers' and isinstance(value_from_payload, list):
                sanitized_offers = []
                for offer_data in value_from_payload:
                    if isinstance(offer_data, dict):
                        clean_offer = {}
                        if 'offer_amount' in offer_data and offer_data['offer_amount'] not in [None, '']:
                            try:
                                clean_offer['offer_amount'] = float(offer_data['offer_amount'])
                            except (ValueError, TypeError):
                                clean_offer['offer_amount'] = None
                        else:
                            clean_offer['offer_amount'] = None

                        if 'offer_date' in offer_data and offer_data['offer_date']:
                            try:
                                dateutil_parser.isoparse(offer_data['offer_date'])
                                clean_offer['offer_date'] = offer_data['offer_date']
                            except:
                                clean_offer['offer_date'] = datetime.now(dt_timezone.utc).isoformat()
                        else:
                            clean_offer['offer_date'] = datetime.now(dt_timezone.utc).isoformat()
                        clean_offer['offer_notes'] = offer_data.get('offer_notes', '')
                        sanitized_offers.append(clean_offer)

                if candidate.offers != sanitized_offers:
                    candidate.offers = sanitized_offers
                    flag_modified(candidate, "offers")
                    updated_fields_tracker = True
                    current_app.logger.debug(f"Candidate {candidate.candidate_id}: Offers updated.")

        new_status_from_payload = data.get('current_status', original_status)
        status_changed_flag = False
        if new_status_from_payload != original_status:
            candidate.current_status = new_status_from_payload
            updated_fields_tracker = True
            status_changed_flag = True
            candidate.add_history_event(
                event_type="status_change",
                description=f"Status changed from '{original_status}' to '{new_status_from_payload}'.",
                actor_id=user_id_for_logs,
                actor_username=user_username_for_logs,
                details={
                    "previous_status": original_status,
                    "new_status": new_status_from_payload,
                }
            )
            current_app.logger.debug(
                f"Candidate {candidate.candidate_id}: Status changed from '{original_status}' to '{new_status_from_payload}' by {user_username_for_logs}")

            if original_status in ['Interview', 'Evaluation'] and new_status_from_payload not in ['Interview',
                                                                                                  'Evaluation',
                                                                                                  'OfferMade', 'Hired']:
                candidate.interview_datetime = None
                candidate.interview_location = None
                candidate.interview_type = None
                candidate.candidate_confirmation_status = None

            if new_status_from_payload == 'NeedsReview' and original_status in ['Rejected', 'Declined', 'Hired',
                                                                                'ParsingFailed']:
                candidate.candidate_confirmation_status = None
                if 'evaluation_rating' not in data: candidate.evaluation_rating = None
                if 'offers' not in data: candidate.offers = []; flag_modified(candidate, "offers")

        if interview_time_changed_flag or (status_changed_flag and candidate.current_status == 'Interview'):
            if candidate.interview_datetime:
                candidate.candidate_confirmation_status = 'Pending'
                candidate.confirmation_uuid = uuid.uuid4()
                current_app.logger.info(
                    f"Candidate {candidate.candidate_id}: Interview (re)scheduled. Confirmation status set to Pending with new UUID {candidate.confirmation_uuid}.")
            else:
                if candidate.candidate_confirmation_status is not None:
                    candidate.candidate_confirmation_status = None
                    current_app.logger.info(
                        f"Candidate {candidate.candidate_id}: Interview cleared. Confirmation status reset.")

        if not updated_fields_tracker:
            cv_url_val_no_change = s3_service.generate_presigned_url(candidate.cv_storage_path,
                                                                     expiration=900) if candidate.cv_storage_path else None
            return jsonify(candidate.to_dict(include_cv_url=True,
                                             cv_url=cv_url_val_no_change)), 200

        try:
            candidate.updated_at = datetime.now(dt_timezone.utc)
            db.session.commit()
            current_app.logger.info(
                f"Candidate {candidate.candidate_id} updated successfully by {user_id_for_logs} ({user_username_for_logs}).")

            should_send_invitation = (
                                             interview_time_changed_flag and candidate.interview_datetime and candidate.current_status == 'Interview') or \
                                     (
                                             status_changed_flag and candidate.current_status == 'Interview' and candidate.interview_datetime and candidate.candidate_confirmation_status == 'Pending')

            if should_send_invitation:
                try:
                    celery.send_task('tasks.communication.send_interview_invitation_email_task',
                                     args=[str(candidate.candidate_id)])
                    current_app.logger.info(f"Sent interview invitation task for candidate {candidate.candidate_id}")
                except Exception as celery_e:
                    current_app.logger.error(
                        f"Celery task queue error (send_interview_invitation_email_task): {celery_e}")

            if status_changed_flag and new_status_from_payload in ['Rejected', 'Declined']:
                try:
                    celery.send_task('tasks.communication.send_rejection_email_task',
                                     args=[str(candidate.candidate_id)])
                    current_app.logger.info(f"Sent rejection email task for candidate {candidate.candidate_id}")
                except Exception as celery_e:
                    current_app.logger.error(f"Celery task queue error (send_rejection_email_task): {celery_e}")

            cv_url_val_updated = s3_service.generate_presigned_url(candidate.cv_storage_path,
                                                                   expiration=900) if candidate.cv_storage_path else None
            return jsonify(candidate.to_dict(include_cv_url=True, cv_url=cv_url_val_updated)), 200
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error committing updates for candidate {candidate.candidate_id}: {e}",
                                     exc_info=True)
            return jsonify({"error": "Failed to update candidate details due to an internal error."}), 500

    elif request.method == 'DELETE':
        current_app.logger.info(
            f"DELETE Candidate {candidate.candidate_id} attempt by User {user_id_for_logs} ({user_username_for_logs})")
        s3_key_to_delete = candidate.cv_storage_path
        candidate_name_log = candidate.get_full_name()
        cand_id_log = str(candidate.candidate_id)

        try:
            db.session.delete(candidate)
            db.session.commit()
            current_app.logger.info(
                f"Candidate {cand_id_log} ('{candidate_name_log}') deleted from DB by {user_id_for_logs} ({user_username_for_logs}).")
            if s3_key_to_delete:
                try:
                    s3_service.delete_file(s3_key_to_delete)
                    current_app.logger.info(f"S3 file {s3_key_to_delete} deleted for candidate {cand_id_log}.")
                except Exception as s3_e:
                    current_app.logger.error(f"S3 Delete error for key {s3_key_to_delete} (Cand {cand_id_log}): {s3_e}",
                                             exc_info=True)
            return jsonify({"message": f"Candidate '{candidate_name_log}' deleted successfully."}), 200
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error deleting candidate {cand_id_log} from DB: {e}", exc_info=True)
            return jsonify({"error": "Failed to delete candidate from database."}), 500

    return jsonify({"error": "Method not supported for this endpoint."}), 405


@bp.route('/candidate/<string:candidate_id_url>/cv_url', methods=['GET'])
@login_required
def get_candidate_cv_url(candidate_id_url):
    try:
        candidate_uuid = uuid.UUID(candidate_id_url)
    except ValueError:
        return jsonify({"error": "Invalid candidate ID format."}), 400

    candidate = Candidate.query.get_or_404(candidate_uuid, description=f"Candidate {candidate_id_url} not found.")
    user_company_id_context = get_current_user_company_id()

    if current_user.role != 'superadmin':
        if not user_company_id_context or candidate.company_id != user_company_id_context:
            return jsonify({"error": "Access denied to this candidate's CV."}), 403

    if not candidate.cv_storage_path:
        return jsonify({"error": "No CV file associated with this candidate."}), 404

    try:
        cv_url = s3_service.generate_presigned_url(candidate.cv_storage_path, expiration=900)
        if cv_url:
            return jsonify({"cv_url": cv_url, "original_filename": candidate.cv_original_filename}), 200
        else:
            current_app.logger.error(
                f"S3 service failed to generate presigned URL for candidate {candidate.candidate_id}, S3 key {candidate.cv_storage_path}")
            return jsonify({"error": "Could not generate CV URL due to S3 service issue."}), 500
    except Exception as e:
        current_app.logger.error(f"Error generating CV presigned URL for candidate {candidate.candidate_id}: {e}",
                                 exc_info=True)
        return jsonify({"error": "Failed to generate CV URL due to an internal error."}), 500


@bp.route('/search', methods=['GET'])
@login_required
def search_candidates():
    query_term = request.args.get('q', '').strip()
    status_filter = request.args.get('status', None)
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 15, type=int)
    user_company_id_context = get_current_user_company_id()
    query_target_company_id = None

    if current_user.role == 'superadmin':
        company_id_param = request.args.get('company_id', type=int)
        if company_id_param:
            query_target_company_id = company_id_param
    elif user_company_id_context:
        query_target_company_id = user_company_id_context
    else:
        return jsonify({"error": "User not associated with a company or unauthorized for search."}), 403

    try:
        query_builder = Candidate.query
        if query_target_company_id:
            query_builder = query_builder.filter(Candidate.company_id == query_target_company_id)

        if query_term:
            search_pattern = f"%{query_term}%"
            conditions = [
                Candidate.first_name.ilike(search_pattern),
                Candidate.last_name.ilike(search_pattern),
                Candidate.email.ilike(search_pattern),
                Candidate.phone_number.ilike(search_pattern),
                Candidate.skills_summary.ilike(search_pattern),
                Candidate.education_summary.ilike(search_pattern),
                Candidate.experience_summary.ilike(search_pattern),
                Candidate.notes.ilike(search_pattern),
                Candidate.hr_comments.ilike(search_pattern)
            ]
            query_builder = query_builder.outerjoin(Candidate.positions).filter(
                or_(*conditions, Position.position_name.ilike(search_pattern))
            )

        if status_filter and status_filter.lower() != 'all':
            query_builder = query_builder.filter(Candidate.current_status == status_filter)

        pagination = query_builder.distinct().order_by(Candidate.submission_date.desc().nullslast()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        candidates_data = [cand.to_dict() for cand in pagination.items]

        return jsonify({
            "candidates": candidates_data,
            "total_results": pagination.total,
            "current_page": pagination.page,
            "per_page": pagination.per_page,
            "total_pages": pagination.pages
        }), 200
    except Exception as e:
        current_app.logger.error(
            f"Search Error (Query: '{query_term}', Status: '{status_filter}', User: {current_user.id}, Company: {query_target_company_id}): {e}",
            exc_info=True)
        return jsonify({"error": "Search operation failed due to an internal error."}), 500


@bp.route('/settings', methods=['GET', 'PUT'])
@login_required
def handle_settings():
    if request.method == 'GET':
        user_settings = {
            "enable_email_interview_reminders": current_user.enable_email_interview_reminders,
            "interview_reminder_lead_time_minutes": current_user.interview_reminder_lead_time_minutes
        }
        return jsonify(user_settings), 200
    elif request.method == 'PUT':
        data = request.get_json()
        if not data: return jsonify({"error": "No data provided."}), 400

        updated = False
        if 'enable_email_interview_reminders' in data:
            current_user.enable_email_interview_reminders = bool(data['enable_email_interview_reminders'])
            updated = True

        if 'interview_reminder_lead_time_minutes' in data:
            try:
                lead_time = int(data['interview_reminder_lead_time_minutes'])
                if not (5 <= lead_time <= 2 * 24 * 60):
                    return jsonify({"error": "Lead time out of range (5-2880 minutes)."}), 400
                current_user.interview_reminder_lead_time_minutes = lead_time
                updated = True
            except (ValueError, TypeError):
                return jsonify({"error": "Invalid lead time format. Must be an integer."}), 400

        if not updated:
            return jsonify({"message": "No settings changed."}), 304

        try:
            db.session.commit()
            return jsonify({
                "message": "Settings updated successfully.",
                "settings": {
                    "enable_email_interview_reminders": current_user.enable_email_interview_reminders,
                    "interview_reminder_lead_time_minutes": current_user.interview_reminder_lead_time_minutes
                }
            }), 200
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to save user settings for {current_user.id}: {e}", exc_info=True)
            return jsonify({"error": "Failed to save settings."}), 500

    return jsonify({"error": "Method not allowed."}), 405


@bp.route('/interviews/confirm/<string:confirmation_uuid_str>', methods=['GET'])
def confirm_interview(confirmation_uuid_str):
    try:
        confirmation_uuid_obj = uuid.UUID(confirmation_uuid_str)
    except ValueError:
        return "<h1>Σφάλμα</h1><p>Ο σύνδεσμος επιβεβαίωσης δεν είναι έγκυρος (λανθασμένη μορφή).</p>", 400

    candidate = Candidate.query.filter_by(confirmation_uuid=confirmation_uuid_obj).first()
    if not candidate:
        return "<h1>Σφάλμα</h1><p>Ο σύνδεσμος επιβεβαίωσης δεν είναι έγκυρος ή έχει λήξει.</p>", 404

    if not candidate.interview_datetime or candidate.current_status != 'Interview':
        return "<h1>Σφάλμα</h1><p>Δεν υπάρχει ενεργή προγραμματισμένη συνέντευξη για αυτόν τον σύνδεσμο ή η κατάσταση του υποψηφίου δεν είναι 'Interview'.</p>", 400

    html_response = ""
    http_code = 200
    original_confirmation_status = candidate.candidate_confirmation_status

    if original_confirmation_status == 'Confirmed':
        html_response = f"<h1>Ήδη Επιβεβαιωμένο</h1><p>Η συνέντευξή σας στις {candidate.interview_datetime.astimezone(dt_timezone.utc).strftime('%d/%m/%Y %H:%M')} UTC έχει ήδη επιβεβαιωθεί.</p>"
    elif original_confirmation_status in ['Pending', 'Declined', None]:
        candidate.candidate_confirmation_status = 'Confirmed'
        candidate.add_history_event(
            event_type="interview_confirmed_by_candidate",
            description=f"Candidate confirmed interview (was: {original_confirmation_status or 'N/A'}) via link.",
            actor_username="Candidate",
            details={"confirmation_uuid": confirmation_uuid_str}
        )
        try:
            db.session.commit()
            current_app.logger.info(
                f"Candidate {candidate.candidate_id} confirmed interview (UUID: {confirmation_uuid_str}).")
            try:
                celery.send_task('tasks.communication.notify_recruiter_interview_confirmed_task',
                                 args=[str(candidate.candidate_id), candidate.company_id])
            except Exception as celery_err:
                current_app.logger.error(f"Celery task error (notify_recruiter_interview_confirmed_task): {celery_err}",
                                         exc_info=True)

            html_response = f"<h1>Επιβεβαίωση Επιτυχής</h1><p>Ευχαριστούμε, {candidate.get_full_name()}! Η συνέντευξή σας στις {candidate.interview_datetime.astimezone(dt_timezone.utc).strftime('%d/%m/%Y %H:%M')} UTC έχει επιβεβαιωθεί.</p>"
        except Exception as e_commit:
            db.session.rollback()
            current_app.logger.error(
                f"Error committing interview confirmation for candidate {candidate.candidate_id}: {e_commit}",
                exc_info=True)
            html_response = "<h1>Σφάλμα Συστήματος</h1><p>Παρουσιάστηκε ένα πρόβλημα κατά την επιβεβαίωση. Παρακαλούμε δοκιμάστε αργότερα.</p>"
            http_code = 500
    else:
        html_response = "<h1>Σφάλμα</h1><p>Αυτή η ενέργεια δεν είναι δυνατή για την τρέχουσα κατάσταση επιβεβαίωσης.</p>"
        http_code = 400

    return html_response, http_code


@bp.route('/interviews/decline/<string:confirmation_uuid_str>', methods=['GET'])
def decline_interview(confirmation_uuid_str):
    try:
        confirmation_uuid_obj = uuid.UUID(confirmation_uuid_str)
    except ValueError:
        return "<h1>Σφάλμα</h1><p>Ο σύνδεσμος απόρριψης δεν είναι έγκυρος (λανθασμένη μορφή).</p>", 400

    candidate = Candidate.query.filter_by(confirmation_uuid=confirmation_uuid_obj).first()
    if not candidate:
        return "<h1>Σφάλμα</h1><p>Ο σύνδεσμος απόρριψης/αλλαγής δεν είναι έγκυρος ή έχει λήξει.</p>", 404

    if not candidate.interview_datetime or candidate.current_status != 'Interview':
        return "<h1>Σφάλμα</h1><p>Δεν υπάρχει ενεργή προγραμματισμένη συνέντευξη για αυτόν τον σύνδεσμο ή η κατάσταση του υποψηφίου δεν είναι 'Interview'.</p>", 400

    html_response = ""
    http_code = 200
    original_confirmation_status = candidate.candidate_confirmation_status

    if original_confirmation_status == 'Declined':
        html_response = f"<h1>Ήδη Δηλωμένη Άρνηση</h1><p>Έχετε ήδη δηλώσει αδυναμία για τη συνέντευξη στις {candidate.interview_datetime.astimezone(dt_timezone.utc).strftime('%d/%m/%Y %H:%M')} UTC.</p>"
    elif original_confirmation_status in ['Pending', 'Confirmed', None]:
        candidate.candidate_confirmation_status = 'Declined'
        candidate.add_history_event(
            event_type="interview_declined_by_candidate",
            description=f"Candidate declined/requested change for interview (was: {original_confirmation_status or 'N/A'}) via link.",
            actor_username="Candidate",
            details={"confirmation_uuid": confirmation_uuid_str}
        )
        try:
            db.session.commit()
            current_app.logger.info(
                f"Candidate {candidate.candidate_id} declined/requested change for interview (UUID: {confirmation_uuid_str}).")
            try:
                celery.send_task('tasks.communication.notify_recruiter_interview_declined_task',
                                 args=[str(candidate.candidate_id), candidate.company_id])
            except Exception as celery_err:
                current_app.logger.error(f"Celery task error (notify_recruiter_interview_declined_task): {celery_err}",
                                         exc_info=True)

            html_response = f"<h1>Επιβεβαίωση Άρνησης/Αλλαγής</h1><p>Λάβαμε την ενημέρωσή σας για τη συνέντευξη στις {candidate.interview_datetime.astimezone(dt_timezone.utc).strftime('%d/%m/%Y %H:%M')} UTC. Ένας υπεύθυνος θα επικοινωνήσει μαζί σας αν χρειαστεί.</p>"
        except Exception as e_commit:
            db.session.rollback()
            current_app.logger.error(
                f"Error committing interview decline for candidate {candidate.candidate_id}: {e_commit}", exc_info=True)
            html_response = "<h1>Σφάλμα Συστήματος</h1><p>Παρουσιάστηκε ένα πρόβλημα κατά την επεξεργασία του αιτήματός σας. Παρακαλούμε δοκιμάστε αργότερα.</p>"
            http_code = 500
    else:
        html_response = "<h1>Σφάλμα</h1><p>Αυτή η ενέργεια δεν είναι δυνατή για την τρέχουσα κατάσταση επιβεβαίωσης.</p>"
        http_code = 400

    return html_response, http_code