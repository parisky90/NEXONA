# backend/app/api/routes_admin.py
from flask import Blueprint, request, jsonify, current_app
from app import db
from app.models import User, Company, CompanySettings
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime, timezone as dt_timezone

admin_bp = Blueprint('admin_api', __name__, url_prefix='/api/v1/admin')

def superadmin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # --- ΠΡΟΣΘΗΚΗ LOGGING ---
        current_app.logger.debug(f"[Decorator @superadmin_required] Path: {request.path}, User: {current_user.username if current_user.is_authenticated else 'Anonymous'}, Role: {current_user.role if current_user.is_authenticated else 'N/A'}")
        # --- ΤΕΛΟΣ ΠΡΟΣΘΗΚΗΣ ---
        if not current_user.is_authenticated or current_user.role != 'superadmin':
            current_app.logger.warning(
                f"Superadmin access denied for user {current_user.username if current_user.is_authenticated else 'Anonymous'} to route {request.path}"
            )
            return jsonify({"error": "Superadmin access required"}), 403
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/companies', methods=['POST'])
@login_required
@superadmin_required
def create_company():
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({"error": "Company name is required"}), 400
    company_name = data.get('name').strip()
    if not company_name:
        return jsonify({"error": "Company name cannot be empty"}), 400
    if Company.query.filter_by(name=company_name).first():
        return jsonify({"error": f"Company with name '{company_name}' already exists"}), 409
    try:
        new_company = Company(name=company_name)
        db.session.add(new_company)
        db.session.commit()
        company_settings = CompanySettings(company_id=new_company.id)
        db.session.add(company_settings)
        db.session.commit()
        current_app.logger.info(
            f"Company '{new_company.name}' (ID: {new_company.id}) created by superadmin {current_user.username}."
        )
        return jsonify(new_company.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating company '{company_name}': {e}", exc_info=True)
        return jsonify({"error": "Failed to create company due to an internal error."}), 500

@admin_bp.route('/companies', methods=['GET'])
@login_required
@superadmin_required
def get_companies():
    try:
        companies_query = Company.query.order_by(Company.name)
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 100, type=int)
        companies_pagination = companies_query.paginate(page=page, per_page=per_page, error_out=False)
        companies_list = [company.to_dict() for company in companies_pagination.items]
        return jsonify({
            "companies": companies_list,
            "total_pages": companies_pagination.pages,
            "current_page": companies_pagination.page,
            "total_companies": companies_pagination.total
        }), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching companies: {e}", exc_info=True)
        return jsonify({"error": "Failed to retrieve companies."}), 500

@admin_bp.route('/companies/<int:company_id>', methods=['GET'])
@login_required
@superadmin_required
def get_company(company_id):
    company = db.session.get(Company, company_id)
    if not company:
        return jsonify({"error": "Company not found"}), 404
    return jsonify(company.to_dict()), 200

