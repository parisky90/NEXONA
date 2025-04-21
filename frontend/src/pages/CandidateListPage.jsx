// frontend/src/pages/CandidateListPage.jsx
import React, { useState, useEffect, useCallback } from 'react';
import DashboardSummary from '../components/DashboardSummary'; // Import Summary
import CandidateList from '../components/CandidateList';
import SearchBar from '../components/SearchBar';
import apiClient from '../api';
// import './CandidateListPage.css'; // Optional page specific styles

// Helper to capitalize status for title
const capitalize = (s) => s && s[0].toUpperCase() + s.slice(1);

// Map status prop to a more readable title if needed
const getListTitle = (status) => {
    switch (status) {
        case 'NeedsReview': return 'Candidates Needing Review';
        case 'Accepted': return 'Accepted Candidates';
        case 'Interested': return 'Interested Candidates';
        case 'Interview': return 'Interview Candidates';
        case 'Evaluation': return 'Candidates Under Evaluation';
        case 'OfferMade': return 'Candidates With Offer';
        case 'Hired': return 'Hired Candidates';
        case 'Rejected': return 'Rejected Candidates';
        case 'Declined': return 'Declined Candidates';
        default: return `${capitalize(status || 'Unknown')} Candidates`;
    }
};

function CandidateListPage({ status }) { // Accept status as a prop from the Router
  const [summaryData, setSummaryData] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [isLoadingSummary, setIsLoadingSummary] = useState(true);
  const [isLoadingList, setIsLoadingList] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');

  const listTitle = getListTitle(status);

  // Fetch Summary Data (common for all list pages)
   const fetchSummary = useCallback(async () => {
     setIsLoadingSummary(true);
     // No need to reset error here
     try {
       const res = await apiClient.get('/dashboard/summary');
       setSummaryData(res.data);
     } catch (err) {
       console.error(`Error fetching summary for ${status} list:`, err);
        if (!error) setError(err.response?.data?.error || 'Failed to load summary data.');
       setSummaryData(null);
     } finally {
       setIsLoadingSummary(false);
     }
   }, [error, status]); // Depend on status only if summary logic changes per status (currently doesn't)

  // Fetch Candidate List (for specific status or search within it)
  const fetchCandidates = useCallback(async (query = '') => {
    if (!status) {
        setError("Status prop not provided to CandidateListPage");
        setIsLoadingList(false);
        setCandidates([]);
        return;
    }
    setIsLoadingList(true);
    setError(null); // Clear previous list errors
    try {
      const url = query
        ? `/search?q=${encodeURIComponent(query)}&status=${status}` // Search within the specific status
        : `/candidates/${status}`; // Fetch all for this status
      const res = await apiClient.get(url);
      setCandidates(res.data);
    } catch (err) {
      console.error(`Error fetching ${status} candidates:`, err);
      setError(err.response?.data?.error || `Failed to load ${status} candidates.`);
      setCandidates([]);
    } finally {
      setIsLoadingList(false);
    }
  }, [status]); // Re-fetch only if status prop changes

  // Initial data fetch whenever the status prop changes
  useEffect(() => {
    fetchSummary();
    fetchCandidates(); // Fetch initial list for this status
  }, [status, fetchSummary, fetchCandidates]); // Add status to dependency array

  // Search Handlers
  const handleSearchChange = (event) => {
    setSearchTerm(event.target.value);
  };
  const handleSearchSubmit = () => {
    fetchCandidates(searchTerm); // Re-fetch list with search term and status
  };

  return (
    <div className="candidate-list-page"> {/* Optional specific class */}
       {/* Render Summary AT THE TOP */}
       {isLoadingSummary ? <p>Loading summary...</p> : null}
       {summaryData && <DashboardSummary summary={summaryData} />}
       {error && !summaryData && !isLoadingList && <p className="error-message">Error loading summary: {error}</p>}

      {/* Render Search Bar Below Summary */}
      <SearchBar
          searchTerm={searchTerm}
          onSearchChange={handleSearchChange}
          onSearchSubmit={handleSearchSubmit}
          placeholder={`Search ${listTitle} by Name or Position...`}
          inputClassName="input-light-gray"  // Apply specific input style
          buttonClassName="button-navy-blue" // Apply specific button style
       />

      {/* Render Candidate List */}
      {isLoadingList && <p>Loading candidates...</p>}
      {error && !isLoadingList && <p className="error-message">Error loading candidates: {error}</p>}
      {!isLoadingList && !error && (
         <CandidateList candidates={candidates} listTitle={listTitle} />
      )}
      {!isLoadingList && !error && candidates.length === 0 && searchTerm && (
            <p>No candidates found matching '{searchTerm}' in {status}.</p>
       )}
        {!isLoadingList && !error && candidates.length === 0 && !searchTerm && (
            <p>No candidates found in {status}.</p>
       )}
    </div>
  );
}

export default CandidateListPage;