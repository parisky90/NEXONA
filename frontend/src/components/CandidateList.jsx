import React from 'react';
import { useNavigate } from 'react-router-dom';
import './CandidateList.css'; // Styles for the list/table

// Helper function για να δίνει κείμενο & κλάση CSS στο confirmation status
const getConfirmationStatusInfo = (confirmationStatus) => {
    switch (confirmationStatus) {
        case 'Confirmed':
            return { text: 'Επιβεβαιώθηκε', className: 'status-confirmed' };
        case 'Declined':
             return { text: 'Απορρίφθηκε / Αλλαγή', className: 'status-declined' };
        case 'Pending':
             return { text: 'Αναμονή Απάντησης', className: 'status-pending' };
        default:
             // Επιστρέφει null αν δεν υπάρχει status (π.χ., δεν έχει οριστεί συνέντευξη)
             // ώστε να μην εμφανίζεται τίποτα.
             return null;
    }
};


// Expects list of candidates, loading state, and error state
function CandidateList({ candidates, isLoading, error, listTitle = "Candidates" }) {
  const navigate = useNavigate();

  const handleRowClick = (candidateId) => {
    navigate(`/candidate/${candidateId}`);
  };

  // Δεν χρειάζεται να ελέγχουμε isLoading/error/empty εδώ,
  // καθώς το γονικό component (CandidateListPage) το χειρίζεται ήδη.
  // Απλά επιστρέφουμε null αν δεν υπάρχουν υποψήφιοι.
  if (!candidates || candidates.length === 0) {
    // Το μήνυμα "No candidates found" εμφανίζεται ήδη στο CandidateListPage
    return null;
  }


  return (
    <div className="candidate-list-container">
      <h3>{listTitle}</h3>
      <div className="table-responsive"> {/* Add responsive wrapper */}
        <table className="candidate-table">
          <thead>
            <tr>
              <th>Όνομα</th>
              <th>Θέση(εις)</th>
              <th>Ημ/νία Υποβολής</th>
              <th>Ημ/νία Συνέντευξης</th> {/* Προσθήκη στήλης Συνέντευξης */}
              <th>Κατάσταση Επιβεβαίωσης</th> {/* ΝΕΑ ΣΤΗΛΗ */}
              <th>Status</th>
              {/* Add more columns if needed */}
            </tr>
          </thead>
          <tbody>
            {candidates.map((candidate) => {
              // Λήψη πληροφορίας status επιβεβαίωσης
              const confirmationInfo = getConfirmationStatusInfo(candidate.candidate_confirmation_status);

              return (
                <tr key={candidate.candidate_id} onClick={() => handleRowClick(candidate.candidate_id)} className="clickable-row">
                  <td>{candidate.full_name || 'N/A'}</td>
                  <td>{Array.isArray(candidate.positions) ? candidate.positions.join(', ') : 'N/A'}</td>{/* Handle array */}
                  <td>{candidate.submission_date ? new Date(candidate.submission_date).toLocaleDateString() : 'N/A'}</td>
                  {/* Εμφάνιση Ημ/νίας Συνέντευξης */}
                  <td>
                    {candidate.interview_datetime ? new Date(candidate.interview_datetime).toLocaleString([], { year: 'numeric', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit'}) : '-'}
                    {candidate.interview_location && ` @ ${candidate.interview_location}`}
                  </td>
                  {/* Εμφάνιση Status Επιβεβαίωσης */}
                  <td>
                    {candidate.interview_datetime && confirmationInfo && ( // Εμφάνιση μόνο αν υπάρχει συνέντευξη ΚΑΙ status
                      <span className={`status-badge ${confirmationInfo.className}`}>
                        {confirmationInfo.text}
                      </span>
                    )}
                  </td>
                  {/* Status Υποψηφίου */}
                  <td>
                    <span className={`status-badge status-${candidate.current_status?.toLowerCase().replace(/\s+/g, '-')}`}> {/* Replace spaces for CSS */}
                      {candidate.current_status || 'N/A'}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default CandidateList;