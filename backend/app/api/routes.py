# backend/app/api/routes.py

from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
import uuid
from datetime import datetime, timezone  # Βεβαιώσου ότι το timezone είναι το σωστό (datetime.timezone)
from dateutil import parser as dateutil_parser
from flask_login import login_user, logout_user, current_user, login_required
from app import db, celery  # Βεβαιώσου ότι το celery import είναι σωστό αν το χρησιμοποιείς εδώ
from app.models import User, Candidate, Position, Company, CompanySettings
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import func, case, or_
from app.services import s3_service  # Βεβαιώσου ότι αυτό το service υπάρχει και είναι προσβάσιμο

# --- ΚΥΡΙΑ ΑΛΛΑΓΗ ΟΝΟΜΑΤΟΣ BLUEPRINT ---
bp = Blueprint('api', __name__)
# --- ΤΕΛΟΣ ΚΥΡΙΑΣ ΑΛΛΑΓΗΣ ---


ALLOWED_EXTENSIONS = {'pdf', 'docx'}


def allowed_file(filename): return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_current_user_company_id():
    if not current_user.is_authenticated:
        return None
    if current_user.role == 'superadmin':
        # Superadmin might operate across companies or without specific company context for some actions
        return None  # Or handle based on specific endpoint logic if a company_id is passed for superadmin
    if not current_user.company_id:
        current_app.logger.error(
            f"User {current_user.id} ({current_user.username}) with role {current_user.role} has no company_id.")
        return None  # Or raise an exception / return error response
    return current_user.company_id


@bp.route('/register', methods=['POST'])  # Άλλαξε από api_bp σε bp
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
        username=username, email=email, role='user', is_active=False  # Default is_active to False
        # enable_email_interview_reminders και interview_reminder_lead_time_minutes θα πάρουν defaults από το model
    )
    new_user.set_password(password)
    try:
        db.session.add(new_user)
        db.session.commit()
        current_app.logger.info(f"New user registered: {username} ({email}). Awaiting activation/assignment.")
        # Consider sending a confirmation email or notifying admin
        # celery.send_task('app.tasks.communication_tasks.send_account_confirmation_email', args=[new_user.id])
        return jsonify({
                           "message": "Registration successful. Account activation and company assignment pending administrator review."}), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error during user registration for {username}: {e}", exc_info=True)
        return jsonify({"error": "Registration failed due to an internal error."}), 500


@bp.route('/login', methods=['POST'])  # Άλλαξε από api_bp σε bp
def login():
    data = request.get_json()
    if not data or not data.get('login_identifier') or not data.get('password'):
        return jsonify({"error": "Login identifier and password required"}), 400
    login_identifier = data.get('login_identifier')
    password = data.get('password')
    remember = data.get('remember', False)  # Default to False if not provided
    user = User.query.filter((User.username == login_identifier) | (User.email == login_identifier)).first()
    if user and user.check_password(password):
        if not user.is_active:
            current_app.logger.warning(f"Login attempt by inactive user: {login_identifier}")
            return jsonify({"error": "Account not active. Please check your email or contact an administrator."}), 403
        if user.role != 'superadmin' and not user.company_id:
            current_app.logger.warning(
                f"Login attempt by user {user.username} (Role: {user.role}) not assigned to any company.")
            return jsonify({"error": "Account not yet assigned to a company by an administrator."}), 403

        login_user(user, remember=remember)
        current_app.logger.info(f"User {user.username} (Role: {user.role}, CompanyID: {user.company_id}) logged in.")

        user_data = user.to_dict(include_company_info=True)  # Χρησιμοποιούμε το to_dict από το model

        # Προσθήκη company settings αν ο χρήστης ανήκει σε εταιρεία (όχι superadmin)
        if user.company_id and user.role != 'superadmin':
            company_settings = CompanySettings.query.filter_by(company_id=user.company_id).first()
            if company_settings:
                user_data["company_settings"] = {
                    "rejection_email_template": company_settings.rejection_email_template,
                    # "reminder_email_template": company_settings.reminder_email_template, # Αν υπάρχει τέτοιο πεδίο
                    "interview_invitation_email_template": company_settings.interview_invitation_email_template,
                    "default_interview_reminder_timing_minutes": company_settings.default_interview_reminder_timing_minutes,
                    "enable_reminders_feature_for_company": company_settings.enable_reminders_feature_for_company
                }
            else:
                user_data["company_settings"] = None  # Ή ένα κενό dict
                current_app.logger.warning(
                    f"No CompanySettings found for company_id {user.company_id} during login for user {user.username}")

        return jsonify({"message": "Login successful", "user": user_data}), 200
    else:
        current_app.logger.warning(f"Failed login attempt for: {login_identifier}")
        return jsonify({"error": "Invalid login identifier or password"}), 401


@bp.route('/logout', methods=['POST'])  # Άλλαξε από api_bp σε bp
@login_required
def logout():
    user_id_log = current_user.id
    username_log = current_user.username
    logout_user()
    current_app.logger.info(f"User {username_log} (ID: {user_id_log}) logged out.")
    return jsonify({"message": "Logout successful"}), 200


