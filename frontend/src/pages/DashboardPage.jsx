// frontend/src/pages/DashboardPage.jsx
import React, { useState, useEffect, useCallback, useMemo } from 'react'; // Προσθήκη useMemo
import DashboardSummary from '../components/DashboardSummary';
import CandidateList from '../components/CandidateList';
import SearchBar from '../components/SearchBar';
import UploadComponent from '../components/UploadComponent';
import StatisticsDisplay from '../components/StatisticsDisplay';
import CandidatesByStageChart from '../components/CandidatesByStageChart';
import apiClient from '../api';
import { useAuth } from '../App';
import './DashboardPage.css';

function DashboardPage() {
  const { currentUser } = useAuth();
  const [summaryData, setSummaryData] = useState(null);
  const [candidatesForNeedsReview, setCandidatesForNeedsReview] = useState([]); // Μετονομασία για σαφήνεια
  
  const [isLoadingSummary, setIsLoadingSummary] = useState(true);
  const [summaryError, setSummaryError] = useState('');
  
  const [isLoadingList, setIsLoadingList] = useState(true);
  const [listError, setListError] = useState('');

  const [searchTerm, setSearchTerm] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [totalCandidatesInList, setTotalCandidatesInList] = useState(0); // Μετονομασία
  const ITEMS_PER_PAGE_DASH = 10;

  // Χρησιμοποίησε useMemo για το companyIdParam για να μην επαναδημιουργείται αν δεν αλλάξει το currentUser
  const companyIdParam = useMemo(() => {
    if (!currentUser) return undefined; // Αν δεν έχει φορτωθεί ο χρήστης ακόμα
    return currentUser.role === 'superadmin' ? undefined : currentUser.company_id;
  }, [currentUser]);

  const fetchSummaryData = useCallback(async () => {
    if (currentUser === null) return; // Μην κάνεις fetch αν δεν έχει φορτωθεί ο χρήστης
    setIsLoadingSummary(true); setSummaryError('');
    try {
      const params = {};
      if (companyIdParam !== undefined) { 
        params.company_id = companyIdParam;
      }
      const res = await apiClient.get('/dashboard/summary', { params });
      setSummaryData(res.data);
    } catch (err) { 
      const errorMsg = err.response?.data?.error || 'Failed to load dashboard data.';
      setSummaryError(errorMsg); 
      setSummaryData(null); 
    }
    finally { setIsLoadingSummary(false); }
  }, [companyIdParam, currentUser]); // Πρόσθεσε το currentUser ως dependency

  const fetchNeedsReviewCandidates = useCallback(async (page = 1, currentSearchTerm = '') => {
    if (currentUser === null) return; // Μην κάνεις fetch αν δεν έχει φορτωθεί ο χρήστης
    setIsLoadingList(true); setListError('');
    try {
      const statusToFetch = 'NeedsReview';
      const params = { page, per_page: ITEMS_PER_PAGE_DASH, status: statusToFetch };
      if (companyIdParam !== undefined) {
        params.company_id = companyIdParam;
      }
      if (currentSearchTerm) {
        params.search = encodeURIComponent(currentSearchTerm);
      }
      
      const response = await apiClient.get(`/candidates`, { params }); 
      
      setCandidatesForNeedsReview(Array.isArray(response.data.candidates) ? response.data.candidates : []);
      setTotalPages(response.data.total_pages || 0);
      setTotalCandidatesInList(response.data.total_results || 0);
      setCurrentPage(response.data.current_page || 1);
    } catch (err) { 
      setListError(err.response?.data?.error || 'Failed to load candidates for review.'); 
      setCandidatesForNeedsReview([]); 
      setTotalPages(0); 
      setTotalCandidatesInList(0);
    }
    finally { setIsLoadingList(false); }
  }, [companyIdParam, ITEMS_PER_PAGE_DASH, currentUser]); // Αφαίρεσα το searchTerm από εδώ, θα το χειριστεί το άλλο useEffect

  useEffect(() => {
    if (currentUser) { // Έλεγχος αν ο currentUser είναι διαθέσιμος
        fetchSummaryData();
    }
  }, [currentUser, fetchSummaryData]); // Εξάρτηση από currentUser και την memoized fetchSummaryData

  useEffect(() => {
    if (currentUser) { // Έλεγχος αν ο currentUser είναι διαθέσιμος
        setCurrentPage(1); // Κάνε reset τη σελίδα όταν αλλάζει το searchTerm
        fetchNeedsReviewCandidates(1, searchTerm);
    }
  }, [currentUser, searchTerm, fetchNeedsReviewCandidates]); // Εξάρτηση από currentUser, searchTerm και την memoized fetchNeedsReviewCandidates
  

  const handleSearchChange = (e) => setSearchTerm(e.target.value);
  const handleSearchSubmit = (e) => { 
    if (e) e.preventDefault(); 
    setCurrentPage(1); // Reset page on new search
    fetchNeedsReviewCandidates(1, searchTerm); 
  };
  const handlePageChange = (newPage) => { 
    if (newPage >= 1 && newPage <= totalPages) {
        fetchNeedsReviewCandidates(newPage, searchTerm); 
    }
  };
  const handleUploadSuccess = () => { 
    setTimeout(() => { 
        if (currentUser) { // Έλεγχος για currentUser
            fetchSummaryData(); 
            fetchNeedsReviewCandidates(1, ''); // Φόρτωσε την πρώτη σελίδα των NeedsReview
            setSearchTerm(''); 
        }
    }, 1800); 
  };
  const handleCandidateDeletedOnDashboard = () => { 
    if (currentUser) { // Έλεγχος για currentUser
        fetchSummaryData(); 
        fetchNeedsReviewCandidates(currentPage, searchTerm); // Ξαναφόρτωσε την τρέχουσα σελίδα
    }
  };

  const keyStatisticsForDisplay = summaryData ? {
    open_positions_count: summaryData.active_positions,
    // Πρόσθεσε κι άλλα αν τα επιστρέφει το /summary, π.χ.:
    // interview_reach_percentage: summaryData.interview_reach_percentage,
    // avg_days_to_interview: summaryData.avg_days_to_interview,
  } : null;

  const candidatesByStageForChart = summaryData ? summaryData.candidates_by_stage : [];

  if (!currentUser) { // Αν ο χρήστης δεν έχει φορτωθεί ακόμα (π.χ. κατά το αρχικό loading του App.jsx)
    return <div className="loading-placeholder card-style">Initializing Dashboard...</div>;
  }

  return (
    <div className="dashboard-page-container">
      <div className="dashboard-top-row">
        <div className="dashboard-summary-wrapper">
          {summaryError && <div className="error-message card-style">{summaryError}</div>}
          {isLoadingSummary && !summaryError && <div className="loading-placeholder card-style">Loading summary...</div>}
          {!isLoadingSummary && !summaryError && summaryData && <DashboardSummary summary={summaryData} />}
          {!isLoadingSummary && !summaryError && !summaryData && <div className="card-style"><p>No summary data available.</p></div>}
        </div>

        <div className="dashboard-statistics-wrapper card-style">
          <h3 className="section-header">Key Statistics</h3>
          {isLoadingSummary && <div className="loading-placeholder">Loading statistics...</div>}
          {!isLoadingSummary && summaryError && <div className="error-message">{summaryError}</div>}
          {!isLoadingSummary && !summaryError && keyStatisticsForDisplay && (
            <>
              <StatisticsDisplay stats={keyStatisticsForDisplay} isLoading={false} />
              {candidatesByStageForChart && candidatesByStageForChart.length > 0 ? (
                 <div style={{marginTop: '2rem'}}>
                    <h4 style={{marginBottom: '1rem', fontSize: '1.15rem', color: '#374151', fontWeight: 600 }}>Candidates Pipeline</h4>
                    <CandidatesByStageChart data={candidatesByStageForChart} />
                 </div>
              ) : (
                !isLoadingSummary && <p style={{textAlign: 'center', marginTop: '1rem', color: '#6b7280'}}>No pipeline data to display.</p>
              )}
            </>
          )}
          {!isLoadingSummary && !summaryError && !keyStatisticsForDisplay && <p style={{textAlign: 'center', marginTop: '1rem', color: '#6b7280'}}>No key statistics available.</p>}
        </div>
      </div>
      
      <div className="upload-section card-style">
        <h3 className="section-header">Upload New CV</h3>
        <UploadComponent onUploadSuccess={handleUploadSuccess} />
      </div>
      
      <div className="needs-review-section card-style">
        <h3 className="section-header">Candidates Needing Review ({totalCandidatesInList})</h3>
        <SearchBar
            searchTerm={searchTerm}
            onSearchChange={handleSearchChange}
            onSearchSubmit={handleSearchSubmit}
            placeholder="Search in 'Needs Review'..."
            buttonClassName="button-action button-secondary"
        />
        {listError && <div className="error-message">{listError}</div>}
        {isLoadingList && !listError && <p className="loading-placeholder">Loading candidates for review...</p>}
        {!isLoadingList && !listError && candidatesForNeedsReview.length === 0 && (
            <p className="empty-list-message">{searchTerm ? `No candidates found matching '${searchTerm}' in Needs Review.` : "No candidates currently need review."}</p>
        )}
        {!isLoadingList && !listError && candidatesForNeedsReview.length > 0 && (
          <CandidateList candidates={candidatesForNeedsReview} onCandidateDeleted={handleCandidateDeletedOnDashboard} listTitle=""/>
        )}
        
        {!isLoadingList && totalPages > 1 && (
            <div className="pagination-controls" style={{ marginTop: '1rem', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '0.5rem' }}>
            <button onClick={() => handlePageChange(currentPage - 1)} disabled={currentPage === 1 || isLoadingList} className="button-action button-secondary">Previous</button>
            <span>Page {currentPage} of {totalPages}</span>
            <button onClick={() => handlePageChange(currentPage + 1)} disabled={currentPage === totalPages || isLoadingList} className="button-action button-secondary">Next</button>
            </div>
        )}
      </div>
    </div>
  );
}

export default DashboardPage;