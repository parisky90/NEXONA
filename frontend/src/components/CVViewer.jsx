// frontend/src/components/CVViewer.jsx
import React, { useState, useEffect, useMemo } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/esm/Page/AnnotationLayer.css';
import 'react-pdf/dist/esm/Page/TextLayer.css';
import './CVViewer.css'; // Βεβαιώσου ότι έχεις αυτό το αρχείο CSS

try {
    pdfjs.GlobalWorkerOptions.workerSrc = new URL(
      'pdfjs-dist/build/pdf.worker.min.mjs',
      import.meta.url,
    ).toString();
} catch (error) {
    console.error("Failed to set pdfjs workerSrc:", error);
}

// Props:
// candidate: The full candidate object which should include:
//   - cv_url (URL of the original CV)
//   - cv_pdf_url (URL of the generated PDF, if available)
//   - cv_original_filename (filename of the original CV)
//   - is_docx (boolean, true if original CV is DOCX)
//   - is_pdf_original (boolean, true if original CV is PDF)
// onCvRefreshNeeded: Function to call when user clicks "refresh" for conversion status
// onError: (Προαιρετικό) callback για σφάλματα φόρτωσης PDF

function CVViewer({ candidate, onCvRefreshNeeded, onError }) {
  const [numPages, setNumPages] = useState(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [isLoadingDocument, setIsLoadingDocument] = useState(false);
  const [isPageLoading, setIsPageLoading] = useState(false);
  const [loadError, setLoadError] = useState('');
  const [currentFileUrlToLoad, setCurrentFileUrlToLoad] = useState(null);
  const [statusMessage, setStatusMessage] = useState(''); // Μήνυμα για DOCX κλπ.
  const [showDownloadOriginalButton, setShowDownloadOriginalButton] = useState(false);

  useEffect(() => {
    // Reset state when candidate prop changes
    setNumPages(null);
    setPageNumber(1);
    setIsLoadingDocument(false); // Θα το θέσουμε true μόνο αν έχουμε URL
    setLoadError('');
    setStatusMessage('');
    setCurrentFileUrlToLoad(null);
    setShowDownloadOriginalButton(false);

    if (candidate && (candidate.cv_url || candidate.cv_pdf_url)) {
        if (candidate.cv_pdf_url) {
            console.log("CVViewer: Attempting to load generated PDF:", candidate.cv_pdf_url);
            setCurrentFileUrlToLoad(candidate.cv_pdf_url);
            setIsLoadingDocument(true);
            setShowDownloadOriginalButton(true); // Offer download of original if PDF is shown
        } else if (candidate.is_pdf_original && candidate.cv_url) {
            console.log("CVViewer: Attempting to load original PDF:", candidate.cv_url);
            setCurrentFileUrlToLoad(candidate.cv_url);
            setIsLoadingDocument(true);
        } else if (candidate.is_docx && candidate.cv_url) {
            setStatusMessage('Το βιογραφικό είναι σε μορφή DOCX. Η μετατροπή σε PDF ενδέχεται να είναι σε εξέλιξη.');
            setShowDownloadOriginalButton(true);
            console.log("CVViewer: DOCX detected, no PDF URL. Original:", candidate.cv_url);
        } else if (candidate.cv_url) { // Other non-previewable types
            setStatusMessage(`Η προεπισκόπηση δεν είναι διαθέσιμη για αυτόν τον τύπο αρχείου (${candidate.cv_original_filename || 'άγνωστο αρχείο'}).`);
            setShowDownloadOriginalButton(true);
            console.log("CVViewer: Non-previewable file type. Original:", candidate.cv_url);
        } else {
            setStatusMessage('Δεν βρέθηκε αρχείο βιογραφικού για προβολή.');
        }
    } else if (candidate) {
        setStatusMessage('Δεν έχει επισυναφθεί βιογραφικό για αυτόν τον υποψήφιο.');
    } else {
        setStatusMessage('Δεν έχουν φορτωθεί δεδομένα υποψηφίου.');
    }
  }, [candidate]);

  function onDocumentLoadSuccess({ numPages: nextNumPages }) {
    setNumPages(nextNumPages);
    setIsLoadingDocument(false);
    setLoadError('');
    console.log(`CV Document loaded successfully from ${currentFileUrlToLoad}. Pages: ${nextNumPages}`);
  }

  function onDocumentLoadError(error) {
    console.error(`Failed to load PDF document from ${currentFileUrlToLoad}:`, error);
    const errorMessage = `Σφάλμα φόρτωσης PDF: ${error.message || 'Ελέγξτε τη διεύθυνση URL ή το δίκτυο.'}`;
    setLoadError(errorMessage);
    setIsLoadingDocument(false);
    setShowDownloadOriginalButton(true); // Offer download if PDF preview fails
    if (onError) {
        onError(errorMessage);
    }
  }

  function onPageLoadSuccess() {
    setIsPageLoading(false);
    console.log(`Page ${pageNumber} loaded.`);
  }

  function onPageLoadError(error) { // Added this based on your original code
    console.error(`Failed to load page ${pageNumber}:`, error);
    setLoadError(`Failed to load page ${pageNumber}: ${error.message}`);
    setIsPageLoading(false);
  }

  function changePage(offset) {
    const newPageNumber = pageNumber + offset;
    if (newPageNumber >= 1 && newPageNumber <= numPages) {
        setPageNumber(newPageNumber);
        setIsPageLoading(true);
    }
  }

  function previousPage() { changePage(-1); }
  function nextPage() { changePage(1); }

  const options = useMemo(() => ({
    cMapUrl: `https://unpkg.com/pdfjs-dist@${pdfjs.version}/cmaps/`,
    cMapPacked: true,
    standardFontDataUrl: `https://unpkg.com/pdfjs-dist@${pdfjs.version}/standard_fonts/`,
  }), []);

  if (!candidate) {
    return <div className="cv-viewer-message"><p>Φόρτωση δεδομένων...</p></div>;
  }

  return (
    <div className="cv-viewer-container">
      {isLoadingDocument && currentFileUrlToLoad && <div className="viewer-status loading-placeholder">Φόρτωση εγγράφου PDF...</div>}
      {loadError && !isLoadingDocument && <div className="viewer-status error">{loadError}</div>}

      {/* Μήνυμα για DOCX ή άλλους τύπους */}
      {!currentFileUrlToLoad && statusMessage && (
        <div className="cv-viewer-message">
          <p>{statusMessage}</p>
        </div>
      )}

      {currentFileUrlToLoad && !loadError && (
         <>
            <Document
                file={currentFileUrlToLoad}
                onLoadSuccess={onDocumentLoadSuccess}
                onLoadError={onDocumentLoadError}
                options={options}
                className="pdf-document"
                key={currentFileUrlToLoad} // Re-mount if URL changes
                loading={<div className="viewer-status loading-placeholder">Αρχικοποίηση εγγράφου...</div>}
            >
                {numPages && ( // Render Page only if numPages is known
                    <Page
                        pageNumber={pageNumber}
                        width={700} 
                        renderAnnotationLayer={true}
                        renderTextLayer={true}
                        onLoadSuccess={onPageLoadSuccess}
                        onRenderError={onPageLoadError}
                        loading={<div className="viewer-status loading-placeholder">Φόρτωση σελίδας {pageNumber}...</div>}
                    />
                )}
            </Document>

            {numPages && numPages > 1 && (
                <div className="pagination-controls">
                    <button type="button" disabled={pageNumber <= 1 || isPageLoading} onClick={previousPage} className="button-action button-secondary">
                        Προηγούμενη
                    </button>
                    <span>
                        Σελίδα {pageNumber} από {numPages}
                    </span>
                    <button type="button" disabled={pageNumber >= numPages || isPageLoading} onClick={nextPage} className="button-action button-secondary">
                        Επόμενη
                    </button>
                </div>
            )}
         </>
      )}
      
      {/* Footer Actions: Download Original & Refresh for PDF */}
      <div className="cv-actions-footer" style={{ marginTop: '15px', paddingTop: '10px', borderTop: '1px solid var(--border-color-light)'}}>
        {candidate.is_docx && !candidate.cv_pdf_url && onCvRefreshNeeded && (
            <button 
                onClick={onCvRefreshNeeded} 
                className="button-action button-secondary"
                style={{marginRight: '10px'}}
                disabled={isLoadingDocument} // Disable if PDF is currently trying to load
            >
                Ανανέωση για PDF
            </button>
        )}
        {showDownloadOriginalButton && candidate.cv_url && (
            <a
                href={candidate.cv_url}
                target="_blank"
                rel="noopener noreferrer"
                download={candidate.cv_original_filename || 'cv_file'}
                className="button-action button-primary"
            >
                Λήψη Πρωτότυπου ({candidate.cv_original_filename || 'Αρχείο'})
            </a>
        )}
        {/* Εμφάνιση link για το πρωτότυπο DOCX αν προβάλλεται το PDF */}
        {currentFileUrlToLoad && currentFileUrlToLoad === candidate.cv_pdf_url && candidate.is_docx && candidate.cv_url && (
             <p style={{fontSize:'0.8em', marginTop:'10px', color: 'var(--text-muted)'}}>
                Προβάλλεται η έκδοση PDF. 
                <a href={candidate.cv_url} download={candidate.cv_original_filename || 'cv_file'} style={{textDecoration:'underline', marginLeft:'5px'}}>
                    Λήψη πρωτότυπου DOCX
                </a>.
            </p>
        )}
      </div>
    </div>
  );
}

export default CVViewer;