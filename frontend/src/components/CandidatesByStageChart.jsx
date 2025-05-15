// frontend/src/components/CandidatesByStageChart.jsx
import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell } from 'recharts';

const COLORS = [ // Πιο "επαγγελματικά" χρώματα, μπορείτε να τα προσαρμόσετε
  '#2563eb', '#16a34a', '#f97316', '#ca8a04', '#6d28d9', 
  '#db2777', '#475569' 
];

const CustomTooltipContent = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div className="custom-recharts-tooltip">
        <p className="recharts-tooltip-label">{`${label}`}</p>
        <p className="recharts-tooltip-value" style={{ color: payload[0].fill }}>
          {`Candidates: ${payload[0].value}`}
        </p>
      </div>
    );
  }
  return null;
};

// CSS για το custom tooltip (μπορεί να μπει και σε global CSS αρχείο)
const tooltipStyles = `
  .custom-recharts-tooltip {
    background-color: #ffffff;
    padding: 10px 12px;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
    font-size: 0.875rem;
  }
  .recharts-tooltip-label {
    margin: 0 0 5px 0;
    font-weight: 600;
    color: #334155;
  }
  .recharts-tooltip-value {
    margin: 0;
  }
`;

function CandidatesByStageChart({ data }) { // Αφαιρέθηκαν isLoading/error, θα τα χειρίζεται το DashboardPage

  if (!data || data.length === 0) {
    // Αυτή η περίπτωση θα πρέπει να καλύπτεται από το DashboardPage.jsx πλέον.
    // Αλλά για ασφάλεια, αν κληθεί απευθείας χωρίς δεδομένα:
    return <div style={{ height: '350px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#64748b' }}>No data for chart.</div>;
  }

  // Βεβαιωθείτε ότι τα δεδομένα έχουν 'stage_name' και 'count'
  const chartData = data.map(item => ({
    stage_name: item.stage_name || 'Unknown Stage', // Fallback για stage_name
    count: typeof item.count === 'number' ? item.count : 0 // Fallback για count
  }));


  return (
    <>
      <style>{tooltipStyles}</style> {/* Ενσωμάτωση CSS για το tooltip */}
      <ResponsiveContainer width="100%" height={350}>
        <BarChart
          data={chartData}
          margin={{
            top: 5,
            right: 5, // Λιγότερο δεξιά για να μην κόβεται
            left: 5,  // Λιγότερο αριστερά
            bottom: 80, // Αυξημένο bottom margin για τα x-axis labels
          }}
          barSize={30} // Προσαρμόστε το πάχος των μπαρών
        >
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
          <XAxis 
            dataKey="stage_name" 
            angle={-40}       // Λίγο μικρότερη γωνία
            textAnchor="end"
            height={90}        // Αυξημένο ύψος για τα labels
            interval={0}       // Εμφάνιση όλων των labels
            tick={{ fontSize: 11, fill: '#475569' }} 
            dy={5} // Μικρή προσαρμογή προς τα κάτω
          />
          <YAxis 
            allowDecimals={false} 
            tick={{ fontSize: 12, fill: '#475569' }}
            label={{ 
              value: 'Number of Candidates', 
              angle: -90, 
              position: 'insideLeft', 
              offset: 10, // Προσαρμογή του offset
              style: { textAnchor: 'middle', fontSize: 13, fill: '#334155' } 
            }}
            width={70} // Δώστε λίγο παραπάνω πλάτος στον Y άξονα για το label
          />
          <Tooltip content={<CustomTooltipContent />} cursor={{ fill: 'rgba(206, 206, 206, 0.2)' }} />
          {/* <Legend verticalAlign="top" height={36}/> */}
          <Bar dataKey="count" name="Candidates" radius={[5, 5, 0, 0]} >
            {chartData.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </>
  );
}

export default CandidatesByStageChart;