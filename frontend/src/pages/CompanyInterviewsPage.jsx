// frontend/src/pages/CompanyInterviewsPage.jsx
import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../App';
import { getCompanyInterviews } from '../services/companyAdminService';
// import './CompanyInterviewsPage.css'; 

function CompanyInterviewsPage() {
  const { currentUser } = useAuth();
  const [interviews, setInterviews] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [fetchCount, setFetchCount] = useState(0); // Μετρητής κλήσεων

  const fetchInterviews = useCallback(async () => {
    setFetchCount(prev => prev + 1); // Αύξηση μετρητή
    const currentFetchAttempt = fetchCount + 1; // Για το log
    console.log(`CompanyInterviewsPage: fetchInterviews attempt #${currentFetchAttempt} - START. currentUser:`, currentUser);

    if (!currentUser) {
      console.warn(`CompanyInterviewsPage: fetchInterviews attempt #${currentFetchAttempt} - currentUser is null, skipping fetch.`);
      setIsLoading(false); // Σταμάτα το loading αν δεν υπάρχει χρήστης
      return;
    }
    // Για company admin, το company_id θα ληφθεί από το session στο backend.
    // Για superadmin, θα πρέπει να περάσουμε company_id αν θέλουμε φιλτράρισμα.
    const params = {};
    if (currentUser.role === 'superadmin') {
        // Προς το παρόν, ο superadmin θα παίρνει 400 αν δεν στείλει company_id,
        // όπως είναι η λογική στο backend. Αυτό θα το φτιάξουμε αργότερα με επιλογή εταιρείας.
        // Αν θέλουμε να ΤΕΣΤΑΡΟΥΜΕ τον superadmin εδώ, πρέπει να βάλουμε ένα company_id χειροκίνητα:
        // params.company_id = 1; // ΠΡΟΣΟΧΗ: ΑΥΤΟ ΕΙΝΑΙ ΜΟΝΟ ΓΙΑ ΤΕΣΤ
        console.log(`CompanyInterviewsPage: fetchInterviews attempt #${currentFetchAttempt} - Superadmin viewing. Params for API:`, params);
    } else if (currentUser.role === 'company_admin') {
        console.log(`CompanyInterviewsPage: fetchInterviews attempt #${currentFetchAttempt} - Company admin viewing. Params for API:`, params);
    }


    setIsLoading(true);
    setError('');
    try {
      const data = await getCompanyInterviews(params);
      console.log(`CompanyInterviewsPage: fetchInterviews attempt #${currentFetchAttempt} - Data fetched SUCCESFULLY:`, data);
      setInterviews(data.interviews || []);
    } catch (err) {
      console.error(`CompanyInterviewsPage: fetchInterviews attempt #${currentFetchAttempt} - ERROR fetching interviews:`, err.response?.data || err.message || err, "Full error object:", err);
      setError(err.response?.data?.error || err.message || 'Failed to load interviews.');
      setInterviews([]); // Καθάρισε τις συνεντεύξεις σε περίπτωση σφάλματος
    } finally {
      setIsLoading(false);
      console.log(`CompanyInterviewsPage: fetchInterviews attempt #${currentFetchAttempt} - FINALLY block. isLoading set to false.`);
    }
  }, [currentUser, fetchCount]); // Προσθήκη fetchCount για να αναγκάσουμε το re-creation αν χρειαστεί

  useEffect(() => {
    console.log("CompanyInterviewsPage: useEffect triggered. Current user:", currentUser);
    // Καλούμε το fetchInterviews μόνο αν υπάρχει currentUser για να αποφύγουμε περιττές κλήσεις
    if (currentUser) {
        fetchInterviews();
    } else {
        setIsLoading(false); // Αν δεν υπάρχει χρήστης, δεν υπάρχει λόγος να είναι σε loading state
    }
  // Το fetchInterviews θα αλλάξει μόνο αν αλλάξει το currentUser, οπότε δεν χρειάζεται να είναι στις εξαρτήσεις το fetchCount
  // eslint-disable-next-line react-hooks/exhaustive-deps 
  }, [currentUser]); 

  if (isLoading) return <div className="loading-placeholder card-style">Loading interviews...</div>;
  
  if (!isLoading && error) return <div className="error-message card-style">{error}</div>;

  return (
    <div className="company-interviews-page card-style">
      <h1>Company Interviews</h1>
      {!isLoading && !error && interviews.length === 0 ? (
        <p>No interviews found for this company.</p>
      ) : !isLoading && !error && interviews.length > 0 ? (
        <table>
          <thead>
            <tr>
              <th>Candidate</th>
              <th>Position</th>
              <th>Status</th>
              <th>Scheduled For</th>
              <th>Recruiter</th>
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
      ) : null}
    </div>
  );
}
export default CompanyInterviewsPage;