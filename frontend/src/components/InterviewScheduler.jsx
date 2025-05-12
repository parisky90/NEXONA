// frontend/src/components/InterviewScheduler.jsx
import React, { useState, useEffect } from 'react';
import './InterviewScheduler.css';

function InterviewScheduler({
  onSchedule,
  disabled,
  inputClassName = '',
  initialDate = '',
  initialTime = '',
  initialLocation = ''
}) {
  const [date, setDate] = useState(initialDate);
  const [time, setTime] = useState(initialTime);
  const [location, setLocation] = useState(initialLocation);
  const [error, setError] = useState('');

  useEffect(() => {
    setDate(initialDate);
    setTime(initialTime);
    setLocation(initialLocation);
  }, [initialDate, initialTime, initialLocation]);

  const handleSubmit = (e) => {
    e.preventDefault();
    setError('');
    if (!date || !time) {
        setError('Date and Time are required.');
        return;
    }
    const todayForCheck = new Date();
    todayForCheck.setHours(0,0,0,0);
    const selectedDateObj = new Date(date);
    selectedDateObj.setHours(0,0,0,0);

    if (selectedDateObj < todayForCheck) {
        setError('Cannot schedule an interview for a past date.');
        return;
    }

    if (onSchedule) {
      onSchedule({ date, time, location });
    }
  };

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
            onChange={(e) => { setDate(e.target.value); setError(''); }}
            required
            min={today}
            disabled={disabled}
            className={inputClassName}
          />
        </div>
        <div className="scheduler-input-group">
          <label htmlFor="interviewTime">Time:</label>
          <input
            type="time"
            id="interviewTime"
            value={time}
            onChange={(e) => { setTime(e.target.value); setError(''); }}
            required
            disabled={disabled}
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
            disabled={disabled}
            className={inputClassName}
          />
        </div>
        <button
           type="submit"
           disabled={disabled}
           className="button-action button-primary"
           style={{marginTop: '15px', width: '100%'}}
        >
          {disabled ? 'Scheduling...' : 'Schedule Interview'}
        </button>
      </form>
    </div>
  );
}

export default InterviewScheduler;