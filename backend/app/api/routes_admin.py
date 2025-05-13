# backend/app/api/routes_admin.py
from flask import Blueprint, request, jsonify, current_app
from app import db
from app.models import User, Company, CompanySettings
from flask_login import login_required, current_user
from functools import wraps

# Δημιουργία ενός νέου Blueprint για τις admin διαδρομές
# Θα το καταχωρήσουμε στο app/__init__.py ή στο κύριο api_bp αν θέλουμε να είναι κάτω από /api/v1/admin
admin_bp = Blueprint('admin_api', __name__, url_prefix='/admin')  # Προτείνω ξεχωριστό prefix /admin


# --- Decorator για έλεγχο αν ο χρήστης είναι superadmin ---
def superadmin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'superadmin':
            return jsonify({"error": "Superadmin access required"}), 403
        return f(*args, **kwargs)

    return decorated_function


# === Company Management Endpoints ===

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
        # Προαιρετικά, μπορείς να πάρεις και owner_user_id από το request αν θέλεις να ορίσεις ιδιοκτήτη αμέσως
        # owner_id = data.get('owner_user_id')
        # if owner_id:
        #     owner = User.query.get(owner_id)
        #     if owner:
        #         new_company.owner_user_id = owner_id
        #     else:
        #         current_app.logger.warning(f"Owner user ID {owner_id} not found for new company {company_name}")

        db.session.add(new_company)
        db.session.commit()  # Commit για να πάρει ID η εταιρεία

        # Δημιουργία CompanySettings για τη νέα εταιρεία
        company_settings = CompanySettings(company_id=new_company.id)
        # Μπορείς να ορίσεις default templates εδώ αν θέλεις
        # settings.rejection_email_template = "Default rejection..."
        db.session.add(company_settings)
        db.session.commit()

        current_app.logger.info(
            f"Company '{new_company.name}' (ID: {new_company.id}) created by superadmin {current_user.username}.")
        # Επιστροφή του πλήρους αντικειμένου της εταιρείας (χωρίς settings για συντομία εδώ)
        return jsonify({
            "id": new_company.id,
            "name": new_company.name,
            "owner_user_id": new_company.owner_user_id,
            "created_at": new_company.created_at.isoformat(),
            "has_settings": True  # Υποδηλώνει ότι δημιουργήθηκαν και settings
        }), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating company '{company_name}': {e}", exc_info=True)
        return jsonify({"error": "Failed to create company due to an internal error."}), 500


@admin_bp.route('/companies', methods=['GET'])
@login_required
@superadmin_required
def get_companies():
    try:
        companies = Company.query.order_by(Company.name).all()
        companies_list = []
        for company in companies:
            company_data = {
                "id": company.id,
                "name": company.name,
                "owner_user_id": company.owner_user_id,
                "created_at": company.created_at.isoformat(),
                "user_count": company.users.count(),  # Παράδειγμα μέτρησης χρηστών
                "candidate_count": company.candidates.count()  # Παράδειγμα μέτρησης υποψηφίων
            }
            # Μπορείς να προσθέσεις και πληροφορίες από το company.settings αν χρειάζεται
            companies_list.append(company_data)
        return jsonify(companies_list), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching companies: {e}", exc_info=True)
        return jsonify({"error": "Failed to retrieve companies."}), 500


@admin_bp.route('/companies/<int:company_id>', methods=['GET'])
@login_required
@superadmin_required
def get_company(company_id):
    company = Company.query.get_or_404(company_id)
    # Μπορείς να προσθέσεις περισσότερες λεπτομέρειες εδώ, π.χ. χρήστες, ρυθμίσεις
    return jsonify({
        "id": company.id,
        "name": company.name,
        "owner_user_id": company.owner_user_id,
        "created_at": company.created_at.isoformat(),
        "settings": {  # Παράδειγμα επιστροφής ρυθμίσεων
            "interview_reminder_timing_minutes": company.settings.interview_reminder_timing_minutes if company.settings else None,
            # ... άλλες ρυθμίσεις ...
        }
    }), 200


