// frontend/src/pages/AdminCompaniesPage.jsx
import React, { useState, useEffect, useCallback } from 'react';
import { getCompanies, createCompany } from '../services/adminService';

function AdminCompaniesPage() {
  const [companies, setCompanies] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [newCompanyName, setNewCompanyName] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [createError, setCreateError] = useState('');

  const fetchCompaniesData = useCallback(async () => {
    setIsLoading(true);
    setError('');
    try {
      const data = await getCompanies();
      setCompanies(data.companies || []);
    } catch (err) {
      setError(err.error || err.message || 'Failed to load companies.');
      setCompanies([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCompaniesData();
  }, [fetchCompaniesData]);

  const handleCreateCompany = async (e) => {
    e.preventDefault();
    if (!newCompanyName.trim()) {
      setCreateError('Company name cannot be empty.');
      return;
    }
    setIsSubmitting(true);
    setCreateError('');
    setError('');
    try {
      await createCompany({ name: newCompanyName.trim() });
      setNewCompanyName('');
      fetchCompaniesData();
    } catch (err) {
      setCreateError(err.error || err.message || 'Failed to create company.');
    } finally {
      setIsSubmitting(false);
    }
  };

  let companyListContent;
  if (isLoading) {
    companyListContent = <div className="loading-placeholder card-style">Loading companies...</div>;
  } else if (error) {
    companyListContent = <p className="error-message">{error}</p>;
  } else if (companies.length === 0) {
    companyListContent = <p>No companies found.</p>;
  } else {
    companyListContent = (
      <div className="table-responsive">
        <table className="candidate-table"><thead>{/* NO WHITESPACE */}
            <tr>
              <th>ID</th>
              <th>Name</th>
              <th>Owner User ID</th>
              <th>Owner Username</th>
              <th>Users</th>
              <th>Candidates</th>
              <th>Created At</th>
            </tr>
          </thead><tbody>{/* NO WHITESPACE */}
            {companies.map((company) => (
              // Το backend Company.to_dict() επιστρέφει company_id, οπότε το χρησιμοποιούμε.
              <tr key={company.company_id !== undefined ? company.company_id : `comp-name-${company.name || Math.random()}`}>{/* NO WHITESPACE & UNIQUE KEY */}
                <td>{company.company_id !== undefined ? company.company_id : 'N/A'}</td>
                <td>{company.name}</td>
                <td>{company.owner_user_id || 'N/A'}</td>
                <td>{company.owner_username || 'N/A'}</td>
                <td>{company.user_count !== undefined ? company.user_count : 'N/A'}</td>
                <td>{company.candidate_count !== undefined ? company.candidate_count : 'N/A'}</td>
                <td>{company.created_at ? new Date(company.created_at).toLocaleDateString() : 'N/A'}</td>
              </tr>
            ))}
          </tbody></table>
      </div>
    );
  }

  return (
    <div className="admin-page-container card-style">
      <h1>Admin - Manage Companies</h1>

      <div className="create-company-form" style={{ marginBottom: '2rem', paddingBottom: '1.5rem', borderBottom: '1px solid var(--border-color)' }}>
        <h3>Create New Company</h3>
        <form onSubmit={handleCreateCompany}>
          <div style={{ marginBottom: '1rem' }}>
            <label htmlFor="newCompanyName" style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500' }}>
              Company Name:
            </label>
            <input
              type="text"
              id="newCompanyName"
              value={newCompanyName}
              onChange={(e) => setNewCompanyName(e.target.value)}
              placeholder="Enter company name"
              required
              className="input-light-gray"
              style={{ width: '100%', maxWidth: '400px', marginRight: '10px' }}
            />
          </div>
          <button type="submit" className="button-action button-primary" disabled={isSubmitting}>
            {isSubmitting ? 'Creating...' : 'Create Company'}
          </button>
          {createError && <p className="error-message" style={{ marginTop: '0.5rem' }}>{createError}</p>}
        </form>
      </div>

      <h3>Existing Companies</h3>
      {companyListContent}
    </div>
  );
}

export default AdminCompaniesPage;