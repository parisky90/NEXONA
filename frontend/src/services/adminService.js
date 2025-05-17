// frontend/src/services/adminService.js
import axios from 'axios';

// Βάση URL για τα admin endpoints
// Δεδομένου ότι το Vite proxy χειρίζεται το /api/v1, και το admin blueprint στο backend
// είναι κάτω από /api/v1/admin, το baseURL εδώ πρέπει να είναι σχετικό.
const ADMIN_API_BASE_URL = '/api/v1/admin'; // Αυτό θα προωθηθεί από το Vite proxy στο http://localhost:5001/api/v1/admin

const adminApiClient = axios.create({
  baseURL: ADMIN_API_BASE_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

adminApiClient.interceptors.response.use(
  response => response,
  error => {
    console.error("Admin API call error:", error.response || error.message || error);
    if (error.response && (error.response.status === 401 || error.response.status === 403)) {
        console.warn("Admin API returned 401/403, consider user logout or redirect.");
        // Εδώ μπορείς να προσθέσεις λογική για logout ή ανακατεύθυνση
        // window.dispatchEvent(new Event('auth-error-admin'));
    }
    // Επέστρεψε το error object όπως είναι ή το data του αν υπάρχει, για να το χειριστεί ο καλών
    return Promise.reject(error.response?.data || new Error(error.message || "Admin API request failed"));
  }
);

/**
 * Fetches a list of all companies.
 * Requires superadmin authentication.
 * @returns {Promise<Array>} A promise that resolves to an array of company objects.
 * @throws Will throw an error if the request fails.
 */
export const getCompanies = async () => {
  try {
    // Το URL είναι σχετικό με το baseURL του adminApiClient, άρα καλεί /api/v1/admin/companies
    const response = await adminApiClient.get('/companies');
    return response.data;
  } catch (error) {
    // Το error εδώ είναι ήδη το error.response.data ή ένα νέο Error object από τον interceptor
    console.error("Error fetching companies (adminService):", error);
    throw error; // Re-throw το επεξεργασμένο error
  }
};

export const getCompanyInterviews = async (params = {}) => {
  try {
    // Το URL θα είναι /api/v1/company/interviews
    const response = await apiClient.get(`${COMPANY_API_PREFIX}/interviews`, { params });
    return response.data;
  } catch (error) {
    console.error("Error fetching company interviews:", error.response || error.message || error);
    throw error.response?.data || new Error(error.message || "Failed to fetch company interviews");
  }
};

/**
 * Creates a new company.
 * Requires superadmin authentication.
 * @param {object} companyData - The data for the new company. Expected: { name: "Company Name" }
 * @returns {Promise<object>} A promise that resolves to the newly created company object.
 * @throws Will throw an error if the request fails.
 */
export const createCompany = async (companyData) => {
  if (!companyData || !companyData.name || typeof companyData.name !== 'string' || companyData.name.trim() === '') {
    const err = { error: "Company name is required and must be a non-empty string." }; // Δημιούργησε ένα error object
    console.error("Error creating company (adminService): Invalid companyData", companyData);
    throw err; // Κάνε throw το error object
  }
  try {
    // Καλεί /api/v1/admin/companies
    const response = await adminApiClient.post('/companies', companyData);
    return response.data;
  } catch (error) {
    console.error("Error creating company (adminService):", error);
    throw error;
  }
};

/**
 * Fetches a list of all users (superadmin view).
 * Requires superadmin authentication.
 * @param {object} params - Optional query parameters (e.g., { page: 1, per_page: 10, role: 'user', company_id: 1 })
 * @returns {Promise<object>} A promise that resolves to an object containing users list and pagination info.
 */
export const getAllUsers = async (params = {}) => {
  try {
    // Καλεί /api/v1/admin/users
    const response = await adminApiClient.get('/users', { params });
    return response.data;
  } catch (error) {
    console.error("Error fetching all users (adminService):", error);
    throw error;
  }
};

/**
 * Creates a new user by a superadmin.
 * Requires superadmin authentication.
 * @param {object} userData - Data for the new user.
 * @returns {Promise<object>} A promise that resolves to the newly created user object.
 */
export const createUserBySuperadmin = async (userData) => {
  // Πρόσθεσε ελέγχους για το userData αν χρειάζεται (π.χ. username, email, password)
  try {
    // Καλεί /api/v1/admin/users
    const response = await adminApiClient.post('/users', userData);
    return response.data;
  } catch (error) {
    console.error("Error creating user by superadmin (adminService):", error);
    throw error;
  }
};

// Θα μπορούσες να προσθέσεις και τις υπόλοιπες admin service functions εδώ, όπως:
// getCompanyById, updateCompany, getUserByIdBySuperadmin, updateUserBySuperadmin, deleteUserBySuperadmin κλπ.
// Όλες θα χρησιμοποιούν το adminApiClient και τα paths τους θα είναι σχετικά με το /api/v1/admin.
// Παράδειγμα:
// export const updateCompany = async (companyId, companyData) => {
//   try {
//     const response = await adminApiClient.put(`/companies/${companyId}`, companyData);
//     return response.data;
//   } catch (error) {
//     console.error(`Error updating company ${companyId} (adminService):`, error);
//     throw error;
//   }
// };