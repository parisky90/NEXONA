// frontend/src/pages/CandidateListPage.jsx
import React, { useState, useEffect, useCallback, useMemo } from 'react'; // useMemo προστέθηκε
// import DashboardSummary from '../components/DashboardSummary'; // Αφαιρέθηκε, δεν χρησιμοποιείται εδώ
import CandidateList from '../components/CandidateList';
import SearchBar from '../components/SearchBar';
import apiClient from '../api';
import { useAuth } from '../App';
import { useParams } from 'react-router-dom';

const capitalize = (s) => s && s[0].toUpperCase() + s.slice(1);

const getListTitle = (statusRouteParam) => {
    if (!statusRouteParam) return 'All Candidates';
    const statusMappings = {
        'needs-review': 'NeedsReview',
        'accepted': 'Accepted',
        'interested': 'Interested',
        'interviewproposed': 'Interview Proposed', // <--- ΝΕΑ ΑΝΤΙΣΤΟΙΧΙΣΗ
        'interviewscheduled': 'Interview Scheduled', // <--- ΝΕΑ ΑΝΤΙΣΤΟΙΧΙΣΗ
        'interview': 'Interview Scheduled', // Alias για το παλιό "Interview"
        'evaluation': 'Evaluation',
        'offermade': 'OfferMade',
        'hired': 'Hired',
        'rejected': 'Rejected',
        'declined': 'Declined',
        'processing': 'Processing',
        'parsing-failed': 'ParsingFailed'
    };
    // Χρησιμοποίησε το statusRouteParam για να βρεις το αντίστοιχο "καθαρό" status
    const cleanStatus = statusMappings[statusRouteParam.toLowerCase()] || capitalize(statusRouteParam);

    switch (cleanStatus) {
        case 'NeedsReview': return 'Candidates Needing Review';
        case 'Accepted': return 'Accepted Candidates';
        case 'Interested': return 'Interested Candidates';
        case 'Interview Proposed': return 'Candidates with Interview Proposed'; // <--- ΝΕΟΣ ΤΙΤΛΟΣ
        case 'Interview Scheduled': return 'Candidates with Interview Scheduled'; // <--- ΝΕΟΣ ΤΙΤΛΟΣ
        case 'Evaluation': return 'Candidates Under Evaluation';
        case 'OfferMade': return 'Candidates With Offer Made';
        case 'Hired': return 'Hired Candidates';
        case 'Rejected': return 'Rejected Candidates';
        case 'Declined': return 'Declined Candidates'; // Αφαίρεσα το "(by Candidate)" για απλότητα
        case 'Processing': return 'Processing CVs';
        case 'ParsingFailed': return 'CVs with Parsing Failed';
        default: return `${capitalize(cleanStatus)} Candidates`;
    }
};


