// frontend/src/pages/DashboardPage.jsx
import React, { useState, useEffect, useCallback } from 'react';
import DashboardSummary from '../components/DashboardSummary';
import CandidateList from '../components/CandidateList';
import SearchBar from '../components/SearchBar';
import UploadComponent from '../components/UploadComponent';
import apiClient from '../api';
// import './DashboardPage.css'; // Optional: Add page-specific styles if needed

function DashboardPage() {
  const [summaryData, setSummaryData] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [isLoadingSummary, setIsLoadingSummary] = useState(true);
  const [isLoadingList, setIsLoadingList] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');

  // Fetch Summary Data
  const fetchSummary = useCallback(async () => {
    // No need to reset error here, let list fetch handle main error display
    setIsLoadingSummary(true);
    try {
      const res = await apiClient.get('/dashboard/summary');
      setSummaryData(res.data);
    } catch (err) {
      console.error("Error fetching summary:", err);
      // Set error only if list isn't already showing an error
      if (!error) setError(err.response?.data?.error || 'Failed to load summary data.');
      setSummaryData(null); // Clear on error
    } finally {
      setIsLoadingSummary(false);
    }
  }, [error]); // Re-fetch summary if error state changes (maybe not needed?)

  // Fetch Candidate List (NeedsReview or Search within NeedsReview)
  const fetchCandidates = useCallback(async (query = '') => {
    setIsLoadingList(true);
    setError(null); // Clear previous errors before list fetch
    try {
      const url = query
        ? `/search?q=${encodeURIComponent(query)}&status=NeedsReview`
        : '/candidates/NeedsReview';
      const res = await apiClient.get(url);
      setCandidates(res.data);
    } catch (err) {
      console.error("Error fetching candidates:", err);
      setError(err.response?.data?.error || 'Failed to load candidates.');
      setCandidates([]); // Clear data on error
    } finally {
      setIsLoadingList(false);
    }
  }, []); // Search term is handled via query param, no need in deps

  // Initial data fetch
  useEffect(() => {
    fetchSummary();
    fetchCandidates(); // Fetch initial NeedsReview list
  }, [fetchSummary, fetchCandidates]); // Depend on the memoized functions

  // Search Handlers
  const handleSearchChange = (event) => {
    setSearchTerm(event.target.value);
  };
  const handleSearchSubmit = () => {
    fetchCandidates(searchTerm); // Fetch based on search term
  };

  // Upload Success Handler
  const handleUploadSuccess = () => {
    console.log("Upload success detected in Dashboard, refreshing data...");
    // Refresh both summary and list
    // Add slight delay to allow backend processing maybe?
    setTimeout(() => {
        fetchSummary();
        fetchCandidates(searchTerm); // Re-fetch with current search term
    }, 500); // 500ms delay - adjust if needed
  }

  return (
    <div className="dashboard-page"> {/* Add specific class if needed */}
      {/* Render Summary */}
      {isLoadingSummary ? <p>Loading summary...</p> : null}
      {summaryData && <DashboardSummary summary={summaryData} />}
      {/* Show error only if summary specifically failed and list isn't loading/failed */}
      {error && !summaryData && !isLoadingList && <p className="error-message">Error loading summary: {error}</p>}

      {/* Render Upload Component */}
      <UploadComponent onUploadSuccess={handleUploadSuccess} />

      {/* Render Search Bar for the list below */}
      <SearchBar
          searchTerm={searchTerm}
          onSearchChange={handleSearchChange}
          onSearchSubmit={handleSearchSubmit}
          placeholder="Search Needs Review by Name or Position..."
          inputClassName="input-light-gray"   // Apply specific input style
          buttonClassName="button-navy-blue" // Apply specific button style
      />

      {/* Render Candidate List */}
      {isLoadingList && <p>Loading candidates...</p>}
      {/* Show list-related error preferentially */}
      {error && !isLoadingList && <p className="error-message">Error loading candidates: {error}</p>}
      {!isLoadingList && !error && (
        <CandidateList candidates={candidates} listTitle="Candidates Needing Review" />
      )}
       {!isLoadingList && !error && candidates.length === 0 && searchTerm && (
            <p>No candidates found matching '{searchTerm}' in Needs Review.</p>
       )}
        {!isLoadingList && !error && candidates.length === 0 && !searchTerm && (
            <p>No candidates currently need review.</p>
       )}
    </div>
  );
}

export default DashboardPage;