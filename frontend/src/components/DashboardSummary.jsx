// frontend/src/components/DashboardSummary.jsx
import React from 'react';
import './DashboardSummary.css';

const statusLabelMapping = {
  total_candidates: 'Total Candidates',
  active_positions: 'Active Positions',
  upcoming_interviews: 'Upcoming Interviews',
  processing: 'Processing',
  parsingfailed: 'Parsing Failed',
  needsreview: 'Needs Review',
  new: 'New',
  accepted: 'Accepted',
  interested: 'Interested',
  interviewscheduled: 'Interview Scheduled', // Το backend στέλνει "Interview Scheduled" στο candidates_by_stage
  interviewing: 'Interviewing', // Αν το έχεις αυτό ως ξεχωριστό stage
  evaluation: 'Evaluation',
  offermade: 'Offer Made',
  hired: 'Hired',
  rejected: 'Rejected',
  declined: 'Declined',
  on_hold: 'On Hold'
};

// Αυτή η σειρά θα χρησιμοποιηθεί για την εμφάνιση.
// Τα κλειδιά πρέπει να αντιστοιχούν σε αυτά που υπάρχουν στο 'summary' prop.
const displayOrder = [
  'total_candidates',
  'active_positions',
  'upcoming_interviews',
  'needsreview',
  'processing',
  'accepted',
  'interested',
  'interviewscheduled', // Ενημέρωσε αυτό αν το backend stage name είναι διαφορετικό (π.χ., "interview")
  'evaluation',
  'offermade',
  'hired',
  'rejected',
  'declined',
  'parsingfailed',
  'on_hold',
  'new', // Αν το 'new' είναι ένα από τα stages που έρχονται στο candidates_by_stage
];

function DashboardSummary({ summary }) {
  console.log('DashboardSummary props received, summary:', summary);

  if (!summary || Object.keys(summary).length === 0) {
    console.log('DashboardSummary: No summary data provided or summary is empty, rendering placeholders.');
    // Render placeholders based on displayOrder
    return (
      <div className="dashboard-summary-container">
        <div className="summary-grid">
          {displayOrder.map(key => {
            // Εμφάνισε μόνο αν υπάρχει label για αυτό το key, για να μην δείχνει "แปลก" κουτιά
            if (statusLabelMapping[key] || ['total_candidates', 'active_positions', 'upcoming_interviews'].includes(key)) {
              return (
                <div key={key} className="summary-item" style={{ opacity: 0.6 }} data-status={key}>
                  <span className="summary-value">-</span>
                  <span className="summary-label">{statusLabelMapping[key] || key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</span>
                </div>
              );
            }
            return null;
          })}
        </div>
      </div>
    );
  }

  const displayItems = displayOrder
    .map(key => {
      // Το summary object που έρχεται από το DashboardPage περιέχει κλειδιά όπως:
      // total_candidates, active_positions, upcoming_interviews
      // και μετά τα ονόματα των stages σε lowercase από το candidates_by_stage (π.χ., needsreview, accepted)
      const countValue = summary[key]; 

      if (summary.hasOwnProperty(key) && (statusLabelMapping[key] || ['total_candidates', 'active_positions', 'upcoming_interviews'].includes(key))) {
        const displayCount = (typeof countValue === 'number') ? countValue : (countValue !== undefined && countValue !== null ? String(countValue) : '0'); // Default σε '0' αν N/A
        return {
          statusKey: key,
          count: displayCount,
          label: statusLabelMapping[key] || key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
        };
      }
      return null; 
    })
    .filter(item => item !== null);

  if (displayItems.length === 0) {
    console.log('DashboardSummary: displayItems is empty after mapping and filtering. Summary object was:', summary);
    return <div className="dashboard-summary-container"><p style={{textAlign: 'center', padding: '1rem'}}>No summary items to display based on current data.</p></div>;
  }

  return (
    <div className="dashboard-summary-container">
      <div className="summary-grid">
        {displayItems.map(item => (
          <div key={item.statusKey} className="summary-item" data-status={item.statusKey}> 
            <span className="summary-value">{item.count}</span>
            <span className="summary-label">{item.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
export default DashboardSummary;