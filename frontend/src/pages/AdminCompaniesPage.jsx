// frontend/src/pages/AdminCompaniesPage.jsx
import React, { useState, useEffect, useCallback } from 'react';
import { getCompanies, createCompany } from '../services/adminService'; // Βεβαιώσου ότι το path είναι σωστό

function AdminCompaniesPage() {
  const [companies, setCompanies] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(''); // Γενικό error για τη φόρτωση της λίστας
  const [newCompanyName, setNewCompanyName] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [createError, setCreateError] = useState(''); // Ειδικό error για τη δημιουργία

  const fetchCompaniesData = useCallback(async () => {
    setIsLoading(true);
    setError(''); // Καθάρισε το γενικό error πριν από κάθε fetch
    try {
      const data = await getCompanies(); // Επιστρέφει { companies: [...], ... }
      setCompanies(data.companies || []); // Πάρε το array από το data.companies
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
      setCreateError('Company name cannot be empty.'); // Χρησιμοποίησε το createError
      return;
    }
    setIsSubmitting(true);
    setCreateError(''); // Καθάρισε το createError
    setError(''); // Καθάρισε και το γενικό error
    try {
      await createCompany({ name: newCompanyName.trim() });
      setNewCompanyName('');
      fetchCompaniesData(); // Επαναφόρτωση λίστας μετά τη δημιουργία
    } catch (err) {
      setCreateError(err.error || err.message || 'Failed to create company.');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Μηνύματα φόρτωσης/σφάλματος για τη λίστα
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
        <table className="candidate-table"> {/* Βεβαιώσου ότι δεν υπάρχει κενό εδώ */}
          <thead>
            <tr>
              <th>ID</th>
              <th>Name</th>
              <th>Owner User ID</th>
              <th>Owner Username</th>
              <th>Users</th>
              <th>Candidates</th>
              <th>Created At</th>
            </tr>
          </thead>
          <tbody>
            {companies.map((company) => (
              <tr key={company.company_id || company.id}> {/* Χρησιμοποίησε company_id ή id */}
                <td>{company.company_id || company.id}</td>
                <td>{company.name}</td>
                <td>{company.owner_user_id || 'N/A'}</td>
                <td>{company.owner_username || 'N/A'}</td>
                <td>{company.user_count !== undefined ? company.user_count : 'N/A'}</td>
                <td>{company.candidate_count !== undefined ? company.candidate_count : 'N/A'}</td>
                <td>{company.created_at ? new Date(company.created_at).toLocaleDateString() : 'N/A'}</td>
              </tr>
            ))}
          </tbody>
        </table>
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