@bp.route('/session', methods=['GET'])  # Άλλαξε από api_bp σε bp
def check_session():
    if current_user.is_authenticated:
        user_data = current_user.to_dict(include_company_info=True)  # Χρησιμοποιούμε το to_dict

        if current_user.company_id and current_user.role != 'superadmin':
            company_settings = CompanySettings.query.filter_by(company_id=current_user.company_id).first()
            if company_settings:
                user_data["company_settings"] = {  # Προσθέτουμε μόνο ό,τι χρειάζεται ο client για το session check
                    "default_interview_reminder_timing_minutes": company_settings.default_interview_reminder_timing_minutes,
                    "enable_reminders_feature_for_company": company_settings.enable_reminders_feature_for_company
                }
        return jsonify({"authenticated": True, "user": user_data}), 200
    else:
        return jsonify({"authenticated": False}), 200


@bp.route('/upload', methods=['POST'])  # Άλλαξε από api_bp σε bp
@login_required
def upload_cv():
    current_app.logger.info(f"--- Upload Request Received by User ID: {current_user.id} ({current_user.username}) ---")

    user_company_id_for_context = get_current_user_company_id()  # Παίρνει το company_id του χρήστη ή None για superadmin

    target_company_id_for_candidate = None

    if current_user.role == 'superadmin':
        # Ο superadmin ΠΡΕΠΕΙ να ορίσει company_id για τον υποψήφιο
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
        # Αυτό δεν θα έπρεπε να συμβεί αν το get_current_user_company_id() και το @login_required δουλεύουν σωστά
        return jsonify({"error": "User not associated with a company or unauthorized."}), 403

    if 'cv_file' not in request.files: return jsonify({"error": "No file part named 'cv_file'"}), 400
    file = request.files['cv_file']
    position_name_from_form = request.form.get('position', None)  # Όνομα θέσης από τη φόρμα

    if file.filename == '': return jsonify({"error": "No selected file"}), 400
    if not allowed_file(file.filename): return jsonify({"error": "Invalid file type. Allowed: pdf, docx"}), 400

    uploaded_s3_key = None  # Για cleanup σε περίπτωση σφάλματος
    try:
        file_ext = file.filename.rsplit('.', 1)[1].lower()
        original_filename = secure_filename(file.filename)
        # Δημιουργία μοναδικού κλειδιού S3
        s3_key = f"company_{target_company_id_for_candidate}/cvs/{uuid.uuid4()}.{file_ext}"

        file.seek(0)  # Επαναφορά του pointer του αρχείου στην αρχή
        uploaded_s3_key = s3_service.upload_file(file, s3_key)
        if not uploaded_s3_key:
            raise Exception("S3 upload service indicated failure. Check S3 service logs.")

        new_candidate = Candidate(
            cv_original_filename=original_filename,
            cv_storage_path=uploaded_s3_key,  # Το κλειδί που επέστρεψε το S3
            current_status='Processing',  # Αρχικό status
            confirmation_uuid=str(uuid.uuid4()),  # Για μελλοντικές επιβεβαιώσεις
            company_id=target_company_id_for_candidate
            # Άλλα πεδία θα συμπληρωθούν από το parsing ή αργότερα
        )

        # Σύνδεση με Position αν δόθηκε όνομα
        if position_name_from_form and position_name_from_form.strip():
            pos_name_cleaned = position_name_from_form.strip()
            # Βρες ή δημιούργησε τη θέση για την συγκεκριμένη εταιρεία
            position = Position.query.filter(
                func.lower(Position.position_name) == func.lower(pos_name_cleaned),
                Position.company_id == target_company_id_for_candidate
            ).first()
            if not position:
                position = Position(position_name=pos_name_cleaned, company_id=target_company_id_for_candidate)
                db.session.add(position)  # Πρόσθεσε το position στο session για να πάρει ID αν είναι νέο
                # Δεν κάνουμε commit εδώ, θα γίνει μαζί με τον candidate
            new_candidate.positions.append(position)

        db.session.add(new_candidate)
        db.session.commit()  # Commit για να πάρουμε το candidate_id

        candidate_id_for_task = new_candidate.candidate_id  # Το ID που δημιουργήθηκε (string UUID)

        # Εκκίνηση του Celery task για parsing
        # Βεβαιώσου ότι το όνομα του task είναι σωστό και το task περιμένει αυτά τα arguments
        celery.send_task('tasks.parsing.parse_cv_task',
                         args=[candidate_id_for_task, uploaded_s3_key, target_company_id_for_candidate])
        current_app.logger.info(
            f"CV uploaded (S3 Key: {uploaded_s3_key}), Candidate ID: {candidate_id_for_task} created for Company {target_company_id_for_candidate}. Parsing task queued.")

        return jsonify(new_candidate.to_dict()), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            f"Overall Upload Error (User: {current_user.id}, TargetCompany: {target_company_id_for_candidate}) during upload: {e}",
            exc_info=True)
        # Προσπάθεια διαγραφής του αρχείου από το S3 αν το upload είχε γίνει αλλά κάτι άλλο απέτυχε
        if uploaded_s3_key:
            try:
                s3_service.delete_file(uploaded_s3_key)
                current_app.logger.info(f"S3 cleanup successful for key {uploaded_s3_key} after upload error.")
            except Exception as s3_del_err:
                current_app.logger.error(
                    f"S3 cleanup FAILED for key {uploaded_s3_key} after upload error: {s3_del_err}")
        return jsonify({"error": "Internal server error during CV upload."}), 500


