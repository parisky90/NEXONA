// frontend/src/components/CVViewer.jsx
import React, { useState, useEffect, useMemo } from 'react'; // Import useMemo
import { Document, Page, pdfjs } from 'react-pdf';

// Import default styling for react-pdf layers
// These ensure annotations and text selection look correct
import 'react-pdf/dist/esm/Page/AnnotationLayer.css';
import 'react-pdf/dist/esm/Page/TextLayer.css';

// Import custom styles for the viewer container and controls
import './CVViewer.css';

// --- Configure PDF.js Worker ---
// Sets the source for the PDF rendering worker.
// Using URL constructor with import.meta.url is the recommended way for Vite/modern JS.
// It points to the worker file within the installed pdfjs-dist package.
// If issues arise (especially in production builds), investigate copying the worker
// file using Vite's public directory or build configurations.
try {
    pdfjs.GlobalWorkerOptions.workerSrc = new URL(
      'pdfjs-dist/build/pdf.worker.min.mjs',
      import.meta.url,
    ).toString();
} catch (error) {
    console.error("Failed to set pdfjs workerSrc:", error);
    // Fallback or alternative worker source could be added here if needed
}


// Expects fileUrl (the pre-signed S3 URL) and optional onError handler prop
function CVViewer({ fileUrl, onError }) {
  const [numPages, setNumPages] = useState(null);
  const [pageNumber, setPageNumber] = useState(1); // Start on the first page
  const [isLoading, setIsLoading] = useState(true); // Loading state for the document
  const [isPageLoading, setIsPageLoading] = useState(false); // Loading state for individual pages
  const [loadError, setLoadError] = useState('');

  // Reset component state when the fileUrl prop changes
  useEffect(() => {
    setNumPages(null);
    setPageNumber(1);
    setIsLoading(true); // Set loading true when URL changes
    setLoadError('');
  }, [fileUrl]); // Dependency array includes fileUrl

  // Callback function for when the PDF document loads successfully
  function onDocumentLoadSuccess({ numPages: nextNumPages }) {
    setNumPages(nextNumPages); // Set the total number of pages
    setIsLoading(false); // Document itself is no longer loading
    setLoadError(''); // Clear any previous errors
    console.log(`CV Document loaded successfully. Pages: ${nextNumPages}`);
  }

  // Callback function for when the PDF document fails to load
  function onDocumentLoadError(error) {
    console.error('Failed to load PDF document:', error);
    // Provide a user-friendly error message
    const errorMessage = `Failed to load PDF: ${error.message || 'Check file URL or network.'}`;
    setLoadError(errorMessage);
    setIsLoading(false); // Stop loading attempt
    // Optionally call the onError prop passed from the parent component
    if (onError) {
        onError(errorMessage);
    }
  }

  // Callback function for when a specific page finishes rendering
  function onPageLoadSuccess() {
    setIsPageLoading(false); // Page finished loading/rendering
    console.log(`Page ${pageNumber} loaded.`);
  }

   // Callback function if page loading/rendering fails
   function onPageLoadError(error) {
    console.error(`Failed to load page ${pageNumber}:`, error);
    setLoadError(`Failed to load page ${pageNumber}: ${error.message}`);
    setIsPageLoading(false);
  }

  // Function to change the current page number
  function changePage(offset) {
    const newPageNumber = pageNumber + offset;
    // Check bounds before setting
    if (newPageNumber >= 1 && newPageNumber <= numPages) {
        setPageNumber(newPageNumber);
        setIsPageLoading(true); // Set page loading true when changing page
    }
  }

  // Go to the previous page
  function previousPage() {
    changePage(-1);
  }

  // Go to the next page
  function nextPage() {
    changePage(1);
  }

  // --- Memoize the options object ---
  // This prevents unnecessary re-renders caused by creating a new options object on every render
  const options = useMemo(() => ({
    cMapUrl: `https://unpkg.com/pdfjs-dist@${pdfjs.version}/cmaps/`, // Required for special character rendering
    cMapPacked: true,
    standardFontDataUrl: `https://unpkg.com/pdfjs-dist@${pdfjs.version}/standard_fonts/`, // Provides standard PDF fonts
  }), []); // Empty dependency array ensures this object is created only once per component instance
  // --- End Memoization ---


  return (
    <div className="cv-viewer-container">
      {/* Show loading indicator while document is loading initially */}
      {isLoading && <div className="viewer-status loading-placeholder">Loading PDF document...</div>}

      {/* Show error message if document loading failed */}
      {loadError && !isLoading && <div className="viewer-status error">{loadError}</div>}

      {/* Render the Document component only if we have a fileUrl and no critical loadError */}
      {fileUrl && !loadError && (
         <>
            {/* The Document component handles fetching and parsing the PDF */}
            {/* Use key={fileUrl} to ensure component remounts if URL changes, helps with potential caching/CORS issues */}
            <Document
                file={fileUrl}
                onLoadSuccess={onDocumentLoadSuccess}
                onLoadError={onDocumentLoadError}
                options={options} // Pass the memoized options
                className="pdf-document"
                key={fileUrl}
                loading={<div className="viewer-status loading-placeholder">Initializing document...</div>} // Display while loading
            >
                {/* Render the current page */}
                <Page
                    pageNumber={pageNumber}
                    width={700} // Adjust width as needed, or make responsive
                    renderAnnotationLayer={true} // Enable rendering of links/annotations in PDF
                    renderTextLayer={true} // Enable text selection and searching
                    onLoadSuccess={onPageLoadSuccess} // Handle page load success
                    onRenderError={onPageLoadError} // Handle page rendering errors
                    loading={<div className="viewer-status loading-placeholder">Rendering page {pageNumber}...</div>} // Display while page renders
                />
            </Document>

            {/* Pagination Controls - Show only if multiple pages exist */}
            {numPages && numPages > 1 && (
                <div className="pagination-controls">
                    <button type="button" disabled={pageNumber <= 1 || isPageLoading} onClick={previousPage} className="secondary">
                        Previous
                    </button>
                    <span>
                        Page {pageNumber} of {numPages}
                    </span>
                    <button type="button" disabled={pageNumber >= numPages || isPageLoading} onClick={nextPage} className="secondary">
                        Next
                    </button>
                </div>
            )}
         </>
      )}
    </div>
  );
}

export default CVViewer;