@admin_bp.route('/companies/<int:company_id>', methods=['PUT'])
@login_required
@superadmin_required
def update_company(company_id):
    company = Company.query.get_or_404(company_id)
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided for update"}), 400

    updated = False
    if 'name' in data:
        new_name = data['name'].strip()
        if not new_name:
            return jsonify({"error": "Company name cannot be empty"}), 400
        if new_name != company.name:
            # Έλεγχος αν το νέο όνομα υπάρχει ήδη (εκτός από την τρέχουσα εταιρεία)
            existing_company_with_new_name = Company.query.filter(Company.name == new_name,
                                                                  Company.id != company_id).first()
            if existing_company_with_new_name:
                return jsonify({"error": f"Another company with name '{new_name}' already exists"}), 409
            company.name = new_name
            updated = True

    if 'owner_user_id' in data:
        new_owner_id = data.get('owner_user_id')
        if new_owner_id is not None:  # Επιτρέπει την αφαίρεση owner με null
            owner = User.query.get(new_owner_id)
            if not owner:
                return jsonify({"error": f"User with ID {new_owner_id} not found to be set as owner."}), 404
            if owner.company_id != company_id and owner.role != 'superadmin':  # Ο owner πρέπει να ανήκει στην εταιρεία ή να είναι superadmin
                return jsonify({
                                   "error": f"User {owner.username} cannot own company {company.name} as they belong to a different company or have an unsuitable role."}), 400
        company.owner_user_id = new_owner_id
        updated = True

    if not updated:
        return jsonify({"message": "No changes detected"}), 304

    try:
        db.session.commit()
        current_app.logger.info(
            f"Company '{company.name}' (ID: {company.id}) updated by superadmin {current_user.username}.")
        return jsonify({"id": company.id, "name": company.name, "owner_user_id": company.owner_user_id}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating company {company_id}: {e}", exc_info=True)
        return jsonify({"error": "Failed to update company."}), 500


# (Προαιρετικό: DELETE company - χρειάζεται προσοχή με τα εξαρτώμενα δεδομένα)
# @admin_bp.route('/companies/<int:company_id>', methods=['DELETE'])
# @login_required
# @superadmin_required
# def delete_company(company_id):
#     # ... (υλοποίηση με προσοχή, ίσως soft delete ή έλεγχος για υπάρχοντες χρήστες/υποψηφίους)


# === User Management Endpoints by Superadmin ===

@admin_bp.route('/users', methods=['POST'])
@login_required
@superadmin_required
def create_user_by_superadmin():
    data = request.get_json()
    if not data: return jsonify({"error": "Request must be JSON"}), 400

    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    role = data.get('role', 'user')  # Default σε 'user'
    company_id = data.get('company_id')  # Το ID της εταιρείας στην οποία θα ανήκει ο χρήστης
    is_active = data.get('is_active', True)  # Default σε active

    if not username or not email or not password:
        return jsonify({"error": "Username, email, and password are required"}), 400
    if role not in ['user', 'company_admin',
                    'superadmin']:  # Ο superadmin μπορεί να δημιουργήσει και άλλους superadmins
        return jsonify({"error": "Invalid role specified"}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username already exists"}), 409
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email address already registered"}), 409

    target_company = None
    if role != 'superadmin':  # Superadmins don't need a company_id
        if not company_id:
            return jsonify({"error": "Company ID is required for roles 'user' and 'company_admin'"}), 400
        target_company = Company.query.get(company_id)
        if not target_company:
            return jsonify({"error": f"Company with ID {company_id} not found"}), 404

    try:
        new_user = User(
            username=username,
            email=email,
            role=role,
            is_active=is_active,
            company_id=target_company.id if target_company else None,
            confirmed_on=datetime.now(timezone.utc) if is_active else None
        )
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        current_app.logger.info(
            f"User '{new_user.username}' (Role: {new_user.role}, Company: {target_company.name if target_company else 'N/A'}) created by superadmin {current_user.username}.")
        return jsonify({
            "id": new_user.id, "username": new_user.username, "email": new_user.email,
            "role": new_user.role, "company_id": new_user.company_id, "is_active": new_user.is_active
        }), 201
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
    company_id_filter = request.args.get('company_id', type=int)

    query = User.query
    if role_filter:
        query = query.filter(User.role == role_filter)
    if company_id_filter:
        query = query.filter(User.company_id == company_id_filter)

    users_pagination = query.order_by(User.username).paginate(page=page, per_page=per_page, error_out=False)
    users_list = [{
        "id": user.id, "username": user.username, "email": user.email,
        "role": user.role, "company_id": user.company_id,
        "company_name": user.company.name if user.company else None,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat()
    } for user in users_pagination.items]

    return jsonify({
        "users": users_list,
        "total_pages": users_pagination.pages,
        "current_page": users_pagination.page,
        "total_users": users_pagination.total
    }), 200


@admin_bp.route('/users/<int:user_id>', methods=['PUT'])
@login_required
@superadmin_required
def update_user_by_superadmin(user_id):
    user_to_update = User.query.get_or_404(user_id)
    data = request.get_json()
    if not data: return jsonify({"error": "No data provided"}), 400

    updated = False
    if 'username' in data and data['username'] != user_to_update.username:
        if User.query.filter(User.username == data['username'], User.id != user_id).first():
            return jsonify({"error": "Username already taken"}), 409
        user_to_update.username = data['username']
        updated = True

    if 'email' in data and data['email'] != user_to_update.email:
        if User.query.filter(User.email == data['email'], User.id != user_id).first():
            return jsonify({"error": "Email already registered"}), 409
        user_to_update.email = data['email']
        updated = True

    if 'role' in data and data['role'] != user_to_update.role:
        if data['role'] not in ['user', 'company_admin', 'superadmin']:
            return jsonify({"error": "Invalid role"}), 400
        user_to_update.role = data['role']
        # If role changes to superadmin, company_id should be None
        if user_to_update.role == 'superadmin':
            user_to_update.company_id = None
        updated = True

    if 'company_id' in data and data['company_id'] != user_to_update.company_id:
        if user_to_update.role == 'superadmin' and data['company_id'] is not None:
            return jsonify({"error": "Superadmin cannot be assigned to a company."}), 400
        if data['company_id'] is not None:
            company = Company.query.get(data['company_id'])
            if not company:
                return jsonify({"error": "Target company not found"}), 404
        user_to_update.company_id = data.get('company_id')  # Can be None
        updated = True

    if 'is_active' in data and data['is_active'] != user_to_update.is_active:
        user_to_update.is_active = bool(data['is_active'])
        if user_to_update.is_active and not user_to_update.confirmed_on:  # Mark as confirmed if activated
            user_to_update.confirmed_on = datetime.now(timezone.utc)
        updated = True

    if 'password' in data and data['password']:  # Allow password change
        user_to_update.set_password(data['password'])
        updated = True

    if not updated: return jsonify({"message": "No changes detected"}), 304

    try:
        db.session.commit()
        current_app.logger.info(f"User ID {user_id} updated by superadmin {current_user.username}.")
        return jsonify({"message": "User updated successfully", "user": {
            "id": user_to_update.id, "username": user_to_update.username, "email": user_to_update.email,
            "role": user_to_update.role, "company_id": user_to_update.company_id, "is_active": user_to_update.is_active
        }}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating user {user_id} by superadmin: {e}", exc_info=True)
        return jsonify({"error": "Failed to update user"}), 500