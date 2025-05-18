// frontend/src/components/StatisticsDisplay.jsx
import React from 'react';
// import './StatisticsDisplay.css';

function StatisticsDisplay({ stats, isLoading }) {
  console.log('StatisticsDisplay props received, stats:', stats, 'isLoading:', isLoading); 
  
  if (isLoading) {
      console.log('StatisticsDisplay: Rendering loading placeholders.');
      return (
        <div className="statistics-text-items" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem' }}>
            <div className="stat-item-placeholder"><h4>Loading...</h4><p>-</p></div>
            {/* Μπορείς να προσθέσεις κι άλλα placeholders αν περιμένεις περισσότερα stats */}
        </div>
      );
  }

  // Έλεγξε αν το stats είναι null/undefined ή αν το open_positions_count είναι undefined
  if (!stats || stats.open_positions_count === undefined) {
    // Αν περιμένεις κι άλλα stats, πρόσθεσέ τα στον έλεγχο:
    // if (!stats || (stats.open_positions_count === undefined && stats.another_stat === undefined)) {
    console.log('StatisticsDisplay: No specific statistics (like open_positions_count) to display or stats object is missing expected keys.');
    return (
      <div className="statistics-text-items">
        <p style={{ textAlign: 'center', color: '#666', marginTop: '1rem' }}>
            No key statistics to display at the moment.
        </p>
      </div>
    );
  }

  return (
    <div className="statistics-text-items" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem' }}>
      
      {stats.open_positions_count !== undefined && (
        <div className="stat-item">
          <h4>Open Positions</h4>
          <p className="stat-value">
            {stats.open_positions_count}
          </p>
        </div>
      )}

      {/* Παραδείγματα για μελλοντικά στατιστικά - προς το παρόν θα είναι σχολιασμένα */}
      {/* {stats.interview_reach_percentage !== undefined && (
        <div className="stat-item">
          <h4>Interview Reach</h4>
          <p className="stat-value">
            {stats.interview_reach_percentage}%
          </p>
          <small>(Of total candidates)</small>
        </div>
      )}

      {stats.avg_days_to_interview !== undefined && (
        <div className="stat-item">
          <h4>Avg. Time to Interview</h4>
          <p className="stat-value">
            {stats.avg_days_to_interview}
            {stats.avg_days_to_interview !== "N/A" ? " days" : ""}
          </p>
          <small>(From submission)</small>
        </div>
      )} */}
    </div>
  );
}

export default StatisticsDisplay;