// frontend/src/components/CustomCalendarEvent.jsx
import React from 'react';
import moment from 'moment';
import './CustomCalendarEvent.css';

const CustomCalendarEvent = ({ event }) => {
  if (!event || !event.resource) {
    return <div className="custom-event-error">Invalid Event Data</div>;
  }

  const { start, resource } = event; // Δεν χρειαζόμαστε το event.title εδώ, το φτιάχνουμε
  const candidateName = resource.candidate_name || "N/A";
  const positionName = resource.position_name || "N/A";
  const interviewType = resource.interview_type || "N/A";
  const location = resource.location || "N/A";

  const startTimeFormatted = moment(start).format('HH:mm');
  
  // Βελτιωμένο tooltip text
  const tooltipText = `Candidate: ${candidateName}\nPosition: ${positionName}\nLocation: ${location}\nType: ${interviewType}\nTime: ${moment(start).format('DD/MM/YYYY HH:mm')} - ${moment(event.end).format('HH:mm')}`;

  return (
    <div className="custom-calendar-event" title={tooltipText}>
      <div className="custom-event-time">{startTimeFormatted}</div>
      <div className="custom-event-title">{candidateName}</div>
      {/* Αν θέλεις και την θέση ορατή πάντα (πρόσεξε τον χώρο): */}
      {/* <div className="custom-event-subtitle">{positionName}</div> */}
    </div>
  );
};

export default CustomCalendarEvent;