// frontend/src/components/StatisticsDisplay.jsx
import React from 'react';
// import './StatisticsDisplay.css'; // Αν έχεις CSS για αυτό

function StatisticsDisplay({ stats, isLoading }) {
  // console.log('StatisticsDisplay props received, stats:', stats, 'isLoading:', isLoading);

  if (isLoading) {
      // console.log('StatisticsDisplay: Rendering loading placeholders.');
      return (
        <div className="statistics-text-items" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem' }}>
            <div className="stat-item-placeholder card-style" style={{padding: '1rem', textAlign:'center'}}><h4 style={{height: '1em', width: '70%', margin: '0 auto 0.5rem auto', backgroundColor:'#e9ecef', color:'#e9ecef', borderRadius:'4px'}}>L</h4><p style={{height: '1.5em', width: '40%', margin: '0 auto', backgroundColor:'#e9ecef', color:'#e9ecef', borderRadius:'4px'}}>L</p></div>
            <div className="stat-item-placeholder card-style" style={{padding: '1rem', textAlign:'center'}}><h4 style={{height: '1em', width: '70%', margin: '0 auto 0.5rem auto', backgroundColor:'#e9ecef', color:'#e9ecef', borderRadius:'4px'}}>L</h4><p style={{height: '1.5em', width: '40%', margin: '0 auto', backgroundColor:'#e9ecef', color:'#e9ecef', borderRadius:'4px'}}>L</p></div>
            <div className="stat-item-placeholder card-style" style={{padding: '1rem', textAlign:'center'}}><h4 style={{height: '1em', width: '70%', margin: '0 auto 0.5rem auto', backgroundColor:'#e9ecef', color:'#e9ecef', borderRadius:'4px'}}>L</h4><p style={{height: '1.5em', width: '40%', margin: '0 auto', backgroundColor:'#e9ecef', color:'#e9ecef', borderRadius:'4px'}}>L</p></div>
            <div className="stat-item-placeholder card-style" style={{padding: '1rem', textAlign:'center'}}><h4 style={{height: '1em', width: '70%', margin: '0 auto 0.5rem auto', backgroundColor:'#e9ecef', color:'#e9ecef', borderRadius:'4px'}}>L</h4><p style={{height: '1.5em', width: '40%', margin: '0 auto', backgroundColor:'#e9ecef', color:'#e9ecef', borderRadius:'4px'}}>L</p></div>
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
    // console.log('StatisticsDisplay: No relevant statistics to display or stats object is missing expected keys.');
    return (
      <div className="statistics-text-items">
        <p style={{ textAlign: 'center', color: '#666', marginTop: '1rem' }}>
            No key statistics to display at the moment.
        </p>
      </div>
    );
  }

  return (
    <div className="statistics-text-items" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>

      {stats.open_positions_count !== undefined && (
        <div className="stat-item card-style">
          <h4>Open Positions</h4>
          <p className="stat-value">
            {stats.open_positions_count}
          </p>
        </div>
      )}

      {stats.stuck_in_needs_review_X_days !== undefined && stats.stuck_in_needs_review_threshold_days !== undefined && (
        <div className="stat-item card-style">
          {/* ΔΙΟΡΘΩΣΗ ΕΔΩ */}
          <h4>Awaiting Review ({'>'}{stats.stuck_in_needs_review_threshold_days} days)</h4>
          <p className="stat-value">
            {stats.stuck_in_needs_review_X_days}
          </p>
          <small>Candidates</small>
        </div>
      )}

      {stats.offer_acceptance_rate !== undefined && (
        <div className="stat-item card-style">
          <h4>Offer Acceptance</h4>
          <p className="stat-value">
            {stats.offer_acceptance_rate}{stats.offer_acceptance_rate !== "N/A" ? "%" : ""}
          </p>
          <small>(Hired / (Hired + Declined))</small>
        </div>
      )}

      {stats.avg_days_in_needs_review !== undefined && (
        <div className="stat-item card-style">
          <h4>Avg. Days in "Needs Review"</h4>
          <p className="stat-value">
            {stats.avg_days_in_needs_review}
            {stats.avg_days_in_needs_review !== "N/A" ? " days" : ""}
          </p>
          <small>(Current in Stage)</small>
        </div>
      )}

      {stats.interview_conversion_rate !== undefined && (
        <div className="stat-item card-style">
          <h4>Interview Conversion</h4>
          <p className="stat-value">
            {stats.interview_conversion_rate}{stats.interview_conversion_rate !== "N/A" ? "%" : ""}
          </p>
          <small>(Scheduled / Initial Pipeline)</small>
        </div>
      )}

      { stats.open_positions_count === undefined &&
        stats.stuck_in_needs_review_X_days === undefined &&
        stats.offer_acceptance_rate === undefined &&
        stats.avg_days_in_needs_review === undefined &&
        stats.interview_conversion_rate === undefined &&
        Object.keys(stats).length > 0 && (
         <div className="stat-item card-style" style={{gridColumn: '1 / -1'}}>
            <p>Some statistics were calculated but are not configured for display here.</p>
         </div>
      )}
    </div>
  );
}

export default StatisticsDisplay;