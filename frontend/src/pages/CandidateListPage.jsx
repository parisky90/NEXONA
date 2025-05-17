// frontend/src/pages/CandidateListPage.jsx
import React, { useState, useEffect, useCallback, useMemo } from 'react'; // Προσθήκη useMemo
import DashboardSummary from '../components/DashboardSummary'; // Αυτό ίσως δεν χρειάζεται εδώ
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
        case 'Declined': return 'Declined Candidates';
        case 'Processing': return 'Processing CVs';
        case 'ParsingFailed': return 'CVs with Parsing Failed';
        default: return `${capitalize(apiStatus)} Candidates`;
    }
};

function CandidateListPage() {
  const { status: statusFromUrl } = useParams();
  const { currentUser } = useAuth();
  // const [summaryData, setSummaryData] = useState(null); // Το summary είναι στο DashboardPage
  const [candidates, setCandidates] = useState([]);
  // const [isLoadingSummary, setIsLoadingSummary] = useState(true); // Δεν χρειάζεται εδώ
  const [isLoadingList, setIsLoadingList] = useState(true);
  const [error, setError] = useState(null); // Γενικό error για τη σελίδα
  const [listError, setListError] = useState(''); // Ειδικό error για τη λίστα
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
  const apiStatus = useMemo(() => statusMappingsForApi[statusFromUrl?.toLowerCase()] || capitalize(statusFromUrl || 'All'), [statusFromUrl]);
  const listTitle = useMemo(() => getListTitle(statusFromUrl), [statusFromUrl]);

  const companyIdParam = useMemo(() => {
    if (!currentUser) return undefined;
    return currentUser.role === 'superadmin' ? undefined : currentUser.company_id;
  }, [currentUser]);

  const fetchCandidates = useCallback(async (page = 1, currentSearchTerm = searchTerm) => {
    if (currentUser === null) return; // Μην κάνεις fetch αν δεν έχει φορτωθεί ο χρήστης
    if (apiStatus === 'All' && !currentSearchTerm) {
        setCandidates([]); setIsLoadingList(false); setTotalPages(0); setTotalCandidates(0); setListError('');
        return;
    }
    setIsLoadingList(true); setListError('');
    try {
      const params = { page, per_page: ITEMS_PER_PAGE_LIST };
      if (companyIdParam !== undefined) {
        params.company_id = companyIdParam;
      }
      if (currentSearchTerm) {
        params.search = encodeURIComponent(currentSearchTerm);
      }
      if (apiStatus && apiStatus.toLowerCase() !== 'all') {
        params.status = apiStatus;
      }
      
      const response = await apiClient.get(`/candidates`, { params }); 
      
      setCandidates(Array.isArray(response.data.candidates) ? response.data.candidates : []);
      setTotalPages(response.data.total_pages || 0);
      setTotalCandidates(response.data.total_results || 0);
      setCurrentPage(response.data.current_page || 1);
    } catch (err) {
      setListError(err.response?.data?.error || `Failed to load ${listTitle}.`);
      setCandidates([]); setTotalPages(0); setTotalCandidates(0);
    } finally {
      setIsLoadingList(false);
    }
  }, [apiStatus, companyIdParam, searchTerm, ITEMS_PER_PAGE_LIST, currentUser, listTitle]); // Προσθήκη listTitle για το error message

  useEffect(() => {
    // Δεν χρειάζεται fetchSummary εδώ, μόνο στο DashboardPage
    if (currentUser) { // Έλεγχος αν ο currentUser είναι διαθέσιμος
        setCurrentPage(1); // Reset σελίδας
        fetchCandidates(1, searchTerm);
    }
  }, [currentUser, apiStatus, searchTerm, fetchCandidates]); // Εξαρτάται από το apiStatus (από το URL) και το searchTerm

  const handleSearchChange = (event) => setSearchTerm(event.target.value);
  
  const handleSearchSubmit = () => {
    setCurrentPage(1);
    fetchCandidates(1, searchTerm);
  };

  const handlePageChange = (newPage) => {
    if (newPage >= 1 && newPage <= totalPages) {
        fetchCandidates(newPage, searchTerm);
    }
  };
  
  const handleCandidateDeletedOnListPage = (deletedCandidateId) => {
    setCandidates(prevCandidates => prevCandidates.filter(c => c.candidate_id !== deletedCandidateId));
    setTotalCandidates(prev => prev -1); // Απλή μείωση, ίσως χρειαστεί ξανά fetch για ακρίβεια
    // fetchSummary(); // Δεν χρειάζεται εδώ
  };
  
  if (!currentUser) {
    return <div className="loading-placeholder card-style">Initializing page...</div>;
  }

  return (
    <div className="candidate-list-page main-content-area">
       <h2 style={{textAlign: 'center', marginBottom: '1rem'}}>{listTitle}</h2>
       {/* Δεν εμφανίζουμε το DashboardSummary εδώ */}
       {error && <p className="error-message" style={{textAlign: 'center'}}>{error}</p>}

      <SearchBar
          searchTerm={searchTerm}
          onSearchChange={handleSearchChange}
          onSearchSubmit={handleSearchSubmit}
          placeholder={`Search in ${listTitle}...`}
          inputClassName="input-light-gray"
          buttonClassName="button-action button-secondary" // Διαφορετικό στυλ από το dashboard
       />

      {isLoadingList && <p className="loading-placeholder" style={{marginTop: '1rem'}}>Loading candidates...</p>}
      {listError && !isLoadingList && <p className="error-message" style={{textAlign: 'center', marginTop: '1rem'}}>{listError}</p>}
      
      {!isLoadingList && !listError && candidates.length === 0 && searchTerm && (
            <p style={{ textAlign: 'center', marginTop: '1rem' }}>No candidates found matching '{searchTerm}' in {listTitle}.</p>
       )}
      {!isLoadingList && !listError && candidates.length === 0 && !searchTerm && apiStatus !== 'All' && (
            <p style={{ textAlign: 'center', marginTop: '1rem' }}>No candidates currently in {listTitle}.</p>
       )}
      {!isLoadingList && !listError && candidates.length === 0 && !searchTerm && apiStatus === 'All' && (
            <p style={{ textAlign: 'center', marginTop: '1rem' }}>Please enter a search term to view all candidates or select a status from the sidebar.</p>
       )}

      {!isLoadingList && !listError && candidates.length > 0 && (
         <CandidateList 
            candidates={candidates} 
            onCandidateDeleted={handleCandidateDeletedOnListPage}
            listTitle="" // Δεν χρειάζεται ο τίτλος μέσα στο CandidateList component πλέον
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