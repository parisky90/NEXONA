# backend/app/api/routes_company_admin.py
from flask import Blueprint, request, jsonify, current_app
from app import db
from app.models import User, Company, Interview, Candidate
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime, timezone as dt_timezone

company_admin_bp = Blueprint('company_admin_api', __name__, url_prefix='/api/v1/company')


def company_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        current_app.logger.info(f"[Decorator @company_admin_required ENTER] Path: {request.path}")
        if not current_user.is_authenticated:
            current_app.logger.warning(
                f"[Decorator @company_admin_required] User NOT AUTHENTICATED. Path: {request.path}")
            return jsonify({"error": "Authentication required"}), 401

        current_app.logger.info(
            f"[Decorator @company_admin_required] User: {current_user.username}, Role: {current_user.role}, Company ID: {current_user.company_id}")

        if current_user.role not in ['company_admin', 'superadmin']:
            current_app.logger.warning(
                f"[Decorator @company_admin_required] Access DENIED. User {current_user.id} ({current_user.username}) with role {current_user.role} to company admin route {request.path}.")
            return jsonify({"error": "Company admin or superadmin access required"}), 403

        if current_user.role == 'company_admin' and not current_user.company_id:
            current_app.logger.error(
                f"[Decorator @company_admin_required] CONFIG ERROR. Company admin {current_user.id} ({current_user.username}) has no company_id!")
            return jsonify({"error": "User configuration error: company admin not linked to a company."}), 500

        current_app.logger.info(
            f"[Decorator @company_admin_required EXIT - GRANTED] Path: {request.path}, User: {current_user.username}")
        return f(*args, **kwargs)

    return decorated_function


@company_admin_bp.route('/users', methods=['GET'])
@login_required
@company_admin_required
def get_company_users():
    current_app.logger.info(
        f"--- HIT /api/v1/company/users (user: {current_user.id}, role: {current_user.role}, company_id from user: {current_user.company_id}) ---")
    current_app.logger.info(f"Request args for company/users: {request.args}")

    target_company_id = None
    if current_user.role == 'superadmin':
        company_id_arg = request.args.get('company_id', type=int)
        if not company_id_arg:
            return jsonify({"error": "Superadmin must specify a 'company_id' query parameter."}), 400
        target_company_id = company_id_arg
        if not db.session.get(Company, target_company_id):
            return jsonify({"error": f"Company with ID {target_company_id} not found."}), 404
    else:
        target_company_id = current_user.company_id

    current_app.logger.info(f"User {current_user.id} fetching users for company {target_company_id}.")
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    try:
        users_pagination = User.query.filter_by(company_id=target_company_id) \
            .order_by(User.username) \
            .paginate(page=page, per_page=per_page, error_out=False)
        users_list = [user.to_dict() for user in users_pagination.items]
        return jsonify({
            "users": users_list, "total_pages": users_pagination.pages,
            "current_page": users_pagination.page, "total_users": users_pagination.total
        }), 200
    except Exception as e:
        current_app.logger.error(
            f"Error fetching users for company {target_company_id} by admin {current_user.id}: {e}", exc_info=True)
        return jsonify({"error": "Failed to retrieve users."}), 500


@company_admin_bp.route('/users', methods=['POST'])
@login_required
@company_admin_required
def create_company_user():
    current_app.logger.info(
        f"[COMPANY_ADMIN_ROUTE] /users POST accessed by: User ID: {current_user.id}, Role: {current_user.role}, Company ID: {current_user.company_id}")
    admin_acting_company_id = None
    data = request.get_json()
    if not data: return jsonify({"error": "Request must be JSON"}), 400
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    role_for_new_user = data.get('role', 'user')
    if current_user.role == 'superadmin':
        company_id_from_payload_str = data.get('company_id')
        if not company_id_from_payload_str and role_for_new_user != 'superadmin':
            return jsonify({"error": "Superadmin must provide company_id for non-superadmin target roles."}), 400
        if company_id_from_payload_str:
            try:
                admin_acting_company_id = int(company_id_from_payload_str)
                if not db.session.get(Company, admin_acting_company_id):
                    return jsonify({"error": f"Company with ID {admin_acting_company_id} not found."}), 404
            except ValueError:
                return jsonify({"error": "Invalid company_id format in payload."}), 400
    else:
        admin_acting_company_id = current_user.company_id
    if not admin_acting_company_id and role_for_new_user != 'superadmin':
        return jsonify({"error": "Target Company ID is required for this user role and could not be determined."}), 400
    if not all([username, email, password]): return jsonify(
        {"error": "Username, email, and password are required"}), 400
    if User.query.filter_by(username=username).first(): return jsonify({"error": "Username already exists"}), 409
    if User.query.filter_by(email=email.lower().strip()).first(): return jsonify(
        {"error": "Email address already registered"}), 409
    if current_user.role == 'company_admin' and role_for_new_user not in ['user']:
        return jsonify({"error": "Company admins can only create users with the 'user' role."}), 403
    if role_for_new_user == 'superadmin' and current_user.role != 'superadmin':
        return jsonify({"error": "Only superadmins can create other superadmins."}), 403
    try:
        new_user = User(
            username=username.strip(), email=email.strip().lower(), role=role_for_new_user,
            is_active=data.get('is_active', True),
            confirmed_on=datetime.now(dt_timezone.utc) if data.get('is_active', True) else None,
            company_id=admin_acting_company_id
        )
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        current_app.logger.info(
            f"User '{new_user.username}' (Role: {role_for_new_user}) created for company ID {admin_acting_company_id} by {current_user.username}.")
        return jsonify(new_user.to_dict(include_company_info=(current_user.role == 'superadmin'))), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating user '{username}' by {current_user.username}: {e}", exc_info=True)
        return jsonify({"error": "Failed to create user due to an internal error."}), 500


