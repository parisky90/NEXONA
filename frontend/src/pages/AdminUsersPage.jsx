// frontend/src/pages/AdminUsersPage.jsx
import React, { useState, useEffect, useCallback } from 'react';
import { getAllUsers, getCompanies } from '../services/adminService';

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
      const params = {
        page: page,
        per_page: ITEMS_PER_PAGE,
      };
      if (roleFilter && roleFilter !== 'all') { // 'all' δεν είναι έγκυρη τιμή για το backend, στέλνουμε κενό
        params.role = roleFilter;
      }
      if (companyFilter && companyFilter !== 'all') { // 'all' δεν είναι έγκυρη τιμή για το backend
        params.company_id = parseInt(companyFilter, 10);
      }

      const data = await getAllUsers(params);
      setUsers(data.users || []);
      setCurrentPage(data.current_page || 1);
      setTotalPages(data.total_pages || 0);
      setTotalUsers(data.total_users || 0);
    } catch (err) {
      setError(err.error || err.message || 'Failed to load users.');
      setUsers([]);
      setTotalPages(0);
      setTotalUsers(0);
    } finally {
      setIsLoading(false);
    }
  }, [roleFilter, companyFilter]);

  useEffect(() => {
    fetchUsersData(1);
  }, [fetchUsersData]);

  const handleRoleFilterChange = (e) => {
    setRoleFilter(e.target.value === 'all' ? '' : e.target.value); // Αν επιλεγεί 'all', στέλνουμε κενό string
    setCurrentPage(1);
  };

  const handleCompanyFilterChange = (e) => {
    setCompanyFilter(e.target.value === 'all' ? '' : e.target.value); // Αν επιλεγεί 'all', στέλνουμε κενό string
    setCurrentPage(1);
  };

  const handlePageChange = (newPage) => {
    if (newPage >= 1 && newPage <= totalPages) {
      fetchUsersData(newPage);
    }
  };

  return (
    <div className="admin-page-container card-style">
      <h1>Admin - Manage Users</h1>

      <div className="filters-container" style={{ marginBottom: '1.5rem', paddingBottom: '1.5rem', borderBottom: '1px solid var(--border-color)', display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
        <div>
          <label htmlFor="roleFilter" style={{ marginRight: '0.5rem', fontWeight: '500' }}>Role:</label>
          <select id="roleFilter" value={roleFilter || 'all'} onChange={handleRoleFilterChange} className="input-light-gray">
            <option value="all">All Roles</option> {/* Χρησιμοποιούμε 'all' για την εμφάνιση */}
            <option value="superadmin">Superadmin</option>
            <option value="company_admin">Company Admin</option>
            <option value="user">User</option>
          </select>
        </div>
        <div>
          <label htmlFor="companyFilter" style={{ marginRight: '0.5rem', fontWeight: '500' }}>Company:</label>
          <select id="companyFilter" value={companyFilter || 'all'} onChange={handleCompanyFilterChange} className="input-light-gray">
            <option value="all">All Companies</option> {/* Χρησιμοποιούμε 'all' για την εμφάνιση */}
            {companiesForFilter.map(company => (
              <option key={company.id} value={company.id}>{company.name} (ID: {company.id})</option>
            ))}
          </select>
        </div>
      </div>

      {/* TODO: Add User Button and Form Section Here Later */}

      {isLoading && <div className="loading-placeholder">Loading users...</div>}
      {error && <p className="error-message">{error}</p>}

      {!isLoading && !error && users.length === 0 && (
        <p>No users found matching the criteria.</p>
      )}

      {!isLoading && users.length > 0 && (
        // --- ΔΙΟΡΘΩΣΗ ΓΙΑ WHITESPACE ---
        // Βεβαιώσου ότι δεν υπάρχουν κενά ή σχόλια JSX εδώ
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
        // --- ΤΕΛΟΣ ΔΙΟΡΘΩΣΗΣ ---
      )}

      {!isLoading && totalPages > 1 && (
        <div className="pagination-controls" style={{ marginTop: '1rem', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '0.5rem' }}>
          <button
            onClick={() => handlePageChange(currentPage - 1)}
            disabled={currentPage === 1 || isLoading}
            className="button-action button-cancel-schedule"
          >
            Previous
          </button>
          <span>Page {currentPage} of {totalPages} (Total: {totalUsers} users)</span>
          <button
            onClick={() => handlePageChange(currentPage + 1)}
            disabled={currentPage === totalPages || isLoading}
            className="button-action button-cancel-schedule"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}

export default AdminUsersPage;