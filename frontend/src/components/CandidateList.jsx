// frontend/src/components/CandidateList.jsx
import React, { useState, useMemo } from 'react'; // Πρόσθεσα useMemo
import { useNavigate } from 'react-router-dom';
import apiClient from '../api';
import './CandidateList.css';

const getConfirmationStatusInfo = (confirmationStatus) => {
    switch (confirmationStatus) {
        case 'Confirmed': return { text: 'Επιβεβαιώθηκε', className: 'status-confirmed' };
        case 'Declined': return { text: 'Απορρίφθηκε / Αλλαγή', className: 'status-declined' };
        case 'Pending': return { text: 'Αναμονή Απάντησης', className: 'status-pending' };
        default: return null;
    }
};

// Οι ίδιες επιλογές με το CandidateDetailPage - ιδανικά σε κοινό αρχείο
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
    return option ? option.order : 99;
};

function CandidateList({ candidates, listTitle = "Candidates", onCandidateDeleted }) {
  const navigate = useNavigate();
  const [sortConfig, setSortConfig] = useState({ key: 'submission_date', direction: 'descending' });

  const handleRowClick = (candidateId) => { navigate(`/candidate/${candidateId}`); };

  const handleDeleteCandidate = async (candidateId, candidateName, event) => {
    event.stopPropagation();
    if (window.confirm(`Are you sure you want to permanently delete candidate: ${candidateName || candidateId}? This action cannot be undone.`)) {
      try {
        await apiClient.delete(`/candidate/${candidateId}`);
        if (onCandidateDeleted) { onCandidateDeleted(candidateId); }
        alert(`Candidate ${candidateName || candidateId} deleted successfully.`);
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

  const sortedCandidates = useMemo(() => { // Χρήση useMemo
    let sortableItems = [...candidates];
    if (sortConfig.key !== null) {
      sortableItems.sort((a, b) => {
        let valA = a[sortConfig.key];
        let valB = b[sortConfig.key];

        if (sortConfig.key === 'evaluation_rating') {
            valA = getRatingOrder(a.evaluation_rating);
            valB = getRatingOrder(b.evaluation_rating);
        } else if (sortConfig.key === 'submission_date' || sortConfig.key === 'interview_datetime') {
            valA = a[sortConfig.key] ? new Date(a[sortConfig.key]) : new Date(0);
            valB = b[sortConfig.key] ? new Date(b[sortConfig.key]) : new Date(0);
            if (isNaN(valA.getTime())) valA = new Date(0);
            if (isNaN(valB.getTime())) valB = new Date(0);
        } else if (typeof valA === 'string' && typeof valB === 'string') {
            valA = valA.toLowerCase();
            valB = valB.toLowerCase();
        }

        if (valA < valB) { return sortConfig.direction === 'ascending' ? -1 : 1; }
        if (valA > valB) { return sortConfig.direction === 'ascending' ? 1 : -1; }
        return 0;
      });
    }
    return sortableItems;
  }, [candidates, sortConfig]);

  const getSortIndicator = (columnKey) => {
    if (sortConfig.key === columnKey) {
      return sortConfig.direction === 'ascending' ? ' ▲' : ' ▼';
    }
    return '';
  };

  if (!candidates || candidates.length === 0) { return null; }

  return (
    <div className="candidate-list-container">
      <h3>{listTitle}</h3>
      <div className="table-responsive">
        <table className="candidate-table">
          <thead>
            <tr>
              <th onClick={() => requestSort('full_name')} className="sortable-header">Όνομα{getSortIndicator('full_name')}</th>
              <th onClick={() => requestSort('positions')} className="sortable-header">Θέση(εις){getSortIndicator('positions')}</th>
              <th onClick={() => requestSort('evaluation_rating')} className="sortable-header" style={{textAlign: 'center'}}>Rating (HR){getSortIndicator('evaluation_rating')}</th>
              <th onClick={() => requestSort('interview_datetime')} className="sortable-header">Ημ/νία Συνέντευξης{getSortIndicator('interview_datetime')}</th>
              <th>Κατάσταση Επιβεβαίωσης</th>
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
                  <td>{Array.isArray(candidate.positions) ? candidate.positions.join(', ') : 'N/A'}</td>
                  <td style={{textAlign: 'center', fontWeight: 'bold'}}>
                    {getRatingLabelForList(candidate.evaluation_rating)}
                  </td>
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
                  <td onClick={(e) => e.stopPropagation()} style={{textAlign: 'center', minWidth: '100px'}}>
                    <button
                      onClick={(e) => handleDeleteCandidate(candidate.candidate_id, candidate.full_name, e)}
                      className="button-action button-reject"
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