# backend/app/api/routes_admin.py
from flask import Blueprint, request, jsonify, current_app
from app import db
from app.models import User, Company, CompanySettings
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime, timezone  # <--- ΠΡΟΣΘΗΚΗ ΑΥΤΟΥ ΤΟΥ IMPORT

# Δημιουργία ενός νέου Blueprint για τις admin διαδρομές
admin_bp = Blueprint('admin_api', __name__, url_prefix='/admin')


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
        db.session.add(new_company)
        db.session.commit()

        company_settings = CompanySettings(company_id=new_company.id)
        db.session.add(company_settings)
        db.session.commit()

        current_app.logger.info(
            f"Company '{new_company.name}' (ID: {new_company.id}) created by superadmin {current_user.username}.")
        return jsonify({
            "id": new_company.id,
            "name": new_company.name,
            "owner_user_id": new_company.owner_user_id,
            "created_at": new_company.created_at.isoformat() if new_company.created_at else None,
            # Προσθήκη ελέγχου για None
            "has_settings": True
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
                "created_at": company.created_at.isoformat() if company.created_at else None,
                "user_count": company.users.count(),
                "candidate_count": company.candidates.count()
            }
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
    company_settings_data = None
    if company.settings:
        company_settings_data = {
            # Άλλαξε το σε default_interview_reminder_timing_minutes για να ταιριάζει με το model
            "default_interview_reminder_timing_minutes": company.settings.default_interview_reminder_timing_minutes,
            "enable_reminders_feature_for_company": company.settings.enable_reminders_feature_for_company,
            "rejection_email_template": company.settings.rejection_email_template,
            "interview_invitation_email_template": company.settings.interview_invitation_email_template,
        }

    return jsonify({
        "id": company.id,
        "name": company.name,
        "owner_user_id": company.owner_user_id,
        "created_at": company.created_at.isoformat() if company.created_at else None,
        "settings": company_settings_data
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
            existing_company_with_new_name = Company.query.filter(Company.name == new_name,
                                                                  Company.id != company_id).first()
            if existing_company_with_new_name:
                return jsonify({"error": f"Another company with name '{new_name}' already exists"}), 409
            company.name = new_name
            updated = True

    if 'owner_user_id' in data:  # Το data.get('owner_user_id') μπορεί να είναι 0, που είναι falsy αλλά έγκυρο ID
        new_owner_id = data.get('owner_user_id')  # Παίρνουμε την τιμή ως έχει
        if new_owner_id is not None:  # Αν είναι None, σημαίνει ότι θέλουμε να το αδειάσουμε
            if isinstance(new_owner_id, str) and new_owner_id.isdigit():  # Αν είναι string αριθμός, μετατροπή
                new_owner_id = int(new_owner_id)
            elif not isinstance(new_owner_id, int):  # Αν δεν είναι int (και δεν είναι None)
                return jsonify({"error": "Invalid owner_user_id format."}), 400

            if new_owner_id == 0:  # Αν ο χρήστης στείλει 0, το κάνουμε None (δεν υπάρχει user με ID 0)
                new_owner_id = None

            if new_owner_id is not None:  # Αν μετά τους ελέγχους δεν είναι None
                owner = User.query.get(new_owner_id)
                if not owner:
                    return jsonify({"error": f"User with ID {new_owner_id} not found to be set as owner."}), 404
                # Έλεγχος αν ο user ανήκει στην εταιρεία ή είναι superadmin
                # (Αν ο owner είναι superadmin, το owner.company_id θα είναι None)
                if owner.role != 'superadmin' and owner.company_id != company_id:
                    return jsonify({"error": f"User {owner.username} cannot own this company."}), 400

        if company.owner_user_id != new_owner_id:
            company.owner_user_id = new_owner_id
            updated = True

    if not updated:
        return jsonify({"message": "No changes detected"}), 304  # HTTP 304 Not Modified

    try:
        db.session.commit()
        current_app.logger.info(
            f"Company '{company.name}' (ID: {company.id}) updated by superadmin {current_user.username}.")
        return jsonify({
            "id": company.id,
            "name": company.name,
            "owner_user_id": company.owner_user_id
        }), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating company {company_id}: {e}", exc_info=True)
        return jsonify({"error": "Failed to update company."}), 500


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
    role = data.get('role', 'user')
    company_id_str = data.get('company_id')  # Παίρνουμε το company_id ως string
    is_active = data.get('is_active', True)

    if not username or not email or not password:
        return jsonify({"error": "Username, email, and password are required"}), 400
    if role not in ['user', 'company_admin', 'superadmin']:
        return jsonify({"error": "Invalid role specified"}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username already exists"}), 409
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email address already registered"}), 409

    target_company_id_int = None
    target_company = None

    if role != 'superadmin':
        if not company_id_str:  # Αν είναι κενό string ή None
            return jsonify({"error": "Company ID is required for roles 'user' and 'company_admin'"}), 400
        try:
            target_company_id_int = int(company_id_str)  # Μετατροπή σε integer
        except ValueError:
            return jsonify({"error": "Invalid Company ID format."}), 400

        target_company = Company.query.get(target_company_id_int)
        if not target_company:
            return jsonify({"error": f"Company with ID {target_company_id_int} not found"}), 404

    # Αν ο ρόλος είναι superadmin, το company_id πρέπει να είναι None
    final_company_id_for_user = target_company.id if target_company and role != 'superadmin' else None

    try:
        new_user = User(
            username=username,
            email=email,
            role=role,
            is_active=is_active,
            company_id=final_company_id_for_user,  # Χρησιμοποιούμε το τελικό ID
            # Το confirmed_on θα πρέπει να ορίζεται όταν ο χρήστης επιβεβαιώνει το email του,
            # ή αν τον ενεργοποιούμε χειροκίνητα.
            # Για τώρα, αν is_active=True, το βάζουμε.
            confirmed_on=datetime.now(timezone.utc) if is_active else None
            # Τα enable_email_interview_reminders και interview_reminder_lead_time_minutes
            # θα πάρουν τις default τιμές από το User model.
        )
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        current_app.logger.info(
            f"User '{new_user.username}' (Role: {new_user.role}, Company ID: {new_user.company_id}) created by superadmin {current_user.username}.")
        return jsonify(new_user.to_dict(include_company_info=True)), 201  # Επιστρέφουμε το user dict
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
    company_id_filter_str = request.args.get('company_id')  # Παίρνουμε ως string

    query = User.query
    if role_filter:
        query = query.filter(User.role == role_filter)

    if company_id_filter_str:  # Αν δόθηκε company_id
        try:
            company_id_val = int(company_id_filter_str)
            query = query.filter(User.company_id == company_id_val)
        except ValueError:
            # Αν το company_id δεν είναι έγκυρος αριθμός, αγνόησέ το ή επέστρεψε σφάλμα
            current_app.logger.warning(f"Invalid company_id filter value: {company_id_filter_str}")
            # return jsonify({"error": "Invalid company_id filter"}), 400

    users_pagination = query.order_by(User.username).paginate(page=page, per_page=per_page, error_out=False)

    users_list = [user.to_dict(include_company_info=True) for user in users_pagination.items]

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

    updated_fields_count = 0  # Μετρητής για να δούμε αν έγινε κάποια αλλαγή

    if 'username' in data and data['username'] != user_to_update.username:
        if User.query.filter(User.username == data['username'], User.id != user_id).first():
            return jsonify({"error": "Username already taken"}), 409
        user_to_update.username = data['username']
        updated_fields_count += 1

    if 'email' in data and data['email'] != user_to_update.email:
        if User.query.filter(User.email == data['email'], User.id != user_id).first():
            return jsonify({"error": "Email already registered"}), 409
        user_to_update.email = data['email']
        updated_fields_count += 1

    if 'role' in data and data['role'] != user_to_update.role:
        if data['role'] not in ['user', 'company_admin', 'superadmin']:
            return jsonify({"error": "Invalid role"}), 400
        user_to_update.role = data['role']
        if user_to_update.role == 'superadmin':  # Superadmin δεν πρέπει να έχει company_id
            user_to_update.company_id = None
        updated_fields_count += 1

    # Χειρισμός company_id: μπορεί να είναι string, int, ή null/κενό από το frontend
    if 'company_id' in data:  # Έλεγχος αν το κλειδί υπάρχει
        new_company_id_val = data.get('company_id')

        # Μετατροπή σε integer αν είναι string αριθμός, ή None αν είναι κενό/null
        processed_company_id = None
        if new_company_id_val is not None and str(new_company_id_val).strip() != "":
            try:
                processed_company_id = int(new_company_id_val)
                if processed_company_id == 0:  # Αν ο χρήστης στείλει 0, το θεωρούμε ως "χωρίς εταιρεία"
                    processed_company_id = None
            except ValueError:
                return jsonify({"error": "Invalid company_id format."}), 400

        if user_to_update.role == 'superadmin' and processed_company_id is not None:
            return jsonify({"error": "Superadmin cannot be assigned to a company."}), 400

        if processed_company_id is not None:  # Αν μετά την επεξεργασία δεν είναι None
            company = Company.query.get(processed_company_id)
            if not company:
                return jsonify({"error": f"Target company with ID {processed_company_id} not found"}), 404

        if user_to_update.company_id != processed_company_id:
            user_to_update.company_id = processed_company_id
            updated_fields_count += 1

    if 'is_active' in data and data['is_active'] != user_to_update.is_active:
        user_to_update.is_active = bool(data['is_active'])
        if user_to_update.is_active and not user_to_update.confirmed_on:
            user_to_update.confirmed_on = datetime.now(timezone.utc)
        updated_fields_count += 1

    if 'password' in data and data['password']:
        user_to_update.set_password(data['password'])
        updated_fields_count += 1

    # Προσθήκη ενημέρωσης για τις ρυθμίσεις υπενθυμίσεων του χρήστη
    if 'enable_email_interview_reminders' in data and data[
        'enable_email_interview_reminders'] != user_to_update.enable_email_interview_reminders:
        user_to_update.enable_email_interview_reminders = bool(data['enable_email_interview_reminders'])
        updated_fields_count += 1

    if 'interview_reminder_lead_time_minutes' in data:
        try:
            lead_time = int(data['interview_reminder_lead_time_minutes'])
            if lead_time < 5 or lead_time > 2880:  # Παράδειγμα ορίων
                return jsonify({"error": "Interview reminder lead time must be between 5 and 2880 minutes."}), 400
            if lead_time != user_to_update.interview_reminder_lead_time_minutes:
                user_to_update.interview_reminder_lead_time_minutes = lead_time
                updated_fields_count += 1
        except ValueError:
            return jsonify({"error": "Invalid format for interview_reminder_lead_time_minutes."}), 400

    if updated_fields_count == 0:
        return jsonify({"message": "No updatable fields provided or values are the same."}), 304

    try:
        db.session.commit()
        current_app.logger.info(f"User ID {user_id} updated by superadmin {current_user.username}.")
        return jsonify(
            {"message": "User updated successfully", "user": user_to_update.to_dict(include_company_info=True)}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating user {user_id} by superadmin: {e}", exc_info=True)
        return jsonify({"error": "Failed to update user"}), 500