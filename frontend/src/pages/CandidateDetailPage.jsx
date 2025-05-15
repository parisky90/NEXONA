// frontend/src/pages/CandidateDetailPage.jsx
import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import apiClient from '../api';
import CVViewer from '../components/CVViewer';
import HistoryLog from '../components/HistoryLog';
import InterviewScheduler from '../components/InterviewScheduler';
import './CandidateDetailPage.css';

const getConfirmationStatusInfo = (confirmationStatus) => {
    switch (confirmationStatus) {
        case 'Confirmed': return { text: 'Επιβεβαιώθηκε από Υποψήφιο', color: 'green', className: 'status-confirmed' };
        case 'Declined': return { text: 'Απορρίφθηκε / Αίτημα Αλλαγής από Υποψήφιο', color: 'red', className: 'status-declined' };
        case 'Pending': return { text: 'Αναμονή Απάντησης από Υποψήφιο', color: 'orange', className: 'status-pending' };
        default: return { text: '', color: 'grey', className: 'status-unknown' };
    }
};

const RATING_OPTIONS = [
    { value: '', label: 'Επιλέξτε Βαθμολογία' },
    { value: 'Teleio', label: 'Τέλειο (5/5)' },
    { value: 'Polu Kalo', label: 'Πολύ Καλό (4/5)' },
    { value: 'Kalo', label: 'Καλό (3/5)' },
    { value: 'Metrio', label: 'Μέτριο (2/5)' },
    { value: 'Kako', label: 'Κακό (1/5)' },
];

