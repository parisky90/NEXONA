// frontend/src/components/ModalDialog.jsx
import React from 'react';
import './ModalDialog.css'; // Θα δημιουργήσουμε αυτό το CSS

function ModalDialog({ isOpen, onClose, title, children }) {
  if (!isOpen) {
    return null;
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          {title && <h3 className="modal-title">{title}</h3>}
          <button onClick={onClose} className="modal-close-button">×</button>
        </div>
        <div className="modal-body">
          {children}
        </div>
      </div>
    </div>
  );
}

export default ModalDialog;