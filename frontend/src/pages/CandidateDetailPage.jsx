// frontend/src/pages/CandidateDetailPage.jsx
import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import apiClient from '../api';
import CVViewer from '../components/CVViewer';
import HistoryLog from '../components/HistoryLog';
import InterviewProposalForm from '../components/InterviewProposalForm';
import ModalDialog from '../components/ModalDialog';
import { useAuth } from '../App'; // Διορθωμένο import
import companyAdminService from '../services/companyAdminService';
import Select from 'react-select'; // Για multi-select
import './CandidateDetailPage.css';

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

// Helper function to format a list of branch/position objects into a string of names
const formatObjectListDisplay = (objectList, nameKey = 'name') => {
    if (!objectList || !Array.isArray(objectList) || objectList.length === 0) {
        return 'N/A';
    }
    return objectList.map(item => item[nameKey] || 'Unnamed').join(', ');
};


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

  const [allCompanyBranches, setAllCompanyBranches] = useState([]);
  const [isLoadingCompanyBranches, setIsLoadingCompanyBranches] = useState(false);

  const initialFormDataState = {
    first_name: '', last_name: '', email: '', phone_number: '', age: '',
    positions: [], // Θα κρατάμε τα ονόματα για το text input, αλλά θα στέλνουμε IDs αν χρειαστεί νέα λογική
    education_summary: '', experience_summary: '', skills_summary: '',
    languages: '', seminars: '', notes: '', evaluation_rating: '',
    hr_comments: '', offers: [],
    branch_ids: [], // Θα κρατάμε τα IDs για το select
    position_ids: [] // Για μελλοντική επεξεργασία positions με IDs
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
        // Για την επεξεργασία των positions, αν στέλνονται objects, πάρε τα ονόματα
        positions: Array.isArray(data.positions) ? data.positions.map(p => p.position_name || p) : [],
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
        // Για την επεξεργασία των branches, πάρε τα IDs
        branch_ids: Array.isArray(data.branches) ? data.branches.map(b => b.id) : [],
        position_ids: Array.isArray(data.positions) ? data.positions.map(p => p.position_id) : [] // Για μελλοντική χρήση
    });
  }, []);

  const fetchCandidateData = useCallback(async () => {
    setIsLoading(true); setError(null);
    try {
      const detailsRes = await apiClient.get(`/candidate/${candidateId}`);
      setCandidate(detailsRes.data);
      initializeFormData(detailsRes.data); // Αυτό θα θέσει και τα branch_ids στο formData
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
            // Το backend /company/{id}/positions δεν υπάρχει, χρησιμοποιούμε το /company/positions με params
            const params = { company_id: companyIdForFetch, status: 'Open', all: true }; // all:true για να μην έχει pagination
            const response = await companyAdminService.getCompanyPositions(params); // Χρήση του companyAdminService
            setCompanyOpenPositions(response.positions || []);
        } catch (error) {
            console.error("Error fetching company open positions:", error);
            setCompanyOpenPositions([]);
        } finally {
            setIsLoadingCompanyPositions(false);
        }
    };

    const fetchAllBranchesForCompany = async () => {
        setIsLoadingCompanyBranches(true);
        try {
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

  const handlePositionNameChange = (event) => { // Για το text input των positions
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

  const handleBranchSelectionChange = (selectedOptions) => {
    const selectedIds = selectedOptions ? selectedOptions.map(option => option.value) : [];
    setFormData(prevData => ({ ...prevData, branch_ids: selectedIds }));
  };
  
  // Για το react-select των positions (αν το υλοποιήσεις)
  const handlePositionIdSelectionChange = (selectedOptions) => {
    const selectedIds = selectedOptions ? selectedOptions.map(option => option.value) : [];
    // Επίσης ενημέρωσε και το `formData.positions` (με τα ονόματα) αν θέλεις να φαίνονται στο text input
    const selectedNames = selectedOptions ? selectedOptions.map(option => option.label) : [];
    setFormData(prevData => ({ 
        ...prevData, 
        position_ids: selectedIds,
        positions: selectedNames // Ενημέρωση και των ονομάτων για εμφάνιση
    }));
  };


  const sendUpdateRequest = async (payload) => {
    if (!candidate) return;
    setIsUpdating(true); setError(null);
    try {
      const response = await apiClient.put(`/candidate/${candidate.candidate_id}`, payload);
      setCandidate(response.data);
      initializeFormData(response.data); // Επανα-αρχικοποίηση για να πάρει τα νέα branch_ids
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
    // Εδώ, όταν αλλάζει το status, στέλνουμε τα branch_ids που είναι ήδη στο formData.
    // Αν δεν είναι σε edit mode, παίρνουμε τα branch_ids από το `candidate.branches`.
    const currentBranchIds = editMode ? formData.branch_ids : (candidate.branches ? candidate.branches.map(b => b.id) : []);
    const currentPositionNames = editMode ? formData.positions : (candidate.positions ? candidate.positions.map(p => p.position_name) : []);

    let payload = {
        current_status: newStatus,
        notes: editMode ? formData.notes : (extraData.notes || candidate?.notes || ''),
        hr_comments: editMode ? formData.hr_comments : (extraData.hr_comments || candidate?.hr_comments || ''),
        branch_ids: currentBranchIds,
        positions: currentPositionNames, // Στέλνουμε τα ονόματα των positions
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
         positions: formData.positions, // Στέλνονται τα ονόματα
         education_summary: formData.education_summary, experience_summary: formData.experience_summary,
         skills_summary: formData.skills_summary, languages: formData.languages, seminars: formData.seminars,
         notes: formData.notes, hr_comments: formData.hr_comments, evaluation_rating: formData.evaluation_rating,
         offers: formData.offers.map(o => ({
            ...o,
            offer_amount: o.offer_amount === '' || o.offer_amount === null ? null : parseFloat(o.offer_amount),
            offer_date: o.offer_date ? new Date(o.offer_date).toISOString() : new Date().toISOString()
         })).filter(o => o.offer_amount !== null || (o.offer_notes && o.offer_notes.trim() !== '')),
         branch_ids: formData.branch_ids, // Στέλνονται τα IDs
      };
      try { await sendUpdateRequest(updatePayload); } catch (err) { /* Error handled */ }
  };

  // Οι υπόλοιπες handlers (handleProposeInterviewClick, handleSendInterviewProposal, etc.) παραμένουν ίδιες
  // ... (αντέγραψε τις υπόλοιπες handlers από τον προηγούμενο κώδικά σου) ...
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
      fetchCandidateData(); // Καλύτερα να κάνουμε refetch
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
  if (!candidate) return null; // Για ασφάλεια

  const candidateResponseInfo = getConfirmationStatusInfo(candidate.candidate_confirmation_status);
  const latestScheduledInterview = candidate.interviews?.filter(inv => inv.status === 'SCHEDULED').sort((a,b) => new Date(b.created_at) - new Date(a.created_at))[0];
  const latestProposedInterview = candidate.interviews?.filter(inv => inv.status === 'PROPOSED').sort((a,b) => new Date(b.created_at) - new Date(a.created_at))[0];

  const canRecruiterCancel = latestScheduledInterview || latestProposedInterview;
  const canMoveToEvaluation = latestScheduledInterview;

  // Options for react-select (Branches)
  const branchOptionsForSelect = allCompanyBranches.map(branch => ({
    value: branch.id,
    label: branch.name,
  }));

  // Options for react-select (Positions - αν το υλοποιήσεις)
  const positionOptionsForSelect = companyOpenPositions.map(pos => ({
      value: pos.position_id,
      label: pos.position_name
  }));


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
            
            {/* Εμφάνιση/Επεξεργασία Positions */}
            <div className="info-item info-item-full">
                <label>Applied for Position(s):</label>
                {editMode ? (
                    <>
                        <input 
                            type="text" 
                            name="positions" 
                            value={formData.positions.join(', ')} 
                            onChange={handlePositionNameChange} 
                            className="input-light-gray" 
                            placeholder="Comma-separated position names"
                            style={{marginBottom: '5px'}}
                        />
                        {/* Προαιρετικά: react-select για επιλογή από υπάρχουσες θέσεις */}
                        <Select
                            isMulti
                            options={positionOptionsForSelect}
                            value={positionOptionsForSelect.filter(opt => formData.position_ids.includes(opt.value))}
                            onChange={handlePositionIdSelectionChange}
                            placeholder="Or select existing positions..."
                            isLoading={isLoadingCompanyPositions}
                            isDisabled={isLoadingCompanyPositions}
                            styles={{ control: (base) => ({ ...base, backgroundColor: '#f8f9fa', borderColor: '#ced4da' }) }}
                        />
                         <small>Enter names directly or select from list. Selections will update the text field.</small>
                    </>
                ) : (
                    <span>{formatObjectListDisplay(candidate.positions, 'position_name')}</span>
                )}
            </div>


            {/* Branches Section - Εμφάνιση και Επεξεργασία */}
            <div className="info-item info-item-full">
                <label>Assigned Branch(es):</label>
                {editMode ? (
                    <Select
                        isMulti
                        options={branchOptionsForSelect}
                        value={branchOptionsForSelect.filter(opt => formData.branch_ids.includes(opt.value))}
                        onChange={handleBranchSelectionChange}
                        placeholder="Select branches..."
                        isLoading={isLoadingCompanyBranches}
                        isDisabled={isLoadingCompanyBranches || allCompanyBranches.length === 0}
                        styles={{ control: (base) => ({ ...base, backgroundColor: '#f8f9fa', borderColor: '#ced4da' }) }}
                    />
                ) : (
                    <span>{formatObjectListDisplay(candidate.branches, 'name')}</span>
                )}
            </div>

            {/* ... (τα υπόλοιπα πεδία παραμένουν ίδια) ... */}
            <div className="info-item"><label>Current Status:</label><span className={`status-badge status-${candidate.current_status?.toLowerCase().replace(/\s+/g, '-')}`}>{candidate.current_status || 'N/A'}</span></div>
            <div className="info-item"><label>Submission Date:</label><span>{formatDate(candidate.submission_date)}</span></div>
            <div className="info-item"><label>Last Updated:</label><span>{formatDate(candidate.updated_at)}</span></div>
            <div className="info-item"><label>Status Last Changed:</label><span>{formatDate(candidate.status_last_changed_date)}</span></div>

             {latestScheduledInterview && ( /* ... (παραμένει ίδιο) ... */ <div /> )}
             {latestProposedInterview && candidate.current_status === 'Interview Proposed' && (  /* ... (παραμένει ίδιο) ... */ <div /> )}
            <div className="info-item"> <label>EVALUATION RATING (HR):</label> {/* ... (παραμένει ίδιο) ... */} </div>
            <div className="info-item info-item-full"><label>EDUCATION SUMMARY:</label>{/* ... (παραμένει ίδιο) ... */}</div>
            <div className="info-item info-item-full"><label>WORK EXPERIENCE SUMMARY:</label>{/* ... (παραμένει ίδιο) ... */}</div>
            <div className="info-item"><label>LANGUAGES:</label>{/* ... (παραμένει ίδιο) ... */}</div>
            <div className="info-item"><label>SEMINARS/CERTIFICATIONS:</label>{/* ... (παραμένει ίδιο) ... */}</div>
            <div className="info-item info-item-full"><label>GENERAL NOTES / AUTO-PARSED INFO:</label>{/* ... (παραμένει ίδιο) ... */}</div>
            <div className="info-item info-item-full"><label style={{fontWeight: 'bold', color: 'var(--primary-color)'}}>HR INTERNAL COMMENTS:</label>{/* ... (παραμένει ίδιο) ... */}</div>
            {(editMode || (candidate.offers && candidate.offers.length > 0 && candidate.offers.some(o => o.offer_amount || o.offer_notes)) || candidate.current_status === 'OfferMade') && ( /* ... (παραμένει ίδιο) ... */ <div /> )}
          </div>

          {!editMode && ( <div className="action-buttons"> <h4>Candidate Actions</h4> {/* ... (τα action buttons παραμένουν ίδια) ... */} </div>)}
           {showRecruiterCancelModal && ( <ModalDialog isOpen={showRecruiterCancelModal} onClose={() => setShowRecruiterCancelModal(false)} title="Cancel Interview (by Recruiter)"> {/* ... (παραμένει ίδιο) ... */} </ModalDialog> )}
          {showProposalModal && candidate && ( <ModalDialog isOpen={showProposalModal} onClose={() => setShowProposalModal(false)} title={`Propose Interview for ${candidate.first_name || ''} ${candidate.last_name || ''}`.trim()}> {/* ... (παραμένει ίδιο) ... */} </ModalDialog> )}
        </div>

        <div className="detail-column detail-column-right"> {/* ... (CV Viewer και History Log παραμένουν ίδια) ... */}
            <div className="cv-viewer-section card-style"> <div/> </div>
            <div className="history-log-section card-style"> <div/> </div>
        </div>
      </div>
    </div>
  );
}

export default CandidateDetailPage;