function CandidateDetailPage() {
  const { candidateId } = useParams();
  const navigate = useNavigate();
  const [candidate, setCandidate] = useState(null);
  const [cvUrl, setCvUrl] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isUpdating, setIsUpdating] = useState(false);
  const [editMode, setEditMode] = useState(false);

  const initialFormDataState = {
    first_name: '', last_name: '', email: '', phone_number: '', age: '',
    positions: [], education_summary: '', experience_summary: '', skills_summary: '',
    languages: '', seminars: '', notes: '', evaluation_rating: '',
    hr_comments: '', // Προστέθηκε
    offers: [],
  };
  const [formData, setFormData] = useState(initialFormDataState);

  const initializeFormData = useCallback((data) => {
    if (!data) {
        setFormData(initialFormDataState);
        return;
    }
    console.log("Initializing formData with data:", data);
    setFormData({
        first_name: data.first_name || '',
        last_name: data.last_name || '',
        email: data.email || '',
        phone_number: data.phone_number || '',
        age: data.age === null || data.age === undefined ? '' : String(data.age),
        positions: Array.isArray(data.positions) ? data.positions.map(p => (typeof p === 'object' ? p.position_name : p)) : [],
        education_summary: data.education_summary || data.education || '',
        experience_summary: data.experience_summary || data.work_experience || '',
        skills_summary: data.skills_summary || '',
        languages: data.languages || '',
        seminars: data.seminars || '',
        notes: data.notes || '',
        evaluation_rating: data.evaluation_rating || '',
        hr_comments: data.hr_comments || '', // Προστέθηκε
        offers: Array.isArray(data.offers) ? data.offers.map(o => ({
            ...o,
            offer_amount: o.offer_amount === null || o.offer_amount === undefined ? '' : String(o.offer_amount),
            offer_date: o.offer_date ? o.offer_date.split('T')[0] : new Date().toISOString().split('T')[0]
        })) : [],
    });
  }, []);

  const fetchCandidateData = useCallback(async () => {
    setIsLoading(true); setError(null);
    console.log(`Fetching data for candidate ID: ${candidateId}`);
    try {
      const detailsRes = await apiClient.get(`/candidate/${candidateId}`);
      console.log("Candidate data from API (fetchCandidateData):", detailsRes.data);
      setCandidate(detailsRes.data);
      initializeFormData(detailsRes.data);

      console.log("CV Storage Path from API (fetchCandidateData):", detailsRes.data?.cv_storage_path);
      console.log("CV URL from API (if included in to_dict - fetchCandidateData):", detailsRes.data?.cv_url);

      if (detailsRes.data && detailsRes.data.cv_storage_path) {
        if (detailsRes.data.cv_url) {
            console.log("Using cv_url from candidate object (fetchCandidateData):", detailsRes.data.cv_url);
            setCvUrl(detailsRes.data.cv_url);
        } else {
            console.log("cv_url not in candidate object, fetching separately (fetchCandidateData)");
            const urlRes = await apiClient.get(`/candidate/${candidateId}/cv_url`);
            console.log("Fetched cv_url separately (fetchCandidateData):", urlRes.data.cv_url);
            setCvUrl(urlRes.data.cv_url);
        }
      } else {
        console.log("No cv_storage_path or no candidate data, setting cvUrl to null (fetchCandidateData)");
        setCvUrl(null);
      }
    } catch (err) {
      console.error("Fetch candidate error (fetchCandidateData):", err.response || err);
      setError(err.response?.data?.error || 'Failed to load candidate details.');
      setCandidate(null); setCvUrl(null);
    } finally {
      setIsLoading(false);
    }
  }, [candidateId, initializeFormData]);

  useEffect(() => { fetchCandidateData(); }, [fetchCandidateData]);

  const handleInputChange = (event) => {
    const { name, value } = event.target;
    setFormData(prevData => ({ ...prevData, [name]: value }));
  };

  const handlePositionChange = (event) => {
    const positionsArray = event.target.value.split(',').map(p => p.trim()).filter(p => p);
    setFormData(prevData => ({ ...prevData, positions: positionsArray }));
  };

  const handleOfferChange = (index, field, value) => {
    const updatedOffers = formData.offers.map((offer, i) =>
        i === index ? { ...offer, [field]: value } : offer
    );
    setFormData(prev => ({ ...prev, offers: updatedOffers }));
  };

  const addOfferField = () => {
    setFormData(prev => ({
        ...prev,
        offers: [ ...prev.offers, { offer_amount: '', offer_notes: '', offer_date: new Date().toISOString().split('T')[0] } ]
    }));
  };

  const removeOfferField = (index) => {
    const updatedOffers = formData.offers.filter((_, i) => i !== index);
    setFormData(prev => ({ ...prev, offers: updatedOffers }));
  };

  const sendUpdateRequest = async (payload) => {
    if (!candidate) return;
    setIsUpdating(true); setError(null);
    try {
      console.log("sendUpdateRequest: Sending PUT request to backend with payload:", payload);
      const response = await apiClient.put(`/candidate/${candidate.candidate_id}`, payload);
      console.log("sendUpdateRequest: PUT request successful, response data:", response.data);
      setCandidate(response.data);
      initializeFormData(response.data);
      setEditMode(false);
      return response.data;
    } catch (err) {
      console.error("sendUpdateRequest: Update candidate error:", err.response || err);
      setError(err.response?.data?.error || `Failed to update candidate.`);
      throw err;
    } finally {
      setIsUpdating(false);
    }
  };

  const handleUpdateStatus = async (newStatus, extraData = {}) => {
    if (!candidate) return;
    const notesForPayload = editMode && !extraData.notes ? formData.notes : (extraData.notes || candidate?.notes || '');
    // Το hr_comments δεν το αγγίζουμε εδώ, εκτός αν το περάσουμε στο extraData
    let payload = {
        current_status: newStatus,
        notes: notesForPayload,
        ...extraData
    };

    if (newStatus === 'OfferMade' && !extraData.offers) {
        const offersToSend = formData.offers.map(o => ({
            ...o,
            offer_amount: o.offer_amount === '' || o.offer_amount === null ? null : parseFloat(o.offer_amount),
            offer_date: o.offer_date ? new Date(o.offer_date).toISOString() : new Date().toISOString()
        })).filter(o => o.offer_amount !== null || (o.offer_notes && o.offer_notes.trim() !== ''));
        payload.offers = offersToSend.length > 0 ? offersToSend : [{ offer_amount: null, offer_notes: 'Initial Offer', offer_date: new Date().toISOString() }];
    }
    if (payload.interview_datetime === '') payload.interview_datetime = null;

    console.log("handleUpdateStatus: Attempting to update status to:", newStatus, "with payload:", payload);
    try {
      const updatedCandidateData = await sendUpdateRequest(payload);
      if (updatedCandidateData.cv_url) { setCvUrl(updatedCandidateData.cv_url); }
      else if (updatedCandidateData.cv_storage_path) {
        try {
            const urlRes = await apiClient.get(`/candidate/${updatedCandidateData.candidate_id}/cv_url`);
            setCvUrl(urlRes.data.cv_url);
        } catch (urlErr) { console.error("Failed to fetch new CV URL after status update:", urlErr); }
      }

      if (newStatus === 'Rejected') { console.log("Navigating to /candidates/Rejected"); navigate('/candidates/Rejected', { replace: true }); }
      else if (newStatus === 'Declined') { console.log("Navigating to /candidates/Declined"); navigate('/candidates/Declined', { replace: true }); }
      else if (newStatus === 'Hired') { console.log("Navigating to /candidates/Hired"); navigate('/candidates/Hired', { replace: true }); }
      else if (newStatus === 'Accepted') { console.log("Navigating to /candidates/Accepted"); navigate('/candidates/Accepted', { replace: true });}
    } catch (err) { /* Error handled in sendUpdateRequest */ }
  };

  const handleSaveChanges = async () => {
      if (!candidate) return;
      const updatePayload = {
         first_name: formData.first_name,
         last_name: formData.last_name,
         email: formData.email,
         phone_number: formData.phone_number,
         age: formData.age === '' || formData.age === null ? null : Number(formData.age),
         positions: formData.positions,
         education_summary: formData.education_summary,
         experience_summary: formData.experience_summary,
         skills_summary: formData.skills_summary,
         languages: formData.languages,
         seminars: formData.seminars,
         notes: formData.notes,
         hr_comments: formData.hr_comments, // Αποστολή hr_comments
         evaluation_rating: formData.evaluation_rating,
         offers: formData.offers.map(o => ({
            ...o,
            offer_amount: o.offer_amount === '' || o.offer_amount === null ? null : parseFloat(o.offer_amount),
            offer_date: o.offer_date ? new Date(o.offer_date).toISOString() : new Date().toISOString()
         })).filter(o => o.offer_amount !== null || (o.offer_notes && o.offer_notes.trim() !== '')),
      };
      console.log("handleSaveChanges: Payload for saving changes:", updatePayload);
      try {
        await sendUpdateRequest(updatePayload);
      } catch (err) { /* Error handled in sendUpdateRequest */ }
  };

  const handleScheduleInterview = async ({ date, time, location, type }) => {
       if (!candidate || !date || !time) { setError("Please select both date and time for the interview."); return; }
       try {
           const localDateTime = new Date(`${date}T${time}:00`);
           if (isNaN(localDateTime.getTime())) { throw new Error("Invalid date/time combination."); }
           const utcDateTimeISO = localDateTime.toISOString();
           console.log("handleScheduleInterview: Scheduling interview with UTC ISO:", utcDateTimeISO, "Location:", location, "Type:", type);
           await handleUpdateStatus('Interview', {
             interview_datetime: utcDateTimeISO,
             interview_location: location || '',
             interview_type: type || '',
           });
       } catch (e) { setError(`Failed to schedule interview: ${e.message}`); }
  };

  const handleConfirmInterviewOutcome = () => handleUpdateStatus('Evaluation');
  const handleCancelOrRescheduleInterview = () => handleUpdateStatus('Interested', {
    interview_datetime: null, interview_location: null, interview_type: null, candidate_confirmation_status: null,
  });
  const handleRejectPostInterview = () => handleUpdateStatus('Rejected');
  const handleMakeOffer = () => {
    if (!formData.offers || formData.offers.length === 0 || formData.offers.every(o => !o.offer_amount && !o.offer_notes)) {
        addOfferField();
    }
    handleUpdateStatus('OfferMade');
    setEditMode(true);
  };
  const handleOfferAccepted = () => handleUpdateStatus('Hired');
  const handleOfferDeclinedByCandidate = () => handleUpdateStatus('Declined');

  const formatDate = (isoString) => {
    if (!isoString) return 'N/A';
    try {
        return new Date(isoString).toLocaleString([], { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false });
    } catch { return 'Invalid Date'; }
  };

  const getRatingLabel = (value) => {
    const option = RATING_OPTIONS.find(opt => opt.value === value);
    return option ? option.label : (value || 'N/A');
  };

  if (isLoading && !candidate) return <div className="loading-placeholder card-style">Loading candidate details...</div>;
  if (error && !candidate && !isUpdating) return <div className="error-message card-style">Error: {error} <button onClick={fetchCandidateData} className="button-action button-secondary">Retry</button></div>;
  if (!candidate && !isLoading) return <div className="card-style">Candidate not found or data unavailable. <Link to="/dashboard">Go to Dashboard</Link></div>;
  if (!candidate) return null;

  const confirmationDisplayInfo = getConfirmationStatusInfo(candidate.candidate_confirmation_status);

  return (
    <div className="candidate-detail-page">
      <button onClick={() => navigate(-1)} className="back-link">← Back</button>
      {error && !isUpdating && <div className="error-message" style={{marginBottom: '1rem'}}>{error} <button onClick={() => setError(null)}>Dismiss</button></div>}
      {isUpdating && <div className="loading-placeholder-action card-style" style={{textAlign: 'center', padding: '1rem', marginBottom: '1rem'}}>Updating...</div>}

      <div className="detail-header">
         <h2>{editMode ? `${formData.first_name || ''} ${formData.last_name || ''}`.trim() || 'Edit Candidate' : `${candidate.first_name || ''} ${candidate.last_name || 'Candidate Details'}`.trim()}</h2>
         <div className="header-actions">
            {!editMode ? (
                <button onClick={() => { setEditMode(true); initializeFormData(candidate); setError(null); }} className="button-action button-edit" disabled={isUpdating}>Edit Details</button>
            ) : (
                <>
                    <button onClick={handleSaveChanges} className="button-action button-save" disabled={isUpdating}>{isUpdating ? 'Saving...' : 'Save Changes'}</button>
                    <button onClick={() => { setEditMode(false); initializeFormData(candidate); setError(null); }} className="button-action button-cancel" disabled={isUpdating}>Cancel Edit</button>
                </>
            )}
         </div>
      </div>

      <div className="detail-content">
        <div className="detail-column detail-column-left">
          <h3>Candidate Information</h3>
          <div className="info-grid">
            {/* ... (fields: first_name, last_name, email, phone, age, positions, status, submission_date) ... */}
            <div className="info-item"><label>First Name:</label>{editMode ? <input type="text" name="first_name" value={formData.first_name} onChange={handleInputChange} className="input-light-gray"/> : <span>{candidate.first_name || 'N/A'}</span>}</div>
            <div className="info-item"><label>Last Name:</label>{editMode ? <input type="text" name="last_name" value={formData.last_name} onChange={handleInputChange} className="input-light-gray"/> : <span>{candidate.last_name || 'N/A'}</span>}</div>
            <div className="info-item"><label>Email:</label>{editMode ? <input type="email" name="email" value={formData.email} onChange={handleInputChange} className="input-light-gray"/> : <span>{candidate.email || 'N/A'}</span>}</div>
            <div className="info-item"><label>Phone:</label>{editMode ? <input type="tel" name="phone_number" value={formData.phone_number} onChange={handleInputChange} className="input-light-gray"/> : <span>{candidate.phone_number || 'N/A'}</span>}</div>
            <div className="info-item"><label>Age:</label>{editMode ? <input type="number" name="age" value={formData.age} onChange={handleInputChange} className="input-light-gray"/> : <span>{candidate.age || 'N/A'}</span>}</div>
            <div className="info-item"><label>Applied for Position(s):</label>{editMode ? <input type="text" name="positions" value={formData.positions.join(', ')} onChange={handlePositionChange} className="input-light-gray" placeholder="Comma-separated"/> : <span>{candidate.positions?.map(p => typeof p === 'object' ? p.position_name : p).join(', ') || 'N/A'}</span>}</div>
            <div className="info-item"><label>Current Status:</label><span className={`status-badge status-${candidate.current_status?.toLowerCase().replace(/\s+/g, '-')}`}>{candidate.current_status || 'N/A'}</span></div>
            <div className="info-item"><label>Submission Date:</label><span>{formatDate(candidate.submission_date)}</span></div>
            
            {candidate.interview_datetime && (
                <>
                    <div className="info-item info-item-full">
                        <label>Scheduled Interview:</label>
                        <span>
                            {formatDate(candidate.interview_datetime)}
                            {candidate.interview_location ? ` at ${candidate.interview_location}` : ''}
                            {candidate.interview_type ? ` (${candidate.interview_type})` : ''}
                        </span>
                    </div>
                    {confirmationDisplayInfo && confirmationDisplayInfo.text && (
                        <div className="info-item info-item-full">
                            <label>Candidate Confirmation:</label>
                            <span style={{ color: confirmationDisplayInfo.color, fontWeight: 'bold', padding: '3px 8px', borderRadius: '12px', backgroundColor: `${confirmationDisplayInfo.color}20`, fontSize: '0.85rem' }} className={`status-badge ${confirmationDisplayInfo.className}`}>
                                {confirmationDisplayInfo.text}
                            </span>
                        </div>
                    )}
                </>
            )}

            <div className="info-item">
                <label>Evaluation Rating (HR):</label>
                {editMode ? ( <select name="evaluation_rating" value={formData.evaluation_rating || ''} onChange={handleInputChange} className="input-light-gray">{RATING_OPTIONS.map(option => (<option key={option.value} value={option.value}>{option.label}</option>))}</select> ) : ( <span>{getRatingLabel(candidate.evaluation_rating)}</span> )}
            </div>

            <div className="info-item info-item-full"><label>Education Summary:</label>{editMode ? <textarea name="education_summary" value={formData.education_summary} onChange={handleInputChange} className="input-light-gray" rows="3"/> : <p>{candidate.education_summary || candidate.education || 'N/A'}</p>}</div>
            <div className="info-item info-item-full"><label>Work Experience Summary:</label>{editMode ? <textarea name="experience_summary" value={formData.experience_summary} onChange={handleInputChange} className="input-light-gray" rows="5"/> : <p>{candidate.experience_summary || candidate.work_experience || 'N/A'}</p>}</div>
            <div className="info-item"><label>Languages:</label>{editMode ? <input type="text" name="languages" value={formData.languages} onChange={handleInputChange} className="input-light-gray"/> : <span>{candidate.languages || 'N/A'}</span>}</div>
            <div className="info-item"><label>Seminars/Certifications:</label>{editMode ? <input type="text" name="seminars" value={formData.seminars} onChange={handleInputChange} className="input-light-gray"/> : <span>{candidate.seminars || 'N/A'}</span>}</div>
            
            <div className="info-item info-item-full">
                <label>General Notes / Auto-Parsed Info:</label>
                {editMode ? (
                    <textarea name="notes" value={formData.notes} onChange={handleInputChange} className="input-light-gray" rows="4"/>
                ) : (
                    <p className="notes-display">{candidate.notes || '(No general notes)'}</p>
                )}
            </div>
            
            {/* --- HR Internal Comments --- */}
            <div className="info-item info-item-full">
                <label style={{fontWeight: 'bold', color: 'var(--primary-color)'}}>HR Internal Comments:</label>
                {editMode ? (
                    <textarea
                        name="hr_comments"
                        value={formData.hr_comments}
                        onChange={handleInputChange}
                        className="input-light-gray"
                        rows="4"
                        placeholder="Internal comments for HR team only..."
                    />
                ) : (
                    <p className="notes-display" style={{borderLeft: '3px solid var(--primary-color)', paddingLeft: '10px', fontStyle: 'italic', backgroundColor: '#f0f4f8', whiteSpace: 'pre-wrap'}}>
                        {candidate.hr_comments || '(No HR comments added)'}
                    </p>
                )}
            </div>
            
            {(editMode || (candidate.offers && candidate.offers.length > 0 && candidate.offers.some(o => o.offer_amount || o.offer_notes)) || candidate.current_status === 'OfferMade') && (
                 <div className="info-item info-item-full offers-section">
                    <label style={{borderBottom: '1px solid var(--border-color)', paddingBottom: '5px', marginBottom: '10px'}}>Offer(s):</label>
                    {formData.offers && formData.offers.map((offer, index) => (
                        <div key={index} className="offer-item">
                            <div className="offer-header">
                                <span>Offer {index + 1}</span>
                                {editMode && ( <button type="button" onClick={() => removeOfferField(index)} className="button-action button-reject" style={{fontSize:'0.7rem', padding:'2px 5px', marginLeft:'10px'}}>Remove</button> )}
                            </div>
                            <div className="info-item">
                                <label htmlFor={`offer_amount_${index}`}>Amount (€):</label>
                                {editMode ? ( <input type="number" id={`offer_amount_${index}`} name="offer_amount" value={offer.offer_amount || ''} onChange={(e) => handleOfferChange(index, 'offer_amount', e.target.value)} className="input-light-gray" placeholder="e.g., 1500.50" step="0.01"/> ) : ( <span>{offer.offer_amount ? `${parseFloat(offer.offer_amount).toFixed(2)} €` : 'N/A'}</span> )}
                            </div>
                            <div className="info-item">
                                <label htmlFor={`offer_date_${index}`}>Offer Date:</label>
                                {editMode ? ( <input type="date" id={`offer_date_${index}`} name="offer_date" value={offer.offer_date ? offer.offer_date.split('T')[0] : ''} onChange={(e) => handleOfferChange(index, 'offer_date', e.target.value)} className="input-light-gray"/> ) : ( <span>{formatDate(offer.offer_date)}</span> )}
                            </div>
                            <div className="info-item info-item-full">
                                <label htmlFor={`offer_notes_${index}`}>Offer Notes:</label>
                                {editMode ? ( <textarea id={`offer_notes_${index}`} name="offer_notes" value={offer.offer_notes || ''} onChange={(e) => handleOfferChange(index, 'offer_notes', e.target.value)} className="input-light-gray" rows="2"/> ) : ( <p className="notes-display" style={{minHeight: 'auto', fontSize:'0.9em'}}>{offer.offer_notes || '(No notes)'}</p> )}
                            </div>
                        </div>
                    ))}
                    {editMode && ( <button type="button" onClick={addOfferField} className="button-action button-primary" style={{marginTop: '10px', fontSize: '0.85rem'}}>+ Add Offer</button> )}
                </div>
            )}
          </div>

          {!editMode && ( /* Action Buttons - ίδια με πριν */
            <div className="action-buttons">
                <h4>Candidate Actions</h4>
                {candidate.current_status === 'NeedsReview' && ( <><button onClick={() => handleUpdateStatus('Accepted')} className="button-action button-accept" disabled={isUpdating}>Mark for Initial Review (→ Accepted)</button><button onClick={() => handleUpdateStatus('Rejected', {notes: `Rejected at NeedsReview stage. ${formData.notes || candidate.notes || ''}`.trim()})} className="button-action button-reject" disabled={isUpdating}>Reject Candidate</button></> )}
                {candidate.current_status === 'Accepted' && ( <><button onClick={() => handleUpdateStatus('Interested')} className="button-action button-primary" disabled={isUpdating}>Consider for Interview (→ Interested)</button><button onClick={() => handleUpdateStatus('Rejected', {notes: `Rejected at Accepted stage. ${formData.notes || candidate.notes || ''}`.trim()})} className="button-action button-reject" disabled={isUpdating}>Reject Candidate</button></> )}
                {candidate.current_status === 'Interested' && (
                    <>
                        <InterviewScheduler
                            onSchedule={handleScheduleInterview} disabled={isUpdating} inputClassName="input-light-gray"
                            initialDate={candidate.interview_datetime ? new Date(candidate.interview_datetime).toISOString().split('T')[0] : ''}
                            initialTime={candidate.interview_datetime ? new Date(candidate.interview_datetime).toTimeString().substring(0,5) : ''}
                            initialLocation={candidate.interview_location || ''} initialType={candidate.interview_type || ''}
                        />
                        <button onClick={() => { if(window.confirm("Are you sure you want to skip scheduling an interview and move this candidate directly to Evaluation? This will clear any previously scheduled interview details.")) { handleUpdateStatus('Evaluation', { notes: `${formData.notes || candidate.notes || ''}\n(Interview skipped by HR, moved directly to Evaluation)`.trim(), interview_datetime: null, interview_location: null, interview_type: null, candidate_confirmation_status: null }); } }}
                            className="button-action button-secondary" disabled={isUpdating} style={{marginTop: '10px'}} title="Move directly to Evaluation stage without scheduling an interview">
                            Skip Interview (→ Evaluation)
                        </button>
                        <button onClick={() => handleUpdateStatus('Rejected', {notes: `Rejected at Interested stage. ${formData.notes || candidate.notes || ''}`.trim()})} className="button-action button-reject" disabled={isUpdating} style={{marginTop: '10px'}}>Reject Candidate</button>
                    </>
                )}
                {candidate.current_status === 'Interview' && (
                    <>
                        <p style={{fontWeight: 'bold', marginTop:'15px'}}>Interview Outcome:</p>
                        <button onClick={handleConfirmInterviewOutcome} className="button-action button-confirm" disabled={isUpdating}>Interview Successful (→ Evaluation)</button>
                        <button onClick={handleCancelOrRescheduleInterview} className="button-action button-cancel-schedule" disabled={isUpdating}>Cancel/Reschedule (→ Interested)</button>
                        <button onClick={handleRejectPostInterview} className="button-action button-reject" disabled={isUpdating}>Reject Post-Interview</button>
                    </>
                )}
                {candidate.current_status === 'Evaluation' && (
                    <>
                        <button onClick={handleMakeOffer} className="button-action button-accept" disabled={isUpdating}>Make Offer (→ OfferMade)</button>
                        <button onClick={() => handleUpdateStatus('Rejected', {notes: `Rejected at Evaluation stage. ${formData.notes || candidate.notes || ''}`.trim()})} className="button-action button-reject" disabled={isUpdating}>Reject Candidate</button>
                    </>
                )}
                {candidate.current_status === 'OfferMade' && (
                    <>
                        <p style={{fontWeight: 'bold', marginTop:'15px'}}>Offer Response:</p>
                        <button onClick={handleOfferAccepted} className="button-action button-accept" disabled={isUpdating}>Candidate Accepted Offer (→ Hired)</button>
                        <button onClick={handleOfferDeclinedByCandidate} className="button-action button-reject" disabled={isUpdating}>Candidate Declined Offer (→ Declined)</button>
                    </>
                )}
                {candidate.current_status && ['Rejected', 'Declined', 'ParsingFailed'].includes(candidate.current_status) && ( // Προσθήκη ParsingFailed εδώ
                    <button
                        onClick={() => {
                            if (window.confirm(`Are you sure you want to move candidate ${candidate.first_name || candidate.candidate_id} back to "Needs Review"? This will clear interview, evaluation, and offer related data.`)) {
                                handleUpdateStatus('NeedsReview', {
                                    interview_datetime: null, interview_location: null, interview_type: null, candidate_confirmation_status: null,
                                    evaluation_rating: '', offers: [], hr_comments: candidate.hr_comments || '' // Διατήρηση των HR comments
                                });
                            }
                        }}
                        className="button-action button-secondary" disabled={isUpdating} title="Move candidate back to Needs Review to re-evaluate" style={{marginTop: '15px'}}
                    >
                        Re-evaluate (Move to Needs Review)
                    </button>
                )}
                {candidate.current_status === 'Hired' && ( <p style={{ fontStyle: 'italic', color: 'var(--text-medium-gray)', marginTop: '15px' }}>Candidate Hired. No further status actions available.</p> )}
            </div>
          )}
        </div>

        <div className="detail-column detail-column-right">
           <div className="cv-viewer-section card-style">
             <h3>CV Document</h3>
             {console.log("Render - CV URL:", cvUrl, "Original Filename:", candidate?.cv_original_filename)}
             {cvUrl && candidate?.cv_original_filename ? (
                candidate.cv_original_filename.toLowerCase().endsWith('.pdf') ? (
                    <CVViewer
                        fileUrl={cvUrl}
                        onError={(errMsg) => {
                            console.error("CVViewer PDF onError:", errMsg);
                            setError(prev => `${prev ? prev + '\n' : ''}CV Preview Error: Could not load PDF. You can try downloading it.`);
                        }}
                    />
                ) : (
                    <div className="cv-download-link" style={{padding: '1rem', border: '1px solid #ddd', borderRadius: '4px', textAlign: 'center', backgroundColor: '#f9f9f9'}}>
                        <p style={{fontWeight: 'bold', marginBottom: '0.5rem'}}>{candidate.cv_original_filename}</p>
                        <p style={{fontSize: '0.9em', marginBottom: '1rem'}}>Preview is not available for this file type (.${candidate.cv_original_filename.split('.').pop()}).</p>
                        <a
                            href={cvUrl}
                            download={candidate.cv_original_filename}
                            className="button-action button-primary"
                            style={{textDecoration: 'none', padding: '8px 15px'}}
                        >
                            Download CV
                        </a>
                    </div>
                )
             ) : (
                <p>{candidate && candidate.cv_storage_path ? 'Loading CV...' : (candidate?.current_status === 'ParsingFailed' && !candidate.cv_storage_path ? 'CV parsing failed and no CV file seems to be stored.' : (candidate?.current_status === 'ParsingFailed' ? 'CV parsing may have failed or CV is not viewable.' : 'No CV uploaded or available.'))}</p>
             )}
           </div>
           <div className="history-log-section card-style">
             <h3>Candidate History</h3>
             <HistoryLog history={candidate?.history || []} />
           </div>
        </div>
      </div>
    </div>
  );
}

export default CandidateDetailPage;