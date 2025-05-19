// frontend/src/components/InterviewProposalForm.jsx
import React, { useState, useEffect } from 'react';
// import apiClient from '../api'; // Δεν χρειάζεται εδώ, το API call γίνεται στο CandidateDetailPage

function InterviewProposalForm({ candidateId, companyPositions = [], onSubmit, onCancel, isSubmitting }) {
  const [formData, setFormData] = useState({
    position_id: '', 
    proposed_slots: [
      { start_time: '', end_time: '' }, 
    ],
    location: '',
    interview_type: '', 
    notes_for_candidate: '',
    internal_notes: ''
  });
  const [availablePositions, setAvailablePositions] = useState([]);

  useEffect(() => {
    // Το console.warn που είχες εδώ είναι χρήσιμο για να δεις αν έρχονται οι θέσεις
    if (companyPositions && companyPositions.length > 0) {
        setAvailablePositions(companyPositions);
        console.log("InterviewProposalForm: companyPositions received:", companyPositions);
    } else {
        console.warn("InterviewProposalForm: No company positions provided or companyPositions array is empty.");
        setAvailablePositions([]); // Βεβαιώσου ότι είναι πάντα array
    }
  }, [companyPositions]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSlotChange = (index, field, value) => {
    const updatedSlots = formData.proposed_slots.map((slot, i) =>
      i === index ? { ...slot, [field]: value } : slot
    );
    setFormData(prev => ({ ...prev, proposed_slots: updatedSlots }));
  };

  const addSlot = () => {
    if (formData.proposed_slots.length < 3) {
      setFormData(prev => ({
        ...prev,
        proposed_slots: [...prev.proposed_slots, { start_time: '', end_time: '' }]
      }));
    }
  };

  const removeSlot = (index) => {
    if (formData.proposed_slots.length > 1) {
      const updatedSlots = formData.proposed_slots.filter((_, i) => i !== index);
      setFormData(prev => ({ ...prev, proposed_slots: updatedSlots }));
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (formData.proposed_slots.some(slot => !slot.start_time || !slot.end_time)) {
      alert('Please fill in start and end times for all proposed slots.');
      return;
    }
    
    const formattedSlots = formData.proposed_slots.map((slot, index) => {
        console.log(`InterviewProposalForm: Slot ${index + 1} before formatting for backend:`, JSON.parse(JSON.stringify(slot))); // Deep copy for logging

        let finalStartTime = slot.start_time;
        let finalEndTime = slot.end_time;

        // Το frontend στέλνει YYYY-MM-DDTHH:mm. Το backend περιμένει YYYY-MM-DD HH:MM:SS
        // Πρέπει να μετατρέψουμε το "T" σε κενό και να προσθέσουμε ":00" για τα δευτερόλεπτα αν λείπουν.
        if (finalStartTime && typeof finalStartTime === 'string') {
            finalStartTime = finalStartTime.replace('T', ' ');
            if (finalStartTime.length === 16) { // YYYY-MM-DD HH:MM
                finalStartTime += ':00';
            }
        }
        if (finalEndTime && typeof finalEndTime === 'string') {
            finalEndTime = finalEndTime.replace('T', ' ');
            if (finalEndTime.length === 16) { // YYYY-MM-DD HH:MM
                finalEndTime += ':00';
            }
        }
        
        console.log(`InterviewProposalForm: Slot ${index + 1} AFTER formatting for backend:`, { start_time: finalStartTime, end_time: finalEndTime });
        return { start_time: finalStartTime, end_time: finalEndTime };
    });

    const payloadToSend = { ...formData, proposed_slots: formattedSlots };
    console.log("InterviewProposalForm: Submitting payload:", JSON.parse(JSON.stringify(payloadToSend))); // Deep copy for logging
    onSubmit(payloadToSend);
  };

  const today = new Date().toISOString().split('T')[0]; // Για το min attribute του date input

  return (
    <div className="interview-proposal-form card-style" style={{marginTop: '20px', border: '1px solid var(--primary-color)'}}>
      <h4 style={{marginTop:0, marginBottom:'15px'}}>Propose Interview Slots</h4>
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="proposal-position_id">Position (Optional):</label>
          <select
            id="proposal-position_id"
            name="position_id"
            value={formData.position_id}
            onChange={handleChange}
            className="input-light-gray"
          >
            <option value="">Select a position...</option>
            {/* Βεβαιώσου ότι το companyPositions έχει αντικείμενα με id και name/position_name */}
            {availablePositions.map(pos => (
              <option key={pos.position_id || pos.id} value={pos.position_id || pos.id}>
                {pos.position_name || pos.name || `Position ID ${pos.position_id || pos.id}`}
              </option>
            ))}
          </select>
        </div>

        {formData.proposed_slots.map((slot, index) => (
          <div key={index} className="proposed-slot-group" style={{border: '1px dashed #ccc', padding: '10px', marginBottom: '10px', borderRadius:'4px'}}>
            <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom:'5px'}}>
                <strong>Slot {index + 1}</strong>
                {formData.proposed_slots.length > 1 && (
                    <button type="button" onClick={() => removeSlot(index)} className="button-action button-reject" style={{fontSize:'0.7rem', padding:'2px 5px'}}>Remove</button>
                )}
            </div>
            {/* Χρησιμοποιούμε datetime-local για ευκολότερη επιλογή ημερομηνίας και ώρας */}
            <div className="form-group">
              <label htmlFor={`slot_datetime_start_${index}`}>Start Date & Time:</label>
              <input
                type="datetime-local"
                id={`slot_datetime_start_${index}`}
                min={`${today}T00:00`} // Ελάχιστη τιμή
                value={slot.start_time ? slot.start_time.substring(0,16) : ''} // Format YYYY-MM-DDTHH:mm
                onChange={(e) => handleSlotChange(index, 'start_time', e.target.value)}
                required
                className="input-light-gray"
              />
            </div>
            <div className="form-group">
              <label htmlFor={`slot_datetime_end_${index}`}>End Date & Time:</label>
              <input
                type="datetime-local"
                id={`slot_datetime_end_${index}`}
                min={slot.start_time ? slot.start_time.substring(0,16) : `${today}T00:00`} // End time >= Start time
                value={slot.end_time ? slot.end_time.substring(0,16) : ''} // Format YYYY-MM-DDTHH:mm
                onChange={(e) => handleSlotChange(index, 'end_time', e.target.value)}
                required
                className="input-light-gray"
              />
            </div>
          </div>
        ))}
        {formData.proposed_slots.length < 3 && (
          <button type="button" onClick={addSlot} className="button-action button-secondary" style={{fontSize:'0.8rem', marginBottom:'10px'}}>
            + Add Another Slot
          </button>
        )}

        <div className="form-group">
          <label htmlFor="proposal-location">Location/Link:</label>
          <input type="text" id="proposal-location" name="location" value={formData.location} onChange={handleChange} className="input-light-gray" placeholder="e.g., Office / Google Meet Link" required />
        </div>
        <div className="form-group">
          <label htmlFor="proposal-interview_type">Interview Type:</label>
          <select id="proposal-interview_type" name="interview_type" value={formData.interview_type} onChange={handleChange} className="input-light-gray" required>
            <option value="">Select type...</option>
            <option value="IN_PERSON">In Person</option>
            <option value="PHONE_SCREEN">Phone Screen</option>
            <option value="VIDEO_CALL">Video Call</option>
            <option value="TECHNICAL_ASSESSMENT">Technical Assessment</option>
            {/* Μπορείς να προσθέσεις κι άλλους τύπους αν χρειάζεται */}
          </select>
        </div>
        <div className="form-group">
          <label htmlFor="proposal-notes_for_candidate">Notes for Candidate (Optional):</label>
          <textarea id="proposal-notes_for_candidate" name="notes_for_candidate" value={formData.notes_for_candidate} onChange={handleChange} className="input-light-gray" rows="3" />
        </div>
        <div className="form-group">
          <label htmlFor="proposal-internal_notes">Internal Notes (Optional):</label>
          <textarea id="proposal-internal_notes" name="internal_notes" value={formData.internal_notes} onChange={handleChange} className="input-light-gray" rows="2" />
        </div>

        <div style={{display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop:'15px'}}>
          <button type="button" onClick={onCancel} className="button-action button-secondary" disabled={isSubmitting}>
            Cancel
          </button>
          <button type="submit" className="button-action button-primary" disabled={isSubmitting}>
            {isSubmitting ? 'Proposing...' : 'Propose Interview'}
          </button>
        </div>
      </form>
    </div>
  );
}

export default InterviewProposalForm;