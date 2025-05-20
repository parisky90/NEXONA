from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from app.models import User, Company, Interview, Candidate, InterviewStatus, Position, Branch  # <<< ΠΡΟΣΘΗΚΗ Branch
from sqlalchemy import or_  # or_ δεν χρησιμοποιείται εδώ, μπορεί να αφαιρεθεί αν δεν χρειάζεται

company_admin_bp = Blueprint('company_admin_api_bp', __name__, url_prefix='/api/v1/company')


def check_company_admin_or_superadmin_access(company_id_to_check=None):
    # ... (η συνάρτηση παραμένει ίδια με την τελευταία πλήρη έκδοση) ...
    target_company_id_for_query = None
    if current_user.role == 'superadmin':
        if company_id_to_check is not None:
            company_obj = db.session.get(Company, company_id_to_check)
            if not company_obj:
                current_app.logger.warning(
                    f"Superadmin {current_user.id} tried to access non-existent company {company_id_to_check}.")
                return jsonify({'error': 'Target company not found'}), 404
            target_company_id_for_query = company_id_to_check
            current_app.logger.debug(f"Superadmin {current_user.id} accessing company {target_company_id_for_query}.")
        else:
            current_app.logger.debug(f"Superadmin {current_user.id} accessing a route without specific company_id.")
            pass
    elif current_user.role == 'company_admin':
        if not current_user.company_id:
            current_app.logger.error(f"Company admin {current_user.id} has no company_id associated.")
            return jsonify({'error': 'User is not associated with any company.'}), 403

        if company_id_to_check is not None and current_user.company_id != company_id_to_check:
            current_app.logger.warning(
                f"Company admin {current_user.id} (company {current_user.company_id}) "
                f"attempted to access resources of company {company_id_to_check}."
            )
            return jsonify({'error': 'Forbidden: You do not have permission to access this company\'s resources.'}), 403
        target_company_id_for_query = current_user.company_id
        current_app.logger.debug(
            f"Company admin {current_user.id} accessing their company {target_company_id_for_query}.")
    else:
        current_app.logger.warning(
            f"User {current_user.id} with role {current_user.role} attempted to access company admin protected route.")
        return jsonify({'error': 'Forbidden: Insufficient permissions.'}), 403
    return target_company_id_for_query


# --- User Management Endpoints (παραμένουν ίδια) ---
@company_admin_bp.route('/users', methods=['GET'])
@login_required
def get_company_users_list():
    # ... (ίδιο με πριν) ...
    company_id_for_query = None
    if current_user.role == 'superadmin':
        company_id_from_param = request.args.get('company_id', type=int)
        if not company_id_from_param:
            return jsonify({'error': 'Superadmin must specify a company_id to view company users via this route.'}), 400
        access_check_result = check_company_admin_or_superadmin_access(company_id_from_param)
        if isinstance(access_check_result, tuple):
            return access_check_result
        company_id_for_query = access_check_result
    elif current_user.role == 'company_admin':
        access_check_result = check_company_admin_or_superadmin_access()
        if isinstance(access_check_result, tuple):
            return access_check_result
        company_id_for_query = access_check_result
    else:
        return jsonify({'error': 'Forbidden: Insufficient permissions.'}), 403

    if not company_id_for_query:
        current_app.logger.error("get_company_users_list: Could not determine company_id_for_query.")
        return jsonify({'error': 'Company ID could not be determined.'}), 400

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    users_query = User.query.filter_by(company_id=company_id_for_query)
    pagination = users_query.paginate(page=page, per_page=per_page, error_out=False)
    users_data = [user.to_dict() for user in pagination.items]

    return jsonify({
        'users': users_data,
        'total_users': pagination.total,
        'total_pages': pagination.pages,
        'current_page': pagination.page
    }), 200


