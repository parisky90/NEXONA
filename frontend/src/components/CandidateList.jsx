// frontend/src/components/CandidateList.jsx
import React, { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient from '../api';
import './CandidateList.css';

// Helper για την κατάσταση επιβεβαίωσης συνέντευξης (από CandidateDetailPage)
const getCandidateConfirmationStatusInfo = (confirmationStatus) => {
    if (!confirmationStatus) return null; // Επιστροφή null αν δεν υπάρχει status
    switch (confirmationStatus) {
        case 'Confirmed': return { text: 'Confirmed', className: 'status-confirmed' };
        case 'DeclinedSlots': return { text: 'Declined Slots', className: 'status-declined-slots' };
        case 'CancelledByUser': return { text: 'Cand. Cancelled', className: 'status-cancelled-user' }; // Συντομευμένο
        case 'RecruiterCancelled': return { text: 'Rec. Cancelled', className: 'status-cancelled-recruiter' }; // Συντομευμένο
        case 'Pending': return { text: 'Pending Resp.', className: 'status-pending' }; // Συντομευμένο
        default: return { text: confirmationStatus, className: 'status-unknown' }; // Εμφάνισε το status αν είναι κάτι άλλο
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

const formatObjectListNames = (objectList, nameKey = 'name') => {
    if (!objectList || !Array.isArray(objectList) || objectList.length === 0) {
        return '-';
    }
    return objectList.map(item => item && item[nameKey] ? item[nameKey] : 'Unnamed').join(', ');
};

// Helper για την ημερομηνία
const formatInterviewDate = (isoString) => {
    if (!isoString) return '-';
    try {
        return new Date(isoString).toLocaleString([], {
            month: 'numeric', day: 'numeric',
            hour: '2-digit', minute: '2-digit' // Πιο σύντομη μορφή για τη λίστα
        });
    } catch { return 'Invalid Date'; }
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
        let valA, valB;

        // Ειδικός χειρισμός για πεδία που μπορεί να είναι σε related objects
        if (sortConfig.key === 'interview_date') {
            const latestInterviewA = a.interviews?.find(iv => iv.status === 'SCHEDULED');
            valA = latestInterviewA?.scheduled_start_time ? new Date(latestInterviewA.scheduled_start_time) : new Date(0);
            const latestInterviewB = b.interviews?.find(iv => iv.status === 'SCHEDULED');
            valB = latestInterviewB?.scheduled_start_time ? new Date(latestInterviewB.scheduled_start_time) : new Date(0);
        } else if (sortConfig.key === 'confirmation') {
            valA = a.candidate_confirmation_status || '';
            valB = b.candidate_confirmation_status || '';
        } else {
            valA = a[sortConfig.key];
            valB = b[sortConfig.key];
        }

        if (sortConfig.key === 'evaluation_rating') {
            valA = getRatingOrder(a.evaluation_rating);
            valB = getRatingOrder(b.evaluation_rating);
        } else if (sortConfig.key === 'submission_date' || sortConfig.key === 'interview_date') { // 'interview_date' χειρίζεται παραπάνω
            if (sortConfig.key !== 'interview_date') { // Για submission_date
                 valA = a[sortConfig.key] ? new Date(a[sortConfig.key]) : new Date(0);
                 valB = b[sortConfig.key] ? new Date(b[sortConfig.key]) : new Date(0);
            }
            if (valA && isNaN(valA.getTime())) valA = new Date(0);
            if (valB && isNaN(valB.getTime())) valB = new Date(0);
        } else if (sortConfig.key === 'positions') {
            valA = (a.positions && a.positions.length > 0 && a.positions[0].position_name) ? a.positions[0].position_name.toLowerCase() : '';
            valB = (b.positions && b.positions.length > 0 && b.positions[0].position_name) ? b.positions[0].position_name.toLowerCase() : '';
        } else if (sortConfig.key === 'branches') {
            valA = (a.branches && a.branches.length > 0 && a.branches[0].name) ? a.branches[0].name.toLowerCase() : '';
            valB = (b.branches && b.branches.length > 0 && b.branches[0].name) ? b.branches[0].name.toLowerCase() : '';
        } else if (typeof valA === 'string' && typeof valB === 'string') {
            valA = valA.toLowerCase();
            valB = valB.toLowerCase();
        }

        // Χειρισμός null/undefined για αριθμητικές/ημερομηνίες μετά τη μετατροπή
        if (valA === null || valA === undefined || (valA instanceof Date && valA.getTime() === new Date(0).getTime())) {
            return sortConfig.direction === 'ascending' ? 1 : -1; // Βάζει τα null/κενά στο τέλος όταν ανεβαίνει
        }
        if (valB === null || valB === undefined || (valB instanceof Date && valB.getTime() === new Date(0).getTime())) {
            return sortConfig.direction === 'ascending' ? -1 : 1; // Βάζει τα null/κενά στην αρχή όταν ανεβαίνει
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
              <th onClick={() => requestSort('branches')} className="sortable-header">Branch(es){getSortIndicator('branches')}</th>
              <th onClick={() => requestSort('evaluation_rating')} className="sortable-header" style={{textAlign: 'center'}}>Rating (HR){getSortIndicator('evaluation_rating')}</th>
              <th onClick={() => requestSort('interview_date')} className="sortable-header">Interview Date{getSortIndicator('interview_date')}</th>
              <th onClick={() => requestSort('confirmation')} className="sortable-header">Confirmation{getSortIndicator('confirmation')}</th>
              <th onClick={() => requestSort('current_status')} className="sortable-header">Status{getSortIndicator('current_status')}</th>
              <th style={{textAlign: 'center'}}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {sortedCandidates.map((candidate) => {
              // Βρες την πιο πρόσφατη προγραμματισμένη συνέντευξη (αν υπάρχει)
              // Υποθέτουμε ότι το backend στέλνει τις συνεντεύξεις ταξινομημένες (π.χ. created_at desc)
              // ή μπορούμε να τις ταξινομήσουμε εδώ. Για απλότητα, παίρνουμε την πρώτη SCHEDULED.
              const latestScheduledInterview = candidate.interviews?.find(
                (iv) => iv.status === 'SCHEDULED' && iv.scheduled_start_time
              );

              const confirmationInfo = getCandidateConfirmationStatusInfo(candidate.candidate_confirmation_status);

              return (
                <tr key={candidate.candidate_id} onClick={() => handleRowClick(candidate.candidate_id)} className="clickable-row">
                  <td>{candidate.full_name || 'N/A'}</td>
                  <td>{formatObjectListNames(candidate.positions, 'position_name')}</td>
                  <td>{formatObjectListNames(candidate.branches, 'name')}</td>
                  <td style={{textAlign: 'center', fontWeight: 'bold'}}>
                    {getRatingLabelForList(candidate.evaluation_rating)}
                  </td>
                  <td>
                    {latestScheduledInterview
                      ? formatInterviewDate(latestScheduledInterview.scheduled_start_time)
                      : '-'
                    }
                    {latestScheduledInterview && latestScheduledInterview.location && ` @ ${latestScheduledInterview.location}`}
                  </td>
                  <td>
                    {/* Εμφάνισε το confirmation status του υποψηφίου αν υπάρχει προγραμματισμένη συνέντευξη */}
                    {latestScheduledInterview && confirmationInfo && confirmationInfo.text && (
                      <span className={`status-badge ${confirmationInfo.className}`}>
                        {confirmationInfo.text}
                      </span>
                    )}
                    {/* Αν δεν υπάρχει προγραμματισμένη συνέντευξη αλλά υπάρχει γενικό confirmation status, δείξτο (λιγότερο πιθανό σενάριο) */}
                    {!latestScheduledInterview && confirmationInfo && confirmationInfo.text && (
                         <span className={`status-badge ${confirmationInfo.className}`}>
                            {confirmationInfo.text} (No Sched. IV)
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