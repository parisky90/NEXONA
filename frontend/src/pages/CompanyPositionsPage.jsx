// frontend/src/pages/CompanyPositionsPage.jsx
import React, { useState, useEffect, useCallback } from 'react';
import companyAdminService from '../services/companyAdminService';
import { useAuth } from '../App';
import ModalDialog from '../components/ModalDialog';
import './CompanyPositionsPage.css'; // Θα χρειαστεί να δημιουργηθεί αυτό το CSS

const POSITION_STATUS_OPTIONS = ['Open', 'Closed', 'On Hold'];

function CompanyPositionsPage() {
  const { currentUser } = useAuth();
  const [positions, setPositions] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  
  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalPositions, setTotalPositions] = useState(0);
  const itemsPerPage = 10; // Ή ό,τι άλλο επιλέξεις

  // Modal state
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [currentPosition, setCurrentPosition] = useState(null); // null for create, object for edit
  const [modalMode, setModalMode] = useState('create'); // 'create' or 'edit'
  const [positionFormData, setPositionFormData] = useState({
    position_name: '',
    description: '',
    status: 'Open',
  });

  // Filter state
  const [statusFilter, setStatusFilter] = useState(''); // Empty string for 'All'

  const fetchPositions = useCallback(async (page = 1, filterStatus = '') => {
    setIsLoading(true);
    setError(null);
    try {
      const params = {
        page,
        per_page: itemsPerPage,
      };
      if (currentUser.role === 'superadmin' && currentUser.selectedCompanyIdForAdminView) {
         // Αν ο superadmin βλέπει αυτή τη σελίδα (π.χ. μέσω ενός dropdown επιλογής εταιρείας που δεν έχουμε φτιάξει ακόμα)
         // Θα πρέπει να περνάμε το company_id. Προς το παρόν, αυτό το route στοχεύει κυρίως τον company_admin.
         // params.company_id = currentUser.selectedCompanyIdForAdminView;
         // Για τώρα, το backend περιμένει το company_id στο query param αν είναι superadmin.
         // Αν ο superadmin δεν το στείλει, το backend route /company/positions θα επιστρέψει σφάλμα.
         // Η σελίδα αυτή είναι κυρίως για τον company_admin που το company_id του είναι γνωστό στο backend.
      }
      if (filterStatus && filterStatus !== 'All') {
        params.status = filterStatus;
      }

      const data = await companyAdminService.getCompanyPositions(params);
      setPositions(data.positions || []);
      setTotalPages(data.total_pages || 1);
      setTotalPositions(data.total_positions || 0);
      setCurrentPage(data.current_page || 1);
    } catch (err) {
      console.error("Error fetching positions:", err);
      setError(err.error || 'Failed to load positions.');
      setPositions([]);
    } finally {
      setIsLoading(false);
    }
  }, [currentUser.role]); // currentUser.selectedCompanyIdForAdminView (αν το προσθέσεις)

  useEffect(() => {
    // Ο company_admin δεν χρειάζεται να στείλει company_id, το backend το ξέρει.
    // Ο superadmin ΘΑ ΕΠΡΕΠΕ να στέλνει company_id μέσω params, αλλά αυτή η σελίδα
    // είναι σχεδιασμένη για τον company_admin προς το παρόν.
    // Αν ο superadmin καταφέρει να φτάσει εδώ χωρίς να έχει "επιλέξει" μια εταιρεία,
    // το backend endpoint /company/positions θα επιστρέψει σφάλμα.
    if (currentUser.role === 'company_admin' && !currentUser.company_id) {
        setError("Company Admin is not associated with a company.");
        setIsLoading(false);
        return;
    }
    fetchPositions(currentPage, statusFilter);
  }, [fetchPositions, currentPage, statusFilter, currentUser.role, currentUser.company_id]);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setPositionFormData(prev => ({ ...prev, [name]: value }));
  };

  const openCreateModal = () => {
    setModalMode('create');
    setCurrentPosition(null);
    setPositionFormData({ position_name: '', description: '', status: 'Open' });
    setIsModalOpen(true);
    setError(null);
  };

  const openEditModal = (position) => {
    setModalMode('edit');
    setCurrentPosition(position);
    setPositionFormData({
      position_name: position.position_name,
      description: position.description || '',
      status: position.status,
    });
    setIsModalOpen(true);
    setError(null);
  };

  const closeModal = () => {
    setIsModalOpen(false);
    setCurrentPosition(null);
    setError(null);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true); // Μπορεί να θες ξεχωριστό isLoading για το modal submit

    const payload = { ...positionFormData };

    try {
      if (modalMode === 'create') {
        await companyAdminService.createPosition(payload);
        alert('Position created successfully!');
      } else if (modalMode === 'edit' && currentPosition) {
        await companyAdminService.updatePosition(currentPosition.position_id, payload);
        alert('Position updated successfully!');
      }
      closeModal();
      fetchPositions(currentPage, statusFilter); // Refetch to show changes
    } catch (err) {
      console.error(`Error ${modalMode === 'create' ? 'creating' : 'updating'} position:`, err);
      setError(err.error || `Failed to ${modalMode === 'create' ? 'create' : 'update'} position.`);
    } finally {
      setIsLoading(false); // Επαναφορά του γενικού isLoading ή του modal isLoading
    }
  };

  const handleDeletePosition = async (positionId, positionName) => {
    if (!window.confirm(`Are you sure you want to delete position "${positionName}"? This action cannot be undone.`)) {
      return;
    }
    setError(null);
    // Μπορεί να θες ένα isDeleting state για κάθε γραμμή ή ένα γενικό
    try {
      await companyAdminService.deletePosition(positionId);
      alert(`Position "${positionName}" deleted successfully.`);
      // Refetch, ιδανικά στην ίδια σελίδα αν δεν ήταν το τελευταίο item
      if (positions.length === 1 && currentPage > 1) {
        fetchPositions(currentPage - 1, statusFilter);
      } else {
        fetchPositions(currentPage, statusFilter);
      }
    } catch (err) {
      console.error("Error deleting position:", err);
      setError(err.error || 'Failed to delete position. It might be associated with candidates or interviews.');
    }
  };
  
  const handlePageChange = (newPage) => {
    if (newPage >= 1 && newPage <= totalPages) {
      setCurrentPage(newPage);
    }
  };

  if (isLoading && positions.length === 0 && !isModalOpen) { // Show main loading only on initial load
    return <div className="loading-placeholder">Loading positions...</div>;
  }

  return (
    <div className="company-positions-page">
      <div className="page-header">
        <h1>Manage Company Positions</h1>
        <button onClick={openCreateModal} className="button-primary">
          Create New Position
        </button>
      </div>

      {error && !isModalOpen && <div className="error-message main-error">{error} <button onClick={() => setError(null)}>Dismiss</button></div>}
      
      <div className="filters-container">
        <label htmlFor="statusFilter">Filter by Status: </label>
        <select 
          id="statusFilter" 
          value={statusFilter} 
          onChange={(e) => { setStatusFilter(e.target.value); setCurrentPage(1); /* Reset page on filter change */ }}
          className="filter-select"
        >
          <option value="">All Statuses</option>
          {POSITION_STATUS_OPTIONS.map(status => (
            <option key={status} value={status}>{status}</option>
          ))}
        </select>
      </div>

      {isLoading && <div className="loading-inline">Updating list...</div>}

      {positions.length > 0 ? (
        <>
          <table className="positions-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Description</th>
                <th>Status</th>
                <th>Candidates</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {positions.map(pos => (
                <tr key={pos.position_id}>
                  <td>{pos.position_name}</td>
                  <td className="position-description">{pos.description || '-'}</td>
                  <td><span className={`status-badge-pos status-pos-${pos.status?.toLowerCase()}`}>{pos.status}</span></td>
                  <td>{pos.candidate_count !== undefined ? pos.candidate_count : 'N/A'}</td>
                  <td>
                    <button onClick={() => openEditModal(pos)} className="button-edit small-button">Edit</button>
                    <button 
                      onClick={() => handleDeletePosition(pos.position_id, pos.position_name)} 
                      className="button-reject small-button"
                      // disabled={pos.candidate_count > 0} // Απενεργοποίηση αν υπάρχουν υποψήφιοι (το backend θα το ελέγξει ούτως ή άλλως)
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="pagination-controls">
            <span>Page {currentPage} of {totalPages} (Total: {totalPositions} positions)</span>
            <button onClick={() => handlePageChange(currentPage - 1)} disabled={currentPage <= 1 || isLoading}>Previous</button>
            <button onClick={() => handlePageChange(currentPage + 1)} disabled={currentPage >= totalPages || isLoading}>Next</button>
          </div>
        </>
      ) : (
        !isLoading && <p>No positions found for this company. <button onClick={openCreateModal}>Create one now?</button></p>
      )}

      {isModalOpen && (
        <ModalDialog
          isOpen={isModalOpen}
          onClose={closeModal}
          title={modalMode === 'create' ? 'Create New Position' : `Edit Position: ${currentPosition?.position_name}`}
        >
          <form onSubmit={handleSubmit} className="position-form">
            {error && <div className="error-message modal-error">{error}</div>}
            <div className="form-group">
              <label htmlFor="position_name">Position Name <span className="required-asterisk">*</span></label>
              <input
                type="text"
                id="position_name"
                name="position_name"
                value={positionFormData.position_name}
                onChange={handleInputChange}
                required
              />
            </div>
            <div className="form-group">
              <label htmlFor="description">Description</label>
              <textarea
                id="description"
                name="description"
                value={positionFormData.description}
                onChange={handleInputChange}
                rows="4"
              />
            </div>
            <div className="form-group">
              <label htmlFor="status">Status <span className="required-asterisk">*</span></label>
              <select
                id="status"
                name="status"
                value={positionFormData.status}
                onChange={handleInputChange}
                required
              >
                {POSITION_STATUS_OPTIONS.map(opt => (
                  <option key={opt} value={opt}>{opt}</option>
                ))}
              </select>
            </div>
            <div className="form-actions">
              <button type="button" onClick={closeModal} className="button-secondary" disabled={isLoading}>Cancel</button>
              <button type="submit" className="button-primary" disabled={isLoading}>
                {isLoading ? 'Saving...' : (modalMode === 'create' ? 'Create Position' : 'Save Changes')}
              </button>
            </div>
          </form>
        </ModalDialog>
      )}
    </div>
  );
}

export default CompanyPositionsPage;