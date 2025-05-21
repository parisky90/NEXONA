# backend/app/api/routes_company_admin.py
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from app.models import User, Company, Interview, Candidate, InterviewStatus, Position, Branch
from sqlalchemy import or_, exc # or_ χρησιμοποιείται στο create_company_user_by_admin, exc for IntegrityError
from datetime import datetime, timezone as dt_timezone, timedelta  # Προσθήκη timedelta

company_admin_bp = Blueprint('company_admin_api_bp', __name__, url_prefix='/api/v1/company')


def check_company_admin_or_superadmin_access(company_id_to_check=None):
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
            # If superadmin and no company_id_to_check is given for a specific resource,
            # it depends on the route whether this is an error or means "all companies".
            # For company-scoped resources (users, branches, positions of *A* company),
            # the superadmin should provide a company_id.
            # This function primarily returns the target_company_id for the query.
            # If it's None and the route expects one (e.g. for creating a branch for a company),
            # the route itself should handle the error if superadmin doesn't provide it.
            current_app.logger.debug(
                f"Superadmin {current_user.id} accessing a company-scoped route without specific company_id context (company_id_to_check was None). Target company ID for query will be None.")
            # Let the route decide if company_id is mandatory for superadmin when company_id_to_check is None
            # For GET /company/positions (list all), SA might need to provide company_id or get an error.
            # For POST /company/positions (create), SA must provide company_id.
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


