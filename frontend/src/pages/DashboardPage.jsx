// frontend/src/pages/DashboardPage.jsx
import React, { useState, useEffect, useCallback, useMemo } from 'react';
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
  const [candidatesForNeedsReview, setCandidatesForNeedsReview] = useState([]);
  
  const [isLoadingSummary, setIsLoadingSummary] = useState(true);
  const [summaryError, setSummaryError] = useState('');
  
  const [isLoadingList, setIsLoadingList] = useState(true);
  const [listError, setListError] = useState('');

  const [searchTerm, setSearchTerm] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [totalCandidatesInList, setTotalCandidatesInList] = useState(0);
  const ITEMS_PER_PAGE_DASH = 10;

  const companyIdParam = useMemo(() => {
    if (!currentUser) return undefined;
    return currentUser.role === 'superadmin' ? undefined : currentUser.company_id;
  }, [currentUser]);

  const fetchSummaryData = useCallback(async () => {
    if (currentUser === null) return;
    setIsLoadingSummary(true); setSummaryError('');
    try {
      const params = {};
      if (companyIdParam !== undefined) { 
        params.company_id = companyIdParam;
      }
      console.log("DashboardPage: Fetching summary data with params:", params); // DEBUG LOG
      const res = await apiClient.get('/dashboard/summary', { params });
      console.log("DashboardPage: Summary data fetched:", res.data); // DEBUG LOG
      setSummaryData(res.data);
    } catch (err) { 
      const errorMsg = err.response?.data?.error || 'Failed to load dashboard data.';
      console.error("DashboardPage: Error fetching summary data:", err.response || err.message || err); // DEBUG LOG
      setSummaryError(errorMsg); 
      setSummaryData(null); 
    }
    finally { setIsLoadingSummary(false); }
  }, [companyIdParam, currentUser]);

  const fetchNeedsReviewCandidates = useCallback(async (page = 1, currentSearchTerm = '') => {
    if (currentUser === null) return;
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
      console.log("DashboardPage: Fetching 'Needs Review' candidates with params:", params); // DEBUG LOG
      const response = await apiClient.get(`/candidates`, { params }); 
      console.log("DashboardPage: 'Needs Review' candidates data received:", response.data); // DEBUG LOG
      
      setCandidatesForNeedsReview(Array.isArray(response.data.candidates) ? response.data.candidates : []);
      setTotalPages(response.data.total_pages || 0);
      setTotalCandidatesInList(response.data.total_results || 0);
      setCurrentPage(response.data.current_page || 1);
    } catch (err) { 
      console.error("DashboardPage: Error fetching 'Needs Review' candidates:", err.response || err.message || err); // DEBUG LOG
      setListError(err.response?.data?.error || 'Failed to load candidates for review.'); 
      setCandidatesForNeedsReview([]); 
      setTotalPages(0); 
      setTotalCandidatesInList(0);
    }
    finally { setIsLoadingList(false); }
  }, [companyIdParam, ITEMS_PER_PAGE_DASH, currentUser]);

  useEffect(() => {
    if (currentUser) {
        console.log("DashboardPage: currentUser available, fetching summary data."); // DEBUG LOG
        fetchSummaryData();
    } else {
        console.log("DashboardPage: currentUser NOT available yet for summary fetch."); // DEBUG LOG
    }
  }, [currentUser, fetchSummaryData]);

  useEffect(() => {
    if (currentUser) {
        console.log("DashboardPage: currentUser available, fetching NeedsReview candidates. SearchTerm:", searchTerm); // DEBUG LOG
        setCurrentPage(1);
        fetchNeedsReviewCandidates(1, searchTerm);
    } else {
        console.log("DashboardPage: currentUser NOT available yet for NeedsReview fetch."); // DEBUG LOG
    }
  }, [currentUser, searchTerm, fetchNeedsReviewCandidates]);
  

  const handleSearchChange = (e) => setSearchTerm(e.target.value);
  const handleSearchSubmit = (e) => { 
    if (e) e.preventDefault(); 
    setCurrentPage(1);
    fetchNeedsReviewCandidates(1, searchTerm); 
  };
  const handlePageChange = (newPage) => { 
    if (newPage >= 1 && newPage <= totalPages) {
        fetchNeedsReviewCandidates(newPage, searchTerm); 
    }
  };
  const handleUploadSuccess = () => { 
    setTimeout(() => { 
        if (currentUser) {
            fetchSummaryData(); 
            fetchNeedsReviewCandidates(1, '');
            setSearchTerm(''); 
        }
    }, 1800); 
  };
  const handleCandidateDeletedOnDashboard = () => { 
    if (currentUser) {
        fetchSummaryData(); 
        fetchNeedsReviewCandidates(currentPage, searchTerm);
    }
  };

  const keyStatisticsForDisplay = summaryData ? {
    open_positions_count: summaryData.active_positions,
  } : null;

  const candidatesByStageForChart = summaryData ? summaryData.candidates_by_stage : [];

  if (!currentUser) {
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