@bp.route('/dashboard/summary', methods=['GET'])  # Άλλαξε από api_bp σε bp
@login_required
def get_dashboard_summary():
    user_company_id_context = get_current_user_company_id()
    query_target_company_id = None

    if current_user.role == 'superadmin':
        # Ο superadmin μπορεί να φιλτράρει ανά company_id αν δοθεί, αλλιώς βλέπει όλα
        company_id_filter_param = request.args.get('company_id', type=int)
        if company_id_filter_param:
            query_target_company_id = company_id_filter_param
    elif user_company_id_context:
        query_target_company_id = user_company_id_context
    else:
        # Αυτό καλύπτει χρήστες (όχι superadmin) χωρίς company_id, που δεν θα έπρεπε να έχουν πρόσβαση
        return jsonify({"error": "User not associated with a company or unauthorized."}), 403

    try:
        # Ορίζουμε τα statuses που μας ενδιαφέρουν για το summary
        # Αυτά πρέπει να ταιριάζουν με τα πιθανά Candidate.current_status
        relevant_statuses = [
            'New', 'Processing', 'NeedsReview', 'Interview', 'OfferMade',
            'Hired', 'Rejected', 'ParsingFailed', 'Accepted', 'Declined',
            'Interested', 'Evaluation', 'On Hold'  # Πρόσθεσε ό,τι άλλο χρησιμοποιείς
        ]

        status_aggregations = [
            func.sum(case((Candidate.current_status == status, 1), else_=0)).label(status.replace(" ", "_"))
            # Χρησιμοποίησε underscores για τα labels
            for status in relevant_statuses
        ]

        query_obj = db.session.query(
            func.count(Candidate.candidate_id).label("total_candidates"),  # Άλλαξα το label για σαφήνεια
            *status_aggregations
        )

        if query_target_company_id:
            query_obj = query_obj.filter(Candidate.company_id == query_target_company_id)

        q_result = query_obj.first()

        summary = {"total_candidates": 0}
        for status in relevant_statuses:
            summary[status.replace(" ", "_")] = 0  # Αρχικοποίηση όλων των status με 0

        if q_result:
            summary.update(
                {k: (v or 0) for k, v in q_result._asdict().items()})  # Ενημέρωση με τα αποτελέσματα του query

        return jsonify(summary), 200
    except Exception as e:
        current_app.logger.error(
            f"Dashboard Summary Error (User: {current_user.id}, Company Filter: {query_target_company_id}): {e}",
            exc_info=True)
        return jsonify({"error": "Failed to retrieve dashboard summary."}), 500


@bp.route('/candidates/<string:status_param>', methods=['GET'])  # Άλλαξε από api_bp σε bp, και το όνομα της παραμέτρου
@login_required
def get_candidates_by_status(status_param):  # Η παράμετρος ταιριάζει με το URL
    # Εδώ μπορείς να έχεις μια λίστα με τα "valid" statuses ή να επιτρέπεις "All"
    valid_statuses_for_filter = [
        'New', 'Processing', 'NeedsReview', 'Interview', 'OfferMade',
        'Hired', 'Rejected', 'ParsingFailed', 'Accepted', 'Declined',
        'Interested', 'Evaluation', 'On Hold', 'All'  # Το 'All' είναι ειδική περίπτωση
    ]
    if status_param not in valid_statuses_for_filter:
        return jsonify(
            {"error": f"Invalid status filter: {status_param}. Valid are: {', '.join(valid_statuses_for_filter)}"}), 400

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
        candidates_query_obj = Candidate.query
        if query_target_company_id:
            candidates_query_obj = candidates_query_obj.filter(Candidate.company_id == query_target_company_id)

        if status_param != 'All':
            candidates_query_obj = candidates_query_obj.filter(Candidate.current_status == status_param)

        # Ταξινόμηση (π.χ., βάσει ημερομηνίας υποβολής)
        candidates_result = candidates_query_obj.order_by(Candidate.submission_date.desc()).all()

        # Επιστροφή λίστας υποψηφίων (με presigned URL για το CV αν χρειάζεται)
        candidates_data = []
        for cand in candidates_result:
            cv_url_val = None
            if cand.cv_storage_path:
                try:
                    cv_url_val = s3_service.generate_presigned_url(cand.cv_storage_path)  # Default expiration
                except Exception as s3_e:
                    current_app.logger.error(
                        f"Failed to generate presigned URL for candidate {cand.candidate_id} in list: {s3_e}")
            candidates_data.append(cand.to_dict(include_cv_url=True, cv_url=cv_url_val))

        return jsonify(candidates_data), 200
    except Exception as e:
        current_app.logger.error(
            f"Error listing candidates (Status: {status_param}, User: {current_user.id}, Company Filter: {query_target_company_id}): {e}",
            exc_info=True)
        return jsonify({"error": "Failed to retrieve candidate list."}), 500


@bp.route('/candidate/<string:candidate_id_url>',
          methods=['GET', 'PUT', 'DELETE'])  # Άλλαξε από api_bp σε bp, και το όνομα της παραμέτρου
