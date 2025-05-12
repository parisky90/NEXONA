// frontend/src/pages/CandidateDetailPage.jsx
import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import apiClient from '../api';
import CVViewer from '../components/CVViewer';
import HistoryLog from '../components/HistoryLog';
import InterviewScheduler from '../components/InterviewScheduler';
import './CandidateDetailPage.css'; // Import the CSS file

// Helper function για να δίνει κείμενο, χρώμα & κλάση CSS στο confirmation status
const getConfirmationStatusInfo = (confirmationStatus) => {
    switch (confirmationStatus) {
        case 'Confirmed':
            return { text: 'Επιβεβαιώθηκε από Υποψήφιο', color: 'green', className: 'status-confirmed' };
        case 'Declined':
             return { text: 'Απορρίφθηκε / Αίτημα Αλλαγής από Υποψήφιο', color: 'red', className: 'status-declined' };
        case 'Pending':
             return { text: 'Αναμονή Απάντησης από Υποψήφιο', color: 'orange', className: 'status-pending' };
        default:
             return { text: '', color: 'grey', className: 'status-unknown' }; // Επιστρέφει κενό κείμενο για null/undefined
    }
};

function CandidateDetailPage() {
  const { candidateId } = useParams();
  const navigate = useNavigate();
  const [candidate, setCandidate] = useState(null);
  const [cvUrl, setCvUrl] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isUpdating, setIsUpdating] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [formData, setFormData] = useState({});

  // Ενσωμάτωση της initializeFormData που είχαμε συζητήσει
  const initializeFormData = (data) => {
    setFormData({
        first_name: data.first_name || '',
        last_name: data.last_name || '',
        email: data.email || '',
        phone_number: data.phone_number || '',
        age: data.age || '',
        positions: data.positions || [],
        education: data.education || '',
        work_experience: data.work_experience || '',
        languages: data.languages || '',
        seminars: data.seminars || '',
        notes: data.notes || '',
        evaluation_rating: data.evaluation_rating || '',
        offer_details: data.offer_details || '',
        interview_datetime: data.interview_datetime || null,
        interview_location: data.interview_location || '',
        candidate_confirmation_status: data.candidate_confirmation_status || null,
    });
  };

  const fetchCandidateData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [detailsRes, urlRes] = await Promise.all([
        apiClient.get(`/candidate/${candidateId}`),
        apiClient.get(`/candidate/${candidateId}/cv_url`)
      ]);
      setCandidate(detailsRes.data);
      initializeFormData(detailsRes.data);
      setCvUrl(urlRes.data.cv_url);
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to load candidate details.');
      setCandidate(null);
      setCvUrl(null);
    } finally {
      setIsLoading(false);
    }
  }, [candidateId]);

  useEffect(() => {
    fetchCandidateData();
  }, [fetchCandidateData]);

  const handleInputChange = (event) => {
        const { name, value, type } = event.target;
        const processedValue = type === 'number' ? (value === '' ? '' : Number(value)) : value;
        setFormData(prevData => ({
            ...prevData,
            [name]: processedValue
        }));
    };

  const handlePositionChange = (event) => {
        const positions = event.target.value.split(',').map(p => p.trim()).filter(p => p);
         setFormData(prevData => ({
             ...prevData,
             positions: positions
         }));
     };

  const handleUpdateStatus = async (newStatus, extraData = {}) => {
    if (!candidate) return;
    setIsUpdating(true); // <<<--- ΕΝΑΡΞΗ ACTION LOADING
    setError(null);
    const currentNotes = editMode ? formData.notes : (candidate?.notes || '');
    const payload = {
        current_status: newStatus,
        notes: currentNotes,
        ...extraData
    };
    if (payload.interview_datetime === '') payload.interview_datetime = null;
    if (payload.offer_response_date === '') payload.offer_response_date = null;

    try {
      const response = await apiClient.put(`/candidate/${candidate.candidate_id}`, payload);
      setCandidate(response.data);
      initializeFormData(response.data);
      if (newStatus === 'Rejected') navigate('/rejected');
      if (newStatus === 'Declined') navigate('/declined');
      if (newStatus === 'NeedsReview' && (candidate.current_status === 'Rejected' || candidate.current_status === 'Declined')) {
        // console.log("Candidate moved to Needs Review");
      }
    } catch (err) {
      setError(err.response?.data?.error || `Failed to update status.`);
    } finally { // <<<--- ΔΙΟΡΘΩΣΗ: finally block
      setIsUpdating(false); // <<<--- ΛΗΞΗ ACTION LOADING ΠΑΝΤΑ
    }
  };

  const handleSaveChanges = async () => {
      if (!candidate) return;
      setIsUpdating(true); // <<<--- ΕΝΑΡΞΗ ACTION LOADING
      setError(null);
      try {
          const updatePayload = {
             first_name: formData.first_name,
             last_name: formData.last_name,
             email: formData.email,
             phone_number: formData.phone_number,
             age: formData.age === '' ? null : formData.age,
             positions: formData.positions,
             education: formData.education,
             work_experience: formData.work_experience,
             languages: formData.languages,
             seminars: formData.seminars,
             notes: formData.notes,
             evaluation_rating: formData.evaluation_rating,
             offer_details: formData.offer_details,
          };
          const response = await apiClient.put(`/candidate/${candidate.candidate_id}`, updatePayload);
          setCandidate(response.data);
          initializeFormData(response.data);
          setEditMode(false);
      } catch (err) {
          setError(err.response?.data?.error || `Failed to save changes.`);
      } finally { // <<<--- ΔΙΟΡΘΩΣΗ: finally block
          setIsUpdating(false); // <<<--- ΛΗΞΗ ACTION LOADING ΠΑΝΤΑ
      }
  };

  const handleScheduleInterview = async ({ date, time, location }) => {
       if (!candidate || !date || !time) {
           setError("Please select both date and time for the interview.");
           return;
       }
       // Το setIsUpdating θα τεθεί (και θα καθαριστεί) από το handleUpdateStatus
       try {
           const localDateTime = new Date(`${date}T${time}:00`);
           if (isNaN(localDateTime.getTime())) {
                throw new Error("Invalid date/time combination.");
           }
           const utcDateTimeISO = localDateTime.toISOString();
           await handleUpdateStatus('Interview', {
               interview_datetime: utcDateTimeISO,
               interview_location: location || ''
           });
       } catch (e) {
           setError(`Failed to schedule: ${e.message}`);
       }
  };

  const handleConfirmInterview = () => handleUpdateStatus('Evaluation');
  const handleCancelOrRescheduleInterview = () => handleUpdateStatus('Interested', { interview_datetime: null, interview_location: null, candidate_confirmation_status: null });
  const handleRejectFromInterview = () => handleUpdateStatus('Rejected'); // Μετονομάστηκε για σαφήνεια
  const handleMakeOffer = () => handleUpdateStatus('OfferMade');
  const handleOfferAccepted = () => handleUpdateStatus('Hired');
  const handleOfferRejected = () => handleUpdateStatus('Declined', { offer_response_date: new Date().toISOString() });

  const formatDate = (isoString) => {
    if (!isoString) return 'N/A';
    try { return new Date(isoString).toLocaleString([], { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }); } catch { return 'Invalid Date'; }
  };

  // --- DEBUGGING LOGS ---
  if (candidate) {
      console.log("Candidate Data for Detail Page (for button logic):", JSON.stringify(candidate, null, 2));
      console.log("CANDIDATE CURRENT STATUS (for button logic):", candidate.current_status);
      console.log("Is status 'Declined' (for button logic)?:", candidate.current_status === 'Declined');
      console.log("Is status 'Rejected' (for button logic)?:", candidate.current_status === 'Rejected');
      console.log("Should show Re-evaluate button (for button logic)?:", candidate.current_status && ['Rejected', 'Declined'].includes(candidate.current_status));
  }
  // --- END DEBUGGING LOGS ---

  if (isLoading && !candidate) return <div className="loading-placeholder card-style">Loading candidate details...</div>;
  if (error && !candidate && !isLoading) return <div className="error-message card-style">Error: {error} <button onClick={fetchCandidateData} className="button-action button-secondary">Retry</button></div>;
  if (!candidate) return <div className="card-style">Candidate not found or data unavailable.</div>;

  const confirmationDisplayInfo = getConfirmationStatusInfo(candidate.candidate_confirmation_status);

  return (
    <div className="candidate-detail-page">
      <Link to={-1} className="back-link">← Back</Link>
      {error && !isUpdating && <div className="error-message">{error}</div>}
      {isUpdating && <div className="loading-placeholder-action card-style" style={{position: 'fixed', top: '10px', left: '50%', transform: 'translateX(-50%)', zIndex: 1001, padding: '10px 20px', background: 'rgba(255,255,255,0.9)', boxShadow: '0 2px 10px rgba(0,0,0,0.2)'}}>Updating...</div>}

      <div className="detail-header">
         <h2>{editMode ? `${formData.first_name || ''} ${formData.last_name || ''}`.trim() || 'Edit Candidate' : `${candidate.first_name || ''} ${candidate.last_name || 'Candidate Details'}`.trim()}</h2>
         <div className="header-actions">
             {!editMode ? (
                 <button onClick={() => { setEditMode(true); setError(null); }} className="button-action button-edit" disabled={isUpdating}>Edit</button>
             ) : (
                 <>
                    <button onClick={handleSaveChanges} className="button-action button-save" disabled={isUpdating}>{isUpdating ? 'Saving...' : 'Save Changes'}</button>
                    <button onClick={() => {
                        setEditMode(false);
                        initializeFormData(candidate);
                        setError(null);
                    }} className="button-action button-cancel" disabled={isUpdating}>Cancel</button>
                 </>
             )}
         </div>
      </div>
      <div className="detail-content">
        <div className="detail-column detail-column-left">
          <h3>Candidate Information</h3>
          <div className="info-grid">
              {/* Fields for display/edit */}
              <div className="info-item"><label>First Name:</label>{editMode ? <input type="text" name="first_name" value={formData.first_name} onChange={handleInputChange} className="input-light-gray"/> : <span>{candidate.first_name || 'N/A'}</span>}</div>
              <div className="info-item"><label>Last Name:</label>{editMode ? <input type="text" name="last_name" value={formData.last_name} onChange={handleInputChange} className="input-light-gray"/> : <span>{candidate.last_name || 'N/A'}</span>}</div>
              <div className="info-item"><label>Email:</label>{editMode ? <input type="email" name="email" value={formData.email} onChange={handleInputChange} className="input-light-gray"/> : <span>{candidate.email || 'N/A'}</span>}</div>
              <div className="info-item"><label>Phone:</label>{editMode ? <input type="tel" name="phone_number" value={formData.phone_number} onChange={handleInputChange} className="input-light-gray"/> : <span>{candidate.phone_number || 'N/A'}</span>}</div>
              <div className="info-item"><label>Age:</label>{editMode ? <input type="number" name="age" value={formData.age} onChange={handleInputChange} className="input-light-gray"/> : <span>{candidate.age || 'N/A'}</span>}</div>
              <div className="info-item"><label>Position(s):</label>{editMode ? <input type="text" name="positions" value={formData.positions.join(', ')} onChange={handlePositionChange} className="input-light-gray" placeholder="Comma-separated"/> : <span>{candidate.positions?.join(', ') || 'N/A'}</span>}</div>
              <div className="info-item"><label>Status:</label><span className={`status-badge status-${candidate.current_status?.toLowerCase().replace(/\s+/g, '-')}`}>{candidate.current_status || 'N/A'}</span></div>
              <div className="info-item"><label>Submission Date:</label><span>{formatDate(candidate.submission_date)}</span></div>

              {/* Interview Details & Confirmation Status */}
              {candidate.interview_datetime && (
                <>
                  <div className="info-item info-item-full">
                    <label>Interview:</label>
                    <span>{formatDate(candidate.interview_datetime)} {candidate.interview_location ? ` at ${candidate.interview_location}` : ''}</span>
                  </div>
                  {confirmationDisplayInfo && confirmationDisplayInfo.text && (
                    <div className="info-item info-item-full">
                        <label>Κατάσταση Επιβεβαίωσης Ραντεβού:</label>
                        <span
                            style={{
                                color: confirmationDisplayInfo.color,
                                fontWeight: 'bold',
                                padding: '3px 8px',
                                borderRadius: '12px',
                                backgroundColor: `${confirmationDisplayInfo.color}20`, // Light tint
                                fontSize: '0.85rem'
                            }}
                            className={`status-badge ${confirmationDisplayInfo.className}`}
                        >
                            {confirmationDisplayInfo.text}
                        </span>
                    </div>
                  )}
                </>
              )}

              <div className="info-item info-item-full"><label>Education:</label>{editMode ? <textarea name="education" value={formData.education} onChange={handleInputChange} className="input-light-gray"/> : <p>{candidate.education || 'N/A'}</p>}</div>
              <div className="info-item info-item-full"><label>Work Experience:</label>{editMode ? <textarea name="work_experience" value={formData.work_experience} onChange={handleInputChange} className="input-light-gray"/> : <p>{candidate.work_experience || 'N/A'}</p>}</div>
              <div className="info-item"><label>Languages:</label>{editMode ? <input type="text" name="languages" value={formData.languages} onChange={handleInputChange} className="input-light-gray"/> : <span>{candidate.languages || 'N/A'}</span>}</div>
              <div className="info-item"><label>Seminars:</label>{editMode ? <input type="text" name="seminars" value={formData.seminars} onChange={handleInputChange} className="input-light-gray"/> : <span>{candidate.seminars || 'N/A'}</span>}</div>
              <div className="info-item info-item-full"><label>Notes / Comments:</label>{editMode ? (<textarea name="notes" value={formData.notes} onChange={handleInputChange} className="input-light-gray" rows="4"/>) : (<p className="notes-display">{candidate.notes || '(No notes added)'}</p>)}</div>
              {['Evaluation', 'OfferMade', 'Hired', 'Declined'].includes(candidate.current_status) && (<div className="info-item"><label>Evaluation Rating:</label>{editMode ? <input type="text" name="evaluation_rating" value={formData.evaluation_rating} onChange={handleInputChange} className="input-light-gray"/> : <span>{candidate.evaluation_rating || 'N/A'}</span>}</div>)}
              {['OfferMade', 'Hired', 'Declined'].includes(candidate.current_status) && (<div className="info-item info-item-full"><label>Offer Details:</label>{editMode ? <textarea name="offer_details" value={formData.offer_details} onChange={handleInputChange} className="input-light-gray"/> : <p>{candidate.offer_details || 'N/A'}</p>}</div>)}
              {candidate.offer_response_date && (<div className="info-item"><label>Offer Response Date:</label><span>{formatDate(candidate.offer_response_date)}</span></div>)}
          </div>

          {/* Action Buttons based on candidate.current_status */}
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
                      <InterviewScheduler
                        onSchedule={handleScheduleInterview}
                        disabled={isUpdating}
                        inputClassName="input-light-gray"
                        initialDate={candidate.interview_datetime ? new Date(candidate.interview_datetime).toISOString().split('T')[0] : ''}
                        initialTime={candidate.interview_datetime ? new Date(candidate.interview_datetime).toTimeString().substring(0,5) : ''}
                        initialLocation={candidate.interview_location || ''}
                      />
                      <button onClick={() => handleUpdateStatus('Rejected')} className="button-action button-reject" disabled={isUpdating} style={{marginTop: '10px'}}>Reject Candidate</button>
                  </>
               )}
               {candidate.current_status === 'Interview' && (
                   <>
                      <p style={{fontWeight: 'bold', marginTop:'15px'}}>Interview Outcome:</p>
                      <button onClick={handleConfirmInterview} className="button-action button-confirm" disabled={isUpdating}>Confirm Happened (→ Evaluation)</button>
                      <button onClick={handleCancelOrRescheduleInterview} className="button-action button-cancel-schedule" disabled={isUpdating}>Cancel/Reschedule (→ Interested)</button>
                      <button onClick={handleRejectFromInterview} className="button-action button-reject" disabled={isUpdating}>Reject Candidate</button>
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
                {/* --- ΚΟΥΜΠΙ RE-EVALUATE --- */}
                {candidate && candidate.current_status && ['Rejected', 'Declined'].includes(candidate.current_status) && (
                  <>
                    <button
                      onClick={() => {
                        if (window.confirm(`Are you sure you want to move candidate ${candidate.full_name || candidate.candidate_id} back to "Needs Review"? This will clear interview and offer related data.`)) {
                          handleUpdateStatus('NeedsReview', {
                            interview_datetime: null,
                            interview_location: null,
                            candidate_confirmation_status: null,
                            evaluation_rating: null,
                            offer_details: null,
                            offer_response_date: null
                          });
                        }
                      }}
                      className="button-action button-secondary"
                      disabled={isUpdating}
                      title="Move candidate back to Needs Review to re-evaluate"
                      style={{marginTop: '15px'}}
                    >
                      Re-evaluate (Move to Needs Review)
                    </button>
                  </>
                )}
                {/* --- ΤΕΛΟΣ ΚΟΥΜΠΙΟΥ RE-EVALUATE --- */}

                {/* Εμφάνιση μηνύματος μόνο αν είναι Hired ΚΑΙ δεν είναι Rejected/Declined */}
                {candidate.current_status === 'Hired' && (
                  <p style={{ fontStyle: 'italic', color: 'var(--text-medium-gray)', marginTop: '15px' }}>No further actions available for this status.</p>
                )}
          </div>
        </div> {/* End Left Column */}

        {/* Right Column: CV & History */}
        <div className="detail-column detail-column-right">
           <div className="cv-viewer-section card-style">
             <h3>CV Document</h3>
             {cvUrl ? <CVViewer fileUrl={cvUrl} /> : <p>Loading CV...</p>}
           </div>
           <div className="history-log-section card-style">
             <h3>Candidate History</h3>
             <HistoryLog history={candidate.history || []} buttonClassName="button-cancel-schedule" />
           </div>
        </div> {/* End Right Column */}
      </div> {/* End Detail Content */}
    </div> // End Page Div
  );
}

export default CandidateDetailPage;