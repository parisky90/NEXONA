// frontend/src/pages/CompanyBranchesPage.jsx
import React, { useState, useEffect, useCallback } from 'react';
import companyAdminService from '../services/companyAdminService';
import ModalDialog from '../components/ModalDialog'; // Υποθέτουμε ότι υπάρχει αυτό το component
import { useAuth } from '../App'; // Για να πάρουμε το currentUser για έλεγχο ρόλου
// import './CompanyBranchesPage.css'; // Δημιούργησε και εισήγαγε αν χρειάζονται custom styles

const CompanyBranchesPage = () => {
    const { currentUser } = useAuth();
    const [branches, setBranches] = useState([]);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);
    const [notification, setNotification] = useState('');

    const [isModalOpen, setIsModalOpen] = useState(false);
    const [currentBranch, setCurrentBranch] = useState(null); // For editing or null for creating
    const [formData, setFormData] = useState({ name: '', address: '', city: '' });
    const [formErrors, setFormErrors] = useState({});

    const fetchBranchesForCurrentCompany = useCallback(async () => {
        if (!currentUser || currentUser.role !== 'company_admin') {
            setError("Access Denied. You must be a Company Admin.");
            setBranches([]);
            setIsLoading(false);
            return;
        }
        setIsLoading(true);
        setError(null);
        try {
            // Το companyAdminService.getBranches δεν χρειάζεται companyId για company_admin
            // καθώς το backend το παίρνει από το session.
            const data = await companyAdminService.getBranches();
            setBranches(data || []);
        } catch (err) {
            setError(err.error || 'Failed to fetch branches. Please try again.');
            console.error("Fetch branches error:", err);
            setBranches([]);
        } finally {
            setIsLoading(false);
        }
    }, [currentUser]);

    useEffect(() => {
        fetchBranchesForCurrentCompany();
    }, [fetchBranchesForCurrentCompany]);

    const clearNotificationAfterDelay = () => {
        setTimeout(() => {
            setNotification('');
            setError(''); // Καθάρισε και το error αν υπάρχει, για να μην μείνει μόνιμα
        }, 5000);
    };

    const handleInputChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => ({ ...prev, [name]: value }));
        if (formErrors[name]) {
            setFormErrors(prev => ({ ...prev, [name]: null }));
        }
    };

    const validateForm = () => {
        const errors = {};
        if (!formData.name.trim()) errors.name = "Branch name is required.";
        // Add other validations if needed
        setFormErrors(errors);
        return Object.keys(errors).length === 0;
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!validateForm()) return;

        setIsLoading(true);
        setError(null);
        setNotification('');

        try {
            let responseMessage = '';
            if (currentBranch && currentBranch.id) { // Editing
                await companyAdminService.updateBranch(currentBranch.id, formData);
                responseMessage = 'Branch updated successfully!';
            } else { // Creating
                await companyAdminService.createBranch(formData);
                responseMessage = 'Branch created successfully!';
            }
            setNotification(responseMessage);
            setIsModalOpen(false);
            fetchBranchesForCurrentCompany(); 
        } catch (err) {
            console.error("Submit branch error:", err);
            setError(err.error || `Failed to ${currentBranch?.id ? 'update' : 'create'} branch.`);
        } finally {
            setIsLoading(false);
            clearNotificationAfterDelay();
        }
    };

    const openModalForCreate = () => {
        setCurrentBranch(null);
        setFormData({ name: '', address: '', city: '' });
        setFormErrors({});
        setError(null); // Clear previous errors
        setNotification('');
        setIsModalOpen(true);
    };

    const openModalForEdit = (branch) => {
        setCurrentBranch(branch);
        setFormData({ 
            name: branch.name, 
            address: branch.address || '', 
            city: branch.city || '', 
        });
        setFormErrors({});
        setError(null); // Clear previous errors
        setNotification('');
        setIsModalOpen(true);
    };

    const handleDeleteBranch = async (branchId, branchName) => {
        if (window.confirm(`Are you sure you want to delete the branch "${branchName}"? This action cannot be undone.`)) {
            setIsLoading(true);
            setError(null);
            setNotification('');
            try {
                const response = await companyAdminService.deleteBranch(branchId);
                setNotification(response.message || 'Branch deleted successfully!');
                fetchBranchesForCurrentCompany(); 
            } catch (err) {
                console.error("Delete branch error:", err);
                setError(err.error || 'Failed to delete branch. It might be associated with candidates or other records.');
            } finally {
                setIsLoading(false);
                clearNotificationAfterDelay();
            }
        }
    };
    
    if (!currentUser || (currentUser.role !== 'company_admin' && !isLoading)) {
      return <div className="admin-page-container card-style error-message">Access Denied. Only Company Admins can manage branches.</div>;
    }

    return (
        <div className="admin-page-container card-style"> {/* Using admin-page-container for consistent styling */}
            <h2 style={{textAlign: 'center', marginBottom: '1.5rem'}}>Manage Company Branches</h2>
            
            {notification && <div className="notification is-success" role="alert">{notification}</div>}
            {error && !isModalOpen && <div className="notification is-danger" role="alert">{error}</div>} {/* Don't show global error if modal has its own */}

            <div style={{marginBottom: '1.5rem'}}>
                <button 
                    onClick={openModalForCreate} 
                    className="button-action button-primary"
                    disabled={isLoading}
                >
                    + Add New Branch
                </button>
            </div>

            {isLoading && branches.length === 0 && <div className="loading-placeholder">Loading branches...</div>}
            {!isLoading && branches.length === 0 && !error && <p style={{textAlign: 'center'}}>No branches found. Add one to get started!</p>}

            {branches.length > 0 && (
                <div className="table-responsive">
                    <table className="candidate-table"> {/* Re-use existing table style if suitable */}
                        <thead>
                            <tr>
                                <th>Name</th>
                                <th>City</th>
                                <th>Address</th>
                                <th style={{textAlign: 'center'}}>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {branches.map(branch => (
                                <tr key={branch.id}>
                                    <td>{branch.name}</td>
                                    <td>{branch.city || 'N/A'}</td>
                                    <td>{branch.address || 'N/A'}</td>
                                    <td style={{textAlign: 'center'}}>
                                        <button 
                                            onClick={() => openModalForEdit(branch)}
                                            className="button-action button-edit"
                                            disabled={isLoading}
                                            style={{marginRight: '5px'}}
                                        >
                                            Edit
                                        </button>
                                        <button 
                                            onClick={() => handleDeleteBranch(branch.id, branch.name)}
                                            className="button-action button-reject" // Using reject style for delete
                                            disabled={isLoading}
                                        >
                                            Delete
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {isModalOpen && (
                <ModalDialog isOpen={isModalOpen} onClose={() => !isLoading && setIsModalOpen(false)} title={currentBranch?.id ? 'Edit Branch' : 'Create New Branch'}>
                    <form onSubmit={handleSubmit}>
                        {error && isModalOpen && <p className="error-message" style={{color:'red', marginBottom:'10px'}}>{error}</p>} {/* Modal specific error */}
                        <div className="form-group">
                            <label htmlFor="name">Branch Name <span style={{color:'red'}}>*</span></label>
                            <input
                                type="text"
                                id="name"
                                name="name"
                                value={formData.name}
                                onChange={handleInputChange}
                                className={`input-light-gray ${formErrors.name ? 'is-danger' : ''}`}
                                required
                                disabled={isLoading}
                            />
                            {formErrors.name && <p className="help is-danger">{formErrors.name}</p>}
                        </div>
                        <div className="form-group">
                            <label htmlFor="city">City</label>
                            <input
                                type="text"
                                id="city"
                                name="city"
                                value={formData.city}
                                onChange={handleInputChange}
                                className="input-light-gray"
                                disabled={isLoading}
                            />
                        </div>
                        <div className="form-group">
                            <label htmlFor="address">Address</label>
                            <input
                                type="text"
                                id="address"
                                name="address"
                                value={formData.address}
                                onChange={handleInputChange}
                                className="input-light-gray"
                                disabled={isLoading}
                            />
                        </div>
                        <div className="form-actions" style={{marginTop: '1.5rem', textAlign: 'right'}}>
                            <button 
                                type="button" 
                                onClick={() => setIsModalOpen(false)} 
                                className="button-action button-secondary"
                                disabled={isLoading}
                                style={{marginRight: '10px'}}
                            >
                                Cancel
                            </button>                            
                            <button 
                                type="submit" 
                                className="button-action button-primary"
                                disabled={isLoading}
                            >
                                {isLoading ? 'Saving...' : (currentBranch?.id ? 'Update Branch' : 'Create Branch')}
                            </button>
                        </div>
                    </form>
                </ModalDialog>
            )}
        </div>
    );
};

export default CompanyBranchesPage;