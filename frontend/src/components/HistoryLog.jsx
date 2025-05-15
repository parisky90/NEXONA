// frontend/src/components/HistoryLog.jsx
import React, { useState } from 'react';
import './HistoryLog.css';

function HistoryLog({ history, buttonClassName = 'button-cancel-schedule' }) {
    const [currentPage, setCurrentPage] = useState(1);
    const itemsPerPage = 5;

    const historyArray = Array.isArray(history) ? history : [];

    if (historyArray.length === 0) {
        return <p className="no-history">No history recorded yet.</p>;
    }

    // Sort by timestamp descending
    const sortedHistory = [...historyArray].sort((a, b) => {
        const dateA = a?.timestamp ? new Date(a.timestamp) : new Date(0);
        const dateB = b?.timestamp ? new Date(b.timestamp) : new Date(0);
        if (isNaN(dateA.getTime())) return 1; // Treat invalid dates as "later" or handle as error
        if (isNaN(dateB.getTime())) return -1;
        return dateB - dateA; // Sorts most recent first
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
        try {
            return new Date(isoString).toLocaleString([], { // Uses browser's default locale
                year: 'numeric', month: 'short', day: 'numeric',
                hour: '2-digit', minute: '2-digit', hour12: false // Use 24-hour format
            });
        } catch { return 'Invalid Date'; }
    };

    return (
        <div className="history-log">
            <ul className="history-list">
                {currentItems.map((entry, index) => (
                    <li key={`${entry?.timestamp || 'ts'}-${index}-${entry?.event_type || 'event'}`} className="history-item">
                        <div className="history-item-main-info">
                            <span className="history-details">
                                {entry?.description || 'No description for this event.'}
                                {entry?.actor_username && entry.actor_username !== "System" && ( // Don't show "(by: System)"
                                    <span className="history-user"> (by: {entry.actor_username})</span>
                                )}
                                 {entry?.actor_username && entry.actor_username === "System" && (
                                    <span className="history-user"> (System Event)</span>
                                )}
                            </span>
                            <span className="history-timestamp">{formatDate(entry?.timestamp)}</span>
                        </div>
                        {/* ΑΦΑΙΡΕΣΗ ΤΗΣ ΕΜΦΑΝΙΣΗΣ ΤΩΝ entry.details 
                        {entry?.details && Object.keys(entry.details).length > 0 && (
                            <div className="history-item-notes" style={{fontSize: '0.8em', background: '#f9f9f9', marginTop: '5px', padding: '5px'}}>
                                <pre>Details: {JSON.stringify(entry.details, null, 2)}</pre>
                            </div>
                        )}
                        */}
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