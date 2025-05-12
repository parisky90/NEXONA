// frontend/src/components/HistoryLog.jsx
import React, { useState } from 'react';
import './HistoryLog.css'; // Import CSS

function HistoryLog({ history, buttonClassName = 'button-cancel-schedule' }) {
    const [currentPage, setCurrentPage] = useState(1);
    const itemsPerPage = 5; // Μπορείς να το κάνεις prop αν θέλεις

    const historyArray = Array.isArray(history) ? history : [];

    if (historyArray.length === 0) {
        return <p className="no-history">No history recorded yet.</p>;
    }

    // Sort history by timestamp descending (most recent first)
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
        try {
            return new Date(isoString).toLocaleString([], {
                year: 'numeric', month: 'short', day: 'numeric',
                hour: '2-digit', minute: '2-digit', hour12: false
            });
        } catch { return 'Invalid Date'; }
    };

    const getStatusClass = (status) => {
        if (!status) return 'status-unknown';
        return `status-${status.toLowerCase().replace(/\s+/g, '-')}`;
    };

    return (
        <div className="history-log">
            <ul className="history-list">
                {currentItems.map((entry, index) => (
                    <li key={`${entry?.timestamp || 'ts'}-${index}-${entry?.status || 'status'}`} className="history-item">
                        <div className="history-item-main-info">
                            <span className={`history-status-badge ${getStatusClass(entry?.status)}`}>
                                {entry?.status || 'Unknown Action'}
                            </span>
                            <span className="history-details">
                                {entry?.previous_status ? (
                                    <>
                                        Moved from <span className={`history-status-badge ${getStatusClass(entry.previous_status)}`}>{entry.previous_status}</span> to current.
                                    </>
                                ) : (
                                    "Initial state or status set." /* Μήνυμα αν δεν υπάρχει previous_status */
                                )}
                                {/* --- ΑΦΑΙΡΕΣΗ USER ID ---
                                {entry?.updated_by && (
                                    <span className="history-user">
                                        (by User ID: {entry.updated_by})
                                    </span>
                                )}
                                --- ΤΕΛΟΣ ΑΦΑΙΡΕΣΗΣ --- */}
                            </span>
                            <span className="history-timestamp">{formatDate(entry?.timestamp)}</span>
                        </div>
                        {entry?.notes_at_this_stage && (
                            <div className="history-item-notes">
                                <pre>{entry.notes_at_this_stage}</pre>
                            </div>
                        )}
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