// frontend/src/services/adminService.js
import axios from 'axios'; // Εισάγουμε το axios απευθείας

// Βάση URL για τα admin endpoints, απευθείας στο backend
const ADMIN_BASE_URL = import.meta.env.DEV
  ? 'http://localhost:5001/admin' // Για development
  : '/admin';                     // Για production (αν το frontend σερβίρεται από τον ίδιο server με το /admin)
                                  // Ή το πλήρες URL του production backend /admin

const adminApiClient = axios.create({
  baseURL: ADMIN_BASE_URL,
  withCredentials: true, // Σημαντικό για session authentication
  headers: {
    'Content-Type': 'application/json',
  },
});

// Προαιρετικό: Interceptor για το adminApiClient αν χρειάζεσαι ειδικό χειρισμό
adminApiClient.interceptors.response.use(
  response => response,
  error => {
    console.error("Admin API call error:", error.response || error.message || error);
    // Εδώ θα μπορούσες να κάνεις logout τον χρήστη αν πάρεις 401/403 από admin endpoint
    if (error.response && (error.response.status === 401 || error.response.status === 403)) {
        // Ίσως να κάνεις logout ή να δείξεις ένα μήνυμα "Not Authorized"
        // Αυτό εξαρτάται από τη ροή της εφαρμογής σου
        console.warn("Admin API returned 401/403, consider user logout or redirect.");
    }
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
    // Τώρα καλεί απευθείας το /companies (το baseURL είναι /admin)
    const response = await adminApiClient.get('/companies');
    return response.data;
  } catch (error) {
    console.error("Error fetching companies (adminService):", error); // Το error εδώ θα είναι ήδη επεξεργασμένο από τον interceptor
    throw error; // Re-throw το επεξεργασμένο error
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
    const err = { error: "Company name is required and must be a non-empty string." };
    console.error("Error creating company (adminService): Invalid companyData", companyData);
    throw err;
  }
  try {
    const response = await adminApiClient.post('/companies', companyData);
    return response.data;
  } catch (error) {
    console.error("Error creating company (adminService):", error);
    throw error;
  }
};

// --- Υπόλοιπες admin service functions (getCompanyById, updateCompany, getAllUsers κλπ.) ---
// Θα χρησιμοποιούν όλες το adminApiClient και τα paths τους θα είναι σχετικά με το /admin
// Παράδειγμα:
export const getAllUsers = async (params = {}) => {
  try {
    const response = await adminApiClient.get('/users', { params });
    return response.data;
  } catch (error) {
    console.error("Error fetching all users (adminService):", error);
    throw error;
  }
};

export const createUserBySuperadmin = async (userData) => {
  try {
    const response = await adminApiClient.post('/users', userData);
    return response.data;
  } catch (error) {
    console.error("Error creating user by superadmin (adminService):", error);
    throw error;
  }
};
// Πρόσθεσε και τις updateCompany, updateUserBySuperadmin κλπ. με τον ίδιο τρόπο