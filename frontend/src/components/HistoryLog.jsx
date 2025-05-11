// frontend/src/components/HistoryLog.jsx
import React, { useState } from 'react';
import './HistoryLog.css'; // Import CSS

// Accept buttonClassName prop
function HistoryLog({ history, buttonClassName = 'button-cancel-schedule' }) { // Default to light blue
    const [currentPage, setCurrentPage] = useState(1);
    const itemsPerPage = 5;

    const historyArray = Array.isArray(history) ? history : [];

    if (historyArray.length === 0) {
        return <p className="no-history">No history recorded yet.</p>;
    }

    const sortedHistory = [...historyArray].sort((a, b) => {
        const dateA = a?.timestamp ? new Date(a.timestamp) : new Date(0);
        const dateB = b?.timestamp ? new Date(b.timestamp) : new Date(0);
        if (isNaN(dateA.getTime())) return 1;
        if (isNaN(dateB.getTime())) return -1;
        return dateB - dateA;
    });

    const indexOfLastItem = currentPage * itemsPerPage;
    const indexOfFirstItem = indexOfLastItem - itemsPerPage;
    const currentItems = sortedHistory.slice(indexOfFirstItem, indexOfLastItem);
    const totalPages = Math.ceil(sortedHistory.length / itemsPerPage);

    const paginate = (pageNumber) => {
        if (pageNumber >= 1 && pageNumber <= totalPages) {
             setCurrentPage(pageNumber);
        }
    };

    const formatDate = (isoString) => {
        if (!isoString) return 'N/A';
        try { return new Date(isoString).toLocaleString(); } catch { return 'Invalid Date'; }
    };

    // Function to get CSS class based on status text
    const getStatusClass = (status) => {
        if (!status) return '';
        // Normalize status text (lowercase, replace spaces) for class name
        const normalizedStatus = status.toLowerCase().replace(/\s+/g, '-');
        return `status-${normalizedStatus}`; // e.g., status-needs-review, status-offer-made
    };

    return (
        <div className="history-log">
            <ul className="history-list">
                {currentItems.map((entry, index) => (
                    <li key={`${entry?.timestamp || index}-${entry?.status || index}`} className="history-item">
                        {/* Apply dynamic class based on status */}
                        <span className={`history-status ${getStatusClass(entry?.status)}`}>
                            {entry?.status || 'Unknown Action'}
                        </span>
                        <span className="history-timestamp">{formatDate(entry?.timestamp)}</span>
                    </li>
                ))}
            </ul>

            {totalPages > 1 && (
                <div className="pagination-controls">
                    <button
                        onClick={() => paginate(currentPage - 1)}
                        disabled={currentPage === 1}
                        className={`button-action ${buttonClassName}`}
                    > Previous </button>
                    <span className="page-info"> Page {currentPage} of {totalPages} </span>
                    <button
                        onClick={() => paginate(currentPage + 1)}
                        disabled={currentPage === totalPages}
                        className={`button-action ${buttonClassName}`}
                    > Next </button>
                </div>
            )}
        </div>
    );
}

export default HistoryLog;