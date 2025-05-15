// frontend/src/pages/CompanyUsersPage.jsx
import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../App'; 
import { getCompanyUsers, createCompanyUser, toggleCompanyUserStatus } from '../services/companyAdminService';
// import './AdminPages.css'; // Αν έχεις κοινό CSS για admin σελίδες
// Εναλλακτικά, μπορείς να χρησιμοποιήσεις το App.css ή να φτιάξεις ένα CompanyUsersPage.css

const ITEMS_PER_PAGE_COMPANY = 10;

function CompanyUsersPage() {
  const { currentUser } = useAuth();
  const [users, setUsers] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [totalUsers, setTotalUsers] = useState(0);

  const [showCreateForm, setShowCreateForm] = useState(false); // <<< ΑΥΤΟ ΤΟ STATE ΕΛΕΓΧΕΙ ΤΗ ΦΟΡΜΑ
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
    setIsLoading(true); setError('');
    try {
      const params = { page, per_page: ITEMS_PER_PAGE_COMPANY };
      const data = await getCompanyUsers(params); // Δεν χρειάζεται company_id, το παίρνει το backend από το session
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
    if (currentUser && currentUser.role === 'company_admin') { // Έλεγχος ρόλου πριν το fetch
        fetchCompanyUsersData(1);
    }
  }, [fetchCompanyUsersData, currentUser]);

  const handleNewUserFormChange = (e) => {
    const { name, value } = e.target;
    setNewUserFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleCreateUserSubmit = async (e) => {
    e.preventDefault();
    setCreateError('');
    if (newUserFormData.password !== newUserFormData.confirmPassword) {
      setCreateError('Passwords do not match.'); return;
    }
    if (newUserFormData.password.length < 8) {
      setCreateError('Password must be at least 8 characters long.'); return;
    }
    setIsSubmitting(true);
    try {
      const { confirmPassword, ...payload } = newUserFormData;
      await createCompanyUser(payload); // Το company_id θα προστεθεί στο backend
      setShowCreateForm(false); // Κλείσιμο φόρμας μετά την επιτυχία
      setNewUserFormData({ username: '', email: '', password: '', confirmPassword: '' });
      fetchCompanyUsersData(1); 
    } catch (err) {
      setCreateError(err.error || err.message || 'Failed to create user.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleToggleUserStatus = async (userId, currentIsActive) => {
    if (currentUser && currentUser.id === userId) {
        alert("You cannot change your own active status."); return;
    }
    const newStatus = !currentIsActive;
    if (window.confirm(`Are you sure you want to ${newStatus ? 'activate' : 'deactivate'} this user?`)) {
      try {
        await toggleCompanyUserStatus(userId, newStatus);
        fetchCompanyUsersData(currentPage); 
      } catch (err) {
        alert(`Failed to update user status: ${err.error || err.message}`);
      }
    }
  };

  const handlePageChange = (newPage) => {
    if (newPage >= 1 && newPage <= totalPages) fetchCompanyUsersData(newPage);
  };

  if (!currentUser || currentUser.role !== 'company_admin') {
    return <div className="card-style error-message">Access Denied.</div>;
  }

  return (
    // Εφάρμοσε .card-style από το App.css ή το DashboardPage.css (αν είναι global)
    // ή δημιούργησε ένα AdminPages.css
    <div className="admin-page-container card-style"> 
      <h1>Manage Users for {currentUser.company_name || 'Your Company'}</h1>

      {/* --- ΚΟΥΜΠΙ ΚΑΙ ΦΟΡΜΑ ΠΡΟΣΘΗΚΗΣ --- */}
      <div className="add-user-section" style={{ marginBottom: '1.5rem', paddingBottom: '1.5rem', borderBottom: '1px solid var(--border-color)' }}>
        {!showCreateForm && (
          <button 
            onClick={() => { setShowCreateForm(true); setCreateError(''); }} 
            className="button-action button-primary" // Χρησιμοποίησε τις global κλάσεις
          >
            + Add New User
          </button>
        )}

        {showCreateForm && (
          // Το card-style εδώ είναι για να ξεχωρίζει η φόρμα
          <div className="create-user-form card-style" style={{ marginTop: '1rem', borderColor: 'var(--primary-color)' }}> 
            <h3 style={{marginTop:0, marginBottom:'1rem'}}>Create New User</h3>
            <form onSubmit={handleCreateUserSubmit}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '1rem' }}>
                <div className="form-group">
                  <label htmlFor="username-company">Username:</label>
                  <input type="text" id="username-company" name="username" value={newUserFormData.username} onChange={handleNewUserFormChange} required className="input-light-gray" autoComplete="off" />
                </div>
                <div className="form-group">
                  <label htmlFor="email-company">Email:</label>
                  <input type="email" id="email-company" name="email" value={newUserFormData.email} onChange={handleNewUserFormChange} required className="input-light-gray" autoComplete="off" />
                </div>
                <div className="form-group">
                  <label htmlFor="password-company">Password:</label>
                  <input type="password" id="password-company" name="password" value={newUserFormData.password} onChange={handleNewUserFormChange} required minLength="8" className="input-light-gray" autoComplete="new-password" />
                </div>
                <div className="form-group">
                  <label htmlFor="confirmPassword-company">Confirm Password:</label>
                  <input type="password" id="confirmPassword-company" name="confirmPassword" value={newUserFormData.confirmPassword} onChange={handleNewUserFormChange} required minLength="8" className="input-light-gray" autoComplete="new-password" />
                </div>
              </div>
              {createError && <p className="error-message" style={{ marginTop: '1rem' }}>{createError}</p>}
              <div style={{ marginTop: '1.5rem', display: 'flex', gap: '1rem', justifyContent:'flex-end' }}>
                <button type="button" onClick={() => {setShowCreateForm(false); setCreateError('');}} className="button-action button-secondary" disabled={isSubmitting}>
                  Cancel
                </button>
                <button type="submit" className="button-action button-primary" disabled={isSubmitting}>
                  {isSubmitting ? 'Creating...' : 'Create User'}
                </button>
              </div>
            </form>
          </div>
        )}
      </div>
      {/* --- ΤΕΛΟΣ ΚΟΥΜΠΙΟΥ ΚΑΙ ΦΟΡΜΑΣ --- */}


      {isLoading && <div className="loading-placeholder">Loading users...</div>}
      {error && !isLoading && <p className="error-message">{error}</p>}
      {!isLoading && !error && users.length === 0 && (
        <p className="empty-list-message">No users found in your company.</p>
      )}

      {!isLoading && users.length > 0 && (
        <>
          <div className="table-responsive"> {/* Για scroll σε μικρές οθόνες */}
            <table className="candidate-table"> {/* Χρησιμοποίησε το styling από το CandidateList.css */}
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Username</th>
                  <th>Email</th>
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
                    <td>{user.is_active ? 'Yes' : 'No'}</td>
                    <td>{user.created_at ? new Date(user.created_at).toLocaleDateString() : 'N/A'}</td>
                    <td>
                      <button
                        onClick={() => handleToggleUserStatus(user.id, user.is_active)}
                        className={`button-action ${user.is_active ? 'button-reject' : 'button-confirm'}`}
                        disabled={currentUser.id === user.id}
                        title={currentUser.id === user.id ? "Cannot change own status" : (user.is_active ? 'Deactivate' : 'Activate')}
                      >
                        {user.is_active ? 'Deactivate' : 'Activate'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {totalPages > 1 && (
            <div className="pagination-controls">
              <button onClick={() => handlePageChange(currentPage - 1)} disabled={currentPage === 1 || isLoading} className="button-action button-secondary">Previous</button>
              <span>Page {currentPage} of {totalPages} (Total: {totalUsers} users)</span>
              <button onClick={() => handlePageChange(currentPage + 1)} disabled={currentPage === totalPages || isLoading} className="button-action button-secondary">Next</button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default CompanyUsersPage;