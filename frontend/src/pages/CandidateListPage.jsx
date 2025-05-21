// frontend/src/pages/CandidateListPage.jsx
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import CandidateList from '../components/CandidateList';
import SearchBar from '../components/SearchBar';
import apiClient from '../api';
import { useAuth } from '../App'; // Διορθωμένο import
import { useParams } from 'react-router-dom';

const capitalize = (s) => s && s[0].toUpperCase() + s.slice(1);

const getListTitle = (statusRouteParam) => {
    if (!statusRouteParam) return 'All Candidates';
    const statusMappings = {
        'needs-review': 'NeedsReview',
        'accepted': 'Accepted',
        'interested': 'Interested',
        'interviewproposed': 'Interview Proposed',
        'interviewscheduled': 'Interview Scheduled',
        'interview': 'Interview Scheduled',
        'evaluation': 'Evaluation',
        'offermade': 'OfferMade',
        'hired': 'Hired',
        'rejected': 'Rejected',
        'declined': 'Declined',
        'processing': 'Processing',
        'parsing-failed': 'ParsingFailed'
    };
    const cleanStatus = statusMappings[statusRouteParam.toLowerCase()] || capitalize(statusRouteParam);

    switch (cleanStatus) {
        case 'NeedsReview': return 'Candidates Needing Review';
        case 'Accepted': return 'Accepted Candidates';
        case 'Interested': return 'Interested Candidates';
        case 'Interview Proposed': return 'Candidates with Interview Proposed';
        case 'Interview Scheduled': return 'Candidates with Interview Scheduled';
        case 'Evaluation': return 'Candidates Under Evaluation';
        case 'OfferMade': return 'Candidates With Offer Made';
        case 'Hired': return 'Hired Candidates';
        case 'Rejected': return 'Rejected Candidates';
        case 'Declined': return 'Declined Candidates';
        case 'Processing': return 'Processing CVs';
        case 'ParsingFailed': return 'CVs with Parsing Failed';
        default: return `${capitalize(cleanStatus)} Candidates`;
    }
};


