// frontend/src/components/StatisticsDisplay.jsx
import React from 'react';
// import './StatisticsDisplay.css'; // Αν το CSS είναι global ή στο DashboardPage.css, δεν χρειάζεται εδώ

function StatisticsDisplay({ stats, isLoading }) { // Αφαιρέθηκε το error prop, θα το χειρίζεται το DashboardPage
  
  // Αν δεν υπάρχουν στατιστικά (αλλά δεν φορτώνει), εμφάνισε σχετικό μήνυμα
  // Αυτό καλύπτει και την περίπτωση που το stats είναι null/undefined ή κενό object
  // μετά την αρχική φόρτωση.
  if (!isLoading && (!stats || Object.keys(stats).length === 0 || 
      (stats.interview_reach_percentage === undefined && 
       stats.avg_days_to_interview === undefined && 
       stats.open_positions_count === undefined))) {
    return (
      <div className="statistics-text-items"> {/* Κλάση για styling αν χρειάζεται */}
        <p style={{ textAlign: 'center', color: '#666', marginTop: '1rem' }}>
            No specific statistics to display at the moment.
        </p>
      </div>
    );
  }

  // Δεν χρειάζεται το isLoading check εδώ αν το DashboardPage το χειρίζεται πριν το render
  // Ωστόσο, αν θέλουμε placeholder *μέσα* στο component:
  if (isLoading) {
      return (
        <div className="statistics-text-items">
            <div className="stat-item-placeholder"><h4>Loading...</h4><p>-</p></div>
            <div className="stat-item-placeholder"><h4>Loading...</h4><p>-</p></div>
            <div className="stat-item-placeholder"><h4>Loading...</h4><p>-</p></div>
        </div>
      );
  }


  return (
    // Δεν χρειάζεται το statistics-container και το h3 εδώ, θα είναι στο DashboardPage
    <div className="statistics-text-items" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem' }}>
      
      {stats?.interview_reach_percentage !== undefined && (
        <div className="stat-item">
          <h4>Interview Reach</h4>
          <p className="stat-value">
            {stats.interview_reach_percentage}%
          </p>
          <small>(Of total candidates)</small>
        </div>
      )}

      {stats?.avg_days_to_interview !== undefined && (
        <div className="stat-item">
          <h4>Avg. Time to Interview</h4>
          <p className="stat-value">
            {stats.avg_days_to_interview}
            {stats.avg_days_to_interview !== "N/A" ? " days" : ""}
          </p>
          <small>(From submission)</small>
        </div>
      )}

      {stats?.open_positions_count !== undefined && (
        <div className="stat-item">
          <h4>Open Positions</h4>
          <p className="stat-value">
            {stats.open_positions_count}
          </p>
        </div>
      )}
    </div>
  );
}

export default StatisticsDisplay;