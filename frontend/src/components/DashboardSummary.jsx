// frontend/src/components/DashboardSummary.jsx
import React from 'react';
import './DashboardSummary.css'; // Import the updated CSS

// Enhanced mapping for better labels if needed
const statusLabelMapping = {
  total_cvs: 'Total CVs',
  Processing: 'Processing',
  ParsingFailed: 'Parsing Failed',
  NeedsReview: 'Needs Review',
  New: 'New', // Or hide this if 'NeedsReview' covers it
  Accepted: 'Accepted',
  Interested: 'Interested',
  Interview: 'Interview',
  Declined: 'Declined',
  Evaluation: 'Evaluation',
  OfferMade: 'Offer Made',
  Hired: 'Hired',
  Rejected: 'Rejected',
  // Add other statuses if present in your data
};

// Define the order and which statuses to display
const displayOrder = [
  'total_cvs',
  'NeedsReview',
  'Accepted',
  'Interview', // Moved up
  'OfferMade', // Moved up
  'Hired',
  'Rejected', // Moved down
];


function DashboardSummary({ summary }) {
  if (!summary) {
    return <div className="dashboard-summary-container"><p>Loading summary...</p></div>;
  }

  // Create display items based on the desired order and mapping
  const displayItems = displayOrder
    .map(key => ({
      status: key,
      count: summary[key] !== undefined ? summary[key] : 'N/A', // Handle missing keys gracefully
      label: statusLabelMapping[key] || key // Use mapping or fallback to key
    }));


  return (
    // Wrap in the new container divs
    <div className="dashboard-summary-container">
      <div className="dashboard-summary-row">
        {displayItems.map(item => (
          <div key={item.status} className="summary-item">
            <span className="count">{item.count}</span>
            <span className="label">{item.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default DashboardSummary;