# --- User Management Endpoints ---
@company_admin_bp.route('/users', methods=['GET'])
@login_required
def get_company_users_list():
    company_id_for_query = None
    if current_user.role == 'superadmin':
        company_id_from_param = request.args.get('company_id', type=int)
        if not company_id_from_param:
            return jsonify({'error': 'Superadmin must specify a company_id to view company users via this route.'}), 400
        access_check_result = check_company_admin_or_superadmin_access(company_id_from_param)
        if isinstance(access_check_result, tuple):  # Indicates an error response
            return access_check_result
        company_id_for_query = access_check_result
    elif current_user.role == 'company_admin':
        access_check_result = check_company_admin_or_superadmin_access()
        if isinstance(access_check_result, tuple):
            return access_check_result
        company_id_for_query = access_check_result
    else:
        return jsonify({'error': 'Forbidden: Insufficient permissions.'}), 403

    if not company_id_for_query: # Should be caught above for SA, CA will always have one or error out
        current_app.logger.error("get_company_users_list: Could not determine company_id_for_query.")
        return jsonify({'error': 'Company ID could not be determined for user query.'}), 400

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
    # This route is specifically for company_admin to create users for THEIR OWN company.
    # Superadmin uses a different route (/api/v1/admin/users)
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
    user_role_from_payload = data.get('role', 'user').lower()
    allowed_roles_for_creation = ['user', 'recruiter', 'hiring_manager']

    if user_role_from_payload not in allowed_roles_for_creation:
        return jsonify(
            {'error': f'Invalid role specified. Allowed roles: {", ".join(allowed_roles_for_creation)}'}), 400

    if not all([username, email, password]):
        return jsonify({'error': 'Username, email, and password are required.'}), 400

    if User.query.filter(or_(User.username == username.strip(), User.email == email.lower().strip())).first():
        return jsonify({'error': 'User with this username or email already exists in the system.'}), 409

    new_user = User(
        username=username.strip(),
        email=email.strip().lower(),
        role=user_role_from_payload,
        company_id=company_id_for_creation,
        is_active=True, # New users created by admin are active by default
        confirmed_on=datetime.now(dt_timezone.utc) # And confirmed
    )
    new_user.set_password(password)
    db.session.add(new_user)
    try:
        db.session.commit()
        current_app.logger.info(
            f"User '{new_user.username}' (Role: {new_user.role}) created for company {company_id_for_creation} by company admin {current_user.username}.")
        return jsonify(new_user.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating user for company {company_id_for_creation}: {e}", exc_info=True)
        return jsonify({'error': f'Could not create user: {str(e)}'}), 500


@company_admin_bp.route('/users/<int:user_id_to_manage>/status', methods=['PUT'])
@login_required
def toggle_user_status_in_company(user_id_to_manage):
    # This route is specifically for company_admin to manage users in THEIR OWN company.
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

    company_obj = db.session.get(Company, company_id_of_admin)
    if company_obj and company_obj.owner_user_id == user_to_manage.id:
        # Potentially disallow deactivating the company owner, or add more checks
        # For now, if 'is_active' is False, we prevent it.
        data = request.get_json()
        if 'is_active' in data and data['is_active'] is False:
            return jsonify({'error': 'The owner of the company cannot be deactivated.'}), 403


    data = request.get_json()
    if 'is_active' not in data or not isinstance(data['is_active'], bool):
        return jsonify({'error': 'Invalid payload. "is_active" (boolean) is required.'}), 400

    user_to_manage.is_active = data['is_active']
    if user_to_manage.is_active and not user_to_manage.confirmed_on: # Confirm if activating and not confirmed
        user_to_manage.confirmed_on = datetime.now(dt_timezone.utc)
    elif not user_to_manage.is_active and company_obj and company_obj.owner_user_id == user_to_manage.id :
        # This case should be caught above, but as a safeguard
        return jsonify({'error': 'The owner of the company cannot be deactivated.'}), 403


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


# --- Interview Endpoints (largely unchanged, but permissions checked) ---
@company_admin_bp.route('/interviews', methods=['GET'])
@login_required
def get_company_interviews_list_or_calendar():
    # This endpoint is used by both CompanyAdmin (for their company)
    # and Superadmin (if they provide a company_id)
    company_id_for_query = None

    if current_user.role == 'superadmin':
        company_id_param_str = request.args.get('company_id')
        if not company_id_param_str:
            return jsonify({'error': 'Superadmin must specify a company_id to view interviews.'}), 400
        try:
            company_id_for_query = int(company_id_param_str)
            if not db.session.get(Company, company_id_for_query):
                return jsonify({'error': f'Company with ID {company_id_for_query} not found.'}), 404
        except ValueError:
            return jsonify({'error': f"Invalid company_id format: {company_id_param_str}"}), 400
    elif current_user.role == 'company_admin':
        if not current_user.company_id:
            return jsonify({'error': 'User not associated with a company.'}), 403
        company_id_for_query = current_user.company_id
    else: # Other roles (e.g. 'user', 'recruiter') shouldn't access all company interviews this way
        return jsonify({'error': 'Forbidden: Insufficient permissions for this resource.'}), 403

    current_app.logger.info(f"Fetching interviews for company_id: {company_id_for_query} by user {current_user.id} (Role: {current_user.role})")

    start_str = request.args.get('start')
    end_str = request.args.get('end')

    if start_str and end_str:
        try:
            start_date = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
            end_date = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
        except ValueError:
            return jsonify({'message': 'Invalid date format for start/end parameters.'}), 400

        query = Interview.query.filter(
            Interview.company_id == company_id_for_query,
            Interview.status == InterviewStatus.SCHEDULED,
            Interview.scheduled_start_time != None,
            Interview.scheduled_start_time < end_date,
            Interview.scheduled_end_time > start_date
        )
        interviews = query.all()
        calendar_events = []
        for interview in interviews:
            if not interview.candidate or not interview.scheduled_start_time or not interview.scheduled_end_time:
                continue
            title = f"Interview: {interview.candidate.get_full_name()}"
            if interview.position:
                title += f" for {interview.position.position_name}"
            event_data = {
                'id': interview.id,
                'title': title,
                'start': interview.scheduled_start_time.isoformat(),
                'end': interview.scheduled_end_time.isoformat(),
                'allDay': False,
                'resource': {
                    'candidate_id': str(interview.candidate_id),
                    'candidate_name': interview.candidate.get_full_name(),
                    'position_id': interview.position_id,
                    'position_name': interview.position.position_name if interview.position else "N/A",
                    'interview_type': interview.interview_type,
                    'location': interview.location,
                    'status': interview.status.value if interview.status else None,
                }
            }
            calendar_events.append(event_data)
        return jsonify(calendar_events), 200
    else:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 15, type=int)
        status_filter_str = request.args.get('status', None, type=str)
        query = Interview.query.filter_by(company_id=company_id_for_query)
        if status_filter_str:
            try:
                status_enum_value = status_filter_str.upper()
                if status_enum_value not in InterviewStatus.__members__: raise KeyError
                status_enum = InterviewStatus[status_enum_value]
                query = query.filter(Interview.status == status_enum)
            except KeyError:
                valid_statuses = [s.name for s in InterviewStatus]
                return jsonify({'error': f"Invalid status filter. Valid: {', '.join(valid_statuses)}"}), 400
        query = query.order_by(Interview.scheduled_start_time.desc().nullslast(), Interview.created_at.desc())
        try:
            pagination = query.paginate(page=page, per_page=per_page, error_out=False)
            interviews_data = [
                interview.to_dict(
                    include_candidate_info=True, include_position_info=True,
                    include_recruiter_info=True, include_sensitive=False, include_slots=True
                ) for interview in pagination.items
            ]
        except Exception as e:
            current_app.logger.error(f"Error paginating interviews: {e}", exc_info=True)
            return jsonify({'error': 'Error fetching interviews list.'}), 500
        return jsonify({
            'interviews': interviews_data, 'total_interviews': pagination.total,
            'total_pages': pagination.pages, 'current_page': pagination.page
        }), 200

