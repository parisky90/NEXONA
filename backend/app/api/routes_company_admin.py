# backend/app/api/routes_company_admin.py
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from app.models import User, Company, Interview, InterviewStatus, Position  # Προσθήκη Position
from sqlalchemy import or_

company_admin_bp = Blueprint('company_admin_api_bp', __name__, url_prefix='/api/v1/company')


def check_company_admin_or_superadmin_access(company_id_to_check=None):
    """
    Decorator or utility function to check if the current user is a superadmin
    or a company_admin of the specified company_id (or their own company if not specified).
    If company_id_to_check is None, it checks against current_user.company_id.
    Returns the target company_id if access is granted, otherwise aborts with 403 or 404.
    """
    # current_app.logger.info(f"check_access: user_role={current_user.role}, user_comp_id={current_user.company_id}, target_comp_id={company_id_to_check}")

    target_company_id_for_query = None

    if current_user.role == 'superadmin':
        if company_id_to_check is not None:
            # Superadmin is trying to access a specific company
            if not db.session.get(Company, company_id_to_check):
                current_app.logger.warning(
                    f"Superadmin {current_user.id} tried to access non-existent company {company_id_to_check}.")
                return jsonify({'error': 'Target company not found'}), 404
            target_company_id_for_query = company_id_to_check
            current_app.logger.debug(f"Superadmin {current_user.id} accessing company {target_company_id_for_query}.")
        else:
            # Superadmin without specific company_id in request (e.g. for listing their own "admin" users if that was a feature)
            # For most company-specific resources, a company_id would be expected for superadmin.
            # If it's a route that *requires* company_id for superadmin, this case should be handled by the route.
            current_app.logger.debug(f"Superadmin {current_user.id} accessing a route without specific company_id.")
            # target_company_id_for_query remains None, route must handle this if company_id is mandatory
            pass  # Let the route decide if this is valid
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
    else:  # 'user' role or other roles
        current_app.logger.warning(
            f"User {current_user.id} with role {current_user.role} attempted to access company admin protected route.")
        return jsonify({'error': 'Forbidden: Insufficient permissions.'}), 403

    return target_company_id_for_query  # Return the ID to be used in queries, can be None for superadmin if no specific company targeted