@login_required
def handle_candidate(candidate_id_url):  # Η παράμετρος ταιριάζει με το URL
    user_company_id_context = get_current_user_company_id()

    candidate = Candidate.query.get_or_404(candidate_id_url,
                                           description=f"Candidate with ID {candidate_id_url} not found.")

    # Έλεγχos δικαιωμάτων: Ο χρήστης πρέπει να είναι superadmin ή να ανήκει στην ίδια εταιρεία με τον υποψήφιο
    if current_user.role != 'superadmin':
        if not user_company_id_context or candidate.company_id != user_company_id_context:
            current_app.logger.warning(
                f"Access denied for user {current_user.id} to candidate {candidate.candidate_id} of company {candidate.company_id}")
            return jsonify({"error": "Access denied to this candidate."}), 403

    user_id_for_logs = current_user.id  # Για logging

    if request.method == 'GET':
        try:
            cv_url_val = None
            if candidate.cv_storage_path:
                cv_url_val = s3_service.generate_presigned_url(candidate.cv_storage_path, expiration=900)  # 15 λεπτά
            return jsonify(candidate.to_dict(include_cv_url=True, cv_url=cv_url_val)), 200
        except Exception as e:
            current_app.logger.error(f"GET Candidate {candidate.candidate_id} Error: {e}", exc_info=True)
            return jsonify({"error": "Failed to retrieve candidate details."}), 500

    elif request.method == 'PUT':
        current_app.logger.info(f"PUT Candidate {candidate.candidate_id} by User {user_id_for_logs}")
        data = request.get_json()
        if not data: return jsonify({"error": "No input data provided. Request body must be JSON."}), 400

        allowed_updates = [
            'first_name', 'last_name', 'age', 'phone_number', 'email',
            'current_status', 'notes',
            'education_summary', 'experience_summary', 'skills_summary',  # Χρησιμοποιούμε τα νέα ονόματα
            'languages', 'seminars',
            'interview_datetime', 'interview_location', 'interview_type', 'interviewers',
            'evaluation_rating', 'offers', 'candidate_confirmation_status'
        ]
        updated_fields_tracker = False  # Για να δούμε αν έγινε κάποια αλλαγή
        original_status = candidate.current_status
        original_interview_time = candidate.interview_datetime
        interview_time_changed_flag = False

        for key, value in data.items():
            if key in allowed_updates:
                current_value_on_candidate = getattr(candidate, key)

                if key == 'interview_datetime':
                    new_dt_value = None
                    if value:  # Αν το value δεν είναι None ή κενό string
                        try:
                            # Προσπάθεια parsing του ISO string σε datetime object
                            parsed_dt = dateutil_parser.isoparse(value)
                            # Μετατροπή σε UTC αν δεν έχει timezone, ή προσαρμογή σε UTC αν έχει
                            new_dt_value = parsed_dt.astimezone(
                                timezone.utc) if parsed_dt.tzinfo else parsed_dt.replace(tzinfo=timezone.utc)
                        except (ValueError, TypeError) as date_parse_err:
                            current_app.logger.warning(
                                f"Invalid date format for interview_datetime ('{value}'). Error: {date_parse_err}. Field not updated.")
                            # Μπορείς να επιστρέψεις σφάλμα 400 εδώ αν θες αυστηρό έλεγχο
                            # return jsonify({"error": f"Invalid date format for interview_datetime: {value}. Use ISO 8601 format."}), 400
                            continue  # Παράλειψη αυτού του πεδίου
                    # new_dt_value είναι είτε datetime object σε UTC, είτε None
                    if new_dt_value != original_interview_time:  # Συγκρίνουμε datetime objects
                        setattr(candidate, key, new_dt_value)
                        interview_time_changed_flag = True
                        updated_fields_tracker = True
                elif key == 'age':
                    new_age_val = None
                    if value is not None and str(value).strip().isdigit(): new_age_val = int(value)
                    if current_value_on_candidate != new_age_val:
                        setattr(candidate, key, new_age_val);
                        updated_fields_tracker = True
                elif key in ['offers', 'interviewers', 'history']:  # JSONB fields
                    # Για JSONB, είναι καλύτερα να ενημερώνεις απευθείας και να κάνεις flag_modified
                    # αν η δομή είναι πολύπλοκη. Για απλή αντικατάσταση λίστας:
                    if isinstance(value, list):  # Βασικός έλεγχος τύπου
                        setattr(candidate, key, value)
                        flag_modified(candidate, key)  # Σημαντικό για JSONB/Array
                        updated_fields_tracker = True
                    else:
                        current_app.logger.warning(
                            f"Invalid data type for '{key}' for candidate {candidate.candidate_id}. Expected list, got {type(value)}.")
                else:  # Για τα υπόλοιπα πεδία
                    if current_value_on_candidate != value:
                        setattr(candidate, key, value)
                        updated_fields_tracker = True

            elif key == 'positions' and isinstance(value, list):  # Διαχείριση των positions
                current_positions_on_candidate = set(p.position_name.lower() for p in candidate.positions)
                target_position_names_from_payload = set(
                    p_name.strip().lower() for p_name in value if isinstance(p_name, str) and p_name.strip())

                # Αφαίρεση θέσεων που δεν υπάρχουν στο payload
                positions_to_remove_from_candidate = [p for p in candidate.positions if
                                                      p.position_name.lower() not in target_position_names_from_payload]
                if positions_to_remove_from_candidate:
                    for pos_obj_to_remove in positions_to_remove_from_candidate:
                        candidate.positions.remove(pos_obj_to_remove)
                    updated_fields_tracker = True

                # Προσθήκη νέων θέσεων από το payload
                for pos_name_to_add_lower in target_position_names_from_payload:
                    if pos_name_to_add_lower not in current_positions_on_candidate:
                        # Βρες ή δημιούργησε τη θέση (case-insensitive search, αλλά αποθήκευση με το case από το payload)
                        # Βρες το αρχικό όνομα από το payload για case-sensitive αποθήκευση
                        original_case_pos_name = next(
                            (p_name for p_name in value if p_name.strip().lower() == pos_name_to_add_lower),
                            pos_name_to_add_lower.title())

                        position_entity = Position.query.filter(
                            func.lower(Position.position_name) == pos_name_to_add_lower,
                            Position.company_id == candidate.company_id  # Σημαντικό: στην ίδια εταιρεία
                        ).first()
                        if not position_entity:
                            position_entity = Position(position_name=original_case_pos_name,
                                                       company_id=candidate.company_id)
                            db.session.add(position_entity)
                        if position_entity not in candidate.positions:  # Διπλός έλεγχos για σιγουριά
                            candidate.positions.append(position_entity)
                        updated_fields_tracker = True

        # Λογική μετά την ενημέρωση των πεδίων
        if interview_time_changed_flag:
            if candidate.interview_datetime:  # Αν ορίστηκε νέα ώρα συνέντευξης
                candidate.candidate_confirmation_status = 'Pending'  # Επαναφορά σε Pending
                candidate.confirmation_uuid = str(uuid.uuid4())  # Νέο UUID για επιβεβαίωση
                flag_modified(candidate, "candidate_confirmation_status")
                flag_modified(candidate, "confirmation_uuid")
            else:  # Αν η ώρα συνέντευξης αφαιρέθηκε
                candidate.candidate_confirmation_status = None
                flag_modified(candidate, "candidate_confirmation_status")
            # updated_fields_tracker είναι ήδη True

        new_status_from_payload = data.get('current_status', original_status)
        if new_status_from_payload != original_status:  # Το status άλλαξε
            candidate.current_status = new_status_from_payload  # Το είχαμε κάνει ήδη, αλλά για σαφήνεια
            # updated_fields_tracker είναι ήδη True
            # Προσθήκη στο history
            candidate.add_history_event(
                event_type="status_change",
                description=f"Status changed from '{original_status}' to '{new_status_from_payload}'.",
                actor_id=user_id_for_logs,
                details={"previous_status": original_status, "new_status": new_status_from_payload,
                         "notes": data.get('notes', candidate.notes)}
            )
            # Αν το status αλλάζει από Interview σε κάτι άλλο (εκτός από Evaluation κλπ), καθάρισε τα interview fields
            if original_status and 'Interview' in original_status and new_status_from_payload not in ['Evaluation',
                                                                                                      'Interview',
                                                                                                      'OfferMade',
                                                                                                      'Hired']:
                candidate.interview_datetime = None
                candidate.interview_location = None
                candidate.interview_type = None
                candidate.interviewers = []
                candidate.candidate_confirmation_status = None
                flag_modified(candidate, "interviewers")  # Σημαντικό για JSONB
                flag_modified(candidate, "candidate_confirmation_status")

        if not updated_fields_tracker:
            return jsonify({"message": "No changes detected or no updatable fields provided."}), 304

        try:
            db.session.commit()
            current_app.logger.info(f"Candidate {candidate.candidate_id} updated by {user_id_for_logs}.")

            # Celery tasks μετά το commit
            if interview_time_changed_flag and candidate.interview_datetime:
                # Βεβαιώσου ότι το task περιμένει το candidate_id ως string
                celery.send_task('tasks.communication.send_interview_invitation_email_task',
                                 args=[str(candidate.candidate_id)])

            if new_status_from_payload != original_status and new_status_from_payload in ['Rejected',
                                                                                          'Declined']:  # Ή όποια άλλα statuses απόρριψης
                celery.send_task('tasks.communication.send_rejection_email_task', args=[str(candidate.candidate_id)])

            return jsonify(candidate.to_dict()), 200
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating candidate {candidate.candidate_id}: {e}", exc_info=True)
            return jsonify({"error": "Failed to update candidate details due to an internal error."}), 500

    elif request.method == 'DELETE':
        current_app.logger.info(f"DELETE Candidate {candidate.candidate_id} by User {user_id_for_logs}")
        s3_key_to_delete_on_success = candidate.cv_storage_path
        candidate_name_for_log_msg = candidate.get_full_name()
        try:
            db.session.delete(candidate)
            db.session.commit()
            current_app.logger.info(
                f"Candidate {candidate.candidate_id} ({candidate_name_for_log_msg}) deleted from DB by {user_id_for_logs}.")
            # Διαγραφή από S3 μετά την επιτυχή διαγραφή από DB
            if s3_key_to_delete_on_success:
                try:
                    s3_service.delete_file(s3_key_to_delete_on_success)
                    current_app.logger.info(
                        f"S3 file {s3_key_to_delete_on_success} deleted for candidate {candidate.candidate_id}.")
                except Exception as s3_e:
                    current_app.logger.error(
                        f"S3 Delete error for key {s3_key_to_delete_on_success} (Candidate {candidate.candidate_id} already deleted from DB): {s3_e}",
                        exc_info=True)
            return jsonify({"message": f"Candidate '{candidate_name_for_log_msg}' deleted successfully."}), 200
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error deleting candidate {candidate.candidate_id} from DB: {e}", exc_info=True)
            return jsonify({"error": "Failed to delete candidate from database."}), 500


