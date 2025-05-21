// frontend/src/pages/CandidateDetailPage.jsx
import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import apiClient from '../api';
import CVViewer from '../components/CVViewer';
import HistoryLog from '../components/HistoryLog';
import InterviewProposalForm from '../components/InterviewProposalForm';
import ModalDialog from '../components/ModalDialog';
import { useAuth } from '../App';
import companyAdminService from '../services/companyAdminService'; // Για τα branches
import './CandidateDetailPage.css';

// ... (getConfirmationStatusInfo, RATING_OPTIONS παραμένουν ίδια) ...
const getConfirmationStatusInfo = (confirmationStatus) => {
    switch (confirmationStatus) {
        case 'Confirmed': return { text: 'Επιβεβαιώθηκε από Υποψήφιο', color: 'green', className: 'status-confirmed' };
        case 'DeclinedSlots': return { text: 'Απορρίφθηκαν Slots από Υποψήφιο', color: '#cc8500', className: 'status-declined-slots' };
        case 'CancelledByUser': return { text: 'Ακυρώθηκε από Υποψήφιο', color: 'red', className: 'status-cancelled-user' };
        case 'RecruiterCancelled': return { text: 'Ακυρώθηκε από Recruiter', color: 'darkred', className: 'status-cancelled-recruiter' };
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
  const { currentUser } = useAuth();

  const [candidate, setCandidate] = useState(null);
  const [cvUrl, setCvUrl] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isUpdating, setIsUpdating] = useState(false);
  const [isSubmittingInterview, setIsSubmittingInterview] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [showProposalModal, setShowProposalModal] = useState(false);
  const [showRecruiterCancelModal, setShowRecruiterCancelModal] = useState(false);
  const [cancellationReasonByRecruiter, setCancellationReasonByRecruiter] = useState('');

  const [companyOpenPositions, setCompanyOpenPositions] = useState([]);
  const [isLoadingCompanyPositions, setIsLoadingCompanyPositions] = useState(false);

  const [allCompanyBranches, setAllCompanyBranches] = useState([]); // Νέο state για τα branches της εταιρείας
  const [isLoadingCompanyBranches, setIsLoadingCompanyBranches] = useState(false); // Νέο state

  const initialFormDataState = {
    first_name: '', last_name: '', email: '', phone_number: '', age: '',
    positions: [], education_summary: '', experience_summary: '', skills_summary: '',
    languages: '', seminars: '', notes: '', evaluation_rating: '',
    hr_comments: '', offers: [], branch_ids: [], // Νέο πεδίο για τα IDs των επιλεγμένων branches
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
            offer_date: o.offer_date ? o.offer_date.split('T')[0] : new Date().toISOString().split('T')[0]
        })) : [],
        branch_ids: Array.isArray(data.branches) ? data.branches.map(b => b.id) : [], // Αρχικοποίηση των branch_ids
    });
  }, []);

  const fetchCandidateData = useCallback(async () => {
    setIsLoading(true); setError(null);
    try {
      const detailsRes = await apiClient.get(`/candidate/${candidateId}`);
      setCandidate(detailsRes.data);
      initializeFormData(detailsRes.data);
      setCvUrl(detailsRes.data?.cv_url || null);
    } catch (err) {
      console.error("Fetch candidate error:", err.response || err);
      setError(err.response?.data?.error || 'Failed to load candidate details.');
      setCandidate(null); setCvUrl(null);
    } finally {
      setIsLoading(false);
    }
  }, [candidateId, initializeFormData]);

  useEffect(() => { fetchCandidateData(); }, [fetchCandidateData]);

  // Fetch company positions and branches when candidate data (and thus company_id) is available
  useEffect(() => {
    const companyIdForFetch = candidate?.company_id;
    if (!companyIdForFetch) {
        setCompanyOpenPositions([]);
        setAllCompanyBranches([]);
        return;
    }

    const fetchOpenPositionsForCompany = async () => {
        setIsLoadingCompanyPositions(true);
        try {
            const response = await apiClient.get(`/company/${companyIdForFetch}/positions?status=Open`);
            setCompanyOpenPositions(response.data.positions || []);
        } catch (error) {
            console.error("Error fetching company open positions:", error.response?.data || error.message);
            setCompanyOpenPositions([]);
        } finally {
            setIsLoadingCompanyPositions(false);
        }
    };

    const fetchAllBranchesForCompany = async () => {
        setIsLoadingCompanyBranches(true);
        try {
            // Το companyAdminService.getBranches παίρνει company_id για superadmin,
            // για company_admin το backend ξέρει την εταιρεία.
            const branchesData = await companyAdminService.getBranches(
                 currentUser?.role === 'superadmin' ? companyIdForFetch : null
            );
            setAllCompanyBranches(branchesData || []);
        } catch (error) {
            console.error("Error fetching company branches:", error);
            setAllCompanyBranches([]);
        } finally {
            setIsLoadingCompanyBranches(false);
        }
    };

    fetchOpenPositionsForCompany();
    fetchAllBranchesForCompany();

  }, [candidate?.company_id, currentUser?.role]);


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

  const handleBranchSelectionChange = (event) => { // Για το multi-select των branches
    const { options } = event.target;
    const value = [];
    for (let i = 0, l = options.length; i < l; i += 1) {
      if (options[i].selected) {
        value.push(options[i].value);
      }
    }
    setFormData(prevData => ({ ...prevData, branch_ids: value.map(id => parseInt(id, 10)) }));
  };


  const sendUpdateRequest = async (payload) => {
    if (!candidate) return;
    setIsUpdating(true); setError(null);
    try {
      const response = await apiClient.put(`/candidate/${candidate.candidate_id}`, payload);
      setCandidate(response.data);
      initializeFormData(response.data);
      if (response.data.cv_url) setCvUrl(response.data.cv_url);
      setEditMode(false);
      return response.data;
    } catch (err) {
      console.error("Update candidate error:", err.response || err);
      setError(err.response?.data?.error || `Failed to update candidate.`);
      throw err;
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
        branch_ids: editMode ? formData.branch_ids : (extraData.branch_ids || (candidate?.branches?.map(b=>b.id) || []) ), // Πρόσθεσε τα branch_ids
        ...extraData
    };
    if (newStatus === 'OfferMade' && (!extraData.offers && (!formData.offers || formData.offers.length === 0))) {
        payload.offers = [{ offer_amount: null, offer_notes: 'Initial offer pending details.', offer_date: new Date().toISOString() }];
    } else if (newStatus === 'OfferMade' && !extraData.offers) {
        payload.offers = formData.offers.map(o => ({
            ...o,
            offer_amount: o.offer_amount === '' || o.offer_amount === null ? null : parseFloat(o.offer_amount),
            offer_date: o.offer_date ? new Date(o.offer_date).toISOString() : new Date().toISOString()
        })).filter(o => o.offer_amount !== null || (o.offer_notes && o.offer_notes.trim() !== ''));
        if (payload.offers.length === 0) {
            payload.offers = [{ offer_amount: null, offer_notes: 'Initial offer pending details.', offer_date: new Date().toISOString() }];
        }
    }
    try {
      await sendUpdateRequest(payload);
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
            offer_date: o.offer_date ? new Date(o.offer_date).toISOString() : new Date().toISOString()
         })).filter(o => o.offer_amount !== null || (o.offer_notes && o.offer_notes.trim() !== '')),
         branch_ids: formData.branch_ids, // Στείλε τα επιλεγμένα branch_ids
      };
      try { await sendUpdateRequest(updatePayload); } catch (err) { /* Error handled */ }
  };

  const handleProposeInterviewClick = () => {
    if (isLoadingCompanyPositions || isLoadingCompanyBranches) {
        alert("Company positions or branches are still loading. Please wait a moment.");
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
    setError(null);
    try {
      const response = await apiClient.post(`/candidates/${candidate.candidate_id}/propose-interview`, proposalData);
      setShowProposalModal(false);
      setCandidate(prev => {
          const updatedInterviews = prev.interviews ?
            prev.interviews.map(iv => iv.status === 'PROPOSED' ? {...iv, status: 'CANCELLED_BY_RECRUITER'} : iv)
            : [];
          return {
              ...prev,
              current_status: "Interview Proposed",
              // Το response.data εδώ είναι το interview object, όχι το candidate object
              interviews: [...updatedInterviews, response.data],
              // Θα ήταν καλύτερο το backend να επιστρέφει το ενημερωμένο candidate object
              // ή να κάνουμε refetch. Προς το παρόν, ενημερώνουμε τοπικά το status.
              history: response.data.new_history_event ? [...(prev.history || []), response.data.new_history_event] : prev.history, // Αν το backend στέλνει το event
          };
      });
       // Καλύτερα να κάνουμε refetch για να είμαστε σίγουροι για την κατάσταση.
      fetchCandidateData();
      alert(`Interview proposed successfully! Candidate status is now "Interview Proposed".`);
    } catch (err) {
      console.error("Error proposing interview:", err.response?.data || err.message);
      setError(err.response?.data?.error || 'Failed to propose interview.');
    } finally {
      setIsSubmittingInterview(false);
    }
  };

  const handleOpenRecruiterCancelModal = () => {
    if (!latestScheduledInterview && !latestProposedInterview) {
        alert("No active interview to cancel for this candidate.");
        return;
    }
    setCancellationReasonByRecruiter('');
    setShowRecruiterCancelModal(true);
  };

  const handleConfirmRecruiterCancelInterview = async () => {
    let interviewToCancel = latestScheduledInterview || latestProposedInterview;
    if (!interviewToCancel) {
        alert("No active interview selected for cancellation.");
        setShowRecruiterCancelModal(false);
        return;
    }
    setIsUpdating(true);
    setError(null);
    try {
      const response = await apiClient.post(`/interviews/${interviewToCancel.id}/cancel-by-recruiter`, {
        reason: cancellationReasonByRecruiter,
      });
      alert(response.data.message || 'Interview cancelled successfully by recruiter.');
      fetchCandidateData();
      setShowRecruiterCancelModal(false);
    } catch (err) {
      console.error("Error cancelling interview by recruiter:", err.response?.data || err.message);
      setError(err.response?.data?.error || 'Failed to cancel interview by recruiter.');
    } finally {
      setIsUpdating(false);
    }
  };

  const handleMoveToEvaluation = () => {
    if (!latestScheduledInterview) {
        alert("No scheduled interview found to move to evaluation.");
        return;
    }
    const interviewEndTime = new Date(latestScheduledInterview.scheduled_end_time);
    if (interviewEndTime > new Date()) {
        if (!window.confirm("This interview has not yet occurred or is currently in progress. Are you sure you want to move this candidate to the Evaluation stage?")) {
            return;
        }
    }
    handleUpdateStatus('Evaluation', {
        notes: `${candidate?.notes || ''}\n(Moved to Evaluation by ${currentUser?.username || 'user'} after interview ID: ${latestScheduledInterview.id})`.trim()
    });
  };

  const handleRejectPostInterview = () => handleUpdateStatus('Rejected', {notes: `Rejected after interview stage. ${formData.hr_comments || candidate?.hr_comments || ''}`.trim()});
  const handleMakeOffer = () => {
    if (!formData.offers || formData.offers.length === 0 || formData.offers.every(o => !o.offer_amount && !o.offer_notes)) {
        addOfferField();
    }
    handleUpdateStatus('OfferMade');
    if (!editMode) setEditMode(true);
  };
  const handleOfferAccepted = () => handleUpdateStatus('Hired');
  const handleOfferDeclinedByCandidate = () => handleUpdateStatus('Declined', {notes: `Offer declined by candidate. ${formData.hr_comments || candidate?.hr_comments || ''}`.trim()});

  const formatDate = (isoString) => {
    if (!isoString) return 'N/A';
    try {
        return new Date(isoString).toLocaleString([], { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false });
    } catch { return 'Invalid Date'; }
  };

  if (isLoading && !candidate) return <div className="loading-placeholder card-style">Loading candidate details...</div>;
  if (error && !candidate && !isUpdating && !isSubmittingInterview) return <div className="error-message card-style">Error: {error} <button onClick={fetchCandidateData} className="button-action button-secondary">Retry</button></div>;
  if (!candidate && !isLoading) return <div className="card-style">Candidate not found or data unavailable. <Link to="/dashboard">Go to Dashboard</Link></div>;
  if (!candidate) return null;

  const candidateResponseInfo = getConfirmationStatusInfo(candidate.candidate_confirmation_status);
  const latestScheduledInterview = candidate.interviews?.filter(inv => inv.status === 'SCHEDULED').sort((a,b) => new Date(b.created_at) - new Date(a.created_at))[0];
  const latestProposedInterview = candidate.interviews?.filter(inv => inv.status === 'PROPOSED').sort((a,b) => new Date(b.created_at) - new Date(a.created_at))[0];

  const canRecruiterCancel = latestScheduledInterview || latestProposedInterview;
  const canMoveToEvaluation = latestScheduledInterview;

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
            <div className="info-item"><label>First Name:</label>{editMode ? <input type="text" name="first_name" value={formData.first_name} onChange={handleInputChange} className="input-light-gray"/> : <span>{candidate.first_name || 'N/A'}</span>}</div>
            <div className="info-item"><label>Last Name:</label>{editMode ? <input type="text" name="last_name" value={formData.last_name} onChange={handleInputChange} className="input-light-gray"/> : <span>{candidate.last_name || 'N/A'}</span>}</div>
            <div className="info-item"><label>Email:</label>{editMode ? <input type="email" name="email" value={formData.email} onChange={handleInputChange} className="input-light-gray"/> : <span>{candidate.email || 'N/A'}</span>}</div>
            <div className="info-item"><label>Phone:</label>{editMode ? <input type="tel" name="phone_number" value={formData.phone_number} onChange={handleInputChange} className="input-light-gray"/> : <span>{candidate.phone_number || 'N/A'}</span>}</div>
            <div className="info-item"><label>Age:</label>{editMode ? <input type="number" name="age" value={formData.age} onChange={handleInputChange} className="input-light-gray"/> : <span>{candidate.age || 'N/A'}</span>}</div>
            <div className="info-item"><label>Applied for Position(s):</label>{editMode ? <input type="text" name="positions" value={formData.positions.join(', ')} onChange={handlePositionChange} className="input-light-gray" placeholder="Comma-separated"/> : <span>{candidate.positions?.map(p => typeof p === 'object' ? p.position_name : p).join(', ') || 'N/A'}</span>}</div>
            
            {/* Branches Section */}
            <div className="info-item info-item-full">
                <label>Assigned Branch(es):</label>
                {editMode ? (
                    <select
                        multiple
                        name="branch_ids"
                        value={formData.branch_ids.map(String)} // Select value needs strings
                        onChange={handleBranchSelectionChange}
                        disabled={isLoadingCompanyBranches || allCompanyBranches.length === 0}
                        className="input-light-gray"
                        size={Math.min(5, allCompanyBranches.length + 1)}
                        style={{ minHeight: '80px' }}
                    >
                        {isLoadingCompanyBranches ? (
                            <option disabled>Loading branches...</option>
                        ) : allCompanyBranches.length === 0 ? (
                            <option disabled>No branches available for this company.</option>
                        ) : (
                            allCompanyBranches.map(branch => (
                                <option key={branch.id} value={branch.id.toString()}>
                                    {branch.name}
                                </option>
                            ))
                        )}
                    </select>
                ) : (
                    <span>{candidate.branches && candidate.branches.length > 0 ? candidate.branches.map(b => b.name).join(', ') : 'N/A'}</span>
                )}
                {editMode && allCompanyBranches.length > 0 && <small>Hold Ctrl/Cmd to select multiple.</small>}
            </div>

            <div className="info-item"><label>Current Status:</label><span className={`status-badge status-${candidate.current_status?.toLowerCase().replace(/\s+/g, '-')}`}>{candidate.current_status || 'N/A'}</span></div>
            <div className="info-item"><label>Submission Date:</label><span>{formatDate(candidate.submission_date)}</span></div>
            <div className="info-item"><label>Last Updated:</label><span>{formatDate(candidate.updated_at)}</span></div>
            <div className="info-item"><label>Status Last Changed:</label><span>{formatDate(candidate.status_last_changed_date)}</span></div>

             {latestScheduledInterview && (
                <div className="info-item info-item-full interview-highlight card-style" style={{borderColor: 'var(--success-color)'}}>
                    <label style={{color: 'var(--success-color)', fontWeight:'bold'}}>ACTIVE SCHEDULED INTERVIEW (ID: {latestScheduledInterview.id}):</label>
                    <span>
                        {formatDate(latestScheduledInterview.scheduled_start_time)}
                        {latestScheduledInterview.location ? ` at ${latestScheduledInterview.location}` : ''}
                        {latestScheduledInterview.interview_type ? ` (${latestScheduledInterview.interview_type})` : ''}
                    </span>
                    {candidateResponseInfo && candidateResponseInfo.text && (
                        <div style={{marginTop: '5px'}}>
                            <label>CANDIDATE RESPONSE:</label>
                            <span style={{ color: candidateResponseInfo.color, fontWeight: 'bold', padding: '3px 8px', borderRadius: '12px', backgroundColor: `${candidateResponseInfo.color}20`, fontSize: '0.85rem' }} className={`status-badge ${candidateResponseInfo.className}`}>
                                {candidateResponseInfo.text}
                            </span>
                        </div>
                    )}
                </div>
            )}
            {latestProposedInterview && candidate.current_status === 'Interview Proposed' && (
                 <div className="info-item info-item-full interview-highlight card-style" style={{borderColor: 'var(--warning-color)'}}>
                    <label style={{color: 'var(--warning-color)', fontWeight:'bold'}}>INTERVIEW PROPOSED (ID: {latestProposedInterview.id}):</label>
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
                <label>EVALUATION RATING (HR):</label>
                {editMode ? ( <select name="evaluation_rating" value={formData.evaluation_rating || ''} onChange={handleInputChange} className="input-light-gray">{RATING_OPTIONS.map(option => (<option key={option.value} value={option.value}>{option.label}</option>))}</select> ) : ( <span>{getRatingLabel(candidate.evaluation_rating)}</span> )}
            </div>
            <div className="info-item info-item-full"><label>EDUCATION SUMMARY:</label>{editMode ? <textarea name="education_summary" value={formData.education_summary} onChange={handleInputChange} className="input-light-gray" rows="3"/> : <p>{candidate.education_summary || candidate.education || 'N/A'}</p>}</div>
            <div className="info-item info-item-full"><label>WORK EXPERIENCE SUMMARY:</label>{editMode ? <textarea name="experience_summary" value={formData.experience_summary} onChange={handleInputChange} className="input-light-gray" rows="5"/> : <p>{candidate.experience_summary || candidate.work_experience || 'N/A'}</p>}</div>
            <div className="info-item"><label>LANGUAGES:</label>{editMode ? <input type="text" name="languages" value={formData.languages} onChange={handleInputChange} className="input-light-gray"/> : <span>{candidate.languages || 'N/A'}</span>}</div>
            <div className="info-item"><label>SEMINARS/CERTIFICATIONS:</label>{editMode ? <input type="text" name="seminars" value={formData.seminars} onChange={handleInputChange} className="input-light-gray"/> : <span>{candidate.seminars || 'N/A'}</span>}</div>
            <div className="info-item info-item-full"><label>GENERAL NOTES / AUTO-PARSED INFO:</label>{editMode ? (<textarea name="notes" value={formData.notes} onChange={handleInputChange} className="input-light-gray" rows="4"/>) : (<p className="notes-display" style={{whiteSpace: 'pre-wrap'}}>{candidate.notes || '(No general notes)'}</p>)}</div>
            <div className="info-item info-item-full"><label style={{fontWeight: 'bold', color: 'var(--primary-color)'}}>HR INTERNAL COMMENTS:</label>{editMode ? (<textarea name="hr_comments" value={formData.hr_comments} onChange={handleInputChange} className="input-light-gray" rows="4" placeholder="Internal comments for HR team only..."/>) : (<p className="notes-display" style={{borderLeft: '3px solid var(--primary-color)', paddingLeft: '10px', fontStyle: 'italic', backgroundColor: '#f0f4f8', whiteSpace: 'pre-wrap'}}>{candidate.hr_comments || '(No HR comments added)'}</p>)}</div>
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

          {!editMode && ( <div className="action-buttons"> <h4>Candidate Actions</h4>
                {/* ====== START OF FIX for 'Processing' state ====== */}
                {candidate.current_status === 'Processing' && (
                    <button onClick={() => handleUpdateStatus('NeedsReview')} className="button-action button-primary" disabled={isUpdating}>Move to 'Needs Review'</button>
                )}
                {/* ====== END OF FIX for 'Processing' state ====== */}

                {(candidate.current_status === 'NeedsReview' || candidate.current_status === 'Accepted' || candidate.current_status === 'Interested' || candidate.current_status === 'Interview Proposed' || candidate.current_status === 'Interview Scheduled' ) && !showProposalModal && (
                    <button onClick={handleProposeInterviewClick} className="button-action button-primary" disabled={isUpdating || isSubmittingInterview || isLoadingCompanyPositions || isLoadingCompanyBranches} style={{marginBottom: '10px'}}>
                        {isLoadingCompanyPositions || isLoadingCompanyBranches ? 'Loading Data...' : (candidate.current_status === 'Interview Proposed' || candidate.current_status === 'Interview Scheduled' ? 'Re-Propose Interview Slots' : 'Propose Interview Slots')}
                    </button>
                )}
                {canRecruiterCancel && (candidate.current_status === 'Interview Scheduled' || candidate.current_status === 'Interview Proposed') && (
                    <button onClick={handleOpenRecruiterCancelModal} className="button-action button-cancel-schedule" disabled={isUpdating || isSubmittingInterview} style={{marginBottom: '10px', marginLeft: '10px'}} title="Cancel this interview (candidate will be notified)">
                        Cancel Interview (by Recruiter)
                    </button>
                )}
                {canMoveToEvaluation && candidate.current_status === 'Interview Scheduled' && (
                    <button onClick={handleMoveToEvaluation} className="button-action button-confirm" disabled={isUpdating || isSubmittingInterview} style={{marginBottom: '10px', marginLeft: '10px'}} title="Mark interview as completed and move candidate to Evaluation stage">
                        Move to Evaluation
                    </button>
                )}
                {/* Removed the empty fragment for 'Processing' as we added a button above */}
                {candidate.current_status === 'NeedsReview' && (
                    <> <button onClick={() => handleUpdateStatus('Accepted')} className="button-action button-accept" disabled={isUpdating}>Move to 'Accepted'</button> <button onClick={() => handleUpdateStatus('Rejected', {notes: `Rejected at NeedsReview stage. ${formData.hr_comments || candidate?.hr_comments || ''}`.trim()})} className="button-action button-reject" disabled={isUpdating}>Reject Candidate</button> </>
                )}
                 {candidate.current_status === 'Accepted' && (
                    <> <button onClick={() => handleUpdateStatus('Interested')} className="button-action button-primary" disabled={isUpdating}>Move to 'Interested'</button> <button onClick={() => handleUpdateStatus('Rejected', {notes: `Rejected at Accepted stage. ${formData.hr_comments || candidate?.hr_comments || ''}`.trim()})} className="button-action button-reject" disabled={isUpdating}>Reject Candidate</button> </>
                )}
                {candidate.current_status === 'Interested' && !(latestProposedInterview || latestScheduledInterview) && (
                    <> <button onClick={() => { if(window.confirm("Are you sure you want to skip scheduling an interview and move this candidate directly to Evaluation?")) { handleUpdateStatus('Evaluation', { notes: `${formData.notes || candidate?.notes || ''}\n(Interview skipped by HR, moved directly to Evaluation)`.trim(), candidate_confirmation_status: null }); } }} className="button-action button-secondary" disabled={isUpdating} style={{marginTop: '10px'}} title="Move directly to Evaluation stage without scheduling an interview"> Skip Interview (→ Evaluation) </button> <button onClick={() => handleUpdateStatus('Rejected', {notes: `Rejected at Interested stage. ${formData.hr_comments || candidate?.hr_comments || ''}`.trim()})} className="button-action button-reject" disabled={isUpdating} style={{marginTop: '10px'}}>Reject Candidate</button> </>
                )}
                {candidate.current_status === 'Evaluation' && (
                    <> <button onClick={handleMakeOffer} className="button-action button-accept" disabled={isUpdating}>Make Offer (→ OfferMade)</button> <button onClick={() => handleUpdateStatus('Rejected', {notes: `Rejected at Evaluation stage. ${formData.hr_comments || candidate?.hr_comments || ''}`.trim()})} className="button-action button-reject" disabled={isUpdating}>Reject Candidate</button> </>
                )}
                {candidate.current_status === 'OfferMade' && (
                    <> <p style={{fontWeight: 'bold', marginTop:'15px'}}>Offer Response:</p> <button onClick={handleOfferAccepted} className="button-action button-accept" disabled={isUpdating}>Candidate Accepted Offer (→ Hired)</button> <button onClick={handleOfferDeclinedByCandidate} className="button-action button-reject" disabled={isUpdating}>Candidate Declined Offer (→ Declined)</button> </>
                )}
                {candidate.current_status && ['Rejected', 'Declined', 'ParsingFailed', 'Hired', 'OfferMade'].includes(candidate.current_status) && (
                    <button onClick={() => { if (window.confirm(`Are you sure you want to move candidate ${candidate.first_name || candidate.candidate_id} back to "Needs Review"? This will clear evaluation and offer related data. Active interviews may also be cancelled by the system.`)) { handleUpdateStatus('NeedsReview'); } }} className="button-action button-secondary" disabled={isUpdating} title="Move candidate back to Needs Review to re-evaluate" style={{marginTop: '15px'}}>Re-evaluate (Move to Needs Review)</button>
                )}
                {candidate.current_status === 'Hired' && ( <p style={{ fontStyle: 'italic', color: 'var(--text-medium-gray)', marginTop: '15px' }}>Candidate Hired. No further status actions available other than re-evaluation.</p> )}
            </div>)}

           {showRecruiterCancelModal && (
                <ModalDialog isOpen={showRecruiterCancelModal} onClose={() => setShowRecruiterCancelModal(false)} title="Cancel Interview (by Recruiter)">
                    <div className="recruiter-cancel-form">
                        <p>You are about to cancel the interview for <strong>{candidate?.first_name} {candidate?.last_name}</strong>.</p>
                        <p style={{fontSize: '0.9em', marginBottom:'10px'}}>Current Interview ID: {latestScheduledInterview?.id || latestProposedInterview?.id}</p>
                        <label htmlFor="cancellationReasonByRecruiter">Reason for cancellation (optional, will be logged and sent to candidate):</label>
                        <textarea id="cancellationReasonByRecruiter" value={cancellationReasonByRecruiter} onChange={(e) => setCancellationReasonByRecruiter(e.target.value)} rows="3" style={{width: '100%', marginBottom: '15px', border:'1px solid #ccc', borderRadius:'4px', padding:'8px'}} />
                        {error && <p className="error-message" style={{color: 'red', marginBottom:'10px'}}>{error}</p>}
                        <div style={{textAlign: 'right'}}>
                            <button onClick={() => setShowRecruiterCancelModal(false)} className="button-action button-secondary" disabled={isUpdating} style={{marginRight: '10px'}}>Back</button>
                            <button onClick={handleConfirmRecruiterCancelInterview} className="button-action button-danger" disabled={isUpdating}> {isUpdating ? 'Cancelling...' : 'Confirm Cancellation'} </button>
                        </div>
                    </div>
                </ModalDialog>
            )}
          {showProposalModal && candidate && (
            <ModalDialog isOpen={showProposalModal} onClose={() => setShowProposalModal(false)} title={`Propose Interview for ${candidate.first_name || ''} ${candidate.last_name || ''}`.trim()}>
                <InterviewProposalForm candidateId={candidate.candidate_id} companyPositions={companyOpenPositions} onSubmit={handleSendInterviewProposal} onCancel={() => setShowProposalModal(false)} isSubmitting={isSubmittingInterview} />
            </ModalDialog>
          )}
        </div>

        <div className="detail-column detail-column-right">
            <div className="cv-viewer-section card-style">
             <h3>CV Document</h3>
             {cvUrl && candidate?.cv_original_filename ? (
                candidate.cv_original_filename.toLowerCase().endsWith('.pdf') ? (
                    <CVViewer fileUrl={cvUrl} onError={(errMsg) => { setError(prev => `${prev ? prev + '\n' : ''}CV Preview Error: Could not load PDF. You can try downloading it.`); }} />
                ) : (
                    <div className="cv-download-link" style={{padding: '1rem', border: '1px solid #ddd', borderRadius: '4px', textAlign: 'center', backgroundColor: '#f9f9f9'}}>
                        <p style={{fontWeight: 'bold', marginBottom: '0.5rem'}}>{candidate.cv_original_filename}</p>
                        <p style={{fontSize: '0.9em', marginBottom: '1rem'}}>Preview is not available for this file type (.${candidate.cv_original_filename.split('.').pop()}).</p>
                        <a href={cvUrl} download={candidate.cv_original_filename} className="button-action button-primary" style={{textDecoration: 'none', padding: '8px 15px'}}> Download CV </a>
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