@company_admin_bp.route('/users', methods=['POST'])
@login_required
def create_company_user_by_admin():
    # ... (ίδιο με πριν) ...
    if current_user.role != 'company_admin':
        return jsonify({'error': 'Only company admins can create users for their company via this route.'}), 403

    company_id_for_creation = current_user.company_id
    if not company_id_for_creation:
        current_app.logger.error(f"Company admin {current_user.id} has no company_id for user creation.")
        return jsonify({'error': 'User is not associated with any company.'}), 403

    data = request.get_json()
    if not data: return jsonify({'error': 'Request must be JSON'}), 400

    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    if not all([username, email, password]):
        return jsonify({'error': 'Username, email, and password are required.'}), 400

    if User.query.filter(or_(User.username == username.strip(), User.email == email.lower().strip())).first():
        return jsonify({'error': 'User with this username or email already exists in the system.'}), 409

    new_user = User(
        username=username.strip(),
        email=email.strip().lower(),
        role='user',
        company_id=company_id_for_creation,
        is_active=True
    )
    new_user.set_password(password)
    db.session.add(new_user)
    try:
        db.session.commit()
        current_app.logger.info(
            f"User '{new_user.username}' created for company {company_id_for_creation} by company admin {current_user.username}.")
        return jsonify(new_user.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating user for company {company_id_for_creation}: {e}", exc_info=True)
        return jsonify({'error': f'Could not create user: {str(e)}'}), 500


@company_admin_bp.route('/users/<int:user_id_to_manage>/status', methods=['PUT'])
@login_required
def toggle_user_status_in_company(user_id_to_manage):
    # ... (ίδιο με πριν) ...
    if current_user.role != 'company_admin':
        return jsonify({'error': 'Only company admins can manage user status via this route.'}), 403

    company_id_of_admin = current_user.company_id
    if not company_id_of_admin:
        return jsonify({'error': 'User is not associated with any company.'}), 403

    user_to_manage = db.session.get(User, user_id_to_manage)
    if not user_to_manage:
        return jsonify({'error': 'User not found.'}), 404
    if user_to_manage.company_id != company_id_of_admin:
        return jsonify({'error': 'User does not belong to your company.'}), 403
    if user_to_manage.id == current_user.id:
        return jsonify({'error': 'You cannot change your own active status.'}), 400

    company_owner = db.session.get(Company, company_id_of_admin)
    if company_owner and company_owner.owner_user_id == user_to_manage.id:
        current_app.logger.info(
            f"Company admin {current_user.id} is attempting to change status of company owner {user_to_manage.id}.")

    data = request.get_json()
    if 'is_active' not in data or not isinstance(data['is_active'], bool):
        return jsonify({'error': 'Invalid payload. "is_active" (boolean) is required.'}), 400

    user_to_manage.is_active = data['is_active']
    try:
        db.session.commit()
        current_app.logger.info(
            f"User {user_to_manage.username} (ID: {user_to_manage.id}) active status set to {user_to_manage.is_active} by company admin {current_user.username}.")
        return jsonify(user_to_manage.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error toggling status for user {user_id_to_manage}: {e}", exc_info=True)
        return jsonify({'error': f'Could not update user status: {str(e)}'}), 500


@company_admin_bp.route('/users/<int:user_id_to_delete>', methods=['DELETE'])
@login_required
def delete_company_user_by_admin(user_id_to_delete):
    # ... (ίδιο με πριν) ...
    if current_user.role != 'company_admin':
        return jsonify({'error': 'Only company admins can delete users for their company via this route.'}), 403

    company_id_of_admin = current_user.company_id
    if not company_id_of_admin:
        current_app.logger.error(f"Company admin {current_user.id} attempting delete user but has no company_id.")
        return jsonify({'error': 'User is not associated with any company.'}), 403

    user_to_delete = db.session.get(User, user_id_to_delete)
    if not user_to_delete:
        return jsonify({'error': 'User not found.'}), 404

    if user_to_delete.company_id != company_id_of_admin:
        current_app.logger.warning(
            f"Company admin {current_user.id} (company {company_id_of_admin}) "
            f"attempted to delete user {user_id_to_delete} (company {user_to_delete.company_id})."
        )
        return jsonify({'error': 'User does not belong to your company.'}), 403

    if user_to_delete.id == current_user.id:
        return jsonify({'error': 'You cannot delete yourself.'}), 400

    company = db.session.get(Company, company_id_of_admin)
    if company and company.owner_user_id == user_to_delete.id:
        return jsonify(
            {'error': 'You cannot delete the owner of the company. Please change the company owner first.'}), 403

    username_for_log = user_to_delete.username
    try:
        db.session.delete(user_to_delete)
        db.session.commit()
        current_app.logger.info(
            f"User '{username_for_log}' (ID: {user_id_to_delete}) from company {company_id_of_admin} "
            f"deleted by company admin {current_user.username} (ID: {current_user.id})."
        )
        return jsonify({'message': f"User '{username_for_log}' deleted successfully."}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting user {user_id_to_delete} by company admin {current_user.id}: {e}",
                                 exc_info=True)
        return jsonify({'error': f'Could not delete user: {str(e)}'}), 500


# --- Interview & Position Endpoints (παραμένουν ίδια) ---
@company_admin_bp.route('/interviews', methods=['GET'])
@login_required
def get_company_interviews_list():
    # ... (ίδιο με την τελευταία πλήρη έκδοση που σου έστειλα) ...
    company_id_for_query = None
    if current_user.role == 'superadmin':
        company_id_param = request.args.get('company_id', type=int)
        if not company_id_param:
            current_app.logger.warning(
                f"Superadmin {current_user.id} attempted to get company interviews without specifying company_id.")
            return jsonify({'error': 'Superadmin must specify a company_id.'}), 400
        company_obj = db.session.get(Company, company_id_param)
        if not company_obj:
            return jsonify({'error': f'Company with ID {company_id_param} not found.'}), 404
        company_id_for_query = company_id_param
    elif current_user.role == 'company_admin':
        if not current_user.company_id:
            current_app.logger.error(f"Company admin {current_user.id} has no company_id.")
            return jsonify({'error': 'User not associated with a company.'}), 403
        company_id_for_query = current_user.company_id
    else:
        return jsonify({'error': 'Forbidden: Insufficient permissions.'}), 403

    current_app.logger.info(f"Fetching interviews for company_id: {company_id_for_query} by user {current_user.id}")

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 15, type=int)
    status_filter = request.args.get('status', None, type=str)

    query = Interview.query.filter_by(company_id=company_id_for_query)

    if status_filter:
        try:
            status_enum = InterviewStatus[status_filter.upper()]
            query = query.filter(Interview.status == status_enum)
        except KeyError:
            return jsonify({'error': f"Invalid interview status filter: {status_filter}"}), 400

    query = query.order_by(Interview.scheduled_start_time.desc().nullslast(), Interview.created_at.desc())

    try:
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        interviews_data = [
            interview.to_dict(
                include_candidate_info=True,
                include_position_info=True,
                include_recruiter_info=True,
                include_sensitive=False,
                include_slots=False
            ) for interview in pagination.items
        ]
        current_app.logger.info(
            f"Successfully fetched {len(interviews_data)} interviews for company {company_id_for_query}.")
    except Exception as e:
        current_app.logger.error(f"Error during interview pagination for company {company_id_for_query}: {e}",
                                 exc_info=True)
        return jsonify({'error': 'Error fetching interviews list.'}), 500

    return jsonify({
        'interviews': interviews_data,
        'total_interviews': pagination.total,
        'total_pages': pagination.pages,
        'current_page': pagination.page
    }), 200


@company_admin_bp.route('/<int:company_id_from_path>/positions', methods=['GET'])
@login_required
def get_company_positions_list(company_id_from_path):
    # ... (ίδιο με την τελευταία πλήρη έκδοση που σου έστειλα) ...
    target_company = db.session.get(Company, company_id_from_path)
    if not target_company:
        current_app.logger.warning(f"Attempt to get positions for non-existent company ID: {company_id_from_path}")
        return jsonify({'error': 'Company not found'}), 404

    if not (current_user.role == 'superadmin' or (
            current_user.role == 'company_admin' and current_user.company_id == company_id_from_path)):
        current_app.logger.warning(
            f"User {current_user.id} (Role: {current_user.role}, Company: {current_user.company_id}) "
            f"attempted to access positions of company {company_id_from_path} without permission."
        )
        return jsonify({'error': 'Forbidden: You do not have permission to view positions for this company.'}), 403

    status_filter = request.args.get('status', None, type=str)
    query = Position.query.filter_by(company_id=company_id_from_path)

    if status_filter:
        query = query.filter(Position.status.ilike(f"%{status_filter}%"))

    positions = query.order_by(Position.position_name).all()
    positions_data = [p.to_dict() for p in positions]

    current_app.logger.info(
        f"Fetched {len(positions_data)} positions for company {company_id_from_path} (User: {current_user.id}). Filter: status='{status_filter}'")
    return jsonify({'positions': positions_data, 'total_positions': len(positions_data)}), 200


# --- ΝΕΑ ENDPOINTS ΓΙΑ BRANCHES ---
@company_admin_bp.route('/branches', methods=['POST'])
@login_required
def create_branch():
    if current_user.role != 'company_admin':
        return jsonify({'error': 'Only company admins can create branches.'}), 403

    company_id = current_user.company_id
    if not company_id:
        return jsonify({'error': 'User not associated with a company.'}), 400

    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'error': 'Branch name is required.'}), 400

    name = data.get('name').strip()
    city = data.get('city', '').strip()
    address = data.get('address', '').strip()

    if not name:
        return jsonify({'error': 'Branch name cannot be empty.'}), 400

    # Έλεγχος αν υπάρχει ήδη κατάστημα με το ίδιο όνομα στην ίδια εταιρεία
    existing_branch = Branch.query.filter_by(name=name, company_id=company_id).first()
    if existing_branch:
        return jsonify({'error': f"A branch named '{name}' already exists for this company."}), 409

    new_branch = Branch(
        name=name,
        city=city if city else None,
        address=address if address else None,
        company_id=company_id
    )
    db.session.add(new_branch)
    try:
        db.session.commit()
        current_app.logger.info(
            f"Branch '{new_branch.name}' (ID: {new_branch.id}) created for company {company_id} by {current_user.username}.")
        return jsonify(new_branch.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating branch for company {company_id}: {e}", exc_info=True)
        return jsonify({'error': f'Could not create branch: {str(e)}'}), 500


@company_admin_bp.route('/branches', methods=['GET'])
@login_required
def get_branches_list():
    # Επιστρέφει τα branches για την εταιρεία του συνδεδεμένου company_admin
    # ή για μια συγκεκριμένη εταιρεία αν ο χρήστης είναι superadmin και παρέχει company_id
    company_id_for_query = None
    if current_user.role == 'superadmin':
        company_id_param = request.args.get('company_id', type=int)
        if not company_id_param:
            return jsonify({'error': 'Superadmin must specify a company_id to view branches.'}), 400
        if not db.session.get(Company, company_id_param):
            return jsonify({'error': f'Company with ID {company_id_param} not found.'}), 404
        company_id_for_query = company_id_param
    elif current_user.role == 'company_admin':
        if not current_user.company_id:
            return jsonify({'error': 'User not associated with a company.'}), 403
        company_id_for_query = current_user.company_id
    else:
        return jsonify({'error': 'Forbidden: Insufficient permissions.'}), 403

    branches = Branch.query.filter_by(company_id=company_id_for_query).order_by(Branch.name).all()
    return jsonify([branch.to_dict() for branch in branches]), 200


@company_admin_bp.route('/branches/<int:branch_id>', methods=['PUT'])
@login_required
def update_branch(branch_id):
    if current_user.role != 'company_admin':
        return jsonify({'error': 'Only company admins can update branches.'}), 403

    company_id = current_user.company_id
    if not company_id:
        return jsonify({'error': 'User not associated with a company.'}), 400

    branch = db.session.get(Branch, branch_id)
    if not branch or branch.company_id != company_id:
        return jsonify({'error': 'Branch not found or you do not have permission to edit it.'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided for update.'}), 400

    updated = False
    if 'name' in data:
        new_name = data['name'].strip()
        if not new_name:
            return jsonify({'error': 'Branch name cannot be empty.'}), 400
        if new_name != branch.name:
            # Έλεγχος αν το νέο όνομα υπάρχει ήδη για την ίδια εταιρεία (εκτός από το τρέχον branch)
            existing_branch = Branch.query.filter(
                Branch.name == new_name,
                Branch.company_id == company_id,
                Branch.id != branch_id
            ).first()
            if existing_branch:
                return jsonify({'error': f"A branch named '{new_name}' already exists for this company."}), 409
            branch.name = new_name
            updated = True

    if 'city' in data:
        new_city = data['city'].strip()
        if branch.city != (new_city if new_city else None):
            branch.city = new_city if new_city else None
            updated = True

    if 'address' in data:
        new_address = data['address'].strip()
        if branch.address != (new_address if new_address else None):
            branch.address = new_address if new_address else None
            updated = True

    if not updated:
        return jsonify({'message': 'No changes detected.'}), 200  # Ή 304 Not Modified

    branch.updated_at = datetime.now(dt_timezone.utc)
    try:
        db.session.commit()
        current_app.logger.info(f"Branch '{branch.name}' (ID: {branch.id}) updated by {current_user.username}.")
        return jsonify(branch.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating branch {branch_id}: {e}", exc_info=True)
        return jsonify({'error': f'Could not update branch: {str(e)}'}), 500


@company_admin_bp.route('/branches/<int:branch_id>', methods=['DELETE'])
@login_required
def delete_branch(branch_id):
    if current_user.role != 'company_admin':
        return jsonify({'error': 'Only company admins can delete branches.'}), 403

    company_id = current_user.company_id
    if not company_id:
        return jsonify({'error': 'User not associated with a company.'}), 400

    branch = db.session.get(Branch, branch_id)
    if not branch or branch.company_id != company_id:
        return jsonify({'error': 'Branch not found or you do not have permission to delete it.'}), 404

    # Έλεγχος αν το κατάστημα χρησιμοποιείται από υποψηφίους.
    # Αν ναι, ίσως να μην θέλουμε να επιτρέψουμε τη διαγραφή ή να κάνουμε unassign.
    # Για απλότητα τώρα, επιτρέπουμε τη διαγραφή. Το association table θα χειριστεί τις συνδέσεις.
    if branch.candidates.first():  # Ελέγχει αν υπάρχει τουλάχιστον ένας υποψήφιος συνδεδεμένος
        current_app.logger.warning(
            f"Attempt to delete branch {branch_id} which has associated candidates. Allowing for now.")
        # Θα μπορούσες να επιστρέψεις σφάλμα εδώ:
        # return jsonify({'error': 'Cannot delete branch. It is currently associated with one or more candidates. Please reassign them first.'}), 409

    branch_name_for_log = branch.name
    try:
        # Η διαγραφή του branch θα αφαιρέσει τις εγγραφές και από τον association table λόγω του ondelete='CASCADE'
        # που ορίσαμε στα ForeignKeys του association table (αν το ορίσαμε έτσι).
        # Στην περίπτωσή μας, το candidate_branch_association έχει ondelete='CASCADE' στα FKs του, οπότε θα δουλέψει.
        db.session.delete(branch)
        db.session.commit()
        current_app.logger.info(f"Branch '{branch_name_for_log}' (ID: {branch_id}) deleted by {current_user.username}.")
        return jsonify({'message': f"Branch '{branch_name_for_log}' deleted successfully."}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting branch {branch_id}: {e}", exc_info=True)
        return jsonify({'error': f'Could not delete branch: {str(e)}'}), 500