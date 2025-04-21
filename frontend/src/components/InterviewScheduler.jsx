// frontend/src/components/InterviewScheduler.jsx
import React, { useState } from 'react';
import './InterviewScheduler.css'; // Optional: Add specific styles if needed

// Accept inputClassName prop and pass it down
function InterviewScheduler({ onSchedule, disabled, inputClassName = '' }) {
  const [date, setDate] = useState('');
  const [time, setTime] = useState('');
  const [location, setLocation] = useState('');
  const [error, setError] = useState(''); // Local error state for validation

  const handleSubmit = (e) => {
    e.preventDefault();
    setError(''); // Clear previous errors
    if (!date || !time) {
        setError('Date and Time are required.');
        return;
    }
    if (onSchedule) {
      onSchedule({ date, time, location });
    }
    // Decide if fields should clear after submit
    // setDate(''); setTime(''); setLocation('');
  };

  // Get today's date in YYYY-MM-DD format for min attribute
  const today = new Date().toISOString().split('T')[0];

  return (
    <div className="interview-scheduler">
      <h4>Schedule Interview</h4>
      {error && <p className="error-message" style={{fontSize: '0.85rem', padding: '5px', marginBottom: '10px'}}>{error}</p>}
      <form onSubmit={handleSubmit} className="scheduler-form">
        <div className="scheduler-input-group">
          <label htmlFor="interviewDate">Date:</label>
          <input
            type="date"
            id="interviewDate"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            required
            min={today} // Prevent selecting past dates
            disabled={disabled}
            // Apply the passed class name (e.g., "input-light-gray")
            className={inputClassName}
          />
        </div>
        <div className="scheduler-input-group">
          <label htmlFor="interviewTime">Time:</label>
          <input
            type="time"
            id="interviewTime"
            value={time}
            onChange={(e) => setTime(e.target.value)}
            required
            disabled={disabled}
            // Apply the passed class name
            className={inputClassName}
          />
        </div>
        <div className="scheduler-input-group">
          <label htmlFor="interviewLocation">Location:</label>
          <input
            type="text"
            id="interviewLocation"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder="e.g., Office Room 3 / Online Link"
            // Location might not always be required? Remove 'required' if so.
            required
            disabled={disabled}
            // Apply the passed class name
            className={inputClassName}
          />
        </div>
        <button
           type="submit"
           disabled={disabled}
           // Use a standard action button style or a specific one
           className="button-action button-primary" // Example using primary style
           style={{marginTop: '10px'}} // Add some space before button
        >
          Schedule Interview
        </button>
      </form>
    </div>
  );
}

export default InterviewScheduler;