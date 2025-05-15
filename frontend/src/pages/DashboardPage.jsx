// frontend/src/pages/DashboardPage.jsx
import React, { useState, useEffect, useCallback } from 'react';
import DashboardSummary from '../components/DashboardSummary';
import CandidateList from '../components/CandidateList';
import SearchBar from '../components/SearchBar';
import UploadComponent from '../components/UploadComponent';
import StatisticsDisplay from '../components/StatisticsDisplay';
import CandidatesByStageChart from '../components/CandidatesByStageChart';
import apiClient, { getDashboardStatistics } from '../api';
import { useAuth } from '../App';
import './DashboardPage.css'; // ΚΡΙΣΙΜΟ: Βεβαιώσου ότι αυτό το αρχείο εισάγεται

function DashboardPage() {
  const { currentUser } = useAuth();
  const [summaryData, setSummaryData] = useState(null);
  const [statisticsData, setStatisticsData] = useState(null);
  const [candidates, setCandidates] = useState([]);
  
  const [isLoadingSummary, setIsLoadingSummary] = useState(true);
  const [summaryError, setSummaryError] = useState('');
  
  const [isLoadingStatistics, setIsLoadingStatistics] = useState(true);
  const [statisticsError, setStatisticsError] = useState('');

  const [isLoadingList, setIsLoadingList] = useState(true);
  const [listError, setListError] = useState('');

  const [searchTerm, setSearchTerm] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [totalCandidates, setTotalCandidates] = useState(0);
  const ITEMS_PER_PAGE_DASH = 10;

  const companyIdForRequests = currentUser?.role === 'superadmin' ? null : currentUser?.company_id;

  const fetchSummary = useCallback(async () => {
    setIsLoadingSummary(true); setSummaryError('');
    try {
      const params = companyIdForRequests ? { company_id: companyIdForRequests } : {};
      const res = await apiClient.get('/dashboard/summary', { params });
      setSummaryData(res.data);
    } catch (err) { setSummaryError(err.response?.data?.error || 'Failed to load summary.'); setSummaryData(null); }
    finally { setIsLoadingSummary(false); }
  }, [companyIdForRequests]);

  const fetchStatistics = useCallback(async () => {
    setIsLoadingStatistics(true); setStatisticsError('');
    try {
      const data = await getDashboardStatistics(companyIdForRequests);
      setStatisticsData(data);
    } catch (err) { setStatisticsError(err.response?.data?.error || 'Failed to load statistics.'); setStatisticsData(null); }
    finally { setIsLoadingStatistics(false); }
  }, [companyIdForRequests]);

  const fetchCandidates = useCallback(async (page = 1, currentSearchTerm = searchTerm) => {
    setIsLoadingList(true); setListError('');
    try {
      const statusToFetch = 'NeedsReview';
      const params = { page, per_page: ITEMS_PER_PAGE_DASH };
      if (companyIdForRequests) params.company_id = companyIdForRequests;
      let response;
      if (currentSearchTerm) {
        params.q = encodeURIComponent(currentSearchTerm);
        response = await apiClient.get('/search', { params });
      } else {
        response = await apiClient.get(`/candidates/${statusToFetch}`, { params });
      }
      setCandidates(Array.isArray(response.data.candidates) ? response.data.candidates : []);
      setTotalPages(response.data.total_pages || 0);
      setTotalCandidates(response.data.total_results || 0);
      setCurrentPage(response.data.current_page || 1);
    } catch (err) { setListError(err.response?.data?.error || 'Failed to load candidates.'); setCandidates([]); }
    finally { setIsLoadingList(false); }
  }, [companyIdForRequests, searchTerm, ITEMS_PER_PAGE_DASH]);

  useEffect(() => { fetchSummary(); fetchStatistics(); }, [fetchSummary, fetchStatistics]);
  useEffect(() => { setCurrentPage(1); fetchCandidates(1, searchTerm); }, [searchTerm, fetchCandidates]);

  const handleSearchChange = (e) => setSearchTerm(e.target.value);
  const handleSearchSubmit = (e) => { if (e) e.preventDefault(); fetchCandidates(1, searchTerm); };
  const handlePageChange = (newPage) => { if (newPage >= 1 && newPage <= totalPages) fetchCandidates(newPage, searchTerm); };
  const handleUploadSuccess = () => { setTimeout(() => { fetchSummary(); fetchStatistics(); fetchCandidates(1, ''); setSearchTerm(''); }, 1800); };
  const handleCandidateDeleted = () => { fetchSummary(); fetchStatistics(); /* Update list as needed */ };

  return (
    <div className="dashboard-page-container">
      
      <div className="dashboard-top-row"> {/* Αυτό το div είναι το κλειδί */}
        
        <div className="dashboard-summary-wrapper">
          {summaryError && <div className="error-message card-style">{summaryError}</div>}
          {isLoadingSummary && !summaryError && <div className="loading-placeholder card-style">Loading summary...</div>}
          {!isLoadingSummary && !summaryError && summaryData && <DashboardSummary summary={summaryData} />}
          {!isLoadingSummary && !summaryError && !summaryData && <div className="card-style"><p>No summary data.</p></div>}
        </div>

        <div className="dashboard-statistics-wrapper card-style">
          <h3 className="section-header">Key Statistics</h3>
          {statisticsError && <div className="error-message">{statisticsError}</div>}
          {isLoadingStatistics && !statisticsError && <div className="loading-placeholder">Loading statistics...</div>}
          {!isLoadingStatistics && !statisticsError && statisticsData && (
            <>
              <StatisticsDisplay stats={statisticsData} isLoading={false} />
              {statisticsData.candidates_by_stage && statisticsData.candidates_by_stage.length > 0 && (
                 <div style={{marginTop: '2rem'}}> {/* Λίγο μεγαλύτερο κενό */}
                    <h4 style={{marginBottom: '1rem', fontSize: '1.15rem', color: '#374151', fontWeight: 600 }}>Candidates Pipeline</h4>
                    <CandidatesByStageChart data={statisticsData.candidates_by_stage} />
                 </div>
              )}
              {/* ... (μηνύματα για κενό chart) ... */}
            </>
          )}
          {!isLoadingStatistics && !statisticsError && !statisticsData && <p>No statistics data.</p>}
        </div>
      
      </div>
      
      <div className="upload-section card-style">
        <h3 className="section-header">Upload New CV</h3>
        <UploadComponent onUploadSuccess={handleUploadSuccess} />
      </div>
      
      <div className="needs-review-section card-style">
        <h3 className="section-header">Candidates Needing Review</h3>
        <SearchBar
            searchTerm={searchTerm}
            onSearchChange={handleSearchChange}
            onSearchSubmit={handleSearchSubmit}
            placeholder="Search in 'Needs Review'..."
            //inputClassName="input-light-gray"
            buttonClassName="button-action button-secondary"
        />
        {listError && <div className="error-message">{listError}</div>}
        {isLoadingList && !listError && <p className="loading-placeholder">Loading candidates...</p>}
        {!isLoadingList && !listError && candidates.length === 0 && (
            <p className="empty-list-message">{searchTerm ? `No candidates found matching '${searchTerm}'.` : "No candidates currently need review."}</p>
        )}
        {!isLoadingList && !listError && candidates.length > 0 && (
          <CandidateList candidates={candidates} onCandidateDeleted={handleCandidateDeleted} />
        )}
        {/* ... (pagination) ... */}
      </div>
    </div>
  );
}

export default DashboardPage;