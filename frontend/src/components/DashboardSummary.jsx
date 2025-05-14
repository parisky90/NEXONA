// frontend/src/components/DashboardSummary.jsx
import React from 'react';
import './DashboardSummary.css'; // Βεβαιώσου ότι το CSS υπάρχει και είναι σωστό

// --- ΔΙΟΡΘΩΣΗ ΟΝΟΜΑΤΟΣ ΚΛΕΙΔΙΟΥ ---
const statusLabelMapping = {
  total_candidates: 'Total Candidates', // Άλλαξε από total_cvs
  Processing: 'Processing',
  ParsingFailed: 'Parsing Failed',
  NeedsReview: 'Needs Review',
  New: 'New',
  Accepted: 'Accepted',
  Interested: 'Interested',
  Interview: 'Interview',
  Declined: 'Declined',
  Evaluation: 'Evaluation',
  OfferMade: 'Offer Made',
  Hired: 'Hired',
  Rejected: 'Rejected',
  // Πρόσθεσε το 'On Hold' αν το χρησιμοποιείς και στο backend summary
  'On_Hold': 'On Hold', // Αν το backend στέλνει 'On_Hold'
  // ή 'On Hold': 'On Hold' αν το backend στέλνει 'On Hold'
};

// --- ΔΙΟΡΘΩΣΗ ΟΝΟΜΑΤΟΣ ΚΛΕΙΔΙΟΥ ---
const displayOrder = [
  'total_candidates', // Άλλαξε από total_cvs
  'NeedsReview',
  'Processing', // Πρόσθεσα το Processing αν θέλεις να το βλέπεις
  'Interested', // Σειρά που μπορεί να βγάζει νόημα
  'Interview',
  'Evaluation',
  'OfferMade',
  'Accepted', // Πριν το Hired
  'Hired',
  'Rejected',
  'Declined',
  'ParsingFailed', // Ίσως στο τέλος ή κοντά στο Processing
  'On_Hold' // Αν το έχεις
];
// --- ΤΕΛΟΣ ΔΙΟΡΘΩΣΕΩΝ ---


function DashboardSummary({ summary }) {
  if (!summary) {
    // Μπορείς να δείξεις ένα πιο διακριτικό loading state εδώ αν θέλεις
    return (
      <div className="dashboard-summary-container">
        <div className="dashboard-summary-row">
          {displayOrder.map(key => (
            <div key={key} className="summary-item" style={{ opacity: 0.5 }}>
              <span className="count">-</span>
              <span className="label">{statusLabelMapping[key] || key}</span>
            </div>
          ))}
        </div>
      </div>
    );
  }

  // Δημιουργία των αντικειμένων προς εμφάνιση
  const displayItems = displayOrder
    .map(key => {
      // Έλεγχos αν το κλειδί υπάρχει στο summary και αν η τιμή είναι αριθμός
      const countValue = summary[key];
      const displayCount = (typeof countValue === 'number') ? countValue : 'N/A';
      
      // Αν το κλειδί δεν υπάρχει καθόλου στο summary object, μπορείς να το παραλείψεις
      // ή να δείξεις N/A. Για τώρα, δείχνουμε N/A.
      if (summary[key] === undefined && key !== 'total_candidates' && !Object.prototype.hasOwnProperty.call(summary, key)) {
        // console.warn(`DashboardSummary: Key "${key}" not found in summary object.`);
        // return null; // Για να το παραλείψεις εντελώς
      }

      return {
        status: key,
        count: displayCount,
        label: statusLabelMapping[key] || key.replace(/_/g, ' ') // Καλύτερο fallback για το label
      };
    })
    .filter(item => item !== null); // Φιλτράρισμα των null αν αποφασίσεις να παραλείψεις κλειδιά


  return (
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