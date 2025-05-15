// frontend/src/pages/CandidateListPage.jsx
import React, { useState, useEffect, useCallback } from 'react';
import DashboardSummary from '../components/DashboardSummary';
import CandidateList from '../components/CandidateList';
import SearchBar from '../components/SearchBar';
import apiClient from '../api';
import { useAuth } from '../App';
import { useParams } from 'react-router-dom'; // Για να παίρνουμε το status από το URL

const capitalize = (s) => s && s[0].toUpperCase() + s.slice(1);

const getListTitle = (statusRouteParam) => {
    // Μετατροπή του status από το URL (π.χ. needs-review) σε αυτό που περιμένει το API (NeedsReview)
    // και για τον τίτλο.
    if (!statusRouteParam) return 'All Candidates';
    const statusMappings = {
        'needs-review': 'NeedsReview',
        'accepted': 'Accepted',
        'interested': 'Interested',
        'interview': 'Interview',
        'evaluation': 'Evaluation',
        'offermade': 'OfferMade', // Το API περιμένει OfferMade
        'hired': 'Hired',
        'rejected': 'Rejected',
        'declined': 'Declined',
        'processing': 'Processing',
        'parsing-failed': 'ParsingFailed' // Νέο status
    };
    const apiStatus = statusMappings[statusRouteParam.toLowerCase()] || capitalize(statusRouteParam);

    switch (apiStatus) {
        case 'NeedsReview': return 'Candidates Needing Review';
        case 'Accepted': return 'Accepted Candidates';
        case 'Interested': return 'Interested Candidates';
        case 'Interview': return 'Candidates for Interview';
        case 'Evaluation': return 'Candidates Under Evaluation';
        case 'OfferMade': return 'Candidates With Offer Made';
        case 'Hired': return 'Hired Candidates';
        case 'Rejected': return 'Rejected Candidates';
        case 'Declined': return 'Declined Candidates (by Candidate)';
        case 'Processing': return 'Processing CVs';
        case 'ParsingFailed': return 'CVs with Parsing Failed';
        default: return `${capitalize(apiStatus)} Candidates`;
    }
};


