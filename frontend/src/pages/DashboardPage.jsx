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
import './DashboardPage.css'; // Βεβαιώσου ότι αυτό το CSS υπάρχει και είναι ενημερωμένο

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
  const ITEMS_PER_PAGE_DASH = 5; // Μικρότερος αριθμός για το dashboard

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
      // console.log("DashboardPage: Fetching summary data with params:", params);
      const res = await apiClient.get('/dashboard/summary', { params });
      // console.log("DashboardPage: Summary data fetched:", res.data);
      setSummaryData(res.data);
    } catch (err) {
      const errorMsg = err.response?.data?.error || 'Failed to load dashboard data.';
      console.error("DashboardPage: Error fetching summary data:", err.response || err.message || err);
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
      // console.log("DashboardPage: Fetching 'Needs Review' candidates with params:", params);
      const response = await apiClient.get(`/candidates`, { params });
      // console.log("DashboardPage: 'Needs Review' candidates data received:", response.data);

      setCandidatesForNeedsReview(Array.isArray(response.data.candidates) ? response.data.candidates : []);
      setTotalPages(response.data.total_pages || 0);
      setTotalCandidatesInList(response.data.total_results || 0);
      setCurrentPage(response.data.current_page || 1);
    } catch (err) {
      console.error("DashboardPage: Error fetching 'Needs Review' candidates:", err.response || err.message || err);
      setListError(err.response?.data?.error || 'Failed to load candidates for review.');
      setCandidatesForNeedsReview([]);
      setTotalPages(0);
      setTotalCandidatesInList(0);
    }
    finally { setIsLoadingList(false); }
  }, [companyIdParam, ITEMS_PER_PAGE_DASH, currentUser]); // Αφαίρεσα το ITEMS_PER_PAGE_DASH από τα deps αν είναι σταθερό

  useEffect(() => {
    if (currentUser) {
        // console.log("DashboardPage: currentUser available, fetching summary data.");
        fetchSummaryData();
    } else {
        // console.log("DashboardPage: currentUser NOT available yet for summary fetch.");
    }
  }, [currentUser, fetchSummaryData]);

  useEffect(() => {
    if (currentUser) {
        // console.log("DashboardPage: currentUser available, fetching NeedsReview candidates. SearchTerm:", searchTerm);
        setCurrentPage(1);
        fetchNeedsReviewCandidates(1, searchTerm);
    } else {
        // console.log("DashboardPage: currentUser NOT available yet for NeedsReview fetch.");
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
            fetchNeedsReviewCandidates(1, ''); // Επαναφορά στο αρχικό φόρτωμα χωρίς search term
            setSearchTerm(''); // Καθαρισμός του search term
        }
    }, 1800);
  };
  const handleCandidateDeletedOnDashboard = () => {
    if (currentUser) {
        fetchSummaryData();
        fetchNeedsReviewCandidates(currentPage, searchTerm); // Επαναφόρτωση της τρέχουσας σελίδας
    }
  };

  const keyStatisticsForDisplay = useMemo(() => {
    if (!summaryData) return null;
    const statsToDisplay = {
      open_positions_count: summaryData.active_positions,
      stuck_in_needs_review_X_days: summaryData.stuck_in_needs_review_X_days,
      stuck_in_needs_review_threshold_days: summaryData.stuck_in_needs_review_threshold_days,
      offer_acceptance_rate: summaryData.offer_acceptance_rate,
      avg_days_in_needs_review: summaryData.avg_days_in_needs_review,
      interview_conversion_rate: summaryData.interview_conversion_rate,
    };
    // console.log("DashboardPage: keyStatisticsForDisplay created:", statsToDisplay);
    return statsToDisplay;
  }, [summaryData]);

  const candidatesByStageForChart = summaryData ? summaryData.candidates_by_stage : [];

  if (!currentUser && !isLoadingSummary) { // Αν δεν υπάρχει χρήστης και δεν φορτώνει το summary (έχει ολοκληρωθεί ο έλεγχος session)
    return <div className="loading-placeholder card-style">User not authenticated or session expired. Please login.</div>;
  }
  if (isLoadingSummary && !summaryData) { // Αν φορτώνει το summary και δεν έχουμε ακόμα δεδομένα
    return <div className="loading-placeholder card-style">Loading dashboard data...</div>;
  }


  return (
    <div className="dashboard-page-container">
      {/* Σειρά 1: Dashboard Summary */}
      <div className="dashboard-row">
        <div className="dashboard-summary-wrapper card-style"> {/* Το card-style εδώ */}
          {summaryError && <div className="error-message">{summaryError}</div>}
          {!summaryError && summaryData && <DashboardSummary summary={summaryData} />}
          {!summaryError && !summaryData && <p>No summary data available.</p>}
        </div>
      </div>

      {/* Σειρά 2: Key Statistics και Upload CV */}
      <div className="dashboard-row dashboard-row-middle">
        <div className="dashboard-statistics-wrapper card-style"> {/* Το card-style εδώ */}
          <h3 className="section-header">Key Statistics</h3>
          {summaryError && <div className="error-message">{summaryError}</div>}
          {!summaryError && keyStatisticsForDisplay && (
            <StatisticsDisplay stats={keyStatisticsForDisplay} isLoading={false} />
          )}
          {!summaryError && !keyStatisticsForDisplay && <p style={{textAlign: 'center', marginTop: '1rem', color: '#6b7280'}}>No key statistics available.</p>}
        </div>

        <div className="upload-section-wrapper card-style"> {/* Το card-style εδώ */}
          <h3 className="section-header">Upload New CV</h3>
          <UploadComponent onUploadSuccess={handleUploadSuccess} />
        </div>
      </div>

      {/* Σειρά 3: Needs Review List και Candidates Pipeline Chart */}
      <div className="dashboard-row dashboard-row-bottom">
        <div className="needs-review-wrapper card-style"> {/* Το card-style εδώ */}
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

        <div className="pipeline-chart-wrapper card-style"> {/* Το card-style εδώ */}
           <h3 className="section-header">Candidates Pipeline</h3>
           {summaryError && <div className="error-message">{summaryError}</div>}
           {!summaryError && candidatesByStageForChart && candidatesByStageForChart.length > 0 ? (
               <CandidatesByStageChart data={candidatesByStageForChart} />
           ) : (
             !isLoadingSummary && <p style={{textAlign: 'center', marginTop: '1rem', color: '#6b7280'}}>No pipeline data to display.</p>
           )}
        </div>
      </div>
    </div>
  );
}

export default DashboardPage;