# --- BRANCHES ENDPOINTS (Existing, verified permissions) ---
@company_admin_bp.route('/branches', methods=['POST'])
@login_required
def create_branch():
    # Only company_admin of their own company
    if current_user.role != 'company_admin':
        return jsonify({'error': 'Only company admins can create branches for their company.'}), 403
    company_id = current_user.company_id
    if not company_id:
        return jsonify({'error': 'User not associated with a company.'}), 400

    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'error': 'Branch name is required.'}), 400
    name = data.get('name').strip()
    city = data.get('city', '').strip() if data.get('city') else None
    address = data.get('address', '').strip() if data.get('address') else None
    if not name: return jsonify({'error': 'Branch name cannot be empty.'}), 400

    existing_branch = Branch.query.filter_by(name=name, company_id=company_id).first()
    if existing_branch:
        return jsonify({'error': f"A branch named '{name}' already exists for this company."}), 409
    new_branch = Branch(name=name, city=city, address=address, company_id=company_id)
    db.session.add(new_branch)
    try:
        db.session.commit()
        current_app.logger.info(f"Branch '{new_branch.name}' created for company {company_id} by {current_user.username}.")
        return jsonify(new_branch.to_dict()), 201
    except exc.IntegrityError: # Catch specific unique constraint violation if missed by above check
        db.session.rollback()
        current_app.logger.warning(f"IntegrityError creating branch '{name}' for company {company_id} (likely duplicate).")
        return jsonify({'error': f"A branch named '{name}' already exists (Integrity constraint)."}), 409
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating branch for company {company_id}: {e}", exc_info=True)
        return jsonify({'error': f'Could not create branch: {str(e)}'}), 500

