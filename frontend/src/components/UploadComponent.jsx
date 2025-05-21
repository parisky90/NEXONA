// frontend/src/components/UploadComponent.jsx
import React, { useState, useCallback, useEffect, useMemo } from 'react';
import { useDropzone } from 'react-dropzone';
import apiClient from '../api';
import companyAdminService from '../services/companyAdminService';
import { useAuth } from '../App';
import './UploadComponent.css';

function UploadComponent({ onUploadSuccess, companyIdForUploadAsSuperadmin }) {
  const { currentUser } = useAuth();
  const [acceptedFiles, setAcceptedFiles] = useState([]);
  
  // Existing state for ad-hoc position name
  const [positionName, setPositionName] = useState(''); 
  
  const [availableBranches, setAvailableBranches] = useState([]);
  const [selectedBranchIds, setSelectedBranchIds] = useState([]);
  const [isLoadingBranches, setIsLoadingBranches] = useState(false);

  // --- ΝΕΟ STATE ΓΙΑ POSITIONS ---
  const [availablePositions, setAvailablePositions] = useState([]);
  const [selectedPositionIds, setSelectedPositionIds] = useState([]);
  const [isLoadingPositions, setIsLoadingPositions] = useState(false);
  // ---------------------------------

  const [message, setMessage] = useState('');
  const [messageType, setMessageType] = useState('');
  const [isUploading, setIsUploading] = useState(false);

  const targetCompanyIdForData = useMemo(() => {
    if (!currentUser) return null;
    return currentUser.role === 'superadmin' ? companyIdForUploadAsSuperadmin : currentUser.company_id;
  }, [currentUser, companyIdForUploadAsSuperadmin]);

  const fetchBranchesForCompany = useCallback(async () => {
    if (!targetCompanyIdForData) {
      setAvailableBranches([]);
      return;
    }
    setIsLoadingBranches(true);
    try {
      const branchesData = await companyAdminService.getBranches(
        currentUser?.role === 'superadmin' ? targetCompanyIdForData : null
      );
      setAvailableBranches(branchesData || []);
    } catch (err) {
      console.error("Failed to fetch branches for upload form:", err);
      setAvailableBranches([]);
      // Don't overwrite general message if positions also fail
    } finally {
      setIsLoadingBranches(false);
    }
  }, [targetCompanyIdForData, currentUser?.role]);

  // --- ΝΕΑ ΣΥΝΑΡΤΗΣΗ ΓΙΑ FETCH POSITIONS ---
  const fetchOpenPositionsForCompany = useCallback(async () => {
    if (!targetCompanyIdForData) {
      setAvailablePositions([]);
      return;
    }
    setIsLoadingPositions(true);
    try {
      const params = { status: 'Open' }; // Fetch only Open positions
      // For company_admin, backend uses current_user.company_id automatically.
      // For superadmin, if targetCompanyIdForData is set (meaning a company is selected), pass it.
      if (currentUser?.role === 'superadmin' && targetCompanyIdForData) {
        params.company_id = targetCompanyIdForData;
      }
      
      const positionsData = await companyAdminService.getCompanyPositions(params);
      setAvailablePositions(positionsData.positions || []);
    } catch (err) {
      console.error("Failed to fetch open positions for upload form:", err);
      setAvailablePositions([]);
      // Append to existing message if any, or set new message
      setMessage(prev => {
        const newError = 'Could not load available positions.';
        if (prev && prev.includes(newError)) return prev; // Avoid duplicate error messages
        return prev ? `${prev}\n${newError}` : newError;
      });
      setMessageType('error'); // Ensure message type is error
    } finally {
      setIsLoadingPositions(false);
    }
  }, [targetCompanyIdForData, currentUser?.role]);
  // ---------------------------------------

  useEffect(() => {
    if (targetCompanyIdForData) {
      fetchBranchesForCompany();
      fetchOpenPositionsForCompany(); // <<< ΚΛΗΣΗ ΓΙΑ POSITIONS
    } else {
      setAvailableBranches([]);
      setAvailablePositions([]); // <<< RESET POSITIONS
    }
  }, [fetchBranchesForCompany, fetchOpenPositionsForCompany, targetCompanyIdForData]);


  const onDrop = useCallback(accepted => {
    if (accepted.length > 0) {
        setAcceptedFiles([accepted[0]]);
        setMessage(`Selected file: ${accepted[0].name}`);
        setMessageType('info');
    } else {
        setMessage('Invalid file type. Please upload PDF, DOCX, DOC, or TXT.');
        setMessageType('error');
        setAcceptedFiles([]);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'application/msword': ['.doc'],
      'text/plain': ['.txt']
    },
    multiple: false
  });

  const handleAdHocPositionNameChange = (event) => {
    setPositionName(event.target.value);
  };

  const handleBranchSelectionChange = (event) => {
    const { options } = event.target;
    const value = [];
    for (let i = 0, l = options.length; i < l; i += 1) {
      if (options[i].selected) {
        value.push(options[i].value);
      }
    }
    setSelectedBranchIds(value.map(idStr => parseInt(idStr, 10)));
  };

  // --- ΝΕΑ HANDLER ΓΙΑ POSITION SELECTION ---
  const handlePositionSelectionChange = (event) => {
    const { options } = event.target;
    const value = [];
    for (let i = 0, l = options.length; i < l; i += 1) {
      if (options[i].selected) {
        value.push(options[i].value);
      }
    }
    setSelectedPositionIds(value.map(idStr => parseInt(idStr, 10)));
  };
  // ------------------------------------------

  const handleUpload = async () => {
    if (acceptedFiles.length === 0) {
        setMessage('Please select a CV file to upload.');
        setMessageType('error');
        return;
    }
    if (currentUser?.role === 'superadmin' && !companyIdForUploadAsSuperadmin) {
        setMessage('Superadmin must select a target company before uploading a CV.');
        setMessageType('error');
        return;
    }

    setIsUploading(true);
    setMessage('Uploading...');
    setMessageType('info');

    const formDataPayload = new FormData();
    formDataPayload.append('cv_file', acceptedFiles[0]);
    
    if (selectedPositionIds.length > 0) { // Προτεραιότητα στα επιλεγμένα IDs
        formDataPayload.append('position_ids', selectedPositionIds.join(','));
    } else if (positionName.trim()) { // Fallback στο ad-hoc όνομα
        formDataPayload.append('position', positionName.trim());
    }

    if (selectedBranchIds.length > 0) {
        formDataPayload.append('branch_ids', selectedBranchIds.join(','));
    }

    if (currentUser?.role === 'superadmin' && companyIdForUploadAsSuperadmin) {
        formDataPayload.append('company_id_for_upload', companyIdForUploadAsSuperadmin);
    }

    try {
        const response = await apiClient.post('/upload', formDataPayload, {
            headers: { 'Content-Type': 'multipart/form-data' },
        });

        setMessage(response.data.message || `Upload successful! Candidate ID: ${response.data.candidate_id || 'N/A'}.`);
        setMessageType('success');
        setAcceptedFiles([]);
        setPositionName(''); 
        setSelectedBranchIds([]);
        setSelectedPositionIds([]); // <<< RESET SELECTED POSITION IDs

        if (document.getElementById('cv-file-input-for-uploadcomponent')) {
            document.getElementById('cv-file-input-for-uploadcomponent').value = null;
        }

        if (onUploadSuccess) {
          onUploadSuccess(response.data);
        }

    } catch (error) {
        let errorMessage = 'Upload failed. Please try again.';
        if (error.response) {
            errorMessage = error.response.data?.error || `Upload failed with status ${error.response.status}.`;
        } else if (error.request) {
            errorMessage = 'Upload failed: No response from server.';
        } else {
            errorMessage = `Upload failed: ${error.message}`;
        }
        setMessage(errorMessage);
        setMessageType('error');
    } finally {
        setIsUploading(false);
    }
  };

  const selectedFileDisplay = acceptedFiles.length > 0 ? (
    <p style={{ fontSize: '0.85rem', marginTop: '10px', textAlign: 'left', color: 'var(--text-secondary)' }}>
        Selected: <strong>{acceptedFiles[0].name}</strong>
    </p>
  ) : null;

  const canUpload = currentUser && (currentUser.role === 'company_admin' || (currentUser.role === 'superadmin' && companyIdForUploadAsSuperadmin));

  if (!currentUser) {
    return <div className="upload-container card-style"><p>Please log in to upload CVs.</p></div>;
  }
  if (currentUser.role === 'superadmin' && !companyIdForUploadAsSuperadmin){
    return (
        <div className="upload-container">
            <p style={{textAlign: 'center', padding: '1rem', color: 'var(--text-muted)'}}>
                {/* Optional: Superadmin message when no company selected */}
            </p>
        </div>
    );
  }

  return (
    <div className="upload-container">
      <div {...getRootProps()} className={`dropzone ${isDragActive ? 'active' : ''}`}>
        <input {...getInputProps()} id="cv-file-input-for-uploadcomponent" />
        {isDragActive ? (
          <p>Drop the CV file here ...</p>
        ) : (
          <p>Drag 'n' drop CV (PDF/DOCX/DOC/TXT), or click to select</p>
        )}
      </div>
      {selectedFileDisplay}

      {/* --- ΝΕΟ DROPDOWN ΓΙΑ POSITIONS --- */}
      <div className="form-group" style={{ marginTop: '1rem', marginBottom: '1rem' }}>
        <label htmlFor="upload-positions-uploadcomponent">Assign to Position(s) (Optional):</label>
        <select
          id="upload-positions-uploadcomponent"
          multiple
          value={selectedPositionIds.map(String)}
          onChange={handlePositionSelectionChange}
          disabled={isUploading || isLoadingPositions || !canUpload}
          className="input-light-gray"
          size={Math.min(5, availablePositions.length > 0 ? availablePositions.length : 1)}
          style={{ minHeight: '80px', width: '100%' }}
        >
          {isLoadingPositions ? (
            <option disabled>Loading company positions...</option>
          ) : availablePositions.length === 0 ? (
            <option disabled>No open positions available for this company.</option>
          ) : (
            availablePositions.map(position => (
              <option key={position.position_id} value={position.position_id.toString()}>
                {position.position_name}
              </option>
            ))
          )}
        </select>
        {availablePositions.length > 0 && <small style={{fontSize: '0.75rem', color: 'var(--text-muted)'}}>Hold Ctrl (or Cmd on Mac) to select multiple positions.</small>}
      </div>
      {/* ------------------------------------ */}

      {/* Ad-hoc position name input */}
      <div className="position-input" style={{ marginBottom: '1rem' }}>
        <label htmlFor="position-applied-for-uploadcomponent">OR Enter Ad-hoc Position Name (Optional):</label>
        <input
          type="text"
          id="position-applied-for-uploadcomponent"
          className="input-light-gray"
          value={positionName}
          onChange={handleAdHocPositionNameChange}
          placeholder="e.g., Software Engineer"
          disabled={isUploading || !canUpload || selectedPositionIds.length > 0} // Disable if IDs are selected
        />
         {selectedPositionIds.length > 0 && <small style={{fontSize: '0.75rem', color: 'var(--text-muted)'}}>Ad-hoc name is disabled when positions are selected from the list.</small>}
      </div>
      
      {/* Branches dropdown */}
      <div className="form-group" style={{ marginBottom: '1rem' }}>
        <label htmlFor="upload-branches-uploadcomponent">Assign to Branch(es) (Optional):</label>
        <select
          id="upload-branches-uploadcomponent"
          multiple
          value={selectedBranchIds.map(String)}
          onChange={handleBranchSelectionChange}
          disabled={isUploading || isLoadingBranches || !canUpload}
          className="input-light-gray"
          size={Math.min(5, availableBranches.length > 0 ? availableBranches.length : 1)}
          style={{ minHeight: '80px', width: '100%' }}
        >
          {isLoadingBranches ? (
            <option disabled>Loading company branches...</option>
          ) : availableBranches.length === 0 ? (
            <option disabled>No branches available for this company.</option>
          ) : (
            availableBranches.map(branch => (
              <option key={branch.id} value={branch.id.toString()}>
                {branch.name}
              </option>
            ))
          )}
        </select>
        {availableBranches.length > 0 && <small style={{fontSize: '0.75rem', color: 'var(--text-muted)'}}>Hold Ctrl (or Cmd on Mac) to select multiple branches.</small>}
      </div>

      <button
        onClick={handleUpload}
        className="button-action button-primary"
        disabled={isUploading || acceptedFiles.length === 0 || !canUpload}
        style={{width: '100%', marginTop: '0.5rem'}}
      >
        {isUploading ? 'Uploading...' : 'Upload CV'}
      </button>

      {message && <p className={`message ${messageType}`}>{message}</p>}
    </div>
  );
}

export default UploadComponent;