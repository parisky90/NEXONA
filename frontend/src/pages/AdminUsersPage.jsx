// frontend/src/pages/AdminUsersPage.jsx
import React, { useState, useEffect, useCallback } from 'react';
import { getAllUsers, getCompanies, createUserBySuperadmin } from '../services/adminService';

const ITEMS_PER_PAGE = 10;

function AdminUsersPage() {
  const [users, setUsers] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [totalUsers, setTotalUsers] = useState(0);
  const [roleFilter, setRoleFilter] = useState('');
  const [companyFilter, setCompanyFilter] = useState('');
  const [companiesForFilter, setCompaniesForFilter] = useState([]);
  const [showCreateUserForm, setShowCreateUserForm] = useState(false);
  const [isSubmittingUser, setIsSubmittingUser] = useState(false);
  const [createUserError, setCreateUserError] = useState('');
  const [newUserFormData, setNewUserFormData] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
    role: 'user',
    company_id: '',
    is_active: true,
  });

  const fetchCompaniesForFilter = useCallback(async () => {
    try {
      const companiesData = await getCompanies();
      setCompaniesForFilter(companiesData || []);
    } catch (err) {
      console.error("Failed to load companies for filter:", err);
    }
  }, []);

  useEffect(() => {
    fetchCompaniesForFilter();
  }, [fetchCompaniesForFilter]);

  const fetchUsersData = useCallback(async (page = 1) => {
    setIsLoading(true);
    setError('');
    try {
      const params = { page, per_page: ITEMS_PER_PAGE };
      if (roleFilter && roleFilter !== 'all') params.role = roleFilter;
      if (companyFilter && companyFilter !== 'all') params.company_id = parseInt(companyFilter, 10);
      const data = await getAllUsers(params);
      setUsers(data.users || []);
      setCurrentPage(data.current_page || 1);
      setTotalPages(data.total_pages || 0);
      setTotalUsers(data.total_users || 0);
    } catch (err) {
      setError(err.error || err.message || 'Failed to load users.');
      setUsers([]); setTotalPages(0); setTotalUsers(0);
    } finally {
      setIsLoading(false);
    }
  }, [roleFilter, companyFilter]);

  useEffect(() => {
    fetchUsersData(1);
  }, [fetchUsersData]);

  const handleRoleFilterChange = (e) => {
    setRoleFilter(e.target.value === 'all' ? '' : e.target.value);
    setCurrentPage(1);
  };

  const handleCompanyFilterChange = (e) => {
    setCompanyFilter(e.target.value === 'all' ? '' : e.target.value);
    setCurrentPage(1);
  };

  const handlePageChange = (newPage) => {
    if (newPage >= 1 && newPage <= totalPages) fetchUsersData(newPage);
  };

  const handleNewUserFormChange = (e) => {
    const { name, value, type, checked } = e.target;
    setNewUserFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }));
  };

  const handleCreateUserSubmit = async (e) => {
    e.preventDefault();
    setCreateUserError('');
    if (newUserFormData.password !== newUserFormData.confirmPassword) {
      setCreateUserError('Passwords do not match.');
      return;
    }
    if (newUserFormData.password.length < 8) {
      setCreateUserError('Password must be at least 8 characters long.');
      return;
    }
    if (newUserFormData.role !== 'superadmin' && !newUserFormData.company_id) {
      setCreateUserError('Company is required for roles "Company Admin" and "User".');
      return;
    }

    setIsSubmittingUser(true);
    try {
      const payload = { ...newUserFormData };
      delete payload.confirmPassword;
      if (payload.role === 'superadmin') {
        payload.company_id = null;
      } else {
        payload.company_id = payload.company_id ? parseInt(payload.company_id, 10) : null;
        if (payload.company_id === null && payload.role !== 'superadmin') {
             setCreateUserError('Company is required for non-superadmin roles.');
             setIsSubmittingUser(false);
             return;
        }
      }

      await createUserBySuperadmin(payload);
      setShowCreateUserForm(false);
      setNewUserFormData({
        username: '', email: '', password: '', confirmPassword: '',
        role: 'user', company_id: '', is_active: true,
      });
      fetchUsersData(1);
    } catch (err) {
      setCreateUserError(err.error || err.message || 'Failed to create user.');
    } finally {
      setIsSubmittingUser(false);
    }
  };

  return (
    <div className="admin-page-container card-style">
      <h1>Admin - Manage Users</h1>

      <div className="filters-container" style={{ marginBottom: '1.5rem', paddingBottom: '1.5rem', borderBottom: '1px solid var(--border-color)', display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
        <div>
          <label htmlFor="roleFilter" style={{ marginRight: '0.5rem', fontWeight: '500' }}>Role:</label>
          <select id="roleFilter" value={roleFilter || 'all'} onChange={handleRoleFilterChange} className="input-light-gray">
            <option value="all">All Roles</option>
            <option value="superadmin">Superadmin</option>
            <option value="company_admin">Company Admin</option>
            <option value="user">User</option>
          </select>
        </div>
        <div>
          <label htmlFor="companyFilter" style={{ marginRight: '0.5rem', fontWeight: '500' }}>Company:</label>
          <select id="companyFilter" value={companyFilter || 'all'} onChange={handleCompanyFilterChange} className="input-light-gray">
            <option value="all">All Companies</option>
            {companiesForFilter.map(company => (
              <option key={company.id} value={company.id}>{company.name} (ID: {company.id})</option>
            ))}
          </select>
        </div>
      </div>

      <div className="add-user-section" style={{ marginBottom: '1.5rem' }}>
        {!showCreateUserForm && (
          <button
            onClick={() => {
              setShowCreateUserForm(true);
              setCreateUserError('');
            }}
            className="button-action button-primary"
          >
            + Add New User
          </button>
        )}

        {showCreateUserForm && (
          <div className="create-user-form card-style" style={{ marginTop: '1rem', padding: '1.5rem' }}>
            <h3>Create New User</h3>
            <form onSubmit={handleCreateUserSubmit}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div className="form-group">
                  <label htmlFor="username">Username:</label>
                  <input type="text" name="username" id="username" value={newUserFormData.username} onChange={handleNewUserFormChange} required className="input-light-gray" autoComplete="username" /> {/* ΠΡΟΣΘΗΚΗ */}
                </div>
                <div className="form-group">
                  <label htmlFor="email">Email:</label>
                  <input type="email" name="email" id="email" value={newUserFormData.email} onChange={handleNewUserFormChange} required className="input-light-gray" autoComplete="email" /> {/* Πρόσθεσα και εδώ */}
                </div>
                <div className="form-group">
                  <label htmlFor="password">Password:</label>
                  <input type="password" name="password" id="password" value={newUserFormData.password} onChange={handleNewUserFormChange} required minLength="8" className="input-light-gray" autoComplete="new-password" />
                </div>
                <div className="form-group">
                  <label htmlFor="confirmPassword">Confirm Password:</label>
                  <input type="password" name="confirmPassword" id="confirmPassword" value={newUserFormData.confirmPassword} onChange={handleNewUserFormChange} required minLength="8" className="input-light-gray" autoComplete="new-password" />
                </div>
                <div className="form-group">
                  <label htmlFor="role">Role:</label>
                  <select name="role" id="role" value={newUserFormData.role} onChange={handleNewUserFormChange} required className="input-light-gray">
                    <option value="user">User</option>
                    <option value="company_admin">Company Admin</option>
                    <option value="superadmin">Superadmin</option>
                  </select>
                </div>
                <div className="form-group">
                  <label htmlFor="company_id">Company:</label>
                  <select
                    name="company_id"
                    id="company_id"
                    value={newUserFormData.company_id}
                    onChange={handleNewUserFormChange}
                    disabled={newUserFormData.role === 'superadmin'}
                    required={newUserFormData.role !== 'superadmin'}
                    className="input-light-gray"
                  >
                    <option value="">{newUserFormData.role === 'superadmin' ? 'N/A for Superadmin' : 'Select Company'}</option>
                    {companiesForFilter.map(company => (
                      <option key={company.id} value={company.id}>{company.name}</option>
                    ))}
                  </select>
                </div>
                <div className="form-group" style={{ gridColumn: 'span 2', display: 'flex', alignItems: 'center' }}>
                  <input type="checkbox" name="is_active" id="is_active" checked={newUserFormData.is_active} onChange={handleNewUserFormChange} style={{ marginRight: '0.5rem' }} />
                  <label htmlFor="is_active" style={{ marginBottom: 0, fontWeight: 'normal' }}>Active User</label>
                </div>
              </div>
              {createUserError && <p className="error-message" style={{ marginTop: '1rem' }}>{createUserError}</p>}
              <div style={{ marginTop: '1.5rem', display: 'flex', gap: '1rem' }}>
                <button type="submit" className="button-action button-save" disabled={isSubmittingUser}>
                  {isSubmittingUser ? 'Creating...' : 'Create User'}
                </button>
                <button type="button" onClick={() => {setShowCreateUserForm(false); setCreateUserError('');}} className="button-action button-cancel" disabled={isSubmittingUser}>
                  Cancel
                </button>
              </div>
            </form>
          </div>
        )}
      </div>

      {isLoading && <div className="loading-placeholder">Loading users...</div>}
      {error && !isLoading && <p className="error-message">{error}</p>}
      {!isLoading && !error && users.length === 0 && (
        <p>No users found matching the criteria.</p>
      )}

      {!isLoading && users.length > 0 && (
        <table className="candidate-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Username</th>
              <th>Email</th>
              <th>Role</th>
              <th>Company</th>
              <th>Active</th>
              <th>Created At</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.id}>
                <td>{user.id}</td>
                <td>{user.username}</td>
                <td>{user.email}</td>
                <td>{user.role}</td>
                <td>{user.company_name || (user.role === 'superadmin' ? 'N/A (Superadmin)' : 'Unassigned')}</td>
                <td>{user.is_active ? 'Yes' : 'No'}</td>
                <td>{user.created_at ? new Date(user.created_at).toLocaleDateString() : 'N/A'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {!isLoading && totalPages > 1 && (
        <div className="pagination-controls" style={{ marginTop: '1rem', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '0.5rem' }}>
          <button onClick={() => handlePageChange(currentPage - 1)} disabled={currentPage === 1 || isLoading} className="button-action button-cancel-schedule">Previous</button>
          <span>Page {currentPage} of {totalPages} (Total: {totalUsers} users)</span>
          <button onClick={() => handlePageChange(currentPage + 1)} disabled={currentPage === totalPages || isLoading} className="button-action button-cancel-schedule">Next</button>
        </div>
      )}
    </div>
  );
}

export default AdminUsersPage;