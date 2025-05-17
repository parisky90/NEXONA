// frontend/src/pages/AdminCompaniesPage.jsx
import React, { useState, useEffect, useCallback } from 'react';
import { getCompanies, createCompany } from '../services/adminService';

function AdminCompaniesPage() {
  const [companies, setCompanies] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [newCompanyName, setNewCompanyName] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // frontend/src/pages/AdminCompaniesPage.jsx
  const fetchCompaniesData = useCallback(async () => {
    setIsLoading(true);
    setError(''); // <--- ΚΑΘΑΡΙΣΕ ΤΟ ERROR ΠΡΙΝ ΤΟ FETCH
    try {
      const data = await getCompanies(); // Αυτό επιστρέφEI { companies: [...], ...}
      setCompanies(data.companies || []); // Χρησιμοποίησε το data.companies
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
      setError('Company name cannot be empty.');
      return;
    }
    setIsSubmitting(true);
    setError('');
    try {
      await createCompany({ name: newCompanyName.trim() });
      setNewCompanyName('');
      fetchCompaniesData();
    } catch (err) {
      setError(err.error || err.message || 'Failed to create company.');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) {
    return <div className="loading-placeholder card-style">Loading companies...</div>;
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
          {/* Εμφάνιση σφάλματος δημιουργίας εταιρείας */}
          {error && isSubmitting === false && newCompanyName === '' && <p className="error-message" style={{ marginTop: '0.5rem' }}>{error}</p>}
          {/* Προσοχή: Το παραπάνω error θα εμφανιστεί ΚΑΙ αν υπάρχει error φόρτωσης. Ίσως χρειάζεται ξεχωριστό state για createError */}
        </form>
      </div>

      <h3>Existing Companies</h3>
      {/* Έλεγχος για σφάλμα φόρτωσης εταιρειών */}
      {error && companies.length === 0 && !isLoading && (
          <p className="error-message">{error}</p>
      )}
      {companies.length === 0 && !isLoading && !error && (
        <p>No companies found.</p>
      )}
      {companies.length > 0 && (
        // --- ΠΙΘΑΝΗ ΔΙΟΡΘΩΣΗ ΓΙΑ WHITESPACE ---
        // Βεβαιώσου ότι δεν υπάρχουν κενά ή σχόλια JSX εδώ
        <table className="candidate-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Name</th>
              <th>Owner User ID</th>
              <th>Users</th>
              <th>Candidates</th>
              <th>Created At</th>
            </tr>
          </thead>
          <tbody>
            {companies.map((company) => (
              <tr key={company.id}>
                <td>{company.id}</td>
                <td>{company.name}</td>
                <td>{company.owner_user_id || 'N/A'}</td>
                <td>{company.user_count !== undefined ? company.user_count : 'N/A'}</td>
                <td>{company.candidate_count !== undefined ? company.candidate_count : 'N/A'}</td>
                <td>{company.created_at ? new Date(company.created_at).toLocaleDateString() : 'N/A'}</td>
              </tr>
            ))}
          </tbody>
        </table>
        // --- ΤΕΛΟΣ ΠΙΘΑΝΗΣ ΔΙΟΡΘΩΣΗΣ ---
      )}
    </div>
  );
}

export default AdminCompaniesPage;