@company_admin_bp.route('/users', methods=['GET'])
@login_required
def get_company_users_list():
    company_id_for_query = check_company_admin_or_superadmin_access()
    if isinstance(company_id_for_query, tuple):  # Error response
        return company_id_for_query

    if not company_id_for_query and current_user.role == 'superadmin':
        # Superadmin viewing all users of all companies - this should be in admin_bp
        # For this route, superadmin *must* specify a company_id if they want to use it.
        # Or, this route is strictly for company_admins.
        # Let's assume for now superadmin can use it if they provide company_id in query_params
        company_id_from_param = request.args.get('company_id', type=int)
        if not company_id_from_param:
            return jsonify({'error': 'Superadmin must specify a company_id to view company users via this route.'}), 400
        company_id_for_query = company_id_from_param
        if not db.session.get(Company, company_id_for_query):
            return jsonify({'error': f'Company with ID {company_id_for_query} not found.'}), 404

    if not company_id_for_query:  # Should not happen if logic above is correct for company_admin
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
    company_id_for_creation = check_company_admin_or_superadmin_access()
    if isinstance(company_id_for_creation, tuple): return company_id_for_creation
    if not company_id_for_creation:
        return jsonify({'error': 'Company ID could not be determined for user creation.'}), 400

    data = request.get_json()
    if not data: return jsonify({'error': 'Request must be JSON'}), 400

    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    if not all([username, email, password]):
        return jsonify({'error': 'Username, email, and password are required.'}), 400

    if User.query.filter(or_(User.username == username, User.email == email.lower().strip())).first():
        return jsonify({'error': 'User with this username or email already exists.'}), 409

    new_user = User(
        username=username.strip(),
        email=email.strip().lower(),
        role='user',  # Company admins can only create 'user' role by default
        company_id=company_id_for_creation,
        is_active=True  # New users are active by default
    )
    new_user.set_password(password)
    db.session.add(new_user)
    try:
        db.session.commit()
        current_app.logger.info(
            f"User '{new_user.username}' created for company {company_id_for_creation} by {current_user.username}.")
        return jsonify(new_user.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating user for company {company_id_for_creation}: {e}", exc_info=True)
        return jsonify({'error': f'Could not create user: {str(e)}'}), 500


@company_admin_bp.route('/users/<int:user_id_to_manage>/status', methods=['PUT'])
@login_required
def toggle_user_status_in_company(user_id_to_manage):
    company_id_of_context = check_company_admin_or_superadmin_access()
    if isinstance(company_id_of_context, tuple): return company_id_of_context
    if not company_id_of_context:
        return jsonify({'error': 'Company context could not be determined.'}), 400

    user_to_manage = db.session.get(User, user_id_to_manage)
    if not user_to_manage:
        return jsonify({'error': 'User not found.'}), 404
    if user_to_manage.company_id != company_id_of_context:
        return jsonify({'error': 'User does not belong to your company.'}), 403
    if user_to_manage.id == current_user.id:
        return jsonify({'error': 'You cannot change your own active status.'}), 400

    data = request.get_json()
    if 'is_active' not in data or not isinstance(data['is_active'], bool):
        return jsonify({'error': 'Invalid payload. "is_active" (boolean) is required.'}), 400

    user_to_manage.is_active = data['is_active']
    try:
        db.session.commit()
        current_app.logger.info(
            f"User {user_to_manage.username} (ID: {user_to_manage.id}) active status set to {user_to_manage.is_active} by {current_user.username}.")
        return jsonify(user_to_manage.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error toggling status for user {user_id_to_manage}: {e}", exc_info=True)
        return jsonify({'error': f'Could not update user status: {str(e)}'}), 500


@company_admin_bp.route('/interviews', methods=['GET'])
@login_required
def get_company_interviews_list():
    # For a company admin, company_id is implicit from their session.
    # For a superadmin, they *must* provide a company_id as a query parameter.
    company_id_for_query = None
    if current_user.role == 'superadmin':
        company_id_param = request.args.get('company_id', type=int)
        if not company_id_param:
            current_app.logger.warning(
                f"Superadmin {current_user.id} attempted to get company interviews without specifying company_id.")
            return jsonify({'error': 'Superadmin must specify a company_id.'}), 400
        if not db.session.get(Company, company_id_param):
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

    # Query interviews directly linked to candidates of the target company
    # This also handles the case where an interview's position_id might be null
    # or the position was deleted, but the interview is still tied to a candidate of the company.
    query = Interview.query.join(Candidate).filter(Candidate.company_id == company_id_for_query)

    if status_filter:
        try:
            status_enum = InterviewStatus[status_filter.upper()]
            query = query.filter(Interview.status == status_enum)
        except KeyError:
            return jsonify({'error': f"Invalid interview status filter: {status_filter}"}), 400

    query = query.order_by(Interview.scheduled_start_time.desc().nullslast(), Interview.created_at.desc())

    try:
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        interviews_data = [interview.to_dict(include_sensitive=False) for interview in
                           pagination.items]  # include_sensitive=False for lists
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


# --- ΝΕΟ ENDPOINT ΓΙΑ ΤΙΣ ΘΕΣΕΙΣ ΤΗΣ ΕΤΑΙΡΕΙΑΣ ---
@company_admin_bp.route('/<int:company_id_from_path>/positions', methods=['GET'])
@login_required
def get_company_positions_list(company_id_from_path):
    target_company = db.session.get(Company, company_id_from_path)
    if not target_company:
        current_app.logger.warning(f"Attempt to get positions for non-existent company ID: {company_id_from_path}")
        return jsonify({'error': 'Company not found'}), 404

    # Έλεγχος δικαιωμάτων: Ο current_user πρέπει να είναι superadmin ή company_admin της company_id_from_path
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
        # Κάνε το filter case-insensitive αν θέλεις
        query = query.filter(Position.status.ilike(f"%{status_filter}%"))

    positions = query.order_by(Position.position_name).all()
    # Βεβαιώσου ότι το Position.to_dict() επιστρέφei τουλάχιστον 'id' (ή 'position_id') και 'name' (ή 'position_name')
    # για το dropdown στο InterviewProposalForm.
    positions_data = [p.to_dict() for p in positions]

    current_app.logger.info(
        f"Fetched {len(positions_data)} positions for company {company_id_from_path} (User: {current_user.id}). Filter: status='{status_filter}'")
    return jsonify({'positions': positions_data, 'total_positions': len(positions_data)}), 200
# --- ΤΕΛΟΣ ΝΕΟΥ ENDPOINT ---