@company_admin_bp.route('/users/<int:user_id>/status', methods=['PUT'])
@login_required
@company_admin_required
def toggle_company_user_status(user_id):
    current_app.logger.info(
        f"[COMPANY_ADMIN_ROUTE] /users/{user_id}/status PUT accessed by: User ID: {current_user.id}, Role: {current_user.role}")
    user_to_toggle = db.session.get(User, user_id)
    if not user_to_toggle: return jsonify({"error": "User not found."}), 404
    if current_user.role == 'company_admin':
        if user_to_toggle.company_id != current_user.company_id: return jsonify(
            {"error": "Forbidden: Cannot manage users outside your company."}), 403
        if user_to_toggle.role != 'user': return jsonify(
            {"error": "Company admins can only toggle status for 'user' role members."}), 403
    elif current_user.role == 'superadmin':
        if user_to_toggle.id == current_user.id and user_to_toggle.role == 'superadmin': return jsonify(
            {"error": "Superadmin cannot change their own active status."}), 403
    data = request.get_json()
    if data is None or 'is_active' not in data or not isinstance(data['is_active'], bool):
        return jsonify({"error": "Invalid or missing 'is_active' status (must be true or false)."}), 400
    new_status = data['is_active']
    if user_to_toggle.is_active == new_status: return jsonify(
        {"message": "No change in user status.", "user": user_to_toggle.to_dict()}), 200
    user_to_toggle.is_active = new_status
    if new_status and not user_to_toggle.confirmed_on: user_to_toggle.confirmed_on = datetime.now(dt_timezone.utc)
    try:
        db.session.commit()
        current_app.logger.info(
            f"User '{user_to_toggle.username}' (ID: {user_to_toggle.id}) status changed to {new_status} by {current_user.username}.")
        return jsonify(user_to_toggle.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error changing status for user {user_id} by {current_user.username}: {e}",
                                 exc_info=True)
        return jsonify({"error": "Failed to update user status."}), 500


@company_admin_bp.route('/interviews', methods=['GET'])
@login_required
@company_admin_required
def get_company_interviews():
    current_app.logger.info(
        f"--- HIT /api/v1/company/interviews (user: {current_user.id}, role: {current_user.role}, company_id from user: {current_user.company_id}) ---")
    current_app.logger.info(f"Request args for company/interviews: {request.args}")

    target_company_id = None
    if current_user.role == 'superadmin':
        company_id_arg = request.args.get('company_id', type=int)
        # --- ΔΙΟΡΘΩΣΗ: Έλεγχος αν το company_id_arg είναι None ή 0 για superadmin ---
        if company_id_arg is None:  # Αν ο superadmin δεν δώσει company_id, δεν πρέπει να είναι 400.
            current_app.logger.info("Superadmin fetching interviews for ALL companies (no company_id provided).")
            # Η λογική για all companies θα εφαρμοστεί παρακάτω στο query
        elif company_id_arg == 0:  # Αν δώσει 0, μπορεί να σημαίνει κάτι ειδικό ή να το αγνοήσουμε
            current_app.logger.info(
                "Superadmin provided company_id=0 for interviews. Treating as 'all companies' or specific logic if intended.")
        elif company_id_arg > 0:
            target_company_id = company_id_arg
            if not db.session.get(Company, target_company_id):
                return jsonify({"error": f"Company with ID {target_company_id} not found."}), 404
        else:  # Αρνητικό ή μη έγκυρο company_id
            return jsonify({"error": f"Invalid company_id '{company_id_arg}' provided by superadmin."}), 400
    else:
        target_company_id = current_user.company_id
        if not target_company_id:  # Αυτό δεν θα έπρεπε να συμβεί λόγω του decorator
            current_app.logger.error(f"Company admin {current_user.id} has no company_id in get_company_interviews!")
            return jsonify({"error": "User configuration error."}), 500

    current_app.logger.info(
        f"User {current_user.id} fetching interviews. Effective target_company_id for query: {target_company_id}.")

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 15, type=int)
    status_filter = request.args.get('status')

    query = Interview.query.join(Candidate)  # Join με Candidate για να μπορούμε να φιλτράρουμε με company_id

    if target_company_id:  # Εφάρμοσε το φίλτρο company_id μόνο αν έχει οριστεί
        query = query.filter(Candidate.company_id == target_company_id)

    if status_filter:
        query = query.filter(
            Interview.status == status_filter.upper())

    query = query.order_by(Interview.created_at.desc())

    try:
        interviews_pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        interviews_list = [interview.to_dict(include_sensitive=True) for interview in
                           interviews_pagination.items]

        return jsonify({
            "interviews": interviews_list,
            "total_pages": interviews_pagination.pages,
            "current_page": interviews_pagination.page,
            "total_interviews": interviews_pagination.total
        }), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching interviews for company {target_company_id}: {e}", exc_info=True)
        return jsonify({"error": "Failed to retrieve interviews."}), 500