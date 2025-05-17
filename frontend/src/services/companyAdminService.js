// frontend/src/services/companyAdminService.js
import apiClient from '../api'; // Ο βασικός σου apiClient από το src/api.js - ΜΟΝΟ ΜΙΑ ΦΟΡΑ ΤΟ IMPORT

const COMPANY_API_PREFIX = '/company'; // Το prefix όπως ορίζεται στο backend για τα company admin routes

/**
 * Fetches a list of users for the currently authenticated company admin's company.
 * @param {object} params - Optional query parameters (e.g., { page: 1, per_page: 10 })
 * @returns {Promise<object>} A promise that resolves to an object containing users list and pagination info.
 */
export const getCompanyUsers = async (params = {}) => {
  try {
    const response = await apiClient.get(`${COMPANY_API_PREFIX}/users`, { params });
    return response.data;
  } catch (error) {
    console.error("Error fetching company users (companyAdminService):", error.response || error.message || error);
    throw error.response?.data || new Error(error.message || "Failed to fetch company users");
  }
};

/**
 * Creates a new user (typically with 'user' role) for the company admin's company.
 * @param {object} userData - Data for the new user (username, email, password).
 * @returns {Promise<object>} A promise that resolves to the newly created user object.
 */
export const createCompanyUser = async (userData) => {
  if (!userData || !userData.username || !userData.email || !userData.password) {
    const err = { error: "Username, email, and password are required." };
    console.error("Error creating company user (companyAdminService): Invalid userData", userData);
    throw err;
  }
  try {
    const response = await apiClient.post(`${COMPANY_API_PREFIX}/users`, userData);
    return response.data;
  } catch (error) {
    console.error("Error creating company user (companyAdminService):", error.response || error.message || error);
    throw error.response?.data || new Error(error.message || "Failed to create company user");
  }
};

/**
 * Toggles the active status of a user within the company admin's company.
 * @param {number|string} userId - The ID of the user whose status to toggle.
 * @param {boolean} isActive - The new desired active status (true or false).
 * @returns {Promise<object>} A promise that resolves to the updated user object.
 */
export const toggleCompanyUserStatus = async (userId, isActive) => {
  if (userId === undefined || typeof isActive !== 'boolean') {
    const err = { error: "User ID and a boolean active status are required." };
    console.error("Error toggling user status (companyAdminService): Invalid parameters", { userId, isActive });
    throw err;
  }
  try {
    const response = await apiClient.put(`${COMPANY_API_PREFIX}/users/${userId}/status`, { is_active: isActive });
    return response.data;
  } catch (error) {
    console.error(`Error toggling status for user ID ${userId} (companyAdminService):`, error.response || error.message || error);
    throw error.response?.data || new Error(error.message || `Failed to toggle status for user ${userId}`);
  }
};

/**
 * Fetches a list of interviews for the company.
 * Accessible by company admins or superadmins (if company_id is provided).
 * @param {object} params - Optional query parameters (e.g., { page: 1, per_page: 15, status: 'SCHEDULED', company_id: X (for superadmin) })
 * @returns {Promise<object>} A promise that resolves to an object containing interviews list and pagination info.
 */
export const getCompanyInterviews = async (params = {}) => {
  try {
    const response = await apiClient.get(`${COMPANY_API_PREFIX}/interviews`, { params });
    return response.data;
  } catch (error) {
    console.error("Error fetching company interviews (companyAdminService):", error.response || error.message || error);
    throw error.response?.data || new Error(error.message || "Failed to fetch company interviews");
  }
};