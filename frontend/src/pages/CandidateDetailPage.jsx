// frontend/src/pages/CandidateDetailPage.jsx
import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import apiClient from '../api';
import CVViewer from '../components/CVViewer';
import HistoryLog from '../components/HistoryLog';
import InterviewScheduler from '../components/InterviewScheduler';
import './CandidateDetailPage.css'; // Import the CSS file

function CandidateDetailPage() {
  const { candidateId } = useParams();
  const navigate = useNavigate();
  const [candidate, setCandidate] = useState(null);
  const [cvUrl, setCvUrl] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isUpdating, setIsUpdating] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [formData, setFormData] = useState({}); // Use for edits

  // Fetch candidate details and CV URL
  const fetchCandidateData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    console.log(`Fetching data for candidate: ${candidateId}`);
    try {
      const [detailsRes, urlRes] = await Promise.all([
        apiClient.get(`/candidate/${candidateId}`),
        apiClient.get(`/candidate/${candidateId}/cv_url`)
      ]);
      console.log("Candidate details fetched:", detailsRes.data);
      console.log("CV URL fetched:", urlRes.data);
      setCandidate(detailsRes.data);
      // Initialize formData with potentially null values handled gracefully
      setFormData({
          first_name: detailsRes.data.first_name || '',
          last_name: detailsRes.data.last_name || '',
          email: detailsRes.data.email || '',
          phone_number: detailsRes.data.phone_number || '',
          age: detailsRes.data.age || '',
          positions: detailsRes.data.positions || [],
          education: detailsRes.data.education || '',
          work_experience: detailsRes.data.work_experience || '',
          languages: detailsRes.data.languages || '',
          seminars: detailsRes.data.seminars || '',
          notes: detailsRes.data.notes || '',
          evaluation_rating: detailsRes.data.evaluation_rating || '',
          offer_details: detailsRes.data.offer_details || '',
          // Read-only fields below, no need to put in formData for edit usually
          // current_status: detailsRes.data.current_status
          // submission_date: detailsRes.data.submission_date
          // interview_datetime: detailsRes.data.interview_datetime
          // interview_location: detailsRes.data.interview_location
      });
      setCvUrl(urlRes.data.cv_url);
    } catch (err) {
      console.error("Error fetching candidate data:", err);
      setError(err.response?.data?.error || 'Failed to load candidate details.');
      setCandidate(null);
      setCvUrl(null);
    } finally {
      setIsLoading(false);
    }
  }, [candidateId]);

  useEffect(() => {
    fetchCandidateData();
  }, [fetchCandidateData]); // Fetch data when component mounts or candidateId changes

  // Handle input changes in edit mode
  const handleInputChange = (event) => {
        const { name, value, type } = event.target;
        // Handle potential number conversion for age
        const processedValue = type === 'number' ? (value === '' ? '' : Number(value)) : value;
        setFormData(prevData => ({
            ...prevData,
            [name]: processedValue
        }));
    };

  // Handle position changes (comma-separated)
  const handlePositionChange = (event) => {
        const positions = event.target.value.split(',').map(p => p.trim()).filter(p => p); // Create array, remove empty
         setFormData(prevData => ({
             ...prevData,
             positions: positions
         }));
     };

  // Handle Status Update / Actions
  const handleUpdateStatus = async (newStatus, extraData = {}) => {
    if (!candidate) return;
    setIsUpdating(true);
    setError(null);
    // Include notes from formData if in edit mode, otherwise from candidate state
    const currentNotes = editMode ? formData.notes : candidate.notes;
    const payload = {
        current_status: newStatus,
        notes: currentNotes, // Always send current notes with status change
        ...extraData
    };

    // Clean payload: remove null values unless specifically allowed by backend
    // Or let backend handle nulls appropriately
    Object.keys(payload).forEach(key => payload[key] == null && delete payload[key]);


    console.log("Updating status with payload:", payload);
    try {
      const response = await apiClient.put(`/candidate/${candidate.candidate_id}`, payload);
      // Update both main state and form state
      setCandidate(response.data);
      setFormData({ // Re-initialize form data after update
        ...formData, // Keep potentially unsaved edits in other fields ? Or reset fully? Resetting fully is safer.
        ...(response.data), // Update with response, ensuring fields match formData structure
         notes: response.data.notes || '', // Ensure notes field is updated
         positions: response.data.positions || [], // Ensure positions are updated
         // Ensure other relevant fields are reset/updated
      });
      console.log(`Candidate status updated to ${newStatus}`);
      // Navigate after specific status changes if desired
      if (newStatus === 'Rejected') navigate('/rejected');
      if (newStatus === 'Declined') navigate('/declined');
    } catch (err) {
      console.error(`Error updating status to ${newStatus}:`, err);
      setError(err.response?.data?.error || `Failed to update status.`);
    } finally {
      setIsUpdating(false);
    }
  };

  // Handle saving general edits
  const handleSaveChanges = async () => {
      if (!candidate) return;
      setIsUpdating(true);
      setError(null);
      try {
          // Construct payload ONLY from editable fields in formData
          const updatePayload = {
             first_name: formData.first_name,
             last_name: formData.last_name,
             email: formData.email,
             phone_number: formData.phone_number,
             age: formData.age === '' ? null : formData.age, // Send null if age is empty
             positions: formData.positions,
             education: formData.education,
             work_experience: formData.work_experience,
             languages: formData.languages,
             seminars: formData.seminars,
             notes: formData.notes,
             evaluation_rating: formData.evaluation_rating,
             offer_details: formData.offer_details,
             // Do NOT send status or other non-editable fields here
             // Status is changed via handleUpdateStatus
          };

          console.log("Saving changes with payload:", updatePayload);
          const response = await apiClient.put(`/candidate/${candidate.candidate_id}`, updatePayload);
          // Update both states
          setCandidate(response.data);
          setFormData({ ...(response.data) }); // Reset form data fully from response
          setEditMode(false); // Exit edit mode on success
          console.log("Candidate details updated successfully.");
      } catch (err) {
          console.error("Error saving candidate details:", err);
          setError(err.response?.data?.error || `Failed to save changes.`);
      } finally {
          setIsUpdating(false);
      }
  };

  // Handle interview scheduling
  const handleScheduleInterview = async ({ date, time, location }) => {
       if (!candidate || !date || !time) {
           setError("Please select both date and time for the interview.");
           return;
       }
       try {
           // Combine date and time inputs into a local date object
           const localDateTime = new Date(`${date}T${time}:00`);
           if (isNaN(localDateTime.getTime())) { // Check if date is valid
                throw new Error("Invalid date/time combination.");
           }
           // Convert to ISO string in UTC
           const utcDateTimeISO = localDateTime.toISOString();

           console.log("Scheduling Interview - Local:", localDateTime, "UTC ISO:", utcDateTimeISO, "Location:", location);

           await handleUpdateStatus('Interview', {
               interview_datetime: utcDateTimeISO,
               interview_location: location || '' // Send empty string if no location
           });
       } catch (e) {
           console.error("Error creating datetime string or scheduling:", e);
           setError(`Failed to schedule: ${e.message}`);
       }
  };

  // Define action handlers clearly
  const handleConfirmInterview = () => handleUpdateStatus('Evaluation');
  const handleCancelOrRescheduleInterview = () => handleUpdateStatus('Interested', { interview_datetime: null, interview_location: null }); // Reverts to Interested
  const handleRejectInterview = () => handleUpdateStatus('Rejected'); // Reject directly from Interview stage
  const handleMakeOffer = () => handleUpdateStatus('OfferMade'); // Add offer details via edit mode if needed
  const handleOfferAccepted = () => handleUpdateStatus('Hired');
  const handleOfferRejected = () => handleUpdateStatus('Declined', { offer_response_date: new Date().toISOString() });


  // --- Render Logic ---
  if (isLoading) return <div>Loading candidate details...</div>;
  // Show error prominently if loading failed
  if (error && !candidate) return <div className="error-message">Error: {error} <button onClick={fetchCandidateData}>Retry</button></div>;
  // Handle case where candidate might become null after an action? Unlikely but safe.
  if (!candidate) return <div>Candidate not found or data unavailable.</div>;

  // Formatting function
  const formatDate = (isoString) => {
    if (!isoString) return 'N/A';
    try { return new Date(isoString).toLocaleString(); } catch { return 'Invalid Date'; }
  };

  return (
    <div className="candidate-detail-page">
      <Link to="/dashboard" className="back-link">← Back to Dashboard</Link>

      {/* Show general errors */}
      {error && <div className="error-message">Error: {error}</div>}

      <div className="detail-header">
         <h2>{editMode ? `${formData.first_name || ''} ${formData.last_name || ''}` : `${candidate.first_name || ''} ${candidate.last_name || 'Candidate Details'}`}</h2>
         <div className="header-actions">
             {!editMode ? (
                 <button onClick={() => setEditMode(true)} className="button-action button-edit">Edit</button>
             ) : (
                 <>
                    <button onClick={handleSaveChanges} className="button-action button-save" disabled={isUpdating}>{isUpdating ? 'Saving...' : 'Save Changes'}</button>
                    {/* Reset form data to original candidate data on cancel */}
                    <button onClick={() => { setEditMode(false); setFormData({ ...candidate }); }} className="button-action button-cancel" disabled={isUpdating}>Cancel</button>
                 </>
             )}
         </div>
      </div>

      <div className="detail-content">
        {/* --- Left Column: Details & Actions --- */}
        <div className="detail-column detail-column-left">
          <h3>Candidate Information</h3>
          <div className="info-grid">
              <div className="info-item"><label>First Name:</label>{editMode ? <input type="text" name="first_name" value={formData.first_name} onChange={handleInputChange} className="input-light-gray"/> : <span>{candidate.first_name || 'N/A'}</span>}</div>
              <div className="info-item"><label>Last Name:</label>{editMode ? <input type="text" name="last_name" value={formData.last_name} onChange={handleInputChange} className="input-light-gray"/> : <span>{candidate.last_name || 'N/A'}</span>}</div>
              <div className="info-item"><label>Email:</label>{editMode ? <input type="email" name="email" value={formData.email} onChange={handleInputChange} className="input-light-gray"/> : <span>{candidate.email || 'N/A'}</span>}</div>
              <div className="info-item"><label>Phone:</label>{editMode ? <input type="tel" name="phone_number" value={formData.phone_number} onChange={handleInputChange} className="input-light-gray"/> : <span>{candidate.phone_number || 'N/A'}</span>}</div>
              <div className="info-item"><label>Age:</label>{editMode ? <input type="number" name="age" value={formData.age} onChange={handleInputChange} className="input-light-gray"/> : <span>{candidate.age || 'N/A'}</span>}</div>
              <div className="info-item"><label>Position(s):</label>{editMode ? <input type="text" name="positions" value={formData.positions.join(', ')} onChange={handlePositionChange} className="input-light-gray" placeholder="Comma-separated"/> : <span>{candidate.positions.join(', ') || 'N/A'}</span>}</div>
              <div className="info-item"><label>Status:</label><span>{candidate.current_status || 'N/A'}</span></div>
              <div className="info-item"><label>Submission Date:</label><span>{formatDate(candidate.submission_date)}</span></div>
              {candidate.interview_datetime && (<div className="info-item info-item-full"><label>Interview:</label><span>{formatDate(candidate.interview_datetime)} {candidate.interview_location ? ` at ${candidate.interview_location}` : ''}</span></div>)}
              <div className="info-item info-item-full"><label>Education:</label>{editMode ? <textarea name="education" value={formData.education} onChange={handleInputChange} className="input-light-gray"/> : <p>{candidate.education || 'N/A'}</p>}</div>
              <div className="info-item info-item-full"><label>Work Experience:</label>{editMode ? <textarea name="work_experience" value={formData.work_experience} onChange={handleInputChange} className="input-light-gray"/> : <p>{candidate.work_experience || 'N/A'}</p>}</div>
              <div className="info-item"><label>Languages:</label>{editMode ? <input type="text" name="languages" value={formData.languages} onChange={handleInputChange} className="input-light-gray"/> : <span>{candidate.languages || 'N/A'}</span>}</div>
              <div className="info-item"><label>Seminars:</label>{editMode ? <input type="text" name="seminars" value={formData.seminars} onChange={handleInputChange} className="input-light-gray"/> : <span>{candidate.seminars || 'N/A'}</span>}</div>
              <div className="info-item info-item-full"><label>Notes / Comments:</label>{editMode ? (<textarea name="notes" value={formData.notes} onChange={handleInputChange} className="input-light-gray" rows="4"/>) : (<p className="notes-display">{candidate.notes || '(No notes added)'}</p>)}</div>
              {['Evaluation', 'OfferMade', 'Hired', 'Declined'].includes(candidate.current_status) && (<div className="info-item"><label>Evaluation Rating:</label>{editMode ? <input type="text" name="evaluation_rating" value={formData.evaluation_rating} onChange={handleInputChange} className="input-light-gray"/> : <span>{candidate.evaluation_rating || 'N/A'}</span>}</div>)}
              {['OfferMade', 'Hired', 'Declined'].includes(candidate.current_status) && (<div className="info-item info-item-full"><label>Offer Details:</label>{editMode ? <textarea name="offer_details" value={formData.offer_details} onChange={handleInputChange} className="input-light-gray"/> : <p>{candidate.offer_details || 'N/A'}</p>}</div>)}
              {candidate.offer_response_date && (<div className="info-item"><label>Offer Response Date:</label><span>{formatDate(candidate.offer_response_date)}</span></div>)}
          </div>

          {/* --- Action Buttons --- */}
          <div className="action-buttons">
              <h4>Actions</h4>
              {candidate.current_status === 'NeedsReview' && (
                  <>
                      <button onClick={() => handleUpdateStatus('Accepted')} className="button-action button-accept" disabled={isUpdating}>Accept</button>
                      <button onClick={() => handleUpdateStatus('Rejected')} className="button-action button-reject" disabled={isUpdating}>Reject</button>
                  </>
              )}
              {candidate.current_status === 'Accepted' && (
                  <>
                      <button onClick={() => handleUpdateStatus('Interested')} className="button-action button-primary" disabled={isUpdating}>Move to Interested</button>
                      <button onClick={() => handleUpdateStatus('Rejected')} className="button-action button-reject" disabled={isUpdating}>Reject</button>
                  </>
              )}
               {candidate.current_status === 'Interested' && (
                  <>
                      <InterviewScheduler onSchedule={handleScheduleInterview} disabled={isUpdating} inputClassName="input-light-gray"/>
                      <button onClick={() => handleUpdateStatus('Rejected')} className="button-action button-reject" disabled={isUpdating}>Reject</button>
                  </>
               )}
               {candidate.current_status === 'Interview' && (
                   <>
                      <p style={{fontWeight: 'bold', marginTop:'15px'}}>Interview Outcome:</p>
                      <button onClick={handleConfirmInterview} className="button-action button-confirm" disabled={isUpdating}>Confirm Happened</button>
                      <button onClick={handleCancelOrRescheduleInterview} className="button-action button-cancel-schedule" disabled={isUpdating}>Cancel/Reschedule</button>
                      <button onClick={handleRejectInterview} className="button-action button-reject" disabled={isUpdating}>Reject Candidate</button>
                  </>
               )}
                {candidate.current_status === 'Evaluation' && (
                   <>
                       <button onClick={handleMakeOffer} className="button-action button-accept" disabled={isUpdating}>Make Offer</button>
                       <button onClick={() => handleUpdateStatus('Rejected')} className="button-action button-reject" disabled={isUpdating}>Reject</button>
                  </>
               )}
                {candidate.current_status === 'OfferMade' && (
                   <>
                       <p style={{fontWeight: 'bold', marginTop:'15px'}}>Offer Response:</p>
                       <button onClick={handleOfferAccepted} className="button-action button-accept" disabled={isUpdating}>Candidate Accepted</button>
                       <button onClick={handleOfferRejected} className="button-action button-reject" disabled={isUpdating}>Candidate Rejected Offer</button>
                  </>
               )}
                {['Hired', 'Rejected', 'Declined'].includes(candidate.current_status) && (
                  <p style={{ fontStyle: 'italic', color: 'var(--text-medium-gray)', marginTop: '15px' }}>No further actions available for this status.</p>
                )}
          </div>
        </div> {/* End Left Column */}

        {/* --- Right Column: CV & History --- */}
        <div className="detail-column detail-column-right">
           <div className="cv-viewer-section card-style">
             <h3>CV Document</h3>
             {cvUrl ? <CVViewer fileUrl={cvUrl} /> : <p>Loading CV...</p>}
           </div>
           <div className="history-log-section card-style">
             <h3>Candidate History</h3>
             <HistoryLog history={candidate.history} buttonClassName="button-cancel-schedule" />
           </div>
        </div> {/* End Right Column */}
      </div> {/* End Detail Content */}
    </div> // End Page Div
  );
}

export default CandidateDetailPage;