function CandidateListPage() {
  const { status: statusFromUrl } = useParams();
  const { currentUser } = useAuth();
  // Το summaryData και το isLoadingSummary αφαιρέθηκαν, δεν τα χρειαζόμαστε εδώ.
  const [candidates, setCandidates] = useState([]);
  const [isLoadingList, setIsLoadingList] = useState(true);
  const [error, setError] = useState(null); // Ένα error state είναι αρκετό
  const [searchTerm, setSearchTerm] = useState('');

  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [totalCandidates, setTotalCandidates] = useState(0);
  const ITEMS_PER_PAGE_LIST = 15;

  console.log("CandidateListPage: statusFromUrl from useParams:", statusFromUrl); // Log για το URL param

  const statusMappingsForApi = useMemo(() => ({ // Χρήση useMemo για σταθερότητα
      'needs-review': 'NeedsReview',
      'accepted': 'Accepted',
      'interested': 'Interested',
      'interviewproposed': 'Interview Proposed', // <--- ΝΕΑ ΑΝΤΙΣΤΟΙΧΙΣΗ ΓΙΑ API
      'interviewscheduled': 'Interview Scheduled', // <--- ΝΕΑ ΑΝΤΙΣΤΟΙΧΙΣΗ ΓΙΑ API
      'interview': 'Interview Scheduled', // Διατήρηση του alias
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
    console.log("CandidateListPage: calculatedApiStatus (for API call):", calculatedApiStatus); // Log για το apiStatus
    return calculatedApiStatus;
  }, [statusFromUrl, statusMappingsForApi]);

  const listTitle = useMemo(() => getListTitle(statusFromUrl), [statusFromUrl]);

  const companyIdForRequests = useMemo(() => { // Χρήση useMemo
    if (!currentUser) return undefined;
    return currentUser.role === 'superadmin' ? null : currentUser.company_id; // null αν superadmin για να μην στέλνει company_id
  }, [currentUser]);

  const fetchCandidates = useCallback(async (page = 1, currentSearchTerm = searchTerm) => {
    if (currentUser === null) {
        setIsLoadingList(false);
        return;
    }
    // Αν το statusFromUrl είναι undefined (δηλαδή είμαστε στο /candidates) και δεν υπάρχει search term,
    // τότε μην κάνεις fetch, εμφάνισε μήνυμα.
    if (!statusFromUrl && !currentSearchTerm) {
        setCandidates([]);
        setIsLoadingList(false);
        setTotalPages(0);
        setTotalCandidates(0);
        setError(null); // Καθάρισε τυχόν προηγούμενα σφάλματα
        return;
    }

    setIsLoadingList(true);
    setError(null);
    try {
      const params = {
        page,
        per_page: ITEMS_PER_PAGE_LIST,
      };
      if (companyIdForRequests !== null && companyIdForRequests !== undefined) { // Στείλε το company_id αν υπάρχει
        params.company_id = companyIdForRequests;
      }

      // Το API endpoint /candidates χειρίζεται και το search και το status filter.
      // Δεν χρειάζεται να καλούμε το /search ξεχωριστά.
      if (currentSearchTerm) {
        params.search = encodeURIComponent(currentSearchTerm);
      }
      if (apiStatus && apiStatus.toLowerCase() !== 'all') {
        params.status = apiStatus;
      }

      console.log(`CandidateListPage: Fetching candidates with params:`, params);
      const response = await apiClient.get(`/candidates`, { params }); // Ένα endpoint για όλες τις λίστες
      console.log("CandidateListPage: Candidates data received:", response.data);

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
  }, [apiStatus, companyIdForRequests, searchTerm, currentUser, listTitle, statusFromUrl]); // Προσθήκη statusFromUrl στο dependency array

  useEffect(() => {
    // Το fetchSummary αφαιρέθηκε, δεν χρειάζεται εδώ.
    if (currentUser) {
        console.log("CandidateListPage: useEffect triggered to fetch candidates. Current apiStatus:", apiStatus, "Current searchTerm:", searchTerm);
        setCurrentPage(1); // Κάνε reset τη σελίδα όταν αλλάζει το status ή το search term
        fetchCandidates(1, searchTerm);
    } else {
        setIsLoadingList(false); // Αν δεν υπάρχει χρήστης, μην αφήνεις το loading true
        setCandidates([]);
        setTotalPages(0);
        setTotalCandidates(0);
    }
  }, [currentUser, apiStatus, searchTerm, fetchCandidates]);


  const handleSearchChange = (event) => setSearchTerm(event.target.value);

  const handleSearchSubmit = (e) => { // Προσθήκη 'e'
    if (e) e.preventDefault(); // Καλό είναι να το έχεις
    setCurrentPage(1); // Πήγαινε στην πρώτη σελίδα όταν γίνεται νέα αναζήτηση
    // Το fetchCandidates θα κληθεί αυτόματα από το useEffect επειδή αλλάζει το searchTerm (αν αλλάξει)
    // ή αν θέλεις να το κάνεις trigger ρητά:
    fetchCandidates(1, searchTerm);
  };

  const handlePageChange = (newPage) => {
    if (newPage >= 1 && newPage <= totalPages && !isLoadingList) { // Έλεγχος και για isLoadingList
        fetchCandidates(newPage, searchTerm);
    }
  };

  const handleCandidateDeletedOnListPage = (deletedCandidateId) => {
    setCandidates(prevCandidates => prevCandidates.filter(c => c.candidate_id !== deletedCandidateId));
    setTotalCandidates(prevTotal => prevTotal > 0 ? prevTotal - 1 : 0);
    // Αν η τρέχουσα σελίδα μείνει άδεια και δεν είναι η πρώτη, πήγαινε στην προηγούμενη
    if (candidates.length === 1 && currentPage > 1) {
        handlePageChange(currentPage - 1);
    } else if (candidates.length === 1 && currentPage === 1) {
        // Αν ήταν ο τελευταίος στην πρώτη σελίδα, ξανακάνε fetch για να δεις αν υπάρχουν άλλοι (αν και δεν θα έπρεπε)
        // ή απλά άφησέ το να δείξει "No candidates".
        // Για απλότητα, δεν κάνουμε κάτι εδώ, η λίστα θα είναι απλά άδεια.
    }
  };

  if (!currentUser && !isLoadingList) { // Αν δεν υπάρχει χρήστης και δεν φορτώνει
    return <div className="loading-placeholder card-style">Initializing page... (No user)</div>;
  }
  if (isLoadingList && candidates.length === 0) { // Αν φορτώνει και δεν έχουμε ακόμα υποψηφίους
      return <div className="loading-placeholder card-style" style={{marginTop: '1rem'}}>Loading candidates...</div>;
  }


  return (
    <div className="candidate-list-page main-content-area">
       <h2 style={{textAlign: 'center', marginBottom: '1rem'}}>{listTitle}</h2>
       {/* Το DashboardSummary αφαιρέθηκε από εδώ */}
       {error && <p className="error-message" style={{textAlign: 'center'}}>{error}</p>}

      <SearchBar
          searchTerm={searchTerm}
          onSearchChange={handleSearchChange}
          onSearchSubmit={handleSearchSubmit}
          placeholder={`Search in ${listTitle}...`}
          inputClassName="input-light-gray"
          buttonClassName="button-action button-secondary" // Το είχες button-navy-blue
       />

      {/* Τα μηνύματα για loading/empty/error έχουν απλοποιηθεί */}
      {isLoadingList && candidates.length === 0 && <p className="loading-placeholder" style={{marginTop: '1rem'}}>Loading candidates...</p>}
      {!isLoadingList && error && <p className="error-message" style={{textAlign: 'center', marginTop: '1rem'}}>{error}</p>}

      {!isLoadingList && !error && candidates.length === 0 && searchTerm && (
            <p style={{ textAlign: 'center', marginTop: '1rem' }}>No candidates found matching '{searchTerm}' in {listTitle}.</p>
       )}
      {!isLoadingList && !error && candidates.length === 0 && !searchTerm && apiStatus !== 'All' && (
            <p style={{ textAlign: 'center', marginTop: '1rem' }}>No candidates currently in {listTitle}.</p>
       )}
      {/* Εμφάνισε αυτό μόνο αν είμαστε στο /candidates (χωρίς status) και δεν υπάρχει search term */}
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