import React from 'react';
import { useNavigate } from 'react-router-dom';
import './CandidateList.css'; // Styles for the list/table

// Expects list of candidates, loading state, and error state
function CandidateList({ candidates, isLoading, error, listTitle = "Candidates" }) {
  const navigate = useNavigate();

  const handleRowClick = (candidateId) => {
    navigate(`/candidate/${candidateId}`);
  };

  if (isLoading) {
    return <div className="candidate-list-status loading-placeholder">Loading candidates...</div>; // Use placeholder class
  }

  if (error) {
    return <div className="candidate-list-status error">Error loading candidates: {error}</div>;
  }

  if (!candidates || candidates.length === 0) {
    return <div className="candidate-list-status">No candidates found for this status.</div>;
  }

  return (
    <div className="candidate-list-container">
      <h3>{listTitle}</h3>
      <table className="candidate-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Position(s)</th>
            <th>Submission Date</th>
            <th>Status</th>
            {/* Add more columns if needed */}
          </tr>
        </thead>
        <tbody>
          {candidates.map((candidate) => (
            <tr key={candidate.candidate_id} onClick={() => handleRowClick(candidate.candidate_id)} className="clickable-row">
              <td>{candidate.full_name || 'N/A'}</td>
              <td>{Array.isArray(candidate.positions) ? candidate.positions.join(', ') : 'N/A'}</td>{/* Handle array */}
              <td>{candidate.submission_date ? new Date(candidate.submission_date).toLocaleDateString() : 'N/A'}</td>
              <td>
                 {/* Use status badge styling */}
                 <span className={`status-badge status-${candidate.current_status?.toLowerCase()}`}>
                    {candidate.current_status || 'N/A'}
                 </span>
                </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default CandidateList;