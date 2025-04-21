// frontend/src/components/UploadComponent.jsx
import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import apiClient, { uploadCV } from '../api'; // Assuming api.js exports apiClient and helper
import './UploadComponent.css'; // Make sure styles are imported

function UploadComponent({ onUploadSuccess }) { // Added optional prop for refresh
  const [acceptedFiles, setAcceptedFiles] = useState([]);
  const [positionName, setPositionName] = useState('');
  const [message, setMessage] = useState('');
  const [messageType, setMessageType] = useState(''); // 'info', 'success', 'error'
  const [isUploading, setIsUploading] = useState(false);

  const onDrop = useCallback(accepted => {
    if (accepted.length > 0) {
        setAcceptedFiles([accepted[0]]);
        setMessage(`Selected file: ${accepted[0].name}`);
        setMessageType('info');
    } else {
        setMessage('Invalid file type or too many files selected.');
        setMessageType('error');
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx']
    },
    multiple: false
  });

  const handlePositionChange = (event) => {
    setPositionName(event.target.value);
  };

  const handleUpload = async () => {
    if (acceptedFiles.length === 0) {
        setMessage('Please select a CV file to upload.');
        setMessageType('error');
        return;
    }
    if (!positionName.trim()) {
         setMessage('Please enter the position name.');
         setMessageType('error');
         return;
     }

    setIsUploading(true);
    setMessage('Uploading...');
    setMessageType('info');

    const formData = new FormData();
    formData.append('cv_file', acceptedFiles[0]);
    formData.append('position', positionName.trim());

    try {
        const response = await uploadCV(formData); // Use helper from api.js

        setMessage(`Upload successful! Candidate ID: ${response.data.candidate_id || 'N/A'}. Parsing started.`);
        setMessageType('success');
        setAcceptedFiles([]);
        setPositionName('');

        if (onUploadSuccess) {
          onUploadSuccess();
        }

    } catch (error) {
        console.error("Upload error object:", error);
        let errorMessage = 'Upload failed. Please try again.';
        if (error.response) {
            console.error("Error response data:", error.response.data);
            console.error("Error response status:", error.response.status);
            if (error.response.status === 401) {
                 errorMessage = 'Upload failed: Please log in again.';
            } else {
                 errorMessage = error.response.data?.error || `Upload failed with status ${error.response.status}.`;
            }
        } else if (error.request) {
            console.error("Error request data:", error.request);
            errorMessage = 'Upload failed: No response from server. Is the backend running?';
        } else {
            console.error('Error message:', error.message);
            errorMessage = `Upload failed: ${error.message}`;
        }
        setMessage(errorMessage);
        setMessageType('error');
    } finally {
        setIsUploading(false);
    }
  };

  const selectedFile = acceptedFiles.length > 0 ? (
    <p style={{ fontSize: '0.85rem', marginTop: '10px', textAlign: 'left' }}>
        Selected: {acceptedFiles[0].name}
    </p>
  ) : null;

  return (
    <div className="upload-container card-style">
      <h3>Upload New CV</h3>
      <div {...getRootProps()} className={`dropzone ${isDragActive ? 'active' : ''}`}>
        <input {...getInputProps()} />
        {isDragActive ? (
          <p>Drop the CV file here ...</p>
        ) : (
          <p>Drag 'n' drop a CV file here (PDF/DOCX), or click to select</p>
        )}
      </div>
      {selectedFile}
      {/* --- Input section --- */}
      <div className="position-input">
        <label htmlFor="position">Position Applied For:</label>
        <input
          type="text"
          id="position"
          className="input-light-gray" // Ensure class is applied
          value={positionName}
          onChange={handlePositionChange}
          placeholder="e.g., Software Engineer" // Ensure quotes are closed
          disabled={isUploading}
        /> {/* Ensure self-closing tag is correct */}
      </div>
      {/* --- Button section --- */}
      <button
        onClick={handleUpload}
        className="button-navy-blue" // Ensure class is applied
        disabled={isUploading || acceptedFiles.length === 0}
      > {/* Closing bracket for button start tag */}
        {isUploading ? 'Uploading...' : 'Upload CV'}
      </button> {/* Closing button tag */}
      {/* --- Message section --- */}
      {message && <p className={`message ${messageType}`}>{message}</p>}
    </div> // Closing upload-container div
  ); // Closing return statement
} // Closing Function Component

export default UploadComponent;