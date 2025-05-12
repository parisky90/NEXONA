// frontend/src/components/CandidateList.jsx
import React from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient from '../api'; // Import apiClient
import './CandidateList.css';

// Helper function για το confirmation status (αντιγραφή από CandidateDetailPage ή import από utils)
const getConfirmationStatusInfo = (confirmationStatus) => {
    switch (confirmationStatus) {
        case 'Confirmed': return { text: 'Επιβεβαιώθηκε', className: 'status-confirmed' };
        case 'Declined': return { text: 'Απορρίφθηκε / Αλλαγή', className: 'status-declined' };
        case 'Pending': return { text: 'Αναμονή Απάντησης', className: 'status-pending' };
        default: return null;
    }
};

function CandidateList({ candidates, listTitle = "Candidates", onCandidateDeleted }) {
  const navigate = useNavigate();

  const handleRowClick = (candidateId) => {
    navigate(`/candidate/${candidateId}`);
  };

  const handleDeleteCandidate = async (candidateId, candidateName, event) => {
    event.stopPropagation(); // Αποτροπή του event bubbling στο tr
    if (window.confirm(`Are you sure you want to permanently delete candidate: ${candidateName || candidateId}? This action cannot be undone.`)) {
      try {
        await apiClient.delete(`/candidate/${candidateId}`);
        if (onCandidateDeleted) {
          onCandidateDeleted(candidateId); // Ενημέρωση του γονικού component
        }
        // Εδώ μπορείς να προσθέσεις toast notification για επιτυχία
        alert(`Candidate ${candidateName || candidateId} deleted successfully.`);
      } catch (err) {
        console.error("Error deleting candidate:", err);
        alert(err.response?.data?.error || "Failed to delete candidate. Please try again.");
      }
    }
  };

  if (!candidates || candidates.length === 0) {
    return null; // Το μήνυμα "No candidates" χειρίζεται από το CandidateListPage
  }

  return (
    <div className="candidate-list-container">
      <h3>{listTitle}</h3>
      <div className="table-responsive">
        <table className="candidate-table">
          <thead>
            <tr>
              <th>Όνομα</th>
              <th>Θέση(εις)</th>
              <th>Ημ/νία Υποβολής</th>
              <th>Ημ/νία Συνέντευξης</th>
              <th>Κατάσταση Επιβεβαίωσης</th>
              <th>Status</th>
              <th style={{textAlign: 'center'}}>Actions</th> {/* ΝΕΑ ΣΤΗΛΗ */}
            </tr>
          </thead>
          <tbody>
            {candidates.map((candidate) => {
              const confirmationInfo = getConfirmationStatusInfo(candidate.candidate_confirmation_status);
              return (
                <tr key={candidate.candidate_id} onClick={() => handleRowClick(candidate.candidate_id)} className="clickable-row">
                  <td>{candidate.full_name || 'N/A'}</td>
                  <td>{Array.isArray(candidate.positions) ? candidate.positions.join(', ') : 'N/A'}</td>
                  <td>{candidate.submission_date ? new Date(candidate.submission_date).toLocaleDateString() : 'N/A'}</td>
                  <td>
                    {candidate.interview_datetime ? new Date(candidate.interview_datetime).toLocaleString([], { year: 'numeric', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit'}) : '-'}
                    {candidate.interview_location && ` @ ${candidate.interview_location}`}
                  </td>
                  <td>
                    {candidate.interview_datetime && confirmationInfo && confirmationInfo.text && (
                      <span className={`status-badge ${confirmationInfo.className}`}>
                        {confirmationInfo.text}
                      </span>
                    )}
                  </td>
                  <td>
                    <span className={`status-badge status-${candidate.current_status?.toLowerCase().replace(/\s+/g, '-')}`}>
                      {candidate.current_status || 'N/A'}
                    </span>
                  </td>
                  {/* --- ΚΟΥΜΠΙ DELETE --- */}
                  <td onClick={(e) => e.stopPropagation()} style={{textAlign: 'center', minWidth: '100px'}}>
                    <button
                      onClick={(e) => handleDeleteCandidate(candidate.candidate_id, candidate.full_name, e)}
                      className="button-action button-reject" // Χρησιμοποίησε το στυλ του reject
                      title={`Delete ${candidate.full_name || 'candidate'}`}
                    >
                      Delete
                    </button>
                  </td>
                  {/* --- ΤΕΛΟΣ ΚΟΥΜΠΙΟΥ DELETE --- */}
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