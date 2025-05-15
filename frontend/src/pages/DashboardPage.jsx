// frontend/src/pages/DashboardPage.jsx
import React, { useState, useEffect, useCallback } from 'react';
import DashboardSummary from '../components/DashboardSummary';
import CandidateList from '../components/CandidateList';
import SearchBar from '../components/SearchBar';
import UploadComponent from '../components/UploadComponent';
import StatisticsDisplay from '../components/StatisticsDisplay';
import apiClient, { getDashboardStatistics } from '../api';
import { useAuth } from '../App';
// import './DashboardPage.css'; // Αφαιρέθηκε ή σχολιάστηκε αν δεν υπάρχει το αρχείο

function DashboardPage() {
  const { currentUser } = useAuth();
  const [summaryData, setSummaryData] = useState(null);
  const [statisticsData, setStatisticsData] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [isLoadingSummary, setIsLoadingSummary] = useState(true);
  const [isLoadingStatistics, setIsLoadingStatistics] = useState(true);
  const [isLoadingList, setIsLoadingList] = useState(true);
  const [error, setError] = useState(null);
  const [statsError, setStatsError] = useState('');
  const [searchTerm, setSearchTerm] = useState('');

  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [totalCandidates, setTotalCandidates] = useState(0);
  const ITEMS_PER_PAGE_DASH = 10;

  const companyIdForRequests = currentUser?.role === 'superadmin' ? null : currentUser?.company_id;

  const fetchSummary = useCallback(async () => {
    setIsLoadingSummary(true);
    try {
      const params = companyIdForRequests ? { company_id: companyIdForRequests } : {};
      const res = await apiClient.get('/dashboard/summary', { params });
      setSummaryData(res.data);
    } catch (err) {
      console.error("Error fetching summary:", err.response || err);
      setError(prev => prev || (err.response?.data?.error || 'Failed to load summary data.'));
      setSummaryData(null);
    } finally {
      setIsLoadingSummary(false);
    }
  }, [companyIdForRequests]);

  const fetchStatistics = useCallback(async () => {
    setIsLoadingStatistics(true);
    setStatsError('');
    try {
      const data = await getDashboardStatistics(companyIdForRequests);
      setStatisticsData(data);
    } catch (err) {
      console.error("Error fetching statistics:", err.response || err);
      setStatsError(err.response?.data?.error || err.message || 'Failed to load statistics.');
      setStatisticsData(null);
    } finally {
      setIsLoadingStatistics(false);
    }
  }, [companyIdForRequests]);

  const fetchCandidates = useCallback(async (page = 1, query = searchTerm) => {
    setIsLoadingList(true);
    try {
      const statusToFetch = 'NeedsReview';
      const params = {
        page,
        per_page: ITEMS_PER_PAGE_DASH
      };
      if (companyIdForRequests) {
        params.company_id = companyIdForRequests;
      }

      let response;
      if (query) {
        params.q = encodeURIComponent(query);
        response = await apiClient.get('/search', { params });
      } else {
        response = await apiClient.get(`/candidates/${statusToFetch}`, { params });
      }
      
      setCandidates(Array.isArray(response.data.candidates) ? response.data.candidates : []);
      setTotalPages(response.data.total_pages || 0);
      setTotalCandidates(response.data.total_results || 0);
      setCurrentPage(response.data.current_page || 1);

    } catch (err) {
      console.error(`Error fetching ${query ? 'searched' : 'NeedsReview'} candidates:`, err.response || err);
      setError(prev => prev || (err.response?.data?.error || 'Failed to load candidates.'));
      setCandidates([]);
      setTotalPages(0);
      setTotalCandidates(0);
    } finally {
      setIsLoadingList(false);
    }
  }, [companyIdForRequests, searchTerm]);

  useEffect(() => {
    setError(null); 
    setStatsError('');
    fetchSummary();
    fetchStatistics();
    fetchCandidates(1, searchTerm);
  }, [fetchSummary, fetchStatistics, fetchCandidates, searchTerm]);

  const handleSearchChange = (event) => setSearchTerm(event.target.value);
  
  const handleSearchSubmit = (event) => {
    if (event) event.preventDefault();
    setCurrentPage(1);
    fetchCandidates(1, searchTerm);
  };

  const handlePageChange = (newPage) => {
    if (newPage >= 1 && newPage <= totalPages) {
      fetchCandidates(newPage, searchTerm);
    }
  };

  const handleUploadSuccess = () => {
    console.log("Upload success detected in Dashboard, refreshing data...");
    setTimeout(() => {
      fetchSummary();
      fetchStatistics();
      fetchCandidates(1, searchTerm); 
    }, 1800);
  };
  
  const handleCandidateDeleted = (deletedCandidateId) => {
    setCandidates(prevCandidates => prevCandidates.filter(c => c.candidate_id !== deletedCandidateId));
    setTotalCandidates(prevTotal => prevTotal > 0 ? prevTotal -1 : 0);
    fetchSummary();
    fetchStatistics();
  };

  // Styles (μπορείς να τα μεταφέρεις σε CSS αρχείο)
  const pageStyles = {
    padding: '20px',
    // maxWidth: '1200px', // Μπορείς να το επαναφέρεις αν θέλεις μέγιστο πλάτος
    // margin: '0 auto',
  };

  const sectionTitleStyles = {
    marginTop: '2rem',
    marginBottom: '1.5rem',
    fontSize: '1.5rem', // Λίγο πιο μικρό για να ταιριάζει
    color: '#334155',
    borderBottom: '1px solid #e2e8f0',
    paddingBottom: '0.5rem',
  };

  const topSectionContainerStyles = {
    display: 'flex',
    flexDirection: 'row',
    gap: '24px',
    alignItems: 'flex-start',
    marginBottom: '24px',
  };

  const summaryContainerStyles = {
    flex: 3, 
    minWidth: 0,
  };

  const statsContainerStyles = {
    flex: 2, 
    minWidth: 0,
    padding: '20px',
    backgroundColor: '#ffffff',
    borderRadius: '8px',
    boxShadow: '0 2px 4px rgba(0,0,0,0.05)', // Πιο διακριτική σκιά
  };

  const cardStyles = { // Γενικό στυλ για "κάρτες"
    backgroundColor: '#ffffff',
    borderRadius: '8px',
    padding: '20px',
    boxShadow: '0 2px 4px rgba(0,0,0,0.05)',
    marginBottom: '1.5rem',
  };


  return (
    <div style={pageStyles} className="dashboard-page-container">
      {error && <div className="error-message" style={{...cardStyles, color: 'red', textAlign: 'center'}}>{error}</div>}
      
      <div style={topSectionContainerStyles} className="dashboard-top-row">
        <div style={summaryContainerStyles} className="dashboard-summary-wrapper">
          {isLoadingSummary ? (
            <div className="loading-placeholder" style={cardStyles}>Loading summary...</div>
          ) : (
            summaryData && <DashboardSummary summary={summaryData} /> /* Το DashboardSummary θα πρέπει να έχει το δικό του card-style */
          )}
        </div>
        <div style={statsContainerStyles} className="dashboard-statistics-wrapper">
          <h3 style={{ marginTop: 0, marginBottom: '1rem', fontSize: '1.15rem', color: '#475569', fontWeight: 600 }}>Key Statistics</h3>
          <StatisticsDisplay stats={statisticsData} isLoading={isLoadingStatistics} error={statsError} />
        </div>
      </div>
      
      <div className="upload-section" style={cardStyles}>
        <h3 style={{ marginTop: 0, marginBottom: '1rem', fontSize: '1.15rem', color: '#475569', fontWeight: 600 }}>Upload New CV</h3>
        <UploadComponent onUploadSuccess={handleUploadSuccess} />
      </div>
      
      <div className="needs-review-section" style={cardStyles}>
        <h3 style={{...sectionTitleStyles, marginTop:0, fontSize: '1.25rem'}}>Candidates Needing Review</h3>
        <SearchBar
            searchTerm={searchTerm}
            onSearchChange={handleSearchChange}
            onSearchSubmit={handleSearchSubmit}
            placeholder="Search in 'Needs Review'..."
            // Μπορείς να προσθέσεις inputClassName και buttonClassName αν χρειάζεται
        />
        {isLoadingList && <p className="loading-placeholder" style={{marginTop: '1rem'}}>Loading candidates...</p>}
        
        {!isLoadingList && !error && candidates.length === 0 && searchTerm && (
              <p style={{ textAlign: 'center', marginTop: '1rem', color: '#64748b' }}>No candidates found matching '{searchTerm}' in Needs Review.</p>
        )}
        {!isLoadingList && !error && candidates.length === 0 && !searchTerm && (
              <p style={{ textAlign: 'center', marginTop: '1rem', color: '#64748b' }}>No candidates currently need review.</p>
        )}

        {!isLoadingList && !error && candidates.length > 0 && (
          <CandidateList 
              candidates={candidates} 
              onCandidateDeleted={handleCandidateDeleted}
          />
        )}
        
        {!isLoadingList && totalPages > 1 && (
          <div className="pagination-controls" style={{ marginTop: '1.5rem', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '10px' }}>
            <button onClick={() => handlePageChange(currentPage - 1)} disabled={currentPage === 1 || isLoadingList} className="button-action button-secondary">Previous</button>
            <span style={{ color: '#475569', fontSize: '0.9rem' }}>Page {currentPage} of {totalPages} (Total: {totalCandidates})</span>
            <button onClick={() => handlePageChange(currentPage + 1)} disabled={currentPage === totalPages || isLoadingList} className="button-action button-secondary">Next</button>
          </div>
        )}
      </div>
    </div>
  );
}

export default DashboardPage;