function CandidateListPage() {
  const { status: statusFromUrl } = useParams(); // Πάρε το status από το URL
  const { currentUser } = useAuth();
  const [summaryData, setSummaryData] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [isLoadingSummary, setIsLoadingSummary] = useState(true);
  const [isLoadingList, setIsLoadingList] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');

  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [totalCandidates, setTotalCandidates] = useState(0);
  const ITEMS_PER_PAGE_LIST = 15;

  // Μετατροπή του status από το URL σε αυτό που καταλαβαίνει το API
  const statusMappingsForApi = {
      'needs-review': 'NeedsReview', 'accepted': 'Accepted', 'interested': 'Interested',
      'interview': 'Interview', 'evaluation': 'Evaluation', 'offermade': 'OfferMade',
      'hired': 'Hired', 'rejected': 'Rejected', 'declined': 'Declined',
      'processing': 'Processing', 'parsing-failed': 'ParsingFailed'
  };
  const apiStatus = statusMappingsForApi[statusFromUrl?.toLowerCase()] || capitalize(statusFromUrl || 'All');
  const listTitle = getListTitle(statusFromUrl); // Για τον τίτλο της σελίδας

  const companyIdForRequests = currentUser?.role === 'superadmin' ? null : currentUser?.company_id;

  const fetchSummary = useCallback(async () => {
    setIsLoadingSummary(true);
    try {
      const params = companyIdForRequests ? { company_id: companyIdForRequests } : {};
      const res = await apiClient.get('/dashboard/summary', { params });
      setSummaryData(res.data);
    } catch (err) {
      console.error(`Error fetching summary for ${apiStatus} list:`, err);
      if (!error) setError(err.response?.data?.error || 'Failed to load summary data.');
      setSummaryData(null);
    } finally {
      setIsLoadingSummary(false);
    }
  }, [companyIdForRequests, error, apiStatus]);

  const fetchCandidates = useCallback(async (page = 1, query = searchTerm) => {
    if (!apiStatus || apiStatus === 'All' && !query) { // Αν είναι 'All' και δεν υπάρχει query, μην κάνεις fetch (ή κάνε για όλους)
        // setError("Status prop not provided or is 'All' without search.");
        // setIsLoadingList(false);
        // setCandidates([]);
        // return;
        // Για την ώρα, αν είναι 'All' και δεν υπάρχει query, δεν κάνουμε τίποτα.
        // Θα μπορούσες να έχεις μια default λίστα ή να απαιτείς search.
        if (apiStatus === 'All' && !query) {
             setCandidates([]); setIsLoadingList(false); setTotalPages(0); setTotalCandidates(0);
             return;
        }
    }
    setIsLoadingList(true);
    setError(null);
    try {
      const params = {
        page,
        per_page: ITEMS_PER_PAGE_LIST,
      };
      if (companyIdForRequests) {
        params.company_id = companyIdForRequests;
      }

      let response;
      if (query) {
        params.q = encodeURIComponent(query);
        if (apiStatus !== 'All') { // Πρόσθεσε το status στο search μόνο αν δεν είναι 'All'
            params.status = apiStatus;
        }
        console.log("Searching with params:", params);
        response = await apiClient.get('/search', { params });
      } else {
        console.log(`Fetching candidates for status: ${apiStatus} with params:`, params);
        response = await apiClient.get(`/candidates/${apiStatus}`, { params });
      }
      
      setCandidates(Array.isArray(response.data.candidates) ? response.data.candidates : []);
      setTotalPages(response.data.total_pages || 0);
      setTotalCandidates(response.data.total_results || 0);
      setCurrentPage(response.data.current_page || 1);

    } catch (err) {
      console.error(`Error fetching ${apiStatus} candidates:`, err);
      setError(err.response?.data?.error || `Failed to load ${apiStatus} candidates.`);
      setCandidates([]);
      setTotalPages(0);
      setTotalCandidates(0);
    } finally {
      setIsLoadingList(false);
    }
  }, [apiStatus, companyIdForRequests, searchTerm]); // searchTerm προστέθηκε

  useEffect(() => {
    setError(null);
    fetchSummary();
    // Αν το status είναι 'All' και δεν υπάρχει searchTerm, μην κάνεις fetch αρχικά.
    if (apiStatus !== 'All' || searchTerm) {
        fetchCandidates(1, searchTerm);
    } else {
        setCandidates([]); // Καθάρισμα υποψηφίων αν είμαστε στο "All" χωρίς search term
        setIsLoadingList(false);
        setTotalPages(0);
        setTotalCandidates(0);
    }
  }, [apiStatus, fetchSummary, fetchCandidates, searchTerm]); // searchTerm προστέθηκε

  const handleSearchChange = (event) => setSearchTerm(event.target.value);
  
  const handleSearchSubmit = () => {
    setCurrentPage(1);
    fetchCandidates(1, searchTerm);
  };

  const handlePageChange = (newPage) => {
    fetchCandidates(newPage, searchTerm);
  };
  
  const handleCandidateDeletedOnListPage = (deletedCandidateId) => {
    setCandidates(prevCandidates => prevCandidates.filter(c => c.candidate_id !== deletedCandidateId));
    fetchSummary(); // Ενημέρωση και του summary
  };

  return (
    <div className="candidate-list-page main-content-area"> {/* Πρόσθεσα main-content-area */}
       <h2 style={{textAlign: 'center', marginBottom: '1rem'}}>{listTitle}</h2>
       {isLoadingSummary ? <p className="loading-placeholder">Loading summary...</p> : null}
       {summaryData && <DashboardSummary summary={summaryData} />}
       {error && !summaryData && !isLoadingList && <p className="error-message" style={{textAlign: 'center'}}>Error loading summary: {error}</p>}

      <SearchBar
          searchTerm={searchTerm}
          onSearchChange={handleSearchChange}
          onSearchSubmit={handleSearchSubmit}
          placeholder={`Search in ${listTitle}...`}
          inputClassName="input-light-gray"
          buttonClassName="button-navy-blue"
       />

      {isLoadingList && <p className="loading-placeholder" style={{marginTop: '1rem'}}>Loading candidates...</p>}
      {error && !isLoadingList && <p className="error-message" style={{textAlign: 'center', marginTop: '1rem'}}>Error loading candidates: {error}</p>}
      
      {!isLoadingList && !error && candidates.length === 0 && searchTerm && (
            <p style={{ textAlign: 'center', marginTop: '1rem' }}>No candidates found matching '{searchTerm}' in {listTitle}.</p>
       )}
      {!isLoadingList && !error && candidates.length === 0 && !searchTerm && apiStatus !== 'All' && (
            <p style={{ textAlign: 'center', marginTop: '1rem' }}>No candidates currently in {listTitle}.</p>
       )}
      {!isLoadingList && !error && candidates.length === 0 && !searchTerm && apiStatus === 'All' && (
            <p style={{ textAlign: 'center', marginTop: '1rem' }}>Please enter a search term to find candidates.</p>
       )}


      {!isLoadingList && !error && candidates.length > 0 && (
         <CandidateList 
            candidates={candidates} 
            listTitle={listTitle} // Δεν χρειάζεται πλέον, ο τίτλος είναι πάνω
            onCandidateDeleted={handleCandidateDeletedOnListPage}
        />
      )}
      
      {!isLoadingList && totalPages > 1 && (
        <div className="pagination-controls" style={{ marginTop: '1rem', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '0.5rem' }}>
          <button onClick={() => handlePageChange(currentPage - 1)} disabled={currentPage === 1 || isLoadingList} className="button-action button-cancel-schedule">Previous</button>
          <span>Page {currentPage} of {totalPages} (Total: {totalCandidates} candidates)</span>
          <button onClick={() => handlePageChange(currentPage + 1)} disabled={currentPage === totalPages || isLoadingList} className="button-action button-cancel-schedule">Next</button>
        </div>
      )}
    </div>
  );
}

export default CandidateListPage;