@bp.route('/candidate/<string:candidate_id_url>/cv_url',
          methods=['GET'])  # Άλλαξε από api_bp σε bp, και το όνομα της παραμέτρου
@login_required
def get_candidate_cv_url(candidate_id_url):  # Η παράμετρος ταιριάζει με το URL
    user_company_id_context = get_current_user_company_id()
    candidate = Candidate.query.get_or_404(candidate_id_url, description=f"Candidate {candidate_id_url} not found.")

    if current_user.role != 'superadmin':
        if not user_company_id_context or candidate.company_id != user_company_id_context:
            return jsonify({"error": "Access denied to this candidate's CV."}), 403

    if not candidate.cv_storage_path:
        return jsonify({"error": "No CV file associated with this candidate."}), 404

    try:
        # Δημιουργία presigned URL (π.χ., για 15 λεπτά = 900 δευτερόλεπτα)
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


@bp.route('/search', methods=['GET'])  # Άλλαξε από api_bp σε bp
@login_required
def search_candidates():
    query_term = request.args.get('q', '').strip()
    status_filter_term = request.args.get('status', None)
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)  # Default 20 results per page

    user_company_id_context = get_current_user_company_id()
    query_target_company_id = None

    if current_user.role == 'superadmin':
        company_id_param = request.args.get('company_id', type=int)
        if company_id_param:
            query_target_company_id = company_id_param
        # Αν ο superadmin δεν δώσει company_id, μπορεί να ψάχνει σε όλες τις εταιρείες (προσοχή στην απόδοση)
        # ή να απαιτείται company_id. Για τώρα, αν δεν δοθεί, δεν φιλτράρει ανά εταιρεία.
    elif user_company_id_context:
        query_target_company_id = user_company_id_context
    else:
        return jsonify({"error": "User not associated with a company or unauthorized."}), 403

    try:
        query_builder = Candidate.query
        if query_target_company_id:
            query_builder = query_builder.filter(Candidate.company_id == query_target_company_id)

        if query_term:
            search_pattern = f"%{query_term}%"
            # Αναζήτηση σε βασικά πεδία του Candidate
            candidate_search_conditions = [
                Candidate.first_name.ilike(search_pattern),
                Candidate.last_name.ilike(search_pattern),
                Candidate.email.ilike(search_pattern),
                Candidate.phone_number.ilike(search_pattern),
                Candidate.skills_summary.ilike(search_pattern),  # Αναζήτηση και στα skills
                Candidate.education_summary.ilike(search_pattern),
                Candidate.experience_summary.ilike(search_pattern),
                Candidate.notes.ilike(search_pattern)
            ]
            # Αναζήτηση και στο όνομα της θέσης (Position)
            # Χρησιμοποιούμε outerjoin για να συμπεριληφθούν και υποψήφιοι χωρίς συνδεδεμένη θέση
            query_builder = query_builder.outerjoin(Candidate.positions).filter(
                or_(*candidate_search_conditions, Position.position_name.ilike(search_pattern))
            )

        if status_filter_term:
            # Μπορείς να έχεις μια λίστα έγκυρων statuses για φιλτράρισμα
            # valid_statuses_for_filter = [...]
            # if status_filter_term in valid_statuses_for_filter:
            query_builder = query_builder.filter(Candidate.current_status == status_filter_term)

        # Χρήση pagination
        candidates_pagination = query_builder.distinct().order_by(Candidate.submission_date.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        candidates_data = [cand.to_dict() for cand in candidates_pagination.items]

        return jsonify({
            "candidates": candidates_data,
            "total_results": candidates_pagination.total,
            "current_page": candidates_pagination.page,
            "per_page": candidates_pagination.per_page,
            "total_pages": candidates_pagination.pages
        }), 200
    except Exception as e:
        current_app.logger.error(
            f"Search Error (Query: '{query_term}', User: {current_user.id}, Company: {query_target_company_id}): {e}",
            exc_info=True)
        return jsonify({"error": "Search operation failed due to an internal error."}), 500


@bp.route('/settings', methods=['GET', 'PUT'])  # Άλλαξε από api_bp σε bp
@login_required
def handle_settings():
    user_company_id_context = get_current_user_company_id()
    company_settings_obj = None

    target_company_id_for_operation = None

    if current_user.role == 'superadmin':
        # Ο superadmin πρέπει να ορίσει company_id για GET/PUT
        target_company_id_param = request.args.get('company_id', type=int)  # Για GET
        if request.method == 'PUT':
            data_for_put = request.get_json()
            if not data_for_put: return jsonify({"error": "Request body must be JSON for PUT."}), 400
            target_company_id_param = data_for_put.get('company_id',
                                                       target_company_id_param)  # Πάρε το από το body αν υπάρχει
            if not isinstance(target_company_id_param, int):  # Εξασφάλιση ότι είναι int
                try:
                    target_company_id_param = int(target_company_id_param)
                except (ValueError, TypeError):
                    target_company_id_param = None

        if not target_company_id_param:
            return jsonify({
                               "error": "Superadmin must specify a 'company_id' (in query params for GET, or in JSON body for PUT) to manage settings."}), 400
        target_company_id_for_operation = target_company_id_param
        company_settings_obj = CompanySettings.query.filter_by(company_id=target_company_id_for_operation).first_or_404(
            description=f"CompanySettings not found for company_id {target_company_id_for_operation}"
        )
    elif user_company_id_context:  # Για company_admin ή user (αν οι users μπορούν να δουν κάποιες ρυθμίσεις)
        target_company_id_for_operation = user_company_id_context
        company_settings_obj = CompanySettings.query.filter_by(company_id=target_company_id_for_operation).first()
        if not company_settings_obj:  # Αν δεν υπάρχουν, δημιούργησέ τα (κυρίως για company_admin)
            if current_user.role == 'company_admin':
                try:
                    company_settings_obj = CompanySettings(company_id=target_company_id_for_operation)
                    db.session.add(company_settings_obj)
                    db.session.commit()
                    current_app.logger.info(
                        f"Dynamically created CompanySettings for company_id {target_company_id_for_operation} by {current_user.username}.")
                except Exception as cs_create_err:
                    db.session.rollback()
                    current_app.logger.error(
                        f"Failed to create CompanySettings for {target_company_id_for_operation}: {cs_create_err}",
                        exc_info=True)
                    return jsonify({"error": "Company settings missing and could not be initialized."}), 500
            else:  # Αν είναι απλός user και δεν υπάρχουν settings
                return jsonify({"error": "Company settings not configured."}), 404
    else:
        return jsonify({"error": "User not associated with a company or unauthorized."}), 403

    # Έλεγχος δικαιωμάτων για PUT
    if request.method == 'PUT' and current_user.role not in ['company_admin', 'superadmin']:
        return jsonify({"error": "You do not have permission to modify company settings."}), 403

    # Αν ο company_admin προσπαθεί να αλλάξει ρυθμίσεις άλλης εταιρείας (μέσω "πειραγμένου" company_id στο PUT request από superadmin context)
    if request.method == 'PUT' and current_user.role == 'company_admin' and company_settings_obj.company_id != user_company_id_context:
        return jsonify({"error": "Company admin can only modify settings for their own company."}), 403

    if request.method == 'GET':
        return jsonify({
            "company_id": company_settings_obj.company_id,
            "rejection_email_template": company_settings_obj.rejection_email_template,
            # "reminder_email_template": company_settings_obj.reminder_email_template, # Αν υπάρχει
            "interview_invitation_email_template": company_settings_obj.interview_invitation_email_template,
            "default_interview_reminder_timing_minutes": company_settings_obj.default_interview_reminder_timing_minutes,
            "enable_reminders_feature_for_company": company_settings_obj.enable_reminders_feature_for_company
        }), 200

    elif request.method == 'PUT':
        data = request.get_json()  # Το έχουμε ήδη πάρει για τον superadmin, αλλά για company_admin το παίρνουμε εδώ
        if not data: return jsonify({"error": "No settings data provided in JSON body."}), 400

        updated_fields_tracker = False
        # Πεδία που επιτρέπεται να ενημερωθούν και ο τύπος τους
        allowed_company_settings_fields = {
            'rejection_email_template': str,
            # 'reminder_email_template': str,
            'interview_invitation_email_template': str,
            'default_interview_reminder_timing_minutes': int,
            'enable_reminders_feature_for_company': bool
        }

        for key, value_from_payload in data.items():
            if key in allowed_company_settings_fields:
                expected_type = allowed_company_settings_fields[key]
                current_value_on_object = getattr(company_settings_obj, key)

                try:
                    casted_value_from_payload = None
                    if value_from_payload is not None:
                        if expected_type == bool:  # Ειδικός χειρισμός για boolean
                            casted_value_from_payload = str(value_from_payload).lower() in ['true', '1', 'yes']
                        else:
                            casted_value_from_payload = expected_type(value_from_payload)

                        # Ειδικοί έλεγχοι (π.χ. range για αριθμούς)
                        if key == 'default_interview_reminder_timing_minutes' and not (
                                5 <= casted_value_from_payload <= 2880):  # 5 λεπτά έως 2 ημέρες
                            raise ValueError("Interview reminder lead time out of range (5-2880 minutes).")

                    if current_value_on_object != casted_value_from_payload:
                        setattr(company_settings_obj, key, casted_value_from_payload)
                        updated_fields_tracker = True
                except (ValueError, TypeError) as cast_err:
                    current_app.logger.warning(
                        f"Invalid value for company setting '{key}': '{value_from_payload}'. Error: {cast_err}")
                    return jsonify({
                                       "error": f"Invalid value or type for setting '{key}'. Expected {expected_type.__name__}."}), 400

        if not updated_fields_tracker:
            return jsonify({"message": "No changes detected in provided settings."}), 304  # Not Modified

        try:
            db.session.commit()
            current_app.logger.info(
                f"Company settings for Company ID {company_settings_obj.company_id} updated by {current_user.username} (ID: {current_user.id}).")
            return jsonify({
                "message": "Company settings updated successfully.",
                "settings": {  # Επιστρέφουμε τις ενημερωμένες ρυθμίσεις
                    "company_id": company_settings_obj.company_id,
                    "rejection_email_template": company_settings_obj.rejection_email_template,
                    "interview_invitation_email_template": company_settings_obj.interview_invitation_email_template,
                    "default_interview_reminder_timing_minutes": company_settings_obj.default_interview_reminder_timing_minutes,
                    "enable_reminders_feature_for_company": company_settings_obj.enable_reminders_feature_for_company
                }
            }), 200
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error saving company settings for {company_settings_obj.company_id}: {e}",
                                     exc_info=True)
            return jsonify({"error": "Failed to save company settings due to an internal error."}), 500