@company_admin_bp.route('/branches', methods=['GET'])
@login_required
def get_branches_list():
    # CompanyAdmin gets their own branches. Superadmin must specify company_id.
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
    if not company_id: return jsonify({'error': 'User not associated with a company.'}), 400

    branch = db.session.get(Branch, branch_id)
    if not branch or branch.company_id != company_id:
        return jsonify({'error': 'Branch not found or you do not have permission to edit it.'}), 404

    data = request.get_json()
    if not data: return jsonify({'error': 'No data provided for update.'}), 400
    updated_fields_count = 0
    if 'name' in data:
        new_name = data['name'].strip()
        if not new_name: return jsonify({'error': 'Branch name cannot be empty.'}), 400
        if new_name != branch.name:
            existing_branch = Branch.query.filter(Branch.name == new_name, Branch.company_id == company_id, Branch.id != branch_id).first()
            if existing_branch: return jsonify({'error': f"A branch named '{new_name}' already exists."}), 409
            branch.name = new_name
            updated_fields_count += 1
    if 'city' in data:
        new_city = data['city'].strip() if data['city'] is not None else None
        if branch.city != new_city: branch.city = new_city; updated_fields_count +=1
    if 'address' in data:
        new_address = data['address'].strip() if data['address'] is not None else None
        if branch.address != new_address: branch.address = new_address; updated_fields_count +=1
    if updated_fields_count == 0: return jsonify({'message': 'No changes detected.'}), 200
    branch.updated_at = datetime.now(dt_timezone.utc)
    try:
        db.session.commit()
        current_app.logger.info(f"Branch ID {branch.id} updated by {current_user.username}.")
        return jsonify(branch.to_dict()), 200
    except exc.IntegrityError:
        db.session.rollback()
        return jsonify({'error': f"A branch with the new name likely already exists (Integrity constraint)."}), 409
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
    if not company_id: return jsonify({'error': 'User not associated with a company.'}), 400

    branch = db.session.get(Branch, branch_id)
    if not branch or branch.company_id != company_id:
        return jsonify({'error': 'Branch not found or you do not have permission to delete it.'}), 404
    if branch.candidates.first():
        return jsonify({'error': 'Cannot delete branch. It has associated candidates.'}), 409
    branch_name_for_log = branch.name
    try:
        db.session.delete(branch)
        db.session.commit()
        current_app.logger.info(f"Branch '{branch_name_for_log}' deleted by {current_user.username}.")
        return jsonify({'message': f"Branch '{branch_name_for_log}' deleted successfully."}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting branch {branch_id}: {e}", exc_info=True)
        return jsonify({'error': f'Could not delete branch: {str(e)}'}), 500


# --- POSITION ENDPOINTS (ΝΕΑ) ---
@company_admin_bp.route('/positions', methods=['POST'])
@login_required
def create_position():
    # Company admin creates for their own company.
    # Superadmin would need to specify company_id if they were to use this,
    # but for now, let's assume SA uses a dedicated admin panel or this requires SA to "act as" a company.
    # For simplicity, this is scoped to company_admin.
    if current_user.role != 'company_admin':
        return jsonify({'error': 'Only company admins can create positions for their company.'}), 403

    company_id = current_user.company_id
    if not company_id:
        return jsonify({'error': 'User not associated with a company.'}), 400

    data = request.get_json()
    if not data or not data.get('position_name'):
        return jsonify({'error': 'Position name is required.'}), 400

    position_name = data.get('position_name').strip()
    description = data.get('description', '').strip() if data.get('description') else None
    # Status can be 'Open', 'Closed', 'On Hold'. Default to 'Open'.
    status = data.get('status', 'Open').strip()
    valid_statuses = ['Open', 'Closed', 'On Hold']
    if status not in valid_statuses:
        return jsonify({'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'}), 400

    if not position_name: # Check after strip
        return jsonify({'error': 'Position name cannot be empty.'}), 400

    # UniqueConstraint('position_name', 'company_id') will be handled by DB
    # but we can check proactively.
    existing_position = Position.query.filter_by(position_name=position_name, company_id=company_id).first()
    if existing_position:
        return jsonify({'error': f"A position named '{position_name}' already exists for this company."}), 409

    new_position = Position(
        company_id=company_id,
        position_name=position_name,
        description=description,
        status=status
    )
    db.session.add(new_position)
    try:
        db.session.commit()
        current_app.logger.info(
            f"Position '{new_position.position_name}' (ID: {new_position.position_id}) created for company {company_id} by {current_user.username}.")
        return jsonify(new_position.to_dict()), 201
    except exc.IntegrityError as ie: # Catch unique constraint violation specifically
        db.session.rollback()
        current_app.logger.warning(f"IntegrityError creating position '{position_name}' for company {company_id}: {ie}")
        return jsonify({'error': f"A position named '{position_name}' already exists (DB constraint)."}), 409
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating position for company {company_id}: {e}", exc_info=True)
        return jsonify({'error': f'Could not create position: {str(e)}'}), 500


@company_admin_bp.route('/positions', methods=['GET'])
@login_required
def get_positions_list():
    # CompanyAdmin gets their own positions. Superadmin must specify company_id.
    company_id_for_query = None
    if current_user.role == 'superadmin':
        company_id_param = request.args.get('company_id', type=int)
        if not company_id_param:
            # For listing, superadmin might want to see ALL positions across all companies,
            # but this endpoint is under /company, implying a company scope.
            # Thus, SA must specify a company.
            return jsonify({'error': 'Superadmin must specify a company_id to view positions.'}), 400
        target_company = db.session.get(Company, company_id_param)
        if not target_company:
            return jsonify({'error': f'Company with ID {company_id_param} not found.'}), 404
        company_id_for_query = company_id_param
    elif current_user.role == 'company_admin':
        if not current_user.company_id:
            return jsonify({'error': 'User not associated with a company.'}), 403
        company_id_for_query = current_user.company_id
    else: # Other roles do not have access to this list view.
        return jsonify({'error': 'Forbidden: Insufficient permissions to view company positions.'}), 403

    status_filter = request.args.get('status', None, type=str)
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int) # Default to 10, can be adjusted

    query = Position.query.filter_by(company_id=company_id_for_query)

    if status_filter and status_filter.lower() != 'all':
        valid_statuses = ['Open', 'Closed', 'On Hold']
        # Allow multiple statuses comma-separated e.g. status=Open,On Hold
        status_list_filter = [s.strip() for s in status_filter.split(',') if s.strip() in valid_statuses]
        if status_list_filter:
            query = query.filter(Position.status.in_(status_list_filter))
        elif status_filter not in valid_statuses and status_filter.lower() != 'all' : # if one invalid status was given
             return jsonify({'error': f'Invalid status filter: {status_filter}. Valid are Open, Closed, On Hold or comma-separated list.'}), 400


    query = query.order_by(Position.status, Position.position_name) # Order by status then name

    try:
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        positions_data = [p.to_dict() for p in pagination.items] # to_dict already includes candidate_count
        current_app.logger.info(
            f"Fetched {len(positions_data)} positions for company {company_id_for_query} (User: {current_user.id}). Page: {page}, Status Filter: '{status_filter}'")

        return jsonify({
            'positions': positions_data,
            'total_positions': pagination.total,
            'total_pages': pagination.pages,
            'current_page': pagination.page
        }), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching positions list for company {company_id_for_query}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to retrieve positions list.'}), 500


