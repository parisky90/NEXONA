// frontend/src/pages/CandidateDetailPage.jsx
import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import apiClient from '../api';
import CVViewer from '../components/CVViewer';
import HistoryLog from '../components/HistoryLog';
// import InterviewScheduler from '../components/InterviewScheduler'; // Μπορεί να μην χρησιμοποιείται πλέον απευθείας
import InterviewProposalForm from '../components/InterviewProposalForm';
import ModalDialog from '../components/ModalDialog';
import { useAuth } from '../App';
import './CandidateDetailPage.css';

const getConfirmationStatusInfo = (confirmationStatus) => {
    // ... (παραμένει ίδιο)
    switch (confirmationStatus) {
        case 'Confirmed': return { text: 'Επιβεβαιώθηκε από Υποψήφιο', color: 'green', className: 'status-confirmed' };
        case 'DeclinedSlots': return { text: 'Απορρίφθηκαν Slots από Υποψήφιο', color: '#cc8500', className: 'status-declined-slots' }; // Πιο σκούρο πορτοκαλί
        case 'CancelledByUser': return { text: 'Ακυρώθηκε από Υποψήφιο', color: 'red', className: 'status-cancelled-user' };
        case 'Pending': return { text: 'Αναμονή Απάντησης από Υποψήφιο', color: 'orange', className: 'status-pending' };
        default: return { text: '', color: 'grey', className: 'status-unknown' }; // Κενό αν null ή undefined
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
  const { currentUser } = useAuth();

  const [candidate, setCandidate] = useState(null);
  const [cvUrl, setCvUrl] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isUpdating, setIsUpdating] = useState(false);
  const [isSubmittingInterview, setIsSubmittingInterview] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [showProposalModal, setShowProposalModal] = useState(false);

  const [companyOpenPositions, setCompanyOpenPositions] = useState([]);
  const [isLoadingCompanyPositions, setIsLoadingCompanyPositions] = useState(false);


  const initialFormDataState = {
    first_name: '', last_name: '', email: '', phone_number: '', age: '',
    positions: [], education_summary: '', experience_summary: '', skills_summary: '',
    languages: '', seminars: '', notes: '', evaluation_rating: '',
    hr_comments: '', offers: [],
  };
  const [formData, setFormData] = useState(initialFormDataState);

  const getRatingLabel = (value) => {
    const option = RATING_OPTIONS.find(opt => opt.value === value);
    return option ? option.label : (value || 'N/A');
  };

  const initializeFormData = useCallback((data) => {
    if (!data) {
        setFormData(initialFormDataState);
        return;
    }
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
        hr_comments: data.hr_comments || '',
        offers: Array.isArray(data.offers) ? data.offers.map(o => ({
            ...o,
            offer_amount: o.offer_amount === null || o.offer_amount === undefined ? '' : String(o.offer_amount),
            offer_date: o.offer_date ? o.offer_date.split('T')[0] : new Date().toISOString().split('T')[0] // Ensure valid date for input type=date
        })) : [],
    });
  }, []); // initialFormDataState is stable

  const fetchCandidateData = useCallback(async () => {
    setIsLoading(true); setError(null);
    try {
      const detailsRes = await apiClient.get(`/candidate/${candidateId}`);
      setCandidate(detailsRes.data);
      initializeFormData(detailsRes.data);

      if (detailsRes.data && detailsRes.data.cv_url) {
            setCvUrl(detailsRes.data.cv_url);
      } else if (detailsRes.data && detailsRes.data.cv_storage_path) {
            console.warn("CV URL not directly provided in candidate data, was expecting candidate.cv_url. Attempting fallback if logic existed.");
            // Fallback logic to fetch presigned URL could go here if backend didn't provide it.
            // For now, assuming to_dict in backend will always try to include it.
            setCvUrl(null); // Or set to a generic "cannot display" URL
      } else {
            setCvUrl(null);
      }
    } catch (err) {
      console.error("Fetch candidate error:", err.response || err);
      setError(err.response?.data?.error || 'Failed to load candidate details.');
      setCandidate(null); setCvUrl(null);
    } finally {
      setIsLoading(false);
    }
  }, [candidateId, initializeFormData]);

  useEffect(() => { fetchCandidateData(); }, [fetchCandidateData]);

  useEffect(() => {
    const fetchOpenPositionsForCompany = async (companyIdForFetch) => {
        if (!companyIdForFetch) {
            setCompanyOpenPositions([]);
            return;
        }
        setIsLoadingCompanyPositions(true);
        try {
            // Ensure the user has rights to this company's positions if companyIdForFetch is not their own
            const response = await apiClient.get(`/company/${companyIdForFetch}/positions?status=Open`);
            setCompanyOpenPositions(response.data.positions || []);
        } catch (error) {
            console.error("Error fetching company open positions:", error.response?.data || error.message);
            setCompanyOpenPositions([]); // Set to empty on error
        } finally {
            setIsLoadingCompanyPositions(false);
        }
    };

    if (candidate && candidate.company_id) {
        fetchOpenPositionsForCompany(candidate.company_id);
    } else {
        setCompanyOpenPositions([]);
    }
  }, [candidate?.company_id]); // Dependency on candidate.company_id


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
      const response = await apiClient.put(`/candidate/${candidate.candidate_id}`, payload);
      setCandidate(response.data); // Update local candidate state with response
      initializeFormData(response.data); // Re-initialize form with fresh data
      if (response.data.cv_url) setCvUrl(response.data.cv_url); // Update CV URL if changed
      setEditMode(false); // Exit edit mode on successful save
      return response.data;
    } catch (err) {
      console.error("Update candidate error:", err.response || err);
      setError(err.response?.data?.error || `Failed to update candidate.`);
      throw err; // Re-throw to be caught by caller if needed
    } finally {
      setIsUpdating(false);
    }
  };

  const handleUpdateStatus = async (newStatus, extraData = {}) => {
    if (!candidate) return;
    const notesForPayload = editMode && !extraData.notes ? formData.notes : (extraData.notes || candidate?.notes || '');
    let payload = {
        current_status: newStatus,
        notes: notesForPayload,
        hr_comments: editMode ? formData.hr_comments : (extraData.hr_comments || candidate?.hr_comments || ''),
        ...extraData
    };
    if (newStatus === 'OfferMade' && (!extraData.offers && (!formData.offers || formData.offers.length === 0))) {
         // If moving to OfferMade and no offers are in extraData or formData, add a placeholder offer
        payload.offers = [{ offer_amount: null, offer_notes: 'Initial offer pending details.', offer_date: new Date().toISOString() }];
    } else if (newStatus === 'OfferMade' && !extraData.offers) {
        // If moving to OfferMade and no offers in extraData, use formData.offers
        payload.offers = formData.offers.map(o => ({
            ...o,
            offer_amount: o.offer_amount === '' || o.offer_amount === null ? null : parseFloat(o.offer_amount),
            offer_date: o.offer_date ? new Date(o.offer_date).toISOString() : new Date().toISOString()
        })).filter(o => o.offer_amount !== null || (o.offer_notes && o.offer_notes.trim() !== ''));
        if (payload.offers.length === 0) { // Still no offers, add placeholder
            payload.offers = [{ offer_amount: null, offer_notes: 'Initial offer pending details.', offer_date: new Date().toISOString() }];
        }
    }


    try {
      const updatedCandidateData = await sendUpdateRequest(payload);
      // Navigation logic (optional, can be based on user experience preference)
      // if (newStatus === 'Rejected') { navigate('/candidates/Rejected', { replace: true }); }
      // else if (newStatus === 'Declined') { navigate('/candidates/Declined', { replace: true }); }
      // else if (newStatus === 'Hired') { navigate('/candidates/Hired', { replace: true }); }
    } catch (err) { /* Error handled in sendUpdateRequest */ }
  };

  const handleSaveChanges = async () => {
      if (!candidate) return;
      const updatePayload = {
         first_name: formData.first_name, last_name: formData.last_name, email: formData.email,
         phone_number: formData.phone_number, age: formData.age === '' || formData.age === null ? null : Number(formData.age),
         positions: formData.positions, education_summary: formData.education_summary, experience_summary: formData.experience_summary,
         skills_summary: formData.skills_summary, languages: formData.languages, seminars: formData.seminars,
         notes: formData.notes, hr_comments: formData.hr_comments, evaluation_rating: formData.evaluation_rating,
         offers: formData.offers.map(o => ({
            ...o,
            offer_amount: o.offer_amount === '' || o.offer_amount === null ? null : parseFloat(o.offer_amount),
            offer_date: o.offer_date ? new Date(o.offer_date).toISOString() : new Date().toISOString() // ensure ISO format
         })).filter(o => o.offer_amount !== null || (o.offer_notes && o.offer_notes.trim() !== '')),
         // Δεν στέλνουμε το current_status εδώ, αυτό γίνεται μέσω handleUpdateStatus
      };
      try { await sendUpdateRequest(updatePayload); } catch (err) { /* Error handled */ }
  };


  const handleProposeInterviewClick = () => {
    if (isLoadingCompanyPositions) {
        alert("Company positions are still loading. Please wait a moment.");
        return;
    }
    if (!candidate || !candidate.company_id) {
        alert("Cannot propose interview: Candidate company information is missing.");
        return;
    }
    setShowProposalModal(true);
  };

  const handleSendInterviewProposal = async (proposalData) => {
    if (!candidate) return;
    setIsSubmittingInterview(true);
    setError(null); // Clear previous errors
    try {
      const response = await apiClient.post(`/candidates/${candidate.candidate_id}/propose-interview`, proposalData);
      setShowProposalModal(false);
      // fetchCandidateData(); // Re-fetch candidate data to show updated status and interview info
      // Instead of full re-fetch, update candidate state locally with the new interview status
      setCandidate(prev => ({
          ...prev,
          current_status: "Interview Proposed", // Assume backend sets this
          interviews: prev.interviews ? [...prev.interviews, response.data] : [response.data], // Add new interview
          history: response.data.history ? [...(prev.history || []), ...response.data.history] : prev.history // if history is returned
      }));

      alert(`Interview proposed successfully! Candidate status is now "Interview Proposed". The candidate will be notified.`);
    } catch (err) {
      console.error("Error proposing interview:", err.response?.data || err.message);
      setError(err.response?.data?.error || 'Failed to propose interview.');
    } finally {
      setIsSubmittingInterview(false);
    }
  };


  const handleConfirmInterviewOutcome = () => handleUpdateStatus('Evaluation');
  const handleCancelOrRescheduleInterview = () => {
    if (window.confirm("This will cancel the currently scheduled interview and move the candidate back to 'Interested'. Are you sure?")) {
        handleUpdateStatus('Interested', {
            candidate_confirmation_status: null, // Reset confirmation
            // Backend should handle cancellation of the Interview object
        });
    }
  };
  const handleRejectPostInterview = () => handleUpdateStatus('Rejected', {notes: `Rejected after interview stage. ${formData.hr_comments || candidate.hr_comments || ''}`.trim()});
  const handleMakeOffer = () => {
    if (!formData.offers || formData.offers.length === 0 || formData.offers.every(o => !o.offer_amount && !o.offer_notes)) {
        addOfferField(); // Add one empty offer if none exist
    }
    handleUpdateStatus('OfferMade');
    if (!editMode) setEditMode(true); // Enter edit mode to fill offer details
  };
  const handleOfferAccepted = () => handleUpdateStatus('Hired');
  const handleOfferDeclinedByCandidate = () => handleUpdateStatus('Declined', {notes: `Offer declined by candidate. ${formData.hr_comments || candidate.hr_comments || ''}`.trim()});

  const formatDate = (isoString) => {
    if (!isoString) return 'N/A';
    try {
        // Display in local time. Assume isoString is UTC.
        return new Date(isoString).toLocaleString([], { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false });
    } catch { return 'Invalid Date'; }
  };


  if (isLoading && !candidate) return <div className="loading-placeholder card-style">Loading candidate details...</div>;
  if (error && !candidate && !isUpdating && !isSubmittingInterview) return <div className="error-message card-style">Error: {error} <button onClick={fetchCandidateData} className="button-action button-secondary">Retry</button></div>;
  if (!candidate && !isLoading) return <div className="card-style">Candidate not found or data unavailable. <Link to="/dashboard">Go to Dashboard</Link></div>;
  if (!candidate) return null; // Should be caught by above conditions

  const candidateResponseInfo = getConfirmationStatusInfo(candidate.candidate_confirmation_status);
  const latestScheduledInterview = candidate.interviews?.filter(inv => inv.status === 'SCHEDULED').sort((a,b) => new Date(b.created_at) - new Date(a.created_at))[0];
  const latestProposedInterview = candidate.interviews?.filter(inv => inv.status === 'PROPOSED').sort((a,b) => new Date(b.created_at) - new Date(a.created_at))[0];


  return (
    <div className="candidate-detail-page">
      <button onClick={() => navigate(-1)} className="back-link">← Back</button>
      {error && !isUpdating && !isSubmittingInterview && <div className="error-message" style={{marginBottom: '1rem'}}>{error} <button onClick={() => setError(null)} className="button-action button-secondary" style={{marginLeft:'10px', padding:'3px 8px'}}>Dismiss</button></div>}
      {(isUpdating || isSubmittingInterview) && <div className="loading-placeholder-action card-style" style={{textAlign: 'center', padding: '1rem', marginBottom: '1rem'}}>Updating...</div>}

      <div className="detail-header">
         <h2>{editMode ? `${formData.first_name || ''} ${formData.last_name || ''}`.trim() || 'Edit Candidate' : `${candidate.first_name || ''} ${candidate.last_name || 'Candidate Details'}`.trim()}</h2>
         <div className="header-actions">
            {!editMode ? (
                <button onClick={() => { setEditMode(true); initializeFormData(candidate); setError(null); }} className="button-action button-edit" disabled={isUpdating || isSubmittingInterview}>Edit Details</button>
            ) : (
                <>
                    <button onClick={handleSaveChanges} className="button-action button-save" disabled={isUpdating || isSubmittingInterview}>{isUpdating ? 'Saving...' : 'Save Changes'}</button>
                    <button onClick={() => { setEditMode(false); initializeFormData(candidate); setError(null); }} className="button-action button-cancel" disabled={isUpdating || isSubmittingInterview}>Cancel Edit</button>
                </>
            )}
         </div>
      </div>

      <div className="detail-content">
        <div className="detail-column detail-column-left">
          <h3>Candidate Information</h3>
          <div className="info-grid">
            {/* ... (τα υπόλοιπα πεδία παραμένουν ίδια) ... */}
            <div className="info-item"><label>First Name:</label>{editMode ? <input type="text" name="first_name" value={formData.first_name} onChange={handleInputChange} className="input-light-gray"/> : <span>{candidate.first_name || 'N/A'}</span>}</div>
            <div className="info-item"><label>Last Name:</label>{editMode ? <input type="text" name="last_name" value={formData.last_name} onChange={handleInputChange} className="input-light-gray"/> : <span>{candidate.last_name || 'N/A'}</span>}</div>
            <div className="info-item"><label>Email:</label>{editMode ? <input type="email" name="email" value={formData.email} onChange={handleInputChange} className="input-light-gray"/> : <span>{candidate.email || 'N/A'}</span>}</div>
            <div className="info-item"><label>Phone:</label>{editMode ? <input type="tel" name="phone_number" value={formData.phone_number} onChange={handleInputChange} className="input-light-gray"/> : <span>{candidate.phone_number || 'N/A'}</span>}</div>
            <div className="info-item"><label>Age:</label>{editMode ? <input type="number" name="age" value={formData.age} onChange={handleInputChange} className="input-light-gray"/> : <span>{candidate.age || 'N/A'}</span>}</div>
            <div className="info-item"><label>Applied for Position(s):</label>{editMode ? <input type="text" name="positions" value={formData.positions.join(', ')} onChange={handlePositionChange} className="input-light-gray" placeholder="Comma-separated"/> : <span>{candidate.positions?.map(p => typeof p === 'object' ? p.position_name : p).join(', ') || 'N/A'}</span>}</div>
            <div className="info-item"><label>Current Status:</label><span className={`status-badge status-${candidate.current_status?.toLowerCase().replace(/\s+/g, '-')}`}>{candidate.current_status || 'N/A'}</span></div>
            <div className="info-item"><label>Submission Date:</label><span>{formatDate(candidate.submission_date)}</span></div>
            <div className="info-item"><label>Last Updated:</label><span>{formatDate(candidate.updated_at)}</span></div>
            <div className="info-item"><label>Status Last Changed:</label><span>{formatDate(candidate.status_last_changed_date)}</span></div>


            {latestScheduledInterview && (
                <div className="info-item info-item-full interview-highlight card-style" style={{borderColor: 'var(--success-color)'}}>
                    <label style={{color: 'var(--success-color)', fontWeight:'bold'}}>Active Scheduled Interview (ID: {latestScheduledInterview.id}):</label>
                    <span>
                        {formatDate(latestScheduledInterview.scheduled_start_time)}
                        {latestScheduledInterview.location ? ` at ${latestScheduledInterview.location}` : ''}
                        {latestScheduledInterview.interview_type ? ` (${latestScheduledInterview.interview_type})` : ''}
                    </span>
                    {candidateResponseInfo && candidateResponseInfo.text && (
                        <div style={{marginTop: '5px'}}>
                            <label>Candidate Response:</label>
                            <span style={{ color: candidateResponseInfo.color, fontWeight: 'bold', padding: '3px 8px', borderRadius: '12px', backgroundColor: `${candidateResponseInfo.color}20`, fontSize: '0.85rem' }} className={`status-badge ${candidateResponseInfo.className}`}>
                                {candidateResponseInfo.text}
                            </span>
                        </div>
                    )}
                </div>
            )}
            {latestProposedInterview && candidate.current_status === 'Interview Proposed' && (
                 <div className="info-item info-item-full interview-highlight card-style" style={{borderColor: 'var(--warning-color)'}}>
                    <label style={{color: 'var(--warning-color)', fontWeight:'bold'}}>Interview Proposed (ID: {latestProposedInterview.id}):</label>
                    <span>Awaiting candidate's response for slots.</span>
                    {latestProposedInterview.slots && latestProposedInterview.slots.length > 0 && (
                        <ul style={{fontSize:'0.85em', paddingLeft:'20px', margin:'5px 0 0 0'}}>
                            {latestProposedInterview.slots.map(s => <li key={s.id}>{formatDate(s.start_time)} - {formatDate(s.end_time)}</li>)}
                        </ul>
                    )}
                     {candidateResponseInfo && candidateResponseInfo.text && (
                        <div style={{marginTop: '5px'}}>
                            <label>Candidate Response Status:</label>
                             <span style={{ color: candidateResponseInfo.color, fontWeight: 'bold', padding: '3px 8px', borderRadius: '12px', backgroundColor: `${candidateResponseInfo.color}20`, fontSize: '0.85rem' }} className={`status-badge ${candidateResponseInfo.className}`}>
                                {candidateResponseInfo.text}
                            </span>
                        </div>
                    )}
                </div>
            )}

            <div className="info-item">
                <label>Evaluation Rating (HR):</label>
                {editMode ? ( <select name="evaluation_rating" value={formData.evaluation_rating || ''} onChange={handleInputChange} className="input-light-gray">{RATING_OPTIONS.map(option => (<option key={option.value} value={option.value}>{option.label}</option>))}</select> ) : ( <span>{getRatingLabel(candidate.evaluation_rating)}</span> )}
            </div>
            <div className="info-item info-item-full"><label>Education Summary:</label>{editMode ? <textarea name="education_summary" value={formData.education_summary} onChange={handleInputChange} className="input-light-gray" rows="3"/> : <p>{candidate.education_summary || candidate.education || 'N/A'}</p>}</div>
            <div className="info-item info-item-full"><label>Work Experience Summary:</label>{editMode ? <textarea name="experience_summary" value={formData.experience_summary} onChange={handleInputChange} className="input-light-gray" rows="5"/> : <p>{candidate.experience_summary || candidate.work_experience || 'N/A'}</p>}</div>
            <div className="info-item"><label>Languages:</label>{editMode ? <input type="text" name="languages" value={formData.languages} onChange={handleInputChange} className="input-light-gray"/> : <span>{candidate.languages || 'N/A'}</span>}</div>
            <div className="info-item"><label>Seminars/Certifications:</label>{editMode ? <input type="text" name="seminars" value={formData.seminars} onChange={handleInputChange} className="input-light-gray"/> : <span>{candidate.seminars || 'N/A'}</span>}</div>
            <div className="info-item info-item-full"><label>General Notes / Auto-Parsed Info:</label>{editMode ? (<textarea name="notes" value={formData.notes} onChange={handleInputChange} className="input-light-gray" rows="4"/>) : (<p className="notes-display" style={{whiteSpace: 'pre-wrap'}}>{candidate.notes || '(No general notes)'}</p>)}</div>
            <div className="info-item info-item-full"><label style={{fontWeight: 'bold', color: 'var(--primary-color)'}}>HR Internal Comments:</label>{editMode ? (<textarea name="hr_comments" value={formData.hr_comments} onChange={handleInputChange} className="input-light-gray" rows="4" placeholder="Internal comments for HR team only..."/>) : (<p className="notes-display" style={{borderLeft: '3px solid var(--primary-color)', paddingLeft: '10px', fontStyle: 'italic', backgroundColor: '#f0f4f8', whiteSpace: 'pre-wrap'}}>{candidate.hr_comments || '(No HR comments added)'}</p>)}</div>
            {(editMode || (candidate.offers && candidate.offers.length > 0 && candidate.offers.some(o => o.offer_amount || o.offer_notes)) || candidate.current_status === 'OfferMade') && (
                 <div className="info-item info-item-full offers-section">
                    <label style={{borderBottom: '1px solid var(--border-color)', paddingBottom: '5px', marginBottom: '10px'}}>Offer(s):</label>
                    {formData.offers && formData.offers.map((offer, index) => (
                        <div key={index} className="offer-item">
                            <div className="offer-header"><span>Offer {index + 1}</span>{editMode && ( <button type="button" onClick={() => removeOfferField(index)} className="button-action button-reject" style={{fontSize:'0.7rem', padding:'2px 5px', marginLeft:'10px'}}>Remove</button> )}</div>
                            <div className="info-item"> <label htmlFor={`offer_amount_${index}`}>Amount (€):</label> {editMode ? ( <input type="number" id={`offer_amount_${index}`} name="offer_amount" value={offer.offer_amount || ''} onChange={(e) => handleOfferChange(index, 'offer_amount', e.target.value)} className="input-light-gray" placeholder="e.g., 1500.50" step="0.01"/> ) : ( <span>{offer.offer_amount ? `${parseFloat(offer.offer_amount).toFixed(2)} €` : 'N/A'}</span> )}</div>
                            <div className="info-item"> <label htmlFor={`offer_date_${index}`}>Offer Date:</label> {editMode ? ( <input type="date" id={`offer_date_${index}`} name="offer_date" value={offer.offer_date ? offer.offer_date.split('T')[0] : ''} onChange={(e) => handleOfferChange(index, 'offer_date', e.target.value)} className="input-light-gray"/> ) : ( <span>{formatDate(offer.offer_date)}</span> )}</div>
                            <div className="info-item info-item-full"> <label htmlFor={`offer_notes_${index}`}>Offer Notes:</label> {editMode ? ( <textarea id={`offer_notes_${index}`} name="offer_notes" value={offer.offer_notes || ''} onChange={(e) => handleOfferChange(index, 'offer_notes', e.target.value)} className="input-light-gray" rows="2"/> ) : ( <p className="notes-display" style={{minHeight: 'auto', fontSize:'0.9em', whiteSpace: 'pre-wrap'}}>{offer.offer_notes || '(No notes)'}</p> )}</div>
                        </div>
                    ))}
                    {editMode && ( <button type="button" onClick={addOfferField} className="button-action button-primary" style={{marginTop: '10px', fontSize: '0.85rem'}}>+ Add Offer</button> )}
                </div>
            )}

          </div>

          {!editMode && (
            <div className="action-buttons">
                <h4>Candidate Actions</h4>
                {/* Processing State Actions */}
                {candidate.current_status === 'Processing' && (
                    <>
                        <button onClick={() => { if (window.confirm("Manually mark this candidate as 'Needs Review'? This is usually done automatically after CV parsing.")) { handleUpdateStatus('NeedsReview', {notes: `${candidate.notes || ''}\n(Manually moved from Processing to Needs Review by ${currentUser?.username || 'user'})`.trim()}); }}}
                            className="button-action button-primary" disabled={isUpdating}>
                            Mark as 'Needs Review' (Manual)
                        </button>
                        <button onClick={() => { if (window.confirm("Manually mark this candidate as 'Parsing Failed'?")) { handleUpdateStatus('ParsingFailed', {notes: `${candidate.notes || ''}\n(Manually marked as Parsing Failed by ${currentUser?.username || 'user'})`.trim()}); }}}
                            className="button-action button-reject" disabled={isUpdating}>
                            Mark as 'Parsing Failed' (Manual)
                        </button>
                    </>
                )}

                {(candidate.current_status === 'NeedsReview' || candidate.current_status === 'Accepted' || candidate.current_status === 'Interested' || candidate.current_status === 'Interview Proposed') && !showProposalModal && (
                    <button onClick={handleProposeInterviewClick} className="button-action button-primary" disabled={isUpdating || isSubmittingInterview || isLoadingCompanyPositions}>
                        {isLoadingCompanyPositions ? 'Loading Positions...' : (candidate.current_status === 'Interview Proposed' ? 'Re-Propose Interview Slots' : 'Propose Interview Slots')}
                    </button>
                )}

                {candidate.current_status === 'NeedsReview' && (
                    <>
                        <button onClick={() => handleUpdateStatus('Accepted')} className="button-action button-accept" disabled={isUpdating}>Move to 'Accepted'</button>
                        <button onClick={() => handleUpdateStatus('Rejected', {notes: `Rejected at NeedsReview stage. ${formData.hr_comments || candidate.hr_comments || ''}`.trim()})} className="button-action button-reject" disabled={isUpdating}>Reject Candidate</button>
                    </>
                )}
                {candidate.current_status === 'Accepted' && (
                    <>
                        <button onClick={() => handleUpdateStatus('Interested')} className="button-action button-primary" disabled={isUpdating}>Move to 'Interested'</button>
                        <button onClick={() => handleUpdateStatus('Rejected', {notes: `Rejected at Accepted stage. ${formData.hr_comments || candidate.hr_comments || ''}`.trim()})} className="button-action button-reject" disabled={isUpdating}>Reject Candidate</button>
                    </>
                )}
                {/* 'Interested' actions: Propose Interview (above) or Skip to Evaluation */}
                 {candidate.current_status === 'Interested' && (
                    <>
                         <button onClick={() => { if(window.confirm("Are you sure you want to skip scheduling an interview and move this candidate directly to Evaluation?")) { handleUpdateStatus('Evaluation', { notes: `${formData.notes || candidate.notes || ''}\n(Interview skipped by HR, moved directly to Evaluation)`.trim(), candidate_confirmation_status: null }); } }}
                            className="button-action button-secondary" disabled={isUpdating} style={{marginTop: '10px'}} title="Move directly to Evaluation stage without scheduling an interview">
                            Skip Interview (→ Evaluation)
                        </button>
                        <button onClick={() => handleUpdateStatus('Rejected', {notes: `Rejected at Interested stage. ${formData.hr_comments || candidate.hr_comments || ''}`.trim()})} className="button-action button-reject" disabled={isUpdating} style={{marginTop: '10px'}}>Reject Candidate</button>
                    </>
                )}

                {candidate.current_status === 'InterviewScheduled' && (
                    <>
                        <p style={{fontWeight: 'bold', marginTop:'15px'}}>Interview Outcome:</p>
                        <button onClick={handleConfirmInterviewOutcome} className="button-action button-confirm" disabled={isUpdating}>Interview Successful (→ Evaluation)</button>
                        <button onClick={handleCancelOrRescheduleInterview} className="button-action button-cancel-schedule" disabled={isUpdating}>Recruiter Cancels/Reschedules (→ Interested)</button>
                        <button onClick={handleRejectPostInterview} className="button-action button-reject" disabled={isUpdating}>Reject Post-Interview</button>
                    </>
                )}
                 {candidate.current_status === 'InterviewProposed' && latestProposedInterview && ( // If interview proposed, but not yet scheduled
                    <button onClick={() => { if(window.confirm("Are you sure you want to cancel this interview proposal and move the candidate back to 'Interested'? The candidate will no longer be able to respond to the proposed slots.")) {
                        // TODO: Need a backend endpoint to cancel a PROPOSED interview by recruiter
                        // For now, just changing candidate status. This will orphan the Interview object.
                        alert("Backend functionality for 'Cancel Proposed Interview by Recruiter' is needed. For now, only candidate status will be changed if you proceed.");
                        handleUpdateStatus('Interested', { notes: `${formData.notes || candidate.notes || ''}\n(Interview proposal (ID: ${latestProposedInterview.id}) cancelled by HR before candidate response.)`.trim()});
                    }}} className="button-action button-cancel-schedule" disabled={isUpdating} style={{marginTop: '10px'}}>
                        Cancel Current Interview Proposal (→ Interested)
                    </button>
                )}
                {candidate.current_status === 'Evaluation' && (
                    <>
                        <button onClick={handleMakeOffer} className="button-action button-accept" disabled={isUpdating}>Make Offer (→ OfferMade)</button>
                        <button onClick={() => handleUpdateStatus('Rejected', {notes: `Rejected at Evaluation stage. ${formData.hr_comments || candidate.hr_comments || ''}`.trim()})} className="button-action button-reject" disabled={isUpdating}>Reject Candidate</button>
                    </>
                )}
                {candidate.current_status === 'OfferMade' && (
                    <>
                        <p style={{fontWeight: 'bold', marginTop:'15px'}}>Offer Response:</p>
                        <button onClick={handleOfferAccepted} className="button-action button-accept" disabled={isUpdating}>Candidate Accepted Offer (→ Hired)</button>
                        <button onClick={handleOfferDeclinedByCandidate} className="button-action button-reject" disabled={isUpdating}>Candidate Declined Offer (→ Declined)</button>
                    </>
                )}
                {candidate.current_status && ['Rejected', 'Declined', 'ParsingFailed', 'Hired', 'OfferMade'].includes(candidate.current_status) && (
                    <button onClick={() => { if (window.confirm(`Are you sure you want to move candidate ${candidate.first_name || candidate.candidate_id} back to "Needs Review"? This will clear evaluation and offer related data. Active interviews may also be cancelled by the system.`)) { handleUpdateStatus('NeedsReview'); } }}
                        className="button-action button-secondary" disabled={isUpdating} title="Move candidate back to Needs Review to re-evaluate" style={{marginTop: '15px'}}
                    >Re-evaluate (Move to Needs Review)</button>
                )}
                {candidate.current_status === 'Hired' && ( <p style={{ fontStyle: 'italic', color: 'var(--text-medium-gray)', marginTop: '15px' }}>Candidate Hired. No further status actions available other than re-evaluation.</p> )}
            </div>
          )}
          {showProposalModal && candidate && (
            <ModalDialog
                isOpen={showProposalModal}
                onClose={() => setShowProposalModal(false)}
                title={`Propose Interview for ${candidate.first_name || ''} ${candidate.last_name || ''}`.trim()}
            >
                <InterviewProposalForm
                  candidateId={candidate.candidate_id}
                  companyPositions={companyOpenPositions} // Pass the fetched positions
                  onSubmit={handleSendInterviewProposal}
                  onCancel={() => setShowProposalModal(false)}
                  isSubmitting={isSubmittingInterview}
                />
            </ModalDialog>
          )}
        </div>

        <div className="detail-column detail-column-right">
           <div className="cv-viewer-section card-style">
             <h3>CV Document</h3>
             {cvUrl && candidate?.cv_original_filename ? (
                candidate.cv_original_filename.toLowerCase().endsWith('.pdf') ? (
                    <CVViewer
                        fileUrl={cvUrl}
                        onError={(errMsg) => {
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