@bp.route('/interviews/confirm/<string:confirmation_uuid>', methods=['GET'])  # Άλλαξε από api_bp σε bp
def confirm_interview(confirmation_uuid):
    try:
        candidate = Candidate.query.filter_by(confirmation_uuid=confirmation_uuid).first()
        if not candidate:
            return "<h1>Σφάλμα</h1><p>Ο σύνδεσμος επιβεβαίωσης δεν είναι έγκυρος ή έχει λήξει.</p>", 404
        if not candidate.interview_datetime:  # Έλεγχος αν υπάρχει προγραμματισμένη συνέντευξη
            return "<h1>Σφάλμα</h1><p>Δεν υπάρχει προγραμματισμένη συνέντευξη για αυτόν τον υποψήφιο που να αντιστοιχεί σε αυτόν τον σύνδεσμο.</p>", 400

        response_message_html = ""
        status_code = 200

        if candidate.candidate_confirmation_status == 'Confirmed':
            response_message_html = f"<h1>Ήδη Επιβεβαιωμένο</h1><p>Η συνέντευξή σας στις {candidate.interview_datetime.strftime('%d/%m/%Y %H:%M')} UTC έχει ήδη επιβεβαιωθεί.</p>"
        elif candidate.candidate_confirmation_status in ['Pending', 'Declined',
                                                         None]:  # Επιτρέπουμε επιβεβαίωση και αν ήταν Declined ή None
            candidate.candidate_confirmation_status = 'Confirmed'
            candidate.add_history_event(
                event_type="interview_confirmed_by_candidate",
                description=f"Candidate confirmed interview via link.",
                details={"confirmation_uuid": confirmation_uuid}
            )
            db.session.commit()

            # Ειδοποίηση του recruiter/εταιρείας μέσω Celery task
            try:
                # Βεβαιώσου ότι το task παίρνει τα σωστά arguments
                celery.send_task('tasks.communication.notify_recruiter_interview_confirmed_task',
                                 args=[str(candidate.candidate_id), candidate.company_id])
            except Exception as celery_err:
                current_app.logger.error(
                    f"Failed to send Celery task for interview confirmation (Candidate: {candidate.candidate_id}): {celery_err}",
                    exc_info=True)

            response_message_html = f"<h1>Επιβεβαίωση Επιτυχής</h1><p>Ευχαριστούμε, {candidate.get_full_name()}! Η συνέντευξή σας στις {candidate.interview_datetime.strftime('%d/%m/%Y %H:%M')} UTC έχει επιβεβαιωθεί.</p>"
        else:  # Άγνωστο status
            response_message_html = "<h1>Σφάλμα</h1><p>Αυτή η ενέργεια δεν είναι δυνατή για την τρέχουσα κατάσταση της συνέντευξης.</p>"
            status_code = 400

        return response_message_html, status_code
    except Exception as e:
        db.session.rollback()  # Κάνε rollback σε περίπτωση σφάλματος
        current_app.logger.error(f"Error confirming interview (UUID: {confirmation_uuid}): {e}", exc_info=True)
        return "<h1>Σφάλμα Συστήματος</h1><p>Παρουσιάστηκε ένα μη αναμενόμενο σφάλμα κατά την επεξεργασία του αιτήματός σας. Παρακαλούμε δοκιμάστε ξανά αργότερα.</p>", 500