@company_admin_bp.route('/positions/<int:position_id>', methods=['GET'])
@login_required
def get_single_position(position_id):
    position = db.session.get(Position, position_id)
    if not position:
        return jsonify({'error': 'Position not found.'}), 404

    # Check access: company_admin of the position's company or superadmin
    company_id_of_position = position.company_id
    access_check_result = check_company_admin_or_superadmin_access(company_id_of_position)
    if isinstance(access_check_result, tuple): # Error response
        return access_check_result
    # If superadmin, access_check_result is company_id_of_position. If CA, it's current_user.company_id.
    # They must match company_id_of_position.
    if access_check_result != company_id_of_position:
         return jsonify({'error': 'Forbidden: You do not have permission to view this specific position.'}), 403


    return jsonify(position.to_dict()), 200


@company_admin_bp.route('/positions/<int:position_id>', methods=['PUT'])
@login_required
def update_position(position_id):
    position_to_update = db.session.get(Position, position_id)
    if not position_to_update:
        return jsonify({'error': 'Position not found.'}), 404

    # Check access: only company_admin of the position's company can update. Superadmin might use a different panel.
    if current_user.role != 'company_admin' or current_user.company_id != position_to_update.company_id:
        # Allow superadmin IF they are updating a position for a company they are "acting as"
        # This part of logic might need refinement based on how superadmin interacts with company data.
        # For now, stricter: only company admin.
        if not (current_user.role == 'superadmin' and current_user.company_id == position_to_update.company_id): # SA acting for this company
             # More robust: check_company_admin_or_superadmin_access(position_to_update.company_id)
            access_check_result = check_company_admin_or_superadmin_access(position_to_update.company_id)
            if isinstance(access_check_result, tuple) or access_check_result != position_to_update.company_id:
                return jsonify({'error': 'Forbidden: You do not have permission to update this position.'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided for update.'}), 400

    updated_fields_count = 0
    if 'position_name' in data:
        new_name = data['position_name'].strip()
        if not new_name:
            return jsonify({'error': 'Position name cannot be empty.'}), 400
        if new_name != position_to_update.position_name:
            # Check for uniqueness within the company, excluding the current position itself
            existing_position = Position.query.filter(
                Position.position_name == new_name,
                Position.company_id == position_to_update.company_id,
                Position.position_id != position_id
            ).first()
            if existing_position:
                return jsonify({'error': f"A position named '{new_name}' already exists for this company."}), 409
            position_to_update.position_name = new_name
            updated_fields_count += 1

    if 'description' in data: # Allows setting description to empty string or None
        new_description = data['description'].strip() if data['description'] is not None else None
        if position_to_update.description != new_description:
            position_to_update.description = new_description
            updated_fields_count += 1

    if 'status' in data:
        new_status = data['status'].strip()
        valid_statuses = ['Open', 'Closed', 'On Hold']
        if new_status not in valid_statuses:
            return jsonify({'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'}), 400
        if position_to_update.status != new_status:
            position_to_update.status = new_status
            updated_fields_count += 1

    if updated_fields_count == 0:
        return jsonify({'message': 'No changes detected in provided data.'}), 200 # Or 304 Not Modified

    position_to_update.updated_at = datetime.now(dt_timezone.utc)
    try:
        db.session.commit()
        current_app.logger.info(
            f"Position '{position_to_update.position_name}' (ID: {position_id}) updated by {current_user.username}.")
        return jsonify(position_to_update.to_dict()), 200
    except exc.IntegrityError as ie: # Catch unique constraint violation if name changed
        db.session.rollback()
        current_app.logger.warning(f"IntegrityError updating position {position_id}: {ie}")
        return jsonify({'error': f"A position with the new name likely already exists (DB constraint)."}), 409
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating position {position_id}: {e}", exc_info=True)
        return jsonify({'error': f'Could not update position: {str(e)}'}), 500


@company_admin_bp.route('/positions/<int:position_id>', methods=['DELETE'])
@login_required
def delete_position(position_id):
    position_to_delete = db.session.get(Position, position_id)
    if not position_to_delete:
        return jsonify({'error': 'Position not found.'}), 404

    # Check access
    if not (current_user.role == 'company_admin' and current_user.company_id == position_to_delete.company_id):
        if not (current_user.role == 'superadmin'): # Superadmin can delete any position
             access_check_result = check_company_admin_or_superadmin_access(position_to_delete.company_id)
             if isinstance(access_check_result, tuple) or access_check_result != position_to_delete.company_id:
                return jsonify({'error': 'Forbidden: You do not have permission to delete this position.'}), 403

    # Check for associated candidates or interviews
    if position_to_delete.candidates.first(): # .first() is efficient to check existence
        return jsonify({
            'error': 'Cannot delete position. It is currently associated with one or more candidates. Please reassign or remove them from this position first.'
        }), 409
    if position_to_delete.interviews: # interviews is a list from lazy='select'
        # Check if any of those interviews are active (not just any interview ever)
        active_interview_exists = any(
            interview.status not in [
                InterviewStatus.CANCELLED_BY_CANDIDATE,
                InterviewStatus.CANCELLED_BY_RECRUITER,
                InterviewStatus.CANCELLED_DUE_TO_REEVALUATION,
                InterviewStatus.COMPLETED, # Or maybe even COMPLETED should prevent deletion
                InterviewStatus.EXPIRED
            ] for interview in position_to_delete.interviews
        )
        if active_interview_exists:
             return jsonify({
                'error': 'Cannot delete position. It has active or upcoming interviews associated with it. Please resolve these interviews first.'
            }), 409
        # If only past/cancelled interviews, we could allow deletion or mark as "Archived" instead.
        # For now, strict: if any interviews exist, block. A more nuanced approach might be needed.


    position_name_for_log = position_to_delete.position_name
    try:
        # Deleting the position will also delete entries from candidate_position_association
        # due to `ondelete='CASCADE'` on the FK.
        db.session.delete(position_to_delete)
        db.session.commit()
        current_app.logger.info(
            f"Position '{position_name_for_log}' (ID: {position_id}) deleted by {current_user.username}.")
        return jsonify({'message': f"Position '{position_name_for_log}' deleted successfully."}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting position {position_id}: {e}", exc_info=True)
        return jsonify({'error': f'Could not delete position: {str(e)}'}), 500

# This was the old /<int:company_id_from_path>/positions GET route.
# It's now replaced by the /positions GET route above which handles permissions better.
# @company_admin_bp.route('/<int:company_id_from_path>/positions', methods=['GET'])
# @login_required
# def get_company_positions_list(company_id_from_path):
#     # ... (This is now handled by GET /company/positions with ?company_id=X for superadmin) ...
#     pass