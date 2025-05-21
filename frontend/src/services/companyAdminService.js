// frontend/src/services/companyAdminService.js
import apiClient from '../api'; // Your pre-configured Axios instance

const COMPANY_API_PREFIX = '/company'; // Matches blueprint prefix in Flask

// === User Management ===
export const getCompanyUsers = async (params) => {
  try {
    const response = await apiClient.get(`${COMPANY_API_PREFIX}/users`, { params });
    return response.data;
  } catch (error) {
    console.error('Error fetching company users:', error.response?.data || error.message);
    throw error.response?.data || { error: error.message || 'Failed to fetch company users' };
  }
};

export const createCompanyUser = async (userData) => {
  try {
    const response = await apiClient.post(`${COMPANY_API_PREFIX}/users`, userData);
    return response.data;
  } catch (error) {
    console.error('Error creating company user:', error.response?.data || error.message);
    throw error.response?.data || { error: error.message || 'Failed to create user' };
  }
};

export const toggleCompanyUserStatus = async (userId, isActive) => {
  try {
    const response = await apiClient.put(`${COMPANY_API_PREFIX}/users/${userId}/status`, { is_active: isActive });
    return response.data;
  } catch (error) {
    console.error(`Error toggling user ${userId} status:`, error.response?.data || error.message);
    throw error.response?.data || { error: error.message || 'Failed to update user status' };
  }
};

export const deleteCompanyUser = async (userId) => {
  try {
    const response = await apiClient.delete(`${COMPANY_API_PREFIX}/users/${userId}`);
    return response.data;
  } catch (error) {
    console.error(`Error deleting company user ${userId}:`, error.response?.data || error.message);
    throw error.response?.data || { error: error.message || 'Failed to delete user' };
  }
};

// === Company Interviews ===
export const getCompanyInterviews = async (params = {}) => {
  try {
    const response = await apiClient.get(`${COMPANY_API_PREFIX}/interviews`, { params });
    return response.data;
  } catch (error) {
    console.error('Error fetching company interviews:', error.response?.data || error.message);
    throw error.response?.data || { error: error.message || 'Failed to fetch company interviews' };
  }
};

// === Branch Management ===
export const getBranches = async (companyIdForSuperadmin = null) => {
    try {
        const params = {};
        if (companyIdForSuperadmin) {
            params.company_id = companyIdForSuperadmin;
        }
        const response = await apiClient.get(`${COMPANY_API_PREFIX}/branches`, { params });
        return response.data;
    } catch (error) {
        console.error("Error fetching branches:", error.response?.data || error.message);
        throw error.response?.data || { error: "Network error or server is down while fetching branches." };
    }
};

export const createBranch = async (branchData) => {
    try {
        const response = await apiClient.post(`${COMPANY_API_PREFIX}/branches`, branchData);
        return response.data;
    } catch (error) {
        console.error("Error creating branch:", error.response?.data || error.message);
        throw error.response?.data || { error: "Failed to create branch." };
    }
};

export const updateBranch = async (branchId, branchData) => {
    try {
        const response = await apiClient.put(`${COMPANY_API_PREFIX}/branches/${branchId}`, branchData);
        return response.data;
    } catch (error) {
        console.error(`Error updating branch ${branchId}:`, error.response?.data || error.message);
        throw error.response?.data || { error: "Failed to update branch." };
    }
};

export const deleteBranch = async (branchId) => {
    try {
        const response = await apiClient.delete(`${COMPANY_API_PREFIX}/branches/${branchId}`);
        return response.data;
    } catch (error) {
        console.error(`Error deleting branch ${branchId}:`, error.response?.data || error.message);
        throw error.response?.data || { error: "Failed to delete branch." };
    }
};

// === Position Management (ΝΕΕΣ ΣΥΝΑΡΤΗΣΕΙΣ) ===
/**
 * Fetches a list of positions for the company.
 * Company Admins get positions for their own company.
 * Superadmins must provide company_id in params to specify which company's positions to fetch.
 * @param {object} params - Query parameters (e.g., { company_id: X, page: Y, per_page: Z, status: 'Open' })
 * @returns {Promise<object>} A promise that resolves to an object containing positions list and pagination info.
 */
export const getCompanyPositions = async (params = {}) => {
    try {
        // The backend /company/positions now handles company_id for superadmin if provided in params.
        // For company_admin, backend uses current_user.company_id automatically.
        const response = await apiClient.get(`${COMPANY_API_PREFIX}/positions`, { params });
        // Expected: { positions: [...], total_positions: X, total_pages: Y, current_page: Z }
        return response.data;
    } catch (error) {
        console.error('Error fetching company positions:', error.response?.data || error.message);
        throw error.response?.data || { error: error.message || 'Failed to fetch company positions' };
    }
};

/**
 * Fetches a single position by its ID.
 * Access control is handled by the backend.
 * @param {number} positionId - The ID of the position to fetch.
 * @returns {Promise<object>} A promise that resolves to the position object.
 */
export const getPositionById = async (positionId) => {
    try {
        const response = await apiClient.get(`${COMPANY_API_PREFIX}/positions/${positionId}`);
        return response.data; // Expected: position object
    } catch (error) {
        console.error(`Error fetching position ${positionId}:`, error.response?.data || error.message);
        throw error.response?.data || { error: `Failed to fetch position ${positionId}` };
    }
};

/**
 * Creates a new position for the company admin's company.
 * @param {object} positionData - Data for the new position (e.g., { position_name: "...", description: "...", status: "Open" }).
 *                                 company_id is handled by the backend for company_admin.
 * @returns {Promise<object>} A promise that resolves to the newly created position object.
 */
export const createPosition = async (positionData) => {
    try {
        const response = await apiClient.post(`${COMPANY_API_PREFIX}/positions`, positionData);
        return response.data; // Expected: new position object
    } catch (error) {
        console.error('Error creating position:', error.response?.data || error.message);
        throw error.response?.data || { error: 'Failed to create position' };
    }
};

/**
 * Updates an existing position.
 * Access control (ensuring company_admin owns the position) is handled by the backend.
 * @param {number} positionId - The ID of the position to update.
 * @param {object} positionData - The data to update the position with.
 * @returns {Promise<object>} A promise that resolves to the updated position object.
 */
export const updatePosition = async (positionId, positionData) => {
    try {
        const response = await apiClient.put(`${COMPANY_API_PREFIX}/positions/${positionId}`, positionData);
        return response.data; // Expected: updated position object
    } catch (error) {
        console.error(`Error updating position ${positionId}:`, error.response?.data || error.message);
        throw error.response?.data || { error: `Failed to update position ${positionId}` };
    }
};

/**
 * Deletes a position.
 * Access control is handled by the backend.
 * @param {number} positionId - The ID of the position to delete.
 * @returns {Promise<object>} A promise that resolves to a success message.
 */
export const deletePosition = async (positionId) => {
    try {
        const response = await apiClient.delete(`${COMPANY_API_PREFIX}/positions/${positionId}`);
        return response.data; // Expected: { message: "Position deleted successfully" }
    } catch (error) {
        console.error(`Error deleting position ${positionId}:`, error.response?.data || error.message);
        throw error.response?.data || { error: `Failed to delete position ${positionId}` };
    }
};


const companyAdminService = {
    getCompanyUsers,
    createCompanyUser,
    toggleCompanyUserStatus,
    deleteCompanyUser,
    getCompanyInterviews,
    getBranches,
    createBranch,
    updateBranch,
    deleteBranch,
    // Position functions
    getCompanyPositions,
    getPositionById,
    createPosition,
    updatePosition,
    deletePosition,
};

export default companyAdminService;