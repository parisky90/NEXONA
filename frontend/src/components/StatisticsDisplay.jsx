// frontend/src/components/StatisticsDisplay.jsx
import React from 'react';
// import './StatisticsDisplay.css'; // Αν έχεις CSS για αυτό, βεβαιώσου ότι είναι συνδεδεμένο

function StatisticsDisplay({ stats, isLoading }) {
  if (isLoading) {
      return (
        <div className="statistics-text-items" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem' }}>
            {/* Placeholder items */}
            {[...Array(5)].map((_, i) => ( // Εμφάνιση 5 placeholders αν υπάρχουν 5 στατιστικά
                 <div key={i} className="stat-item-placeholder card-style" style={{padding: '1rem', textAlign:'center'}}>
                    <h4 style={{height: '1em', width: '70%', margin: '0 auto 0.5rem auto', backgroundColor:'#e9ecef', color:'#e9ecef', borderRadius:'4px'}}> </h4>
                    <p style={{height: '1.5em', width: '40%', margin: '0 auto', backgroundColor:'#e9ecef', color:'#e9ecef', borderRadius:'4px'}}> </p>
                    <small style={{height: '0.8em', width: '60%', margin: '0.25rem auto 0 auto', backgroundColor:'#f3f4f6', color:'#f3f4f6', borderRadius:'3px', display:'block'}}> </small>
                </div>
            ))}
        </div>
      );
  }

  const hasRelevantStats = stats && (
    stats.open_positions_count !== undefined ||
    stats.stuck_in_needs_review_X_days !== undefined ||
    stats.offer_acceptance_rate !== undefined ||
    stats.avg_days_in_needs_review !== undefined ||
    stats.interview_conversion_rate !== undefined
  );

  if (!hasRelevantStats) {
    return (
      <div className="statistics-text-items" style={{paddingTop: '1rem', paddingBottom: '1rem'}}>
        <p style={{ textAlign: 'center', color: 'var(--text-muted)', fontStyle: 'italic' }}>
            Δεν υπάρχουν διαθέσιμα βασικά στατιστικά στοιχεία αυτή τη στιγμή.
        </p>
      </div>
    );
  }

  return (
    <div className="statistics-text-items" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem' }}>

      {stats.open_positions_count !== undefined && (
        <div className="stat-item card-style">
          <h4>Ανοιχτές Θέσεις</h4>
          <p className="stat-value">
            {stats.open_positions_count}
          </p>
        </div>
      )}

      {stats.stuck_in_needs_review_X_days !== undefined && stats.stuck_in_needs_review_threshold_days !== undefined && (
        <div className="stat-item card-style">
          <h4>Σε Αναμονή ({'>'}{stats.stuck_in_needs_review_threshold_days} ημ.)</h4>
          <p className="stat-value">
            {stats.stuck_in_needs_review_X_days}
          </p>
          <small>Υποψήφιοι</small>
        </div>
      )}

      {stats.offer_acceptance_rate !== undefined && (
        <div className="stat-item card-style">
          <h4>Αποδοχή Προσφορών</h4>
          <p className="stat-value">
            {(stats.offer_acceptance_rate === "N/A" || stats.offer_acceptance_rate === null || stats.offer_acceptance_rate === undefined) 
              ? "Μ/Δ" 
              : `${stats.offer_acceptance_rate}%`
            }
          </p>
          {/* <small>(Προσλήφθηκαν / Σύνολο Απαντήσεων)</small> */}
        </div>
      )}

      {stats.avg_days_in_needs_review !== undefined && (
        <div className="stat-item card-style">
          <h4>Μ.Ο. Ημερών σε "Αναμονή"</h4>
          <p className="stat-value">
            {(stats.avg_days_in_needs_review === "N/A" || stats.avg_days_in_needs_review === null || stats.avg_days_in_needs_review === undefined)
              ? "Μ/Δ"
              : `${stats.avg_days_in_needs_review} ημ.`
            }
          </p>
          <small>(Τρέχοντες στο Στάδιο)</small>
        </div>
      )}

      {stats.interview_conversion_rate !== undefined && (
        <div className="stat-item card-style">
          <h4>Μετατροπή σε Συνέντευξη</h4>
          <p className="stat-value">
            {(stats.interview_conversion_rate === "N/A" || stats.interview_conversion_rate === null || stats.interview_conversion_rate === undefined)
              ? "Μ/Δ"
              : `${stats.interview_conversion_rate}%`
            }
          </p>
          {/* <small>(Προγραμματισμένες / Αρχική Ροή)</small> */}
        </div>
      )}

      { !stats.open_positions_count &&
        !stats.stuck_in_needs_review_X_days &&
        !stats.offer_acceptance_rate &&
        !stats.avg_days_in_needs_review &&
        !stats.interview_conversion_rate &&
        Object.keys(stats).length > 0 && (
         <div className="stat-item card-style" style={{gridColumn: '1 / -1'}}>
            <p>Δεν υπάρχουν επαρκή δεδομένα για την εμφάνιση στατιστικών.</p>
         </div>
      )}
    </div>
  );
}

export default StatisticsDisplay;