@bp.route('/interviews/decline/<string:confirmation_uuid>', methods=['GET'])  # Άλλαξε από api_bp σε bp
def decline_interview(confirmation_uuid):
    try:
        candidate = Candidate.query.filter_by(confirmation_uuid=confirmation_uuid).first()
        if not candidate:
            return "<h1>Σφάλμα</h1><p>Ο σύνδεσμος απόρριψης δεν είναι έγκυρος ή έχει λήξει.</p>", 404
        if not candidate.interview_datetime:
            return "<h1>Σφάλμα</h1><p>Δεν υπάρχει προγραμματισμένη συνέντευξη για αυτόν τον υποψήφιο που να αντιστοιχεί σε αυτόν τον σύνδεσμο.</p>", 400

        response_message_html = ""
        status_code = 200

        if candidate.candidate_confirmation_status == 'Declined':
            response_message_html = f"<h1>Ήδη Δηλωμένη Άρνηση</h1><p>Έχετε ήδη δηλώσει αδυναμία για τη συνέντευξη στις {candidate.interview_datetime.strftime('%d/%m/%Y %H:%M')} UTC.</p>"
        elif candidate.candidate_confirmation_status in ['Pending', 'Confirmed',
                                                         None]:  # Επιτρέπουμε άρνηση και αν ήταν Confirmed ή None
            candidate.candidate_confirmation_status = 'Declined'
            candidate.add_history_event(
                event_type="interview_declined_by_candidate",
                description=f"Candidate declined interview via link.",
                details={"confirmation_uuid": confirmation_uuid}
            )
            db.session.commit()

            try:
                celery.send_task('tasks.communication.notify_recruiter_interview_declined_task',
                                 args=[str(candidate.candidate_id), candidate.company_id])
            except Exception as celery_err:
                current_app.logger.error(
                    f"Failed to send Celery task for interview declination (Candidate: {candidate.candidate_id}): {celery_err}",
                    exc_info=True)

            response_message_html = f"<h1>Επιβεβαίωση Άρνησης</h1><p>Λάβαμε την ενημέρωσή σας ότι δεν μπορείτε να παραστείτε στη συνέντευξη στις {candidate.interview_datetime.strftime('%d/%m/%Y %H:%M')} UTC.</p>"
        else:
            response_message_html = "<h1>Σφάλμα</h1><p>Αυτή η ενέργεια δεν είναι δυνατή για την τρέχουσα κατάσταση της συνέντευξης.</p>"
            status_code = 400

        return response_message_html, status_code
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error declining interview (UUID: {confirmation_uuid}): {e}", exc_info=True)
        return "<h1>Σφάλμα Συστήματος</h1><p>Παρουσιάστηκε ένα μη αναμενόμενο σφάλμα. Παρακαλούμε δοκιμάστε ξανά αργότερα.</p>", 500