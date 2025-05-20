// frontend/src/pages/CompanyUsersPage.jsx
import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../App'; 
import { getCompanyUsers, createCompanyUser, toggleCompanyUserStatus, deleteCompanyUser } from '../services/companyAdminService'; // <<< ΠΡΟΣΘΗΚΗ deleteCompanyUser

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
      console.warn("CompanyUsersPage: fetchCompanyUsersData - Access denied or user not company admin. Current user:", currentUser);
      setError("Access denied. You must be a Company Admin to view this page.");
      setIsLoading(false);
      setUsers([]); 
      setTotalPages(0); 
      setTotalUsers(0);
      return;
    }
    setIsLoading(true); setError('');
    try {
      const params = { page, per_page: ITEMS_PER_PAGE_COMPANY };
      const data = await getCompanyUsers(params);
      setUsers(data.users || []);
      setCurrentPage(data.current_page || 1);
      setTotalPages(data.total_pages || 0);
      setTotalUsers(data.total_users || 0);
    } catch (err) {
      console.error("CompanyUsersPage: Error fetching company users:", err.response?.data?.error || err.message || err);
      setError(err.response?.data?.error || err.message || 'Failed to load company users.');
      setUsers([]); setTotalPages(0); setTotalUsers(0);
    } finally {
      setIsLoading(false);
    }
  }, [currentUser]);

  useEffect(() => {
    if (currentUser && currentUser.role === 'company_admin') {
        fetchCompanyUsersData(1);
    } else if (currentUser) {
        setIsLoading(false);
        setUsers([]);
        setError("Access Denied. You must be a Company Admin to view this page.");
    } else {
      setIsLoading(false);
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
      await createCompanyUser(payload);
      setShowCreateForm(false);
      setNewUserFormData({ username: '', email: '', password: '', confirmPassword: '' });
      fetchCompanyUsersData(1); 
      alert('User created successfully!');
    } catch (err) {
      setCreateError(err.response?.data?.error || err.message || 'Failed to create user.');
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
      setIsLoading(true); // Για να δείχνει ότι κάτι γίνεται
      try {
        await toggleCompanyUserStatus(userId, newStatus);
        fetchCompanyUsersData(currentPage); 
        alert(`User status updated to ${newStatus ? 'Active' : 'Inactive'}.`);
      } catch (err) {
        alert(`Failed to update user status: ${err.response?.data?.error || err.message}`);
      } finally {
        setIsLoading(false);
      }
    }
  };

  // --- ΝΕΑ ΣΥΝΑΡΤΗΣΗ ΓΙΑ DELETE USER ---
  const handleDeleteUser = async (userId, username) => {
    if (currentUser && currentUser.id === userId) {
        alert("You cannot delete yourself."); 
        return;
    }
    // Πρόσθεσε έλεγχο για τον owner αν είναι εύκολο να τον πάρεις από το `currentUser` ή την εταιρεία
    // if (currentUser?.company?.owner_user_id === userId) {
    //    alert("You cannot delete the company owner.");
    //    return;
    // }

    if (window.confirm(`Are you sure you want to PERMANENTLY DELETE user '${username}' (ID: ${userId})? This action cannot be undone.`)) {
        setIsLoading(true);
        try {
            await deleteCompanyUser(userId); // Κλήση της νέας service function
            alert(`User '${username}' deleted successfully.`);
            fetchCompanyUsersData(users.length === 1 && currentPage > 1 ? currentPage - 1 : currentPage); // Πήγαινε στην προηγούμενη σελίδα αν η τρέχουσα αδειάζει
        } catch (err) {
            console.error("Error deleting user:", err.response?.data || err.message);
            alert(`Failed to delete user: ${err.response?.data?.error || err.message}`);
        } finally {
            setIsLoading(false);
        }
    }
  };
  // --- ΤΕΛΟΣ ΝΕΑΣ ΣΥΝΑΡΤΗΣΗΣ ---


  const handlePageChange = (newPage) => {
    if (newPage >= 1 && newPage <= totalPages && !isLoading) { // Πρόσθεσε έλεγχο !isLoading
        fetchCompanyUsersData(newPage);
    }
  };
  
  if (!currentUser && isLoading) { 
    return <div className="loading-placeholder card-style">Loading user data...</div>;
  }
  if (currentUser && currentUser.role !== 'company_admin' && !isLoading) {
    return <div className="card-style error-message">Access Denied. You must be a Company Admin to view this page.</div>;
  }


  return (
    <div className="admin-page-container card-style"> 
      <h1>Manage Users for {currentUser?.company_name || 'Your Company'}</h1>

      <div className="add-user-section" style={{ marginBottom: '1.5rem', paddingBottom: '1.5rem', borderBottom: '1px solid var(--border-color)' }}>
        {!showCreateForm && (
          <button 
            onClick={() => { setShowCreateForm(true); setCreateError(''); setNewUserFormData({ username: '', email: '', password: '', confirmPassword: '' });}} 
            className="button-action button-primary"
          >
            + Add New User
          </button>
        )}

        {showCreateForm && (
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
                  <label htmlFor="password-company">Password (min 8 chars):</label>
                  <input type="password" id="password-company" name="password" value={newUserFormData.password} onChange={handleNewUserFormChange} required minLength="8" className="input-light-gray" autoComplete="new-password" />
                </div>
                <div className="form-group">
                  <label htmlFor="confirmPassword-company">Confirm Password:</label>
                  <input type="password" id="confirmPassword-company" name="confirmPassword" value={newUserFormData.confirmPassword} onChange={handleNewUserFormChange} required minLength="8" className="input-light-gray" autoComplete="new-password" />
                </div>
              </div>
              {createError && <p className="error-message" style={{ marginTop: '1rem', color: 'red' }}>{createError}</p>}
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

      {isLoading && users.length === 0 && <div className="loading-placeholder">Loading users...</div>}
      {error && !isLoading && <p className="error-message" style={{color: 'red'}}>{error}</p>}
      {!isLoading && !error && users.length === 0 && (
        <p className="empty-list-message" style={{textAlign: 'center', marginTop: '1rem'}}>No users found in your company. Click "+ Add New User" to create one.</p>
      )}

      {!isLoading && !error && users.length > 0 && (
        <>
          <div className="table-responsive">
            <table className="candidate-table"> {/* Ίσως θέλεις άλλο class name εδώ */}
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Username</th>
                  <th>Email</th>
                  <th>Active</th>
                  <th>Created At</th>
                  <th style={{textAlign: 'center'}}>Actions</th>
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
                    <td style={{textAlign: 'center'}}>
                      <button
                        onClick={() => handleToggleUserStatus(user.id, user.is_active)}
                        className={`button-action ${user.is_active ? 'button-warning' : 'button-confirm'}`} // Άλλαξα το class για deactivate
                        disabled={currentUser?.id === user.id || isSubmitting || isLoading} 
                        title={currentUser?.id === user.id ? "Cannot change own status" : (user.is_active ? 'Deactivate User' : 'Activate User')}
                        style={{marginRight: '5px'}}
                      >
                        {user.is_active ? 'Deactivate' : 'Activate'}
                      </button>
                      {/* --- ΝΕΟ ΚΟΥΜΠΙ DELETE --- */}
                      <button
                        onClick={() => handleDeleteUser(user.id, user.username)}
                        className="button-action button-reject" // Χρησιμοποίησε το class για reject/delete
                        disabled={currentUser?.id === user.id || isSubmitting || isLoading} // Δεν μπορείς να διαγράψεις τον εαυτό σου
                        title={currentUser?.id === user.id ? "Cannot delete self" : `Delete user ${user.username}`}
                      >
                        Delete
                      </button>
                      {/* --- ΤΕΛΟΣ ΝΕΟΥ ΚΟΥΜΠΙΟΥ --- */}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {totalPages > 1 && (
            <div className="pagination-controls" style={{ marginTop: '1rem', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '0.5rem' }}>
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