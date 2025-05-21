// frontend/src/components/CustomCalendarEvent.jsx
import React from 'react';
import moment from 'moment';
import './CustomCalendarEvent.css'; // Θα δημιουργήσουμε αυτό το αρχείο

const CustomCalendarEvent = ({ event }) => {
  if (!event || !event.resource) {
    // Fallback αν κάτι δεν πάει καλά με το event data
    return <div className="custom-event-error">Invalid Event Data</div>;
  }

  const { title, start, resource } = event;
  const candidateName = resource.candidate_name || "N/A";
  const positionName = resource.position_name || "N/A";
  const interviewType = resource.interview_type || "N/A";
  const location = resource.location || "N/A";

  const startTime = moment(start).format('HH:mm'); // Μόνο η ώρα

  // Δημιουργία του string για το tooltip
  const tooltipText = `Candidate: ${candidateName}\nPosition: ${positionName}\nType: ${interviewType}\nLocation: ${location}\nTime: ${moment(start).format('lll')} - ${moment(event.end).format('LT')}`;

  return (
    <div className="custom-calendar-event" title={tooltipText}>
      <div className="custom-event-time">{startTime}</div>
      <div className="custom-event-title">{candidateName}</div>
      {/* Μπορείς να προσθέσεις και το positionName αν υπάρχει χώρος και το θέλεις πάντα ορατό */}
      {/* <div className="custom-event-subtitle">{positionName}</div> */}
    </div>
  );
};

export default CustomCalendarEvent;