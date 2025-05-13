# backend/app/api/routes_company_admin.py
from flask import Blueprint, request, jsonify, current_app
from app import db
from app.models import User
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime, timezone

# Αφαιρέσαμε το url_prefix από εδώ
company_admin_bp = Blueprint('company_admin_api', __name__)
print("!!!!!!!! FULL routes_company_admin.py - BLUEPRINT DEFINED (NO INTERNAL PREFIX, FOR OPTION A) !!!!!!!!!!")

def company_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({"error": "Authentication required"}), 401
        if current_user.role != 'company_admin':
            current_app.logger.warning(f"Access denied for user {current_user.id} ({current_user.username}) with role {current_user.role} to company admin route.")
            return jsonify({"error": "Company admin access required"}), 403
        if not current_user.company_id:
            current_app.logger.error(f"Company admin {current_user.id} ({current_user.username}) has no company_id!")
            return jsonify({"error": "User configuration error: company admin not linked to a company."}), 500
        return f(*args, **kwargs)
    return decorated_function

# Προσθέσαμε το /company στο path του route εδώ
@company_admin_bp.route('/company/users', methods=['GET'])
@login_required
@company_admin_required
def get_company_users():
    admin_company_id = current_user.company_id
    current_app.logger.info(f"Company admin {current_user.id} fetching users for company {admin_company_id}.")
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    try:
        users_pagination = User.query.filter_by(company_id=admin_company_id)\
                                     .order_by(User.username)\
                                     .paginate(page=page, per_page=per_page, error_out=False)
        users_list = [{
            "id": user.id, "username": user.username, "email": user.email,
            "role": user.role, "is_active": user.is_active,
            "created_at": user.created_at.isoformat() if user.created_at else None
        } for user in users_pagination.items]
        return jsonify({
            "users": users_list, "total_pages": users_pagination.pages,
            "current_page": users_pagination.page, "total_users": users_pagination.total
        }), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching users for company {admin_company_id} by admin {current_user.id}: {e}", exc_info=True)
        return jsonify({"error": "Failed to retrieve users."}), 500

# Προσθέσαμε το /company στο path του route εδώ
@company_admin_bp.route('/company/users', methods=['POST'])
@login_required
@company_admin_required
def create_company_user():
    admin_company_id = current_user.company_id
    data = request.get_json()
    current_app.logger.info(f"Company admin {current_user.id} attempting to create user for company {admin_company_id} with data: {data}")
    if not data: return jsonify({"error": "Request must be JSON"}), 400
    username = data.get('username'); email = data.get('email'); password = data.get('password')
    if not username or not email or not password:
        return jsonify({"error": "Username, email, and password are required"}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username already exists"}), 409
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email address already registered"}), 409
    try:
        new_user = User(
            username=username, email=email, role='user', is_active=True,
            confirmed_on=datetime.now(timezone.utc), company_id=admin_company_id
        )
        new_user.set_password(password)
        db.session.add(new_user); db.session.commit()
        current_app.logger.info(f"User '{new_user.username}' created for company ID {admin_company_id} by company admin {current_user.username}.")
        return jsonify({
            "id": new_user.id, "username": new_user.username, "email": new_user.email,
            "role": new_user.role, "company_id": new_user.company_id, "is_active": new_user.is_active
        }), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Company admin {current_user.id} error creating user '{username}': {e}", exc_info=True)
        return jsonify({"error": "Failed to create user due to an internal error."}), 500

# Προσθέσαμε το /company στο path του route εδώ
@company_admin_bp.route('/company/users/<int:user_id>/status', methods=['PUT'])
@login_required
@company_admin_required
def toggle_company_user_status(user_id):
    admin_company_id = current_user.company_id
    current_app.logger.info(f"Company admin {current_user.id} attempting to toggle status for user {user_id} in company {admin_company_id}.")
    user_to_toggle = User.query.filter_by(id=user_id, company_id=admin_company_id).first_or_404(
        description="User not found in your company or does not exist."
    )
    if user_to_toggle.id == current_user.id:
        return jsonify({"error": "Cannot change your own status via this endpoint."}), 403
    if user_to_toggle.role in ['company_admin', 'superadmin'] and user_to_toggle.id != current_user.id :
         return jsonify({"error": "You cannot change the status of another administrator."}), 403
    data = request.get_json()
    if data is None or 'is_active' not in data or not isinstance(data['is_active'], bool):
        return jsonify({"error": "Invalid or missing 'is_active' status (must be true or false)."}), 400
    new_status = data['is_active']
    if user_to_toggle.is_active == new_status:
        return jsonify({"message": "No change in user status."}), 200
    user_to_toggle.is_active = new_status
    if new_status and not user_to_toggle.confirmed_on:
        user_to_toggle.confirmed_on = datetime.now(timezone.utc)
    try:
        db.session.commit()
        current_app.logger.info(f"User '{user_to_toggle.username}' (ID: {user_to_toggle.id}) status changed to {new_status} by company admin {current_user.username}.")
        return jsonify({
            "id": user_to_toggle.id, "username": user_to_toggle.username, "is_active": user_to_toggle.is_active
        }), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error changing status for user {user_id} by company admin {current_user.id}: {e}", exc_info=True)
        return jsonify({"error": "Failed to update user status."}), 500