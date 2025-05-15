// frontend/src/components/UploadComponent.jsx
import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { uploadCV } from '../api'; // Έχουμε ήδη το uploadCV helper
import './UploadComponent.css'; 

function UploadComponent({ onUploadSuccess }) {
  const [acceptedFiles, setAcceptedFiles] = useState([]);
  const [positionName, setPositionName] = useState('');
  const [message, setMessage] = useState('');
  const [messageType, setMessageType] = useState(''); 
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
    // Το position name μπορεί να είναι προαιρετικό, ανάλογα με τη λογική σου.
    // Αν είναι υποχρεωτικό:
    // if (!positionName.trim()) {
    //      setMessage('Please enter the position name.');
    //      setMessageType('error');
    //      return;
    //  }

    setIsUploading(true);
    setMessage('Uploading...');
    setMessageType('info');

    const formData = new FormData();
    formData.append('cv_file', acceptedFiles[0]);
    if (positionName.trim()) { // Στείλε το position μόνο αν έχει συμπληρωθεί
        formData.append('position', positionName.trim());
    }


    try {
        const response = await uploadCV(formData); 

        setMessage(`Upload successful! Candidate ID: ${response.data.candidate_id || 'N/A'}. Parsing started.`);
        setMessageType('success');
        setAcceptedFiles([]);
        setPositionName(''); // Καθάρισμα και του position name

        if (onUploadSuccess) {
          onUploadSuccess();
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

  const selectedFile = acceptedFiles.length > 0 ? (
    <p style={{ fontSize: '0.85rem', marginTop: '10px', textAlign: 'left', color: 'var(--text-secondary)' }}>
        Selected: <strong>{acceptedFiles[0].name}</strong>
    </p>
  ) : null;

  return (
    // Το .upload-container ΔΕΝ χρειάζεται card-style αν το γονικό του (π.χ. στο DashboardPage) έχει ήδη card-style.
    // Αν το UploadComponent χρησιμοποιείται και αυτόνομα, τότε μπορεί να χρειάζεται.
    // Ας υποθέσουμε ότι το γονικό έχει card-style.
    <div className="upload-container"> 
      {/* Ο τίτλος h3 μπορεί να προέρχεται από το γονικό component (DashboardPage) */}
      {/* <h3>Upload New CV</h3>  */}
      <div {...getRootProps()} className={`dropzone ${isDragActive ? 'active' : ''}`}>
        <input {...getInputProps()} />
        {isDragActive ? (
          <p>Drop the CV file here ...</p>
        ) : (
          <p>Drag 'n' drop a CV file here (PDF/DOCX), or click to select</p>
        )}
      </div>
      {selectedFile}
      
      <div className="position-input"> {/* Αυτό το div θα πάρει στυλ από το UploadComponent.css */}
        <label htmlFor="position-applied-for">Position Applied For (Optional):</label>
        <input
          type="text"
          id="position-applied-for"
          className="input-light-gray" // Χρήση της global κλάσης για inputs
          value={positionName}
          onChange={handlePositionChange}
          placeholder="e.g., Software Engineer"
          disabled={isUploading}
        />
      </div>
      
      <button
        onClick={handleUpload}
        className="button-action button-primary" // Χρήση global κλάσεων για κουμπιά
        disabled={isUploading || acceptedFiles.length === 0}
        style={{width: '100%', marginTop: '0.5rem'}} // Πλήρες πλάτος και λίγο κενό
      >
        {isUploading ? 'Uploading...' : 'Upload CV'}
      </button>
      
      {message && <p className={`message ${messageType}`}>{message}</p>}
    </div>
  );
}

export default UploadComponent;