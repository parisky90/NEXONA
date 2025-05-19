// frontend/src/components/CandidatesByStageChart.jsx
import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell } from 'recharts';

const COLORS = [
  '#2563eb', '#16a34a', '#f97316', '#ca8a04', '#6d28d9',
  '#db2777', '#475569', '#0891b2', '#d946ef', '#f59e0b',
  '#84cc16', '#ef4444', '#6b7280', '#3b82f6'
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

function CandidatesByStageChart({ data }) {
  // console.log('CandidatesByStageChart props received, data:', data);

  if (!data || !Array.isArray(data) || data.length === 0) {
    // console.log('CandidatesByStageChart: No data or data is not an array, rendering placeholder.');
    return <div style={{ height: '350px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#64748b' }}>No pipeline data to display for chart.</div>;
  }

  const chartData = data.map(item => ({
    stage_name: item.stage_name || 'Unknown Stage',
    count: typeof item.count === 'number' ? item.count : 0
  }));

  const filteredChartData = chartData.filter(item => item.count > 0);

  if (filteredChartData.length === 0) {
    // console.log('CandidatesByStageChart: chartData is empty AFTER filtering for count > 0. Original mapped data:', chartData);
    // ΔΙΟΡΘΩΣΗ ΕΔΩ
    return <div style={{ height: '350px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#64748b' }}>No candidates in any active stage with count > 0.</div>;
  }


  return (
    <>
      <style>{tooltipStyles}</style>
      <ResponsiveContainer width="100%" height={350}>
        <BarChart
          data={filteredChartData}
          margin={{
            top: 5,
            right: 5,
            left: 5,
            bottom: 80,
          }}
          barSize={filteredChartData.length < 5 ? 50 : (filteredChartData.length < 10 ? 30 : 20) }
        >
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
          <XAxis
            dataKey="stage_name"
            angle={-40}
            textAnchor="end"
            height={90}
            interval={0}
            tick={{ fontSize: 11, fill: '#475569' }}
            dy={5}
          />
          <YAxis
            allowDecimals={false}
            tick={{ fontSize: 12, fill: '#475569' }}
            label={{
              value: 'Number of Candidates',
              angle: -90,
              position: 'insideLeft',
              offset: -5,
              style: { textAnchor: 'middle', fontSize: 13, fill: '#334155' }
            }}
            width={80}
          />
          <Tooltip content={<CustomTooltipContent />} cursor={{ fill: 'rgba(206, 206, 206, 0.2)' }} />
          <Bar dataKey="count" name="Candidates" radius={[5, 5, 0, 0]} >
            {filteredChartData.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </>
  );
}

export default CandidatesByStageChart;