function CandidateListPage() {
  const { status: statusFromUrl } = useParams();
  const { currentUser } = useAuth();
  const [candidates, setCandidates] = useState([]);
  const [isLoadingList, setIsLoadingList] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');

  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [totalCandidates, setTotalCandidates] = useState(0);
  const ITEMS_PER_PAGE_LIST = 15;

  const statusMappingsForApi = useMemo(() => ({
      'needs-review': 'NeedsReview',
      'accepted': 'Accepted',
      'interested': 'Interested',
      'interviewproposed': 'Interview Proposed',
      'interviewscheduled': 'Interview Scheduled',
      'interview': 'Interview Scheduled',
      'evaluation': 'Evaluation',
      'offermade': 'OfferMade',
      'hired': 'Hired',
      'rejected': 'Rejected',
      'declined': 'Declined',
      'processing': 'Processing',
      'parsing-failed': 'ParsingFailed'
  }), []);

  const apiStatus = useMemo(() => {
    const calculatedApiStatus = statusMappingsForApi[statusFromUrl?.toLowerCase()] || capitalize(statusFromUrl || 'All');
    return calculatedApiStatus;
  }, [statusFromUrl, statusMappingsForApi]);

  const listTitle = useMemo(() => getListTitle(statusFromUrl), [statusFromUrl]);

  const companyIdForRequests = useMemo(() => {
    if (!currentUser) return undefined;
    return currentUser.role === 'superadmin' ? null : currentUser.company_id;
  }, [currentUser]);

  const fetchCandidates = useCallback(async (page = 1, currentSearchTerm = searchTerm) => {
    if (currentUser === null) {
        setIsLoadingList(false);
        return;
    }
    if (!statusFromUrl && !currentSearchTerm) {
        setCandidates([]);
        setIsLoadingList(false);
        setTotalPages(0);
        setTotalCandidates(0);
        setError(null);
        return;
    }

    setIsLoadingList(true);
    setError(null);
    try {
      const params = {
        page,
        per_page: ITEMS_PER_PAGE_LIST,
      };
      if (companyIdForRequests !== null && companyIdForRequests !== undefined) {
        params.company_id = companyIdForRequests;
      }
      if (currentSearchTerm) {
        params.search = encodeURIComponent(currentSearchTerm);
      }
      // Ο έλεγχos apiStatus.toLowerCase() !== 'all' είναι σωστός.
      // Η συνθήκη `statusFromUrl` ελέγχει αν βρισκόμαστε σε συγκεκριμένη λίστα (π.χ. /candidates/hired)
      // Αν ναι, τότε το apiStatus θα έχει τιμή. Αν είμαστε στο /candidates (χωρίς status), τότε το statusFromUrl είναι undefined
      // και το apiStatus θα γίνει 'All'. Σε αυτή την περίπτωση, δεν θέλουμε να στείλουμε `status=All` στο backend.
      if (statusFromUrl && apiStatus && apiStatus.toLowerCase() !== 'all') {
        params.status = apiStatus;
      }

      const response = await apiClient.get(`/candidates`, { params });
      
      // Τα δεδομένα των branches έρχονται μέσα στο candidate object ως candidate.branches (πίνακας αντικειμένων)
      // Τα δεδομένα των positions έρχονται μέσα στο candidate object ως candidate.positions (πίνακας αντικειμένων)
      setCandidates(Array.isArray(response.data.candidates) ? response.data.candidates : []);
      setTotalPages(response.data.total_pages || 0);
      setTotalCandidates(response.data.total_results || 0);
      setCurrentPage(response.data.current_page || 1);

    } catch (err) {
      console.error(`Error fetching ${apiStatus} candidates:`, err.response || err);
      setError(err.response?.data?.error || `Failed to load ${listTitle}.`);
      setCandidates([]);
      setTotalPages(0);
      setTotalCandidates(0);
    } finally {
      setIsLoadingList(false);
    }
  }, [apiStatus, companyIdForRequests, searchTerm, currentUser, listTitle, statusFromUrl, ITEMS_PER_PAGE_LIST]);

  useEffect(() => {
    if (currentUser) {
        setCurrentPage(1);
        fetchCandidates(1, searchTerm);
    } else {
        setIsLoadingList(false);
        setCandidates([]);
        setTotalPages(0);
        setTotalCandidates(0);
    }
  }, [currentUser, apiStatus, searchTerm, fetchCandidates]);


  const handleSearchChange = (event) => setSearchTerm(event.target.value);

  const handleSearchSubmit = (e) => {
    if (e) e.preventDefault();
    setCurrentPage(1);
    fetchCandidates(1, searchTerm);
  };

  const handlePageChange = (newPage) => {
    if (newPage >= 1 && newPage <= totalPages && !isLoadingList) {
        fetchCandidates(newPage, searchTerm);
    }
  };

  const handleCandidateDeletedOnListPage = (deletedCandidateId) => {
    setCandidates(prevCandidates => prevCandidates.filter(c => c.candidate_id !== deletedCandidateId));
    setTotalCandidates(prevTotal => prevTotal > 0 ? prevTotal - 1 : 0);
    if (candidates.length === 1 && currentPage > 1) {
        handlePageChange(currentPage - 1);
    }
  };

  if (!currentUser && !isLoadingList) {
    return <div className="loading-placeholder card-style">Initializing page... (No user)</div>;
  }
  if (isLoadingList && candidates.length === 0) {
      return <div className="loading-placeholder card-style" style={{marginTop: '1rem'}}>Loading candidates...</div>;
  }

  return (
    <div className="candidate-list-page main-content-area">
       <h2 style={{textAlign: 'center', marginBottom: '1rem'}}>{listTitle}</h2>
       {error && <p className="error-message" style={{textAlign: 'center'}}>{error}</p>}

      <SearchBar
          searchTerm={searchTerm}
          onSearchChange={handleSearchChange}
          onSearchSubmit={handleSearchSubmit}
          placeholder={`Search in ${listTitle}...`}
          inputClassName="input-light-gray"
          buttonClassName="button-action button-secondary"
       />

      {isLoadingList && candidates.length === 0 && <p className="loading-placeholder" style={{marginTop: '1rem'}}>Loading candidates...</p>}
      {!isLoadingList && error && <p className="error-message" style={{textAlign: 'center', marginTop: '1rem'}}>{error}</p>}
      {!isLoadingList && !error && candidates.length === 0 && searchTerm && (
            <p style={{ textAlign: 'center', marginTop: '1rem' }}>No candidates found matching '{searchTerm}' in {listTitle}.</p>
       )}
      {!isLoadingList && !error && candidates.length === 0 && !searchTerm && apiStatus !== 'All' && (
            <p style={{ textAlign: 'center', marginTop: '1rem' }}>No candidates currently in {listTitle}.</p>
       )}
      {!isLoadingList && !error && candidates.length === 0 && !searchTerm && apiStatus === 'All' && !statusFromUrl && (
            <p style={{ textAlign: 'center', marginTop: '1rem' }}>Please enter a search term to view all candidates or select a status from the sidebar.</p>
       )}

      {!isLoadingList && !error && candidates.length > 0 && (
         <CandidateList
            candidates={candidates}
            onCandidateDeleted={handleCandidateDeletedOnListPage}
            listTitle="" // Ο τίτλος είναι ήδη στη σελίδα
        />
      )}

      {!isLoadingList && totalPages > 1 && (
        <div className="pagination-controls" style={{ marginTop: '1rem', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '0.5rem' }}>
          <button onClick={() => handlePageChange(currentPage - 1)} disabled={currentPage === 1 || isLoadingList} className="button-action button-secondary">Previous</button>
          <span>Page {currentPage} of {totalPages} (Total: {totalCandidates} candidates)</span>
          <button onClick={() => handlePageChange(currentPage + 1)} disabled={currentPage === totalPages || isLoadingList} className="button-action button-secondary">Next</button>
        </div>
      )}
    </div>
  );
}

export default CandidateListPage;