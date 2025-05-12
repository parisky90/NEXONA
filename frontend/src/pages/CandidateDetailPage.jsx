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

  const fetchCandidateData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [detailsRes, urlRes] = await Promise.all([
        apiClient.get(`/candidate/${candidateId}`),
        apiClient.get(`/candidate/${candidateId}/cv_url`)
      ]);
      setCandidate(detailsRes.data);
      // Αρχικοποίηση του formData με τα δεδομένα του υποψηφίου
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
          interview_datetime: detailsRes.data.interview_datetime || null,
          interview_location: detailsRes.data.interview_location || '',
          candidate_confirmation_status: detailsRes.data.candidate_confirmation_status || null,
      });
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
    setIsUpdating(true);
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
      // Επαναφορά του formData με τα νέα δεδομένα από το response
      setFormData({
        first_name: response.data.first_name || '',
        last_name: response.data.last_name || '',
        email: response.data.email || '',
        phone_number: response.data.phone_number || '',
        age: response.data.age || '',
        positions: response.data.positions || [],
        education: response.data.education || '',
        work_experience: response.data.work_experience || '',
        languages: response.data.languages || '',
        seminars: response.data.seminars || '',
        notes: response.data.notes || '',
        evaluation_rating: response.data.evaluation_rating || '',
        offer_details: response.data.offer_details || '',
        interview_datetime: response.data.interview_datetime || null,
        interview_location: response.data.interview_location || '',
        candidate_confirmation_status: response.data.candidate_confirmation_status || null,
      });
      if (newStatus === 'Rejected') navigate('/rejected');
      if (newStatus === 'Declined') navigate('/declined');
    } catch (err) {
      setError(err.response?.data?.error || `Failed to update status.`);
    } finally {
      setIsUpdating(false);
    }
  };

  const handleSaveChanges = async () => {
      if (!candidate) return;
      setIsUpdating(true);
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
          // Επαναφορά του formData με τα νέα δεδομένα από το response
           setFormData({
                first_name: response.data.first_name || '',
                last_name: response.data.last_name || '',
                email: response.data.email || '',
                phone_number: response.data.phone_number || '',
                age: response.data.age || '',
                positions: response.data.positions || [],
                education: response.data.education || '',
                work_experience: response.data.work_experience || '',
                languages: response.data.languages || '',
                seminars: response.data.seminars || '',
                notes: response.data.notes || '',
                evaluation_rating: response.data.evaluation_rating || '',
                offer_details: response.data.offer_details || '',
                interview_datetime: response.data.interview_datetime || null,
                interview_location: response.data.interview_location || '',
                candidate_confirmation_status: response.data.candidate_confirmation_status || null,
            });
          setEditMode(false);
      } catch (err) {
          setError(err.response?.data?.error || `Failed to save changes.`);
      } finally {
          setIsUpdating(false);
      }
  };

  const handleScheduleInterview = async ({ date, time, location }) => {
       if (!candidate || !date || !time) {
           setError("Please select both date and time for the interview.");
           return;
       }
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
  const handleRejectInterview = () => handleUpdateStatus('Rejected');
  const handleMakeOffer = () => handleUpdateStatus('OfferMade');
  const handleOfferAccepted = () => handleUpdateStatus('Hired');
  const handleOfferRejected = () => handleUpdateStatus('Declined', { offer_response_date: new Date().toISOString() });

  const formatDate = (isoString) => {
    if (!isoString) return 'N/A';
    try { return new Date(isoString).toLocaleString([], { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }); } catch { return 'Invalid Date'; }
  };

  if (isLoading) return <div className="loading-placeholder card-style">Loading candidate details...</div>;
  if (error && !candidate) return <div className="error-message card-style">Error: {error} <button onClick={fetchCandidateData} className="button-action button-secondary">Retry</button></div>;
  if (!candidate) return <div className="card-style">Candidate not found or data unavailable.</div>;

  const confirmationDisplayInfo = getConfirmationStatusInfo(candidate.candidate_confirmation_status);

  return (
    <div className="candidate-detail-page">
      <Link to="/dashboard" className="back-link">← Back to Dashboard</Link>
      {error && <div className="error-message">{error}</div>}
      <div className="detail-header">
         <h2>{editMode ? `${formData.first_name || ''} ${formData.last_name || ''}`.trim() || 'Edit Candidate' : `${candidate.first_name || ''} ${candidate.last_name || 'Candidate Details'}`.trim()}</h2>
         <div className="header-actions">
             {!editMode ? (
                 <button onClick={() => setEditMode(true)} className="button-action button-edit">Edit</button>
             ) : (
                 <>
                    <button onClick={handleSaveChanges} className="button-action button-save" disabled={isUpdating}>{isUpdating ? 'Saving...' : 'Save Changes'}</button>
                    <button onClick={() => {
                        setEditMode(false);
                        // Επαναφορά του formData από το τρέχον candidate state
                        setFormData({
                            first_name: candidate.first_name || '', last_name: candidate.last_name || '',
                            email: candidate.email || '', phone_number: candidate.phone_number || '',
                            age: candidate.age || '', positions: candidate.positions || [],
                            education: candidate.education || '', work_experience: candidate.work_experience || '',
                            languages: candidate.languages || '', seminars: candidate.seminars || '',
                            notes: candidate.notes || '', evaluation_rating: candidate.evaluation_rating || '',
                            offer_details: candidate.offer_details || '',
                            interview_datetime: candidate.interview_datetime || null,
                            interview_location: candidate.interview_location || '',
                            candidate_confirmation_status: candidate.candidate_confirmation_status || null,
                        });
                        setError(null); // Καθαρισμός τυχόν σφαλμάτων
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