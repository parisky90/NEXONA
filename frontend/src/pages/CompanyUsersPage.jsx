// frontend/src/pages/CandidateListPage.jsx
import React, { useState, useEffect, useCallback } from 'react';
import DashboardSummary from '../components/DashboardSummary';
import CandidateList from '../components/CandidateList';
import SearchBar from '../components/SearchBar';
import apiClient from '../api';
import { useAuth } from '../App';
import { useParams } from 'react-router-dom';

const capitalize = (s) => s && s[0].toUpperCase() + s.slice(1);

const getListTitle = (statusRouteParam) => {
    if (!statusRouteParam) return 'All Candidates';
    const statusMappings = {
        'needs-review': 'NeedsReview', 'accepted': 'Accepted', 'interested': 'Interested',
        'interview': 'Interview', 'evaluation': 'Evaluation', 'offermade': 'OfferMade',
        'hired': 'Hired', 'rejected': 'Rejected', 'declined': 'Declined',
        'processing': 'Processing', 'parsing-failed': 'ParsingFailed'
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
  const { status: statusFromUrl } = useParams();
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

  const statusMappingsForApi = {
      'needs-review': 'NeedsReview', 'accepted': 'Accepted', 'interested': 'Interested',
      'interview': 'Interview', 'evaluation': 'Evaluation', 'offermade': 'OfferMade',
      'hired': 'Hired', 'rejected': 'Rejected', 'declined': 'Declined',
      'processing': 'Processing', 'parsing-failed': 'ParsingFailed'
  };
  const apiStatus = statusMappingsForApi[statusFromUrl?.toLowerCase()] || capitalize(statusFromUrl || 'All');
  const listTitle = getListTitle(statusFromUrl);

  const companyIdForRequests = currentUser?.role === 'superadmin' ? null : currentUser?.company_id;

  const fetchSummary = useCallback(async () => {
    setIsLoadingSummary(true);
    try {
      const params = companyIdForRequests ? { company_id: companyIdForRequests } : {};
      const res = await apiClient.get('/dashboard/summary', { params });
      setSummaryData(res.data);
    } catch (err) {
      if (!error) setError(err.response?.data?.error || 'Failed to load summary.');
      setSummaryData(null);
    } finally {
      setIsLoadingSummary(false);
    }
  }, [companyIdForRequests, error, apiStatus]);

  const fetchCandidates = useCallback(async (page = 1, query = searchTerm) => {
    if (apiStatus === 'All' && !query) {
        setCandidates([]); setIsLoadingList(false); setTotalPages(0); setTotalCandidates(0);
        return;
    }
    setIsLoadingList(true);
    setError(null);
    try {
      const params = { page, per_page: ITEMS_PER_PAGE_LIST };
      if (companyIdForRequests) params.company_id = companyIdForRequests;
      let response;
      if (query) {
        params.q = encodeURIComponent(query);
        if (apiStatus !== 'All') params.status = apiStatus;
        response = await apiClient.get('/search', { params });
      } else {
        response = await apiClient.get(`/candidates/${apiStatus}`, { params });
      }
      setCandidates(Array.isArray(response.data.candidates) ? response.data.candidates : []);
      setTotalPages(response.data.total_pages || 0);
      setTotalCandidates(response.data.total_results || 0);
      setCurrentPage(response.data.current_page || 1);
    } catch (err) {
      setError(err.response?.data?.error || `Failed to load ${apiStatus} candidates.`);
      setCandidates([]); setTotalPages(0); setTotalCandidates(0);
    } finally {
      setIsLoadingList(false);
    }
  }, [apiStatus, companyIdForRequests, searchTerm]);

  useEffect(() => {
    setError(null);
    fetchSummary();
    if (apiStatus !== 'All' || searchTerm) {
        fetchCandidates(1, searchTerm);
    } else {
        setCandidates([]); setIsLoadingList(false); setTotalPages(0); setTotalCandidates(0);
    }
  }, [apiStatus, fetchSummary, fetchCandidates, searchTerm]);

  const handleSearchChange = (e) => setSearchTerm(e.target.value);
  const handleSearchSubmit = () => { setCurrentPage(1); fetchCandidates(1, searchTerm); };
  const handlePageChange = (newPage) => { fetchCandidates(newPage, searchTerm); };
  const handleCandidateDeletedOnListPage = () => { fetchSummary(); fetchCandidates(currentPage, searchTerm); }; // Re-fetch current page

  return (
    // Η κλάση card-style θα εφαρμοστεί από το App.css ή το DashboardPage.css αν είναι global
    // Αν όχι, μπορείς να την προσθέσεις εδώ: className="candidate-list-page card-style"
    <div className="candidate-list-page"> 
       <h2 style={{textAlign: 'center', marginBottom: '1rem', color: 'var(--text-primary)'}}>{listTitle}</h2>
       
       {isLoadingSummary ? <p className="loading-placeholder">Loading summary...</p> : null}
       {summaryData && <DashboardSummary summary={summaryData} />}
       {/* Το error του summary θα εμφανιστεί αν το summaryData είναι null */}
       {!isLoadingSummary && !summaryData && error && 
         <p className="error-message" style={{textAlign: 'center'}}>Error loading summary: {error}</p>
       }

      <SearchBar
          searchTerm={searchTerm}
          onSearchChange={handleSearchChange}
          onSearchSubmit={handleSearchSubmit}
          placeholder={`Search in ${listTitle}...`}
          // ΑΦΑΙΡΕΣΗ inputClassName και buttonClassName ΓΙΑ ΝΑ ΠΑΡΕΙ ΤΑ DEFAULT STYLES ΤΟΥ SearchBar.css
       />

      {isLoadingList && <p className="loading-placeholder" style={{marginTop: '1rem'}}>Loading candidates...</p>}
      {/* Εμφάνιση σφάλματος λίστας μόνο αν δεν φορτώνει ΚΑΙ υπάρχει σφάλμα */}
      {!isLoadingList && error && <p className="error-message" style={{textAlign: 'center', marginTop: '1rem'}}>{error}</p>}
      
      {!isLoadingList && !error && candidates.length === 0 && (
        <p className="empty-list-message">
            {searchTerm ? `No candidates found matching '${searchTerm}' in ${listTitle}.` : 
             apiStatus === 'All' ? 'Please enter a search term to find candidates.' :
             `No candidates currently in ${listTitle}.`}
        </p>
       )}

      {!isLoadingList && !error && candidates.length > 0 && (
         <CandidateList 
            candidates={candidates} 
            onCandidateDeleted={handleCandidateDeletedOnListPage}
        />
      )}
      
      {!isLoadingList && totalPages > 1 && (
        <div className="pagination-controls">
          <button onClick={() => handlePageChange(currentPage - 1)} disabled={currentPage === 1 || isLoadingList} className="button-action button-secondary">Previous</button>
          <span>Page {currentPage} of {totalPages} (Total: {totalCandidates} candidates)</span>
          <button onClick={() => handlePageChange(currentPage + 1)} disabled={currentPage === totalPages || isLoadingList} className="button-action button-secondary">Next</button>
        </div>
      )}
    </div>
  );
}

export default CandidateListPage;