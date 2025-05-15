// frontend/src/components/CandidateList.jsx
import React, { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient from '../api'; // Για το delete
import './CandidateList.css';

// Helper για την κατάσταση επιβεβαίωσης συνέντευξης
const getConfirmationStatusInfo = (confirmationStatus) => {
    switch (confirmationStatus) {
        case 'Confirmed': return { text: 'Confirmed', className: 'status-confirmed' };
        case 'Declined': return { text: 'Declined', className: 'status-declined' };
        case 'Pending': return { text: 'Pending', className: 'status-pending' };
        default: return null; // Μην εμφανίζεις τίποτα αν δεν υπάρχει status
    }
};

// Helper για την εμφάνιση και ταξινόμηση του rating
const RATING_OPTIONS_FOR_DISPLAY = [
    { value: 'Teleio', label: 'Τέλειο', order: 1 },
    { value: 'Polu Kalo', label: 'Πολύ Καλό', order: 2 },
    { value: 'Kalo', label: 'Καλό', order: 3 },
    { value: 'Metrio', label: 'Μέτριο', order: 4 },
    { value: 'Kako', label: 'Κακό', order: 5 },
    { value: 'Polu Kako', label: 'Πολύ Κακό', order: 6 },
    { value: '', label: '-', order: 99 }, // Για κενές/N/A τιμές
];

const getRatingLabelForList = (value) => {
    const option = RATING_OPTIONS_FOR_DISPLAY.find(opt => opt.value === value);
    return option ? option.label : (value || '-');
};

const getRatingOrder = (value) => {
    const option = RATING_OPTIONS_FOR_DISPLAY.find(opt => opt.value === value);
    return option ? option.order : 99; // Βάλε τις μη ταξινομημένες τιμές στο τέλος
};


function CandidateList({ candidates, listTitle = "Candidates", onCandidateDeleted }) {
  const navigate = useNavigate();
  // Αρχική ταξινόμηση βάσει submission_date (πιο πρόσφατα πρώτα)
  const [sortConfig, setSortConfig] = useState({ key: 'submission_date', direction: 'descending' });

  const handleRowClick = (candidateId) => {
    navigate(`/candidate/${candidateId}`);
  };

  const handleDeleteCandidate = async (candidateId, candidateName, event) => {
    event.stopPropagation(); // Για να μην γίνει trigger το handleRowClick
    if (window.confirm(`Are you sure you want to permanently delete candidate: ${candidateName || candidateId}? This action cannot be undone.`)) {
      try {
        await apiClient.delete(`/candidate/${candidateId}`); // Κλήση στο backend API
        if (onCandidateDeleted) {
          onCandidateDeleted(candidateId); // Ενημέρωσε τη γονική σελίδα
        }
        // alert(`Candidate ${candidateName || candidateId} deleted successfully.`); // Προαιρετικό
      } catch (err) {
        console.error("Error deleting candidate:", err);
        alert(err.response?.data?.error || "Failed to delete candidate. Please try again.");
      }
    }
  };

  const requestSort = (key) => {
    let direction = 'ascending';
    if (sortConfig.key === key && sortConfig.direction === 'ascending') {
      direction = 'descending';
    }
    setSortConfig({ key, direction });
  };

  const sortedCandidates = useMemo(() => {
    if (!candidates || !Array.isArray(candidates)) { // Έλεγχos αν το candidates είναι πίνακας
        return [];
    }
    let sortableItems = [...candidates]; // Δημιουργία αντιγράφου για ταξινόμηση
    if (sortConfig.key !== null) {
      sortableItems.sort((a, b) => {
        let valA = a[sortConfig.key];
        let valB = b[sortConfig.key];

        // Ειδικός χειρισμός για το rating
        if (sortConfig.key === 'evaluation_rating') {
            valA = getRatingOrder(a.evaluation_rating);
            valB = getRatingOrder(b.evaluation_rating);
        }
        // Ειδικός χειρισμός για ημερομηνίες
        else if (sortConfig.key === 'submission_date' || sortConfig.key === 'interview_datetime') {
            // Χειρισμός null/undefined ημερομηνιών για να μην σπάει η ταξινόμηση
            valA = a[sortConfig.key] ? new Date(a[sortConfig.key]) : new Date(0); // Βάλε μια πολύ παλιά ημερομηνία για null
            valB = b[sortConfig.key] ? new Date(b[sortConfig.key]) : new Date(0);
            if (isNaN(valA.getTime())) valA = new Date(0); // Extra check for invalid dates
            if (isNaN(valB.getTime())) valB = new Date(0);
        }
        // Για strings, κάνε ταξινόμηση case-insensitive
        else if (typeof valA === 'string' && typeof valB === 'string') {
            valA = valA.toLowerCase();
            valB = valB.toLowerCase();
        } else if (valA === null || valA === undefined) { // null/undefined τιμές στο τέλος (ή αρχή)
            return sortConfig.direction === 'ascending' ? 1 : -1;
        } else if (valB === null || valB === undefined) {
            return sortConfig.direction === 'ascending' ? -1 : 1;
        }


        if (valA < valB) {
          return sortConfig.direction === 'ascending' ? -1 : 1;
        }
        if (valA > valB) {
          return sortConfig.direction === 'ascending' ? 1 : -1;
        }
        return 0; // Αν είναι ίσα
      });
    }
    return sortableItems;
  }, [candidates, sortConfig]);

  const getSortIndicator = (columnKey) => {
    if (sortConfig.key === columnKey) {
      return sortConfig.direction === 'ascending' ? ' ▲' : ' ▼';
    }
    return ''; // Κενό αν δεν είναι η ταξινομημένη στήλη
  };


  // Μην κάνεις render τίποτα αν δεν υπάρχουν candidates (το χειρίζεται η γονική σελίδα)
  if (!candidates || candidates.length === 0) {
    return null; // Η γονική σελίδα (CandidateListPage/DashboardPage) θα δείξει το "No candidates..."
  }

  return (
    <div className="candidate-list-container">
      <h3>{listTitle} ({sortedCandidates.length})</h3> {/* Εμφάνισε τον αριθμό των υποψηφίων */}
      <div className="table-responsive">
        <table className="candidate-table">
          <thead>
            <tr>
              <th onClick={() => requestSort('full_name')} className="sortable-header">Name{getSortIndicator('full_name')}</th>
              <th onClick={() => requestSort('positions')} className="sortable-header">Position(s){getSortIndicator('positions')}</th>
              <th onClick={() => requestSort('evaluation_rating')} className="sortable-header" style={{textAlign: 'center'}}>Rating (HR){getSortIndicator('evaluation_rating')}</th>
              <th onClick={() => requestSort('interview_datetime')} className="sortable-header">Interview Date{getSortIndicator('interview_datetime')}</th>
              <th>Confirmation</th>
              <th onClick={() => requestSort('current_status')} className="sortable-header">Status{getSortIndicator('current_status')}</th>
              <th style={{textAlign: 'center'}}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {sortedCandidates.map((candidate) => {
              const confirmationInfo = getConfirmationStatusInfo(candidate.candidate_confirmation_status);
              return (
                <tr key={candidate.candidate_id} onClick={() => handleRowClick(candidate.candidate_id)} className="clickable-row">
                  <td>{candidate.full_name || 'N/A'}</td>
                  <td>{Array.isArray(candidate.positions) && candidate.positions.length > 0 ? candidate.positions.join(', ') : 'N/A'}</td>
                  <td style={{textAlign: 'center', fontWeight: 'bold'}}>
                    {getRatingLabelForList(candidate.evaluation_rating)}
                  </td>
                  <td>
                    {candidate.interview_datetime ? new Date(candidate.interview_datetime).toLocaleString([], { year: 'numeric', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit'}) : '-'}
                    {candidate.interview_datetime && candidate.interview_location && ` @ ${candidate.interview_location}`}
                  </td>
                  <td>
                    {/* Εμφάνισε το confirmation status μόνο αν υπάρχει προγραμματισμένη συνέντευξη */}
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
                  <td onClick={(e) => e.stopPropagation()} style={{textAlign: 'center', minWidth: '100px'}}>
                    <button
                      onClick={(e) => handleDeleteCandidate(candidate.candidate_id, candidate.full_name, e)}
                      className="button-action button-reject" // Χρησιμοποίησε το στυλ απόρριψης
                      title={`Delete ${candidate.full_name || 'candidate'}`}
                    >
                      Delete
                    </button>
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