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
    if (companyPositions.length > 0) {
        setAvailablePositions(companyPositions);
    } else {
        console.warn("InterviewProposalForm: No company positions provided or fetched.");
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
    // Πρόσθεσε έλεγχο για το format των start_time/end_time αν χρειάζεται
    // π.χ. να είναι "YYYY-MM-DD HH:MM:SS"
    const formattedSlots = formData.proposed_slots.map(slot => {
        // Αυτή η λογική υποθέτει ότι τα inputs για date και time ενημερώνουν σωστά το slot.start_time/end_time
        // σε format "YYYY-MM-DD HH:MM:SS"
        if (!slot.start_time.includes(':')) slot.start_time += ' 00:00:00'; // Πρόσθεσε default ώρα αν λείπει
        if (!slot.end_time.includes(':')) slot.end_time += ' 00:00:00';     // Πρόσθεσε default ώρα αν λείπει
        return slot;
    });

    onSubmit({ ...formData, proposed_slots: formattedSlots });
  };

  const today = new Date().toISOString().split('T')[0];

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
            {availablePositions.map(pos => (
              <option key={pos.position_id || pos.id} value={pos.position_id || pos.id}>
                {pos.position_name || pos.name}
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
            <div className="form-group">
              <label htmlFor={`slot_date_${index}`}>Date:</label>
              <input
                type="date"
                id={`slot_date_${index}`}
                min={today}
                // Διαχείριση του value για να μην είναι "undefined 00:00:00"
                value={slot.start_time ? slot.start_time.split(' ')[0] : ''}
                onChange={(e) => {
                    const currentTime = slot.start_time.split(' ')[1] || '00:00:00';
                    handleSlotChange(index, 'start_time', `${e.target.value} ${currentTime}`);
                    // Αν θέλεις να ενημερώνεις και το end_time date ταυτόχρονα (προαιρετικό)
                    // const currentEndTime = slot.end_time.split(' ')[1] || '00:00:00';
                    // handleSlotChange(index, 'end_time', `${e.target.value} ${currentEndTime}`);
                }}
                required
                className="input-light-gray"
              />
            </div>
            <div className="form-group">
              <label htmlFor={`slot_time_start_${index}`}>Start Time:</label>
              <input
                type="time"
                id={`slot_time_start_${index}`}
                value={slot.start_time ? (slot.start_time.split(' ')[1]?.substring(0,5) || '') : ''}
                onChange={(e) => {
                    const currentDate = slot.start_time.split(' ')[0] || today;
                    handleSlotChange(index, 'start_time', `${currentDate} ${e.target.value}:00`);
                }}
                required
                className="input-light-gray"
              />
            </div>
            <div className="form-group">
              <label htmlFor={`slot_time_end_${index}`}>End Time:</label>
              <input
                type="time"
                id={`slot_time_end_${index}`}
                value={slot.end_time ? (slot.end_time.split(' ')[1]?.substring(0,5) || '') : ''}
                onChange={(e) => {
                    // Χρησιμοποίησε την ημερομηνία από το start_time για συνέπεια, ή την ημερομηνία του end_time αν υπάρχει
                    const currentDate = slot.start_time.split(' ')[0] || slot.end_time.split(' ')[0] || today;
                    handleSlotChange(index, 'end_time', `${currentDate} ${e.target.value}:00`);
                }}
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

export default InterviewProposalForm; // <-- Η ΓΡΑΜΜΗ ΠΟΥ ΕΛΕΙΠΕ