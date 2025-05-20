// frontend/src/services/companyAdminService.js
import apiClient from '../api'; 

export const getCompanyUsers = async (params) => {
  try {
    const response = await apiClient.get('/company/users', { params });
    return response.data;
  } catch (error) {
    console.error('Error fetching company users:', error.response?.data || error.message);
    throw error.response?.data || { error: error.message || 'Failed to fetch company users' };
  }
};

export const createCompanyUser = async (userData) => {
  try {
    const response = await apiClient.post('/company/users', userData);
    return response.data;
  } catch (error) {
    console.error('Error creating company user:', error.response?.data || error.message);
    throw error.response?.data || { error: error.message || 'Failed to create user' };
  }
};

export const toggleCompanyUserStatus = async (userId, isActive) => {
  try {
    const response = await apiClient.put(`/company/users/${userId}/status`, { is_active: isActive });
    return response.data;
  } catch (error) {
    console.error(`Error toggling user ${userId} status:`, error.response?.data || error.message);
    throw error.response?.data || { error: error.message || 'Failed to update user status' };
  }
};

export const deleteCompanyUser = async (userId) => {
  try {
    const response = await apiClient.delete(`/company/users/${userId}`);
    return response.data; 
  } catch (error) {
    console.error(`Error deleting company user ${userId}:`, error.response?.data || error.message);
    throw error.response?.data || { error: error.message || 'Failed to delete user' };
  }
};

// --- ΝΕΑ ΣΥΝΑΡΤΗΣΗ ΠΟΥ ΠΡΟΣΤΕΘΗΚΕ ---
export const getCompanyInterviews = async (params) => {
  // Το params μπορεί να περιέχει page, per_page, status_filter, company_id (για superadmin)
  // Το backend endpoint είναι /api/v1/company/interviews
  try {
    const response = await apiClient.get('/company/interviews', { params });
    return response.data; // Αναμένουμε { interviews: [...], total_interviews: X, ... }
  } catch (error) {
    console.error('Error fetching company interviews:', error.response?.data || error.message);
    throw error.response?.data || { error: error.message || 'Failed to fetch company interviews' };
  }
};
// --- ΤΕΛΟΣ ΝΕΑΣ ΣΥΝΑΡΤΗΣΗΣ ---