@admin_bp.route('/companies/<int:company_id>', methods=['PUT'])
@login_required
@superadmin_required
def update_company(company_id):
    company = db.session.get(Company, company_id)
    if not company:
        return jsonify({"error": "Company not found"}), 404
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided for update"}), 400
    updated_fields_count = 0
    if 'name' in data:
        new_name = data['name'].strip()
        if not new_name: return jsonify({"error": "Company name cannot be empty"}), 400
        if new_name != company.name:
            if Company.query.filter(Company.name == new_name, Company.id != company_id).first():
                return jsonify({"error": f"Another company with name '{new_name}' already exists"}), 409
            company.name = new_name
            updated_fields_count +=1
    if 'owner_user_id' in data:
        new_owner_id = data.get('owner_user_id')
        processed_owner_id = None
        if new_owner_id is not None:
            try:
                processed_owner_id = int(new_owner_id)
                if processed_owner_id == 0: processed_owner_id = None
            except ValueError: return jsonify({"error": "Invalid owner_user_id format."}), 400
        if processed_owner_id is not None:
            owner = db.session.get(User, processed_owner_id)
            if not owner: return jsonify({"error": f"User with ID {processed_owner_id} not found to be set as owner."}), 404
            if owner.role != 'superadmin' and owner.company_id != company_id:
                 return jsonify({"error": f"User {owner.username} (ID: {owner.id}, Company: {owner.company_id}) cannot own company {company.name} (ID: {company.id})."}), 400
        if company.owner_user_id != processed_owner_id:
            company.owner_user_id = processed_owner_id
            updated_fields_count +=1
    if 'settings' in data and isinstance(data['settings'], dict):
        company_settings = company.settings or CompanySettings(company_id=company.id)
        settings_data = data['settings']
        if 'default_interview_reminder_timing_minutes' in settings_data:
            try:
                val = int(settings_data['default_interview_reminder_timing_minutes'])
                if val >=0:
                    company_settings.default_interview_reminder_timing_minutes = val
                    updated_fields_count +=1
            except ValueError: pass
        if 'enable_reminders_feature_for_company' in settings_data:
            company_settings.enable_reminders_feature_for_company = bool(settings_data['enable_reminders_feature_for_company'])
            updated_fields_count +=1
        if 'rejection_email_template' in settings_data:
            company_settings.rejection_email_template = settings_data['rejection_email_template']
            updated_fields_count +=1
        if 'interview_invitation_email_template' in settings_data:
            company_settings.interview_invitation_email_template = settings_data['interview_invitation_email_template']
            updated_fields_count +=1
        if not company.settings: db.session.add(company_settings)
    if updated_fields_count == 0:
        return jsonify({"message": "No changes detected or no updatable fields provided."}), 304
    try:
        company.updated_at = datetime.now(dt_timezone.utc)
        db.session.commit()
        current_app.logger.info(f"Company '{company.name}' (ID: {company.id}) updated by superadmin {current_user.username}.")
        return jsonify(company.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating company {company_id}: {e}", exc_info=True)
        return jsonify({"error": "Failed to update company."}), 500

@admin_bp.route('/users', methods=['POST'])
@login_required
@superadmin_required
def create_user_by_superadmin():
    data = request.get_json()
    if not data: return jsonify({"error": "Request must be JSON"}), 400
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    role = data.get('role', 'user')
    company_id_str = data.get('company_id')
    is_active = data.get('is_active', True)
    if not username or not email or not password: return jsonify({"error": "Username, email, and password are required"}), 400
    if role not in ['user', 'company_admin', 'superadmin']: return jsonify({"error": "Invalid role specified"}), 400
    if User.query.filter_by(username=username).first(): return jsonify({"error": "Username already exists"}), 409
    if User.query.filter_by(email=email).first(): return jsonify({"error": "Email address already registered"}), 409
    target_company_id_int = None
    if role != 'superadmin':
        if not company_id_str: return jsonify({"error": "Company ID is required for roles 'user' and 'company_admin'"}), 400
        try:
            target_company_id_int = int(company_id_str)
            if not db.session.get(Company, target_company_id_int): return jsonify({"error": f"Company with ID {target_company_id_int} not found"}), 404
        except ValueError: return jsonify({"error": "Invalid Company ID format."}), 400
    final_company_id_for_user = target_company_id_int if role != 'superadmin' else None
    try:
        new_user = User(
            username=username, email=email, role=role,
            is_active=is_active, company_id=final_company_id_for_user,
            confirmed_on=datetime.now(dt_timezone.utc) if is_active else None
        )
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        current_app.logger.info(f"User '{new_user.username}' (Role: {new_user.role}, Company ID: {new_user.company_id}) created by superadmin {current_user.username}.")
        return jsonify(new_user.to_dict(include_company_info=True)), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Superadmin error creating user '{username}': {e}", exc_info=True)
        return jsonify({"error": "Failed to create user due to an internal error."}), 500

@admin_bp.route('/users', methods=['GET'])
@login_required
@superadmin_required
def get_users_by_superadmin():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    role_filter = request.args.get('role')
    company_id_filter_str = request.args.get('company_id')
    query = User.query
    if role_filter and role_filter.lower() != 'all': query = query.filter(User.role == role_filter)
    if company_id_filter_str and company_id_filter_str.lower() != 'all':
        try:
            company_id_val = int(company_id_filter_str)
            if company_id_val == 0: query = query.filter(User.company_id.is_(None))
            elif db.session.get(Company, company_id_val): query = query.filter(User.company_id == company_id_val)
            else:
                current_app.logger.warning(f"Company ID {company_id_val} for filter not found.")
                return jsonify({"users": [], "total_pages": 0, "current_page": 1, "total_users": 0}), 200
        except ValueError: current_app.logger.warning(f"Invalid company_id filter value: {company_id_filter_str}")
    users_pagination = query.order_by(User.username).paginate(page=page, per_page=per_page, error_out=False)
    users_list = [user.to_dict(include_company_info=True) for user in users_pagination.items]
    return jsonify({"users": users_list, "total_pages": users_pagination.pages, "current_page": users_pagination.page, "total_users": users_pagination.total}), 200

@admin_bp.route('/users/<int:user_id>', methods=['PUT'])
@login_required
@superadmin_required
def update_user_by_superadmin(user_id):
    user_to_update = db.session.get(User, user_id)
    if not user_to_update: return jsonify({"error": "User not found"}), 404
    data = request.get_json()
    if not data: return jsonify({"error": "No data provided"}), 400
    updated_fields_count = 0
    if 'username' in data and data['username'] != user_to_update.username:
        if User.query.filter(User.username == data['username'], User.id != user_id).first(): return jsonify({"error": "Username already taken"}), 409
        user_to_update.username = data['username']
        updated_fields_count += 1
    if 'email' in data and data['email'] != user_to_update.email:
        if User.query.filter(User.email == data['email'], User.id != user_id).first(): return jsonify({"error": "Email already registered"}), 409
        user_to_update.email = data['email']
        updated_fields_count += 1
    if 'role' in data and data['role'] != user_to_update.role:
        if data['role'] not in ['user', 'company_admin', 'superadmin']: return jsonify({"error": "Invalid role"}), 400
        user_to_update.role = data['role']
        if user_to_update.role == 'superadmin': user_to_update.company_id = None
        updated_fields_count += 1
    if 'company_id' in data:
        new_company_id_val = data.get('company_id')
        processed_company_id = None
        if new_company_id_val is not None and str(new_company_id_val).strip() != "":
            try:
                processed_company_id = int(new_company_id_val)
                if processed_company_id == 0: processed_company_id = None
            except ValueError: return jsonify({"error": "Invalid company_id format."}), 400
        if user_to_update.role == 'superadmin' and processed_company_id is not None: return jsonify({"error": "Superadmin cannot be assigned to a company."}), 400
        if processed_company_id is not None and not db.session.get(Company, processed_company_id): return jsonify({"error": f"Target company with ID {processed_company_id} not found"}), 404
        if user_to_update.company_id != processed_company_id:
            user_to_update.company_id = processed_company_id
            updated_fields_count += 1
    if 'is_active' in data and data['is_active'] != user_to_update.is_active:
        user_to_update.is_active = bool(data['is_active'])
        if user_to_update.is_active and not user_to_update.confirmed_on: user_to_update.confirmed_on = datetime.now(dt_timezone.utc)
        updated_fields_count += 1
    if 'password' in data and data['password']:
        user_to_update.set_password(data['password'])
        updated_fields_count += 1
    if 'enable_email_interview_reminders' in data and data['enable_email_interview_reminders'] != user_to_update.enable_email_interview_reminders:
        user_to_update.enable_email_interview_reminders = bool(data['enable_email_interview_reminders'])
        updated_fields_count += 1
    if 'interview_reminder_lead_time_minutes' in data:
        try:
            lead_time = int(data['interview_reminder_lead_time_minutes'])
            if not (5 <= lead_time <= 2880): return jsonify({"error": "Interview reminder lead time must be between 5 and 2880 minutes."}), 400
            if lead_time != user_to_update.interview_reminder_lead_time_minutes:
                user_to_update.interview_reminder_lead_time_minutes = lead_time
                updated_fields_count += 1
        except (ValueError, TypeError): return jsonify({"error": "Invalid format for interview_reminder_lead_time_minutes."}), 400
    if updated_fields_count == 0: return jsonify({"message": "No updatable fields provided or values are the same."}), 304
    try:
        user_to_update.updated_at = datetime.now(dt_timezone.utc)
        db.session.commit()
        current_app.logger.info(f"User ID {user_id} updated by superadmin {current_user.username}.")
        return jsonify({"message": "User updated successfully", "user": user_to_update.to_dict(include_company_info=True)}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating user {user_id} by superadmin: {e}", exc_info=True)
        return jsonify({"error": "Failed to update user"}), 500