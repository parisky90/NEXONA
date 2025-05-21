// frontend/src/components/CandidateList.jsx
import React, { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient from '../api';
import './CandidateList.css';

const getConfirmationStatusInfo = (confirmationStatus) => {
    switch (confirmationStatus) {
        case 'Confirmed': return { text: 'Confirmed', className: 'status-confirmed' };
        case 'Declined': return { text: 'Declined', className: 'status-declined' }; // Assuming this is for interview slots
        case 'DeclinedSlots': return { text: 'Declined Slots', className: 'status-declined-slots' };
        case 'Pending': return { text: 'Pending', className: 'status-pending' };
        default: return null;
    }
};

const RATING_OPTIONS_FOR_DISPLAY = [
    { value: 'Teleio', label: 'Τέλειο', order: 1 },
    { value: 'Polu Kalo', label: 'Πολύ Καλό', order: 2 },
    { value: 'Kalo', label: 'Καλό', order: 3 },
    { value: 'Metrio', label: 'Μέτριο', order: 4 },
    { value: 'Kako', label: 'Κακό', order: 5 },
    { value: 'Polu Kako', label: 'Πολύ Κακό', order: 6 },
    { value: '', label: '-', order: 99 },
];

const getRatingLabelForList = (value) => {
    const option = RATING_OPTIONS_FOR_DISPLAY.find(opt => opt.value === value);
    return option ? option.label : (value || '-');
};

const getRatingOrder = (value) => {
    const option = RATING_OPTIONS_FOR_DISPLAY.find(opt => opt.value === value);
    return option ? option.order : 99;
};

// Helper function to format a list of objects (branches or positions) into a string of names/titles
const formatObjectListNames = (objectList, nameKey = 'name') => {
    if (!objectList || !Array.isArray(objectList) || objectList.length === 0) {
        return '-';
    }
    return objectList.map(item => item[nameKey] || 'Unnamed').join(', ');
};


function CandidateList({ candidates, listTitle = "Candidates", onCandidateDeleted }) {
  const navigate = useNavigate();
  const [sortConfig, setSortConfig] = useState({ key: 'submission_date', direction: 'descending' });

  const handleRowClick = (candidateId) => {
    navigate(`/candidate/${candidateId}`);
  };

  const handleDeleteCandidate = async (candidateId, candidateName, event) => {
    event.stopPropagation();
    if (window.confirm(`Are you sure you want to permanently delete candidate: ${candidateName || candidateId}? This action cannot be undone.`)) {
      try {
        await apiClient.delete(`/candidate/${candidateId}`);
        if (onCandidateDeleted) {
          onCandidateDeleted(candidateId);
        }
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
    if (!candidates || !Array.isArray(candidates)) {
        return [];
    }
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
        } else if (sortConfig.key === 'positions') { // Ταξινόμηση βάσει του πρώτου position name
            valA = (a.positions && a.positions.length > 0 && a.positions[0].position_name) ? a.positions[0].position_name.toLowerCase() : '';
            valB = (b.positions && b.positions.length > 0 && b.positions[0].position_name) ? b.positions[0].position_name.toLowerCase() : '';
        } else if (sortConfig.key === 'branches') { // Ταξινόμηση βάσει του πρώτου branch name
            valA = (a.branches && a.branches.length > 0 && a.branches[0].name) ? a.branches[0].name.toLowerCase() : '';
            valB = (b.branches && b.branches.length > 0 && b.branches[0].name) ? b.branches[0].name.toLowerCase() : '';
        } else if (typeof valA === 'string' && typeof valB === 'string') {
            valA = valA.toLowerCase();
            valB = valB.toLowerCase();
        } else if (valA === null || valA === undefined) {
            return sortConfig.direction === 'ascending' ? 1 : -1;
        } else if (valB === null || valB === undefined) {
            return sortConfig.direction === 'ascending' ? -1 : 1;
        }

        if (valA < valB) return sortConfig.direction === 'ascending' ? -1 : 1;
        if (valA > valB) return sortConfig.direction === 'ascending' ? 1 : -1;
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

  if (!candidates || candidates.length === 0) {
    return null;
  }

  return (
    <div className="candidate-list-container">
      {listTitle && <h3>{listTitle} ({sortedCandidates.length})</h3>}
      <div className="table-responsive">
        <table className="candidate-table">
          <thead>
            <tr>
              <th onClick={() => requestSort('full_name')} className="sortable-header">Name{getSortIndicator('full_name')}</th>
              <th onClick={() => requestSort('positions')} className="sortable-header">Position(s){getSortIndicator('positions')}</th>
              <th onClick={() => requestSort('branches')} className="sortable-header">Branch(es){getSortIndicator('branches')}</th> {/* ΝΕΑ ΣΤΗΛΗ */}
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
              // Το candidate.positions είναι πίνακας αντικειμένων [{position_id: X, position_name: "YYY"}, ...]
              // Το candidate.branches είναι πίνακας αντικειμένων [{id: X, name: "YYY"}, ...]
              return (
                <tr key={candidate.candidate_id} onClick={() => handleRowClick(candidate.candidate_id)} className="clickable-row">
                  <td>{candidate.full_name || 'N/A'}</td>
                  <td>{formatObjectListNames(candidate.positions, 'position_name')}</td>
                  <td>{formatObjectListNames(candidate.branches, 'name')}</td> {/* ΕΜΦΑΝΙΣΗ BRANCHES */}
                  <td style={{textAlign: 'center', fontWeight: 'bold'}}>
                    {getRatingLabelForList(candidate.evaluation_rating)}
                  </td>
                  <td>
                    {candidate.interview_datetime ? new Date(candidate.interview_datetime).toLocaleString([], { year: 'numeric', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit'}) : '-'}
                    {candidate.interview_datetime && candidate.interview_location && ` @ ${candidate.interview_location}`}
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