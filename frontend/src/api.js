// frontend/src/api.js
import axios from 'axios';

const getApiBaseUrl = () => {
    if (import.meta.env.DEV) {
        return 'http://localhost:5001/api/v1';
    } else {
        return '/api/v1';
    }
};

const apiClient = axios.create({
    baseURL: getApiBaseUrl(),
    withCredentials: true,
    headers: {
        'Content-Type': 'application/json',
    },
});

apiClient.interceptors.response.use(
    response => response,
    error => {
        console.error("API call error:", error.response || error.message || error);
        return Promise.reject(error);
    }
);

// --- ΥΠΑΡΧΟΥΣΑ ΣΥΝΑΡΤΗΣΗ ---
export const uploadCV = (formData) => {
    return apiClient.post('/upload', formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
    });
};

// --- ΝΕΑ ΣΥΝΑΡΤΗΣΗ ΓΙΑ DASHBOARD STATISTICS ---
/**
 * Fetches dashboard statistics.
 * @param {number|string|null} companyId - Optional company ID to filter statistics (for superadmin).
 * @returns {Promise<object>} A promise that resolves to the statistics object.
 */
export const getDashboardStatistics = async (companyId = null) => {
  try {
    const params = companyId ? { company_id: companyId } : {};
    // Το endpoint είναι /api/v1/dashboard/statistics
    const response = await apiClient.get('/dashboard/statistics', { params });
    return response.data;
  } catch (error) {
    // Ο interceptor θα κάνει log το error, εδώ απλά το κάνουμε re-throw
    // ή μπορούμε να κάνουμε throw ένα πιο συγκεκριμένο error object για το UI
    throw error.response?.data || new Error(error.message || "Failed to fetch dashboard statistics");
  }
};
// --- ΤΕΛΟΣ ΝΕΑΣ ΣΥΝΑΡΤΗΣΗΣ ---


export default apiClient;