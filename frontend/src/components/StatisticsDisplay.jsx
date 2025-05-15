// frontend/src/components/StatisticsDisplay.jsx
import React from 'react';
// import './StatisticsDisplay.css'; // Βεβαιώσου ότι αυτό το αρχείο CSS υπάρχει αν το χρησιμοποιείς

function StatisticsDisplay({ stats, isLoading, error }) {
  if (isLoading) {
    return <div className="loading-placeholder card-style">Loading statistics...</div>;
  }
  
  // Εμφάνιση σφάλματος αν υπάρχει και δεν φορτώνει
  if (error && !isLoading) {
    return <div className="error-message card-style">Error loading statistics: {error}</div>;
  }
  
  // Εμφάνιση μηνύματος αν δεν υπάρχουν στατιστικά (και δεν υπάρχει σφάλμα ή φόρτωση)
  if (!isLoading && !error && (!stats || Object.keys(stats).length === 0)) {
    return (
      <div className="statistics-container card-style" style={{ marginTop: '2rem' }}>
        <h3>Key Statistics</h3>
        <p>No statistics available yet or not applicable for the current filter.</p>
      </div>
    );
  }

  // Αν το stats είναι null/undefined μετά τους παραπάνω ελέγχους, κάτι πήγε πολύ στραβά.
  // Αυτό είναι ένα επιπλέον δίχτυ ασφαλείας.
  if (!stats) {
    return (
        <div className="statistics-container card-style" style={{ marginTop: '2rem' }}>
            <h3>Key Statistics</h3>
            <p>Statistics data is currently unavailable.</p>
        </div>
    );
  }

  return (
    <div className="statistics-container card-style" style={{ marginTop: '2rem' }}>
      <h3>Key Statistics</h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
        
        {/* Interview Reach Percentage */}
        {stats.interview_reach_percentage !== undefined && (
          <div className="stat-item">
            <h4>Interview Reach</h4>
            <p style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>
              {stats.interview_reach_percentage}%
            </p>
            <small>(Of total candidates)</small>
          </div>
        )}

        {/* Average Days to Interview */}
        {stats.avg_days_to_interview !== undefined && (
          <div className="stat-item">
            <h4>Avg. Time to Interview</h4>
            <p style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>
              {stats.avg_days_to_interview}
              {stats.avg_days_to_interview !== "N/A" ? " days" : ""}
            </p>
            <small>(From submission)</small>
          </div>
        )}

        {/* Open Positions Count */}
        {stats.open_positions_count !== undefined && (
          <div className="stat-item">
            <h4>Open Positions</h4>
            <p style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>
              {stats.open_positions_count}
            </p>
          </div>
        )}
        
        {/* Μπορείς να προσθέσεις κι άλλα στατιστικά εδώ με παρόμοιο τρόπο */}
        {/* π.χ., αν το backend στέλνει 'conversion_rate_offer_to_hire' */}
        {/* {stats.conversion_rate_offer_to_hire !== undefined && (
          <div className="stat-item">
            <h4>Offer to Hire Rate</h4>
            <p style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>
              {stats.conversion_rate_offer_to_hire}%
            </p>
          </div>
        )} */}

      </div>
    </div>
  );
}

export default StatisticsDisplay;