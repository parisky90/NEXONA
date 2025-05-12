// frontend/src/pages/DashboardPage.jsx
import React, { useState, useEffect, useCallback } from 'react';
import DashboardSummary from '../components/DashboardSummary';
import CandidateList from '../components/CandidateList';
import SearchBar from '../components/SearchBar';
import UploadComponent from '../components/UploadComponent';
import apiClient from '../api';
// import './DashboardPage.css'; // Optional page-specific styles

function DashboardPage() {
  const [summaryData, setSummaryData] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [isLoadingSummary, setIsLoadingSummary] = useState(true);
  const [isLoadingList, setIsLoadingList] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');

  // Fetch Summary Data
  const fetchSummary = useCallback(async () => {
    setIsLoadingSummary(true);
    // Don't clear main error here
    try {
      const res = await apiClient.get('/dashboard/summary');
      setSummaryData(res.data);
    } catch (err) {
      console.error("Error fetching summary:", err);
      if (!error) setError(err.response?.data?.error || 'Failed to load summary data.');
      setSummaryData(null);
    } finally {
      setIsLoadingSummary(false);
    }
  }, [error]); // Depend on error state? Maybe not.

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
      // Prioritize showing list error
      setError(err.response?.data?.error || 'Failed to load candidates.');
      setCandidates([]); // Clear data on error
    } finally {
      setIsLoadingList(false);
    }
  }, []); // No dependency on search term here, passed as arg

  // Initial data fetch
  useEffect(() => {
    fetchSummary();
    fetchCandidates(); // Fetch initial NeedsReview list
  }, [fetchSummary, fetchCandidates]); // Depend on the memoized functions

  // Search Handlers
  const handleSearchChange = (event) => {
    setSearchTerm(event.target.value);
     // Decide if real-time search is wanted vs. button click
     // If real-time: fetchCandidates(event.target.value);
  };

  const handleSearchSubmit = () => {
    // Trigger search only when button is clicked or Enter is pressed
    fetchCandidates(searchTerm);
  };

  // Upload Success Handler
  const handleUploadSuccess = () => {
    console.log("Upload success detected in Dashboard, refreshing data...");
    // Add slight delay to allow backend processing maybe?
    setTimeout(() => {
        fetchSummary();
        fetchCandidates(searchTerm); // Re-fetch with current search term
    }, 500); // 500ms delay - adjust if needed
  }

  return (
    <div className="dashboard-page">
      {/* Render Summary */}
      {isLoadingSummary ? <p>Loading summary...</p> : null}
      {summaryData && <DashboardSummary summary={summaryData} />}
      {error && !summaryData && !isLoadingList && <p className="error-message">Error loading summary: {error}</p>}

      {/* Render Upload Component */}
      <UploadComponent onUploadSuccess={handleUploadSuccess} />

      {/* Render Search Bar */}
      <SearchBar
          searchTerm={searchTerm}
          onSearchChange={handleSearchChange}
          onSearchSubmit={handleSearchSubmit}
          placeholder="Search Needs Review by Name, Position, or Phone..." // Updated placeholder
          inputClassName="input-light-gray"   // Apply specific input style
          buttonClassName="button-cancel-schedule" // <<< USE LIGHT BLUE BUTTON STYLE
      />

      {/* Render Candidate List */}
      {isLoadingList && <p>Loading candidates...</p>}
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