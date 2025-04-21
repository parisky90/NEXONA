// frontend/src/components/HistoryLog.jsx
import React, { useState } from 'react';
import './HistoryLog.css'; // Import CSS

// Accept buttonClassName prop
function HistoryLog({ history, buttonClassName = 'button-cancel-schedule' }) { // Default to light blue
    const [currentPage, setCurrentPage] = useState(1);
    const itemsPerPage = 5; // Show 5 history items per page

    // Ensure history is an array before processing
    const historyArray = Array.isArray(history) ? history : [];

    if (historyArray.length === 0) {
        return <p className="no-history">No history recorded yet.</p>;
    }

    // Sort history chronologically (most recent first)
    const sortedHistory = [...historyArray].sort((a, b) => {
        // Handle potentially invalid dates during sort
        const dateA = a?.timestamp ? new Date(a.timestamp) : new Date(0);
        const dateB = b?.timestamp ? new Date(b.timestamp) : new Date(0);
        if (isNaN(dateA.getTime())) return 1; // Put invalid dates last
        if (isNaN(dateB.getTime())) return -1;
        return dateB - dateA; // Sort descending
    });

    // Pagination logic
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
        try {
            return new Date(isoString).toLocaleString(); // Format for user's locale
        } catch {
            return 'Invalid Date';
        }
    };

    return (
        <div className="history-log"> {/* Ensure background is handled by parent card */}
            <ul className="history-list">
                {currentItems.map((entry, index) => (
                    <li key={`${entry?.timestamp || index}-${entry?.status || index}`} className="history-item">
                         {/* Add safety checks for entry properties */}
                        <span className="history-status">{entry?.status || 'Unknown Action'}</span>
                        <span className="history-timestamp">{formatDate(entry?.timestamp)}</span>
                    </li>
                ))}
            </ul>

            {/* Pagination Controls */}
            {totalPages > 1 && (
                <div className="pagination-controls">
                    <button
                        onClick={() => paginate(currentPage - 1)}
                        disabled={currentPage === 1}
                        // Apply passed class name and base action class
                        className={`button-action ${buttonClassName}`}
                    >
                        Previous
                    </button>
                    <span className="page-info">
                        Page {currentPage} of {totalPages}
                    </span>
                    <button
                        onClick={() => paginate(currentPage + 1)}
                        disabled={currentPage === totalPages}
                        // Apply passed class name and base action class
                        className={`button-action ${buttonClassName}`}
                    >
                        Next
                    </button>
                </div>
            )}
        </div>
    );
}

export default HistoryLog;