// frontend/src/pages/CompanyUsersPage.jsx
import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../App'; // Για να πάρουμε το company_id του admin
import { getCompanyUsers, createCompanyUser, toggleCompanyUserStatus } from '../services/companyAdminService';
// import './AdminPages.css'; // Μπορείς να χρησιμοποιήσεις παρόμοιο styling

const ITEMS_PER_PAGE_COMPANY = 10;

function CompanyUsersPage() {
  const { currentUser } = useAuth();
  const [users, setUsers] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [totalUsers, setTotalUsers] = useState(0);

  const [showCreateForm, setShowCreateForm] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [createError, setCreateError] = useState('');
  const [newUserFormData, setNewUserFormData] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
  });

  const fetchCompanyUsersData = useCallback(async (page = 1) => {
    if (!currentUser || currentUser.role !== 'company_admin') {
      setError("Access denied or user not a company admin.");
      return;
    }
    setIsLoading(true);
    setError('');
    try {
      const params = { page, per_page: ITEMS_PER_PAGE_COMPANY };
      const data = await getCompanyUsers(params);
      setUsers(data.users || []);
      setCurrentPage(data.current_page || 1);
      setTotalPages(data.total_pages || 0);
      setTotalUsers(data.total_users || 0);
    } catch (err) {
      setError(err.error || err.message || 'Failed to load company users.');
      setUsers([]); setTotalPages(0); setTotalUsers(0);
    } finally {
      setIsLoading(false);
    }
  }, [currentUser]);

  useEffect(() => {
    fetchCompanyUsersData(1);
  }, [fetchCompanyUsersData]);

  const handleNewUserFormChange = (e) => {
    const { name, value } = e.target;
    setNewUserFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleCreateUserSubmit = async (e) => {
    e.preventDefault();
    setCreateError('');
    if (newUserFormData.password !== newUserFormData.confirmPassword) {
      setCreateError('Passwords do not match.');
      return;
    }
    if (newUserFormData.password.length < 8) {
      setCreateError('Password must be at least 8 characters long.');
      return;
    }
    setIsSubmitting(true);
    try {
      const { confirmPassword, ...payload } = newUserFormData; // Αφαιρούμε το confirmPassword
      await createCompanyUser(payload);
      setShowCreateForm(false);
      setNewUserFormData({ username: '', email: '', password: '', confirmPassword: '' });
      fetchCompanyUsersData(1); // Ανανέωσε στην πρώτη σελίδα
    } catch (err) {
      setCreateError(err.error || err.message || 'Failed to create user.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleToggleUserStatus = async (userId, currentIsActive) => {
    // Προσοχή: Μην επιτρέπεις στον company admin να απενεργοποιήσει τον εαυτό του
    if (currentUser && currentUser.id === userId) {
        alert("You cannot change your own active status.");
        return;
    }
    const newStatus = !currentIsActive;
    const confirmMessage = `Are you sure you want to ${newStatus ? 'activate' : 'deactivate'} this user?`;
    if (window.confirm(confirmMessage)) {
      try {
        await toggleCompanyUserStatus(userId, newStatus);
        fetchCompanyUsersData(currentPage); // Ανανέωσε την τρέχουσα σελίδα
      } catch (err) {
        alert(`Failed to update user status: ${err.error || err.message}`);
      }
    }
  };

  const handlePageChange = (newPage) => {
    if (newPage >= 1 && newPage <= totalPages) {
      fetchCompanyUsersData(newPage);
    }
  };


  if (!currentUser || currentUser.role !== 'company_admin') {
    return <div className="card-style error-message">Access Denied: You must be a Company Admin to view this page.</div>;
  }

  return (
    <div className="company-users-page-container card-style">
      <h1>Manage Users for {currentUser.company_name || 'Your Company'}</h1>

      <div className="add-user-section" style={{ marginBottom: '1.5rem' }}>
        {!showCreateForm && (
          <button onClick={() => {setShowCreateForm(true); setCreateError('');}} className="button-action button-primary">
            + Add New User
          </button>
        )}
        {showCreateForm && (
          <div className="create-user-form card-style" style={{ marginTop: '1rem', padding: '1.5rem' }}>
            <h3>Create New User (for {currentUser.company_name})</h3>
            <form onSubmit={handleCreateUserSubmit}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div className="form-group">
                  <label htmlFor="username">Username:</label>
                  <input type="text" name="username" value={newUserFormData.username} onChange={handleNewUserFormChange} required className="input-light-gray" autoComplete="off" />
                </div>
                <div className="form-group">
                  <label htmlFor="email">Email:</label>
                  <input type="email" name="email" value={newUserFormData.email} onChange={handleNewUserFormChange} required className="input-light-gray" autoComplete="off" />
                </div>
                <div className="form-group">
                  <label htmlFor="password">Password:</label>
                  <input type="password" name="password" value={newUserFormData.password} onChange={handleNewUserFormChange} required minLength="8" className="input-light-gray" autoComplete="new-password" />
                </div>
                <div className="form-group">
                  <label htmlFor="confirmPassword">Confirm Password:</label>
                  <input type="password" name="confirmPassword" value={newUserFormData.confirmPassword} onChange={handleNewUserFormChange} required minLength="8" className="input-light-gray" autoComplete="new-password" />
                </div>
              </div>
              {createError && <p className="error-message" style={{ marginTop: '1rem' }}>{createError}</p>}
              <div style={{ marginTop: '1.5rem', display: 'flex', gap: '1rem' }}>
                <button type="submit" className="button-action button-save" disabled={isSubmitting}>
                  {isSubmitting ? 'Creating...' : 'Create User'}
                </button>
                <button type="button" onClick={() => {setShowCreateForm(false); setCreateError('');}} className="button-action button-cancel" disabled={isSubmitting}>
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
        <p>No users found in your company.</p>
      )}

      {!isLoading && users.length > 0 && (
        <>
          <table className="candidate-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Username</th>
                <th>Email</th>
                {/* Ο Ρόλος θα είναι πάντα 'user' εδώ, οπότε ίσως δεν χρειάζεται */}
                {/* <th>Role</th> */}
                <th>Active</th>
                <th>Created At</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id}>
                  <td>{user.id}</td>
                  <td>{user.username}</td>
                  <td>{user.email}</td>
                  {/* <td>{user.role}</td> */}
                  <td>{user.is_active ? 'Yes' : 'No'}</td>
                  <td>{user.created_at ? new Date(user.created_at).toLocaleDateString() : 'N/A'}</td>
                  <td>
                    <button
                      onClick={() => handleToggleUserStatus(user.id, user.is_active)}
                      className={`button-action ${user.is_active ? 'button-reject' : 'button-confirm'}`}
                      disabled={currentUser.id === user.id} // Απενεργοποίηση για τον ίδιο τον admin
                      title={currentUser.id === user.id ? "Cannot change your own status" : (user.is_active ? 'Deactivate User' : 'Activate User')}
                    >
                      {user.is_active ? 'Deactivate' : 'Activate'}
                    </button>
                    {/* TODO: Edit User button αργότερα */}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {totalPages > 1 && (
            <div className="pagination-controls" style={{ marginTop: '1rem', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '0.5rem' }}>
              <button onClick={() => handlePageChange(currentPage - 1)} disabled={currentPage === 1 || isLoading} className="button-action button-cancel-schedule">Previous</button>
              <span>Page {currentPage} of {totalPages} (Total: {totalUsers} users)</span>
              <button onClick={() => handlePageChange(currentPage + 1)} disabled={currentPage === totalPages || isLoading} className="button-action button-cancel-schedule">Next</button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default CompanyUsersPage;