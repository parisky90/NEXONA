// frontend/src/components/DashboardSummary.jsx
import React from 'react';
import './DashboardSummary.css';

const statusLabelMapping = {
  total_candidates: 'Total Candidates',
  processing: 'Processing',
  parsingfailed: 'Parsing Failed', 
  needsreview: 'Needs Review',   
  new: 'New',
  accepted: 'Accepted',
  interested: 'Interested',
  interview: 'Interview',
  declined: 'Declined',
  evaluation: 'Evaluation',
  offermade: 'Offer Made',     
  hired: 'Hired',
  rejected: 'Rejected',
  on_hold: 'On Hold' 
};

const displayOrder = [
  'total_candidates', 'needsreview', 'processing', 'interested', 'interview',
  'evaluation', 'offermade', 'accepted', 'hired', 'rejected', 'declined',
  'parsingfailed', 'on_hold'
];

function DashboardSummary({ summary }) {
  if (!summary) {
    return (
      <div className="dashboard-summary-container">
        <div className="summary-grid">
          {displayOrder.map(key => (
            <div key={key} className="summary-item" style={{ opacity: 0.6 }} data-status={key}> {/* Προσθήκη data-status */}
              <span className="summary-value">-</span>
              <span className="summary-label">{statusLabelMapping[key] || key.replace(/_/g, ' ')}</span>
            </div>
          ))}
        </div>
      </div>
    );
  }

  const displayItems = displayOrder
    .map(key => {
      const countValue = summary[key];
      const displayCount = (typeof countValue === 'number') ? countValue : 'N/A';
      
      if (key === 'total_candidates' || statusLabelMapping[key]) {
        return {
          statusKey: key,
          count: displayCount,
          label: statusLabelMapping[key] || key.replace(/_/g, ' ')
        };
      }
      return null; 
    })
    .filter(item => item !== null);

  return (
    <div className="dashboard-summary-container">
      <div className="summary-grid">
        {displayItems.map(item => (
          // Προσθήκη data-status attribute για στοχευμένο CSS
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