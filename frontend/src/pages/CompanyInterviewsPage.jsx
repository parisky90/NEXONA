// frontend/src/pages/CompanyInterviewsPage.jsx
import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../App';
import { getCompanyInterviews } from '../services/companyAdminService';
// import './CompanyInterviewsPage.css'; // Φτιάξε CSS αν χρειάζεται

function CompanyInterviewsPage() {
  const { currentUser } = useAuth();
  const [interviews, setInterviews] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  // Πρόσθεσε pagination state αν χρειάζεται

  const fetchInterviews = useCallback(async () => {
    if (!currentUser) return;
    setIsLoading(true);
    setError('');
    try {
      // Ο superadmin θα πρέπει να μπορεί να δει αυτό το route αν του δώσεις company_id ως param
      const params = {};
      if (currentUser.role === 'superadmin' && currentUser.viewing_company_id) { // Παράδειγμα
         params.company_id = currentUser.viewing_company_id;
      }

      const data = await getCompanyInterviews(params);
      setInterviews(data.interviews || []);
    } catch (err) {
      setError(err.error || err.message || 'Failed to load interviews.');
    } finally {
      setIsLoading(false);
    }
  }, [currentUser]);

  useEffect(() => {
    fetchInterviews();
  }, [fetchInterviews]);

  if (isLoading) return <div className="loading-placeholder card-style">Loading interviews...</div>;
  if (error) return <div className="error-message card-style">{error}</div>;

  return (
    <div className="company-interviews-page card-style">
      <h1>Company Interviews</h1>
      {interviews.length === 0 ? (
        <p>No interviews found for this company.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Candidate</th>
              <th>Position</th>
              <th>Status</th>
              <th>Scheduled For</th>
              <th>Recruiter</th>
              {/* Add more columns as needed */}
            </tr>
          </thead>
          <tbody>
            {interviews.map(interview => (
              <tr key={interview.id}>
                <td>{interview.candidate_name || 'N/A'}</td>
                <td>{interview.position_name || 'N/A'}</td>
                <td><span className={`status-badge status-${interview.status?.toLowerCase()}`}>{interview.status || 'N/A'}</span></td>
                <td>{interview.scheduled_start_time ? new Date(interview.scheduled_start_time).toLocaleString() : 'Not Scheduled'}</td>
                <td>{interview.recruiter_name || 'N/A'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
export default CompanyInterviewsPage;