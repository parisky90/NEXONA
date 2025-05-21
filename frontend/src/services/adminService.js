// frontend/src/services/adminService.js
import axios from 'axios'; // Αν δεν το έχεις ήδη, npm install axios

// Βάση URL για τα admin endpoints
// Δεδομένου ότι το Vite proxy χειρίζεται το /api/v1, και το admin blueprint στο backend
// είναι κάτω από /api/v1/admin, το baseURL εδώ πρέπει να είναι σχετικό.
const ADMIN_API_BASE_URL = '/api/v1/admin'; // Αυτό θα προωθηθεί από το Vite proxy στο http://localhost:5001/api/v1/admin

const adminApiClient = axios.create({
  baseURL: ADMIN_API_BASE_URL,
  withCredentials: true, // Σημαντικό για cookies/sessions αν χρησιμοποιούνται
  headers: {
    'Content-Type': 'application/json',
    // 'X-Requested-With': 'XMLHttpRequest', // Μπορεί να χρειαστεί για ορισμένα CSRF setups
  },
});

// Interceptor για responses - για κεντρικό χειρισμό σφαλμάτων ή logging
adminApiClient.interceptors.response.use(
  response => response, // Αν η απάντηση είναι ΟΚ, απλά την επιστρέφει
  error => {
    // Κάνε log το σφάλμα για debugging
    console.error("Admin API call error:", error.response || error.message || error);

    // Έλεγχος για συγκεκριμένους κωδικούς σφάλματος (π.χ., 401 Unauthorized, 403 Forbidden)
    if (error.response && (error.response.status === 401 || error.response.status === 403)) {
        // Εδώ θα μπορούσες να κάνεις trigger ένα event για logout, ή να ανακατευθύνεις τον χρήστη.
        // Π.χ., window.location.href = '/login';
        // ή αν έχεις ένα global event bus/context για auth:
        // window.dispatchEvent(new CustomEvent('auth-error-admin', { detail: error.response.data }));
        console.warn(`Admin API returned ${error.response.status}. User might need to re-authenticate or lacks permissions.`);
    }
    
    // Επέστρεψε το error object (ή το data του αν υπάρχει) για να το χειριστούν οι callers.
    // Προτιμάμε να επιστρέφουμε το error.response.data αν υπάρχει, αλλιώς το error.message.
    return Promise.reject(error.response?.data || new Error(error.message || "Admin API request failed"));
  }
);


/**
 * Fetches a list of all companies.
 * Requires superadmin authentication.
 * @returns {Promise<Array>} A promise that resolves to an array of company objects.
 * @throws Will throw an error (το επεξεργασμένο error από τον interceptor) if the request fails.
 */
export const getCompanies = async () => {
  try {
    const response = await adminApiClient.get('/companies');
    return response.data; // Περιμένουμε ότι το response.data είναι ο πίνακας των εταιρειών
  } catch (error) {
    // Ο interceptor έχει ήδη κάνει log το error και το έχει επεξεργαστεί.
    // Εδώ απλά το ξανακάνουμε throw για να το πιάσει ο καλών.
    console.error("Error fetching companies (adminService getCompanies function):", error);
    throw error; 
  }
};

/**
 * Creates a new company.
 * Requires superadmin authentication.
 * @param {object} companyData - The data for the new company. Expected: { name: "Company Name", industry?: "...", owner_email?: "..." }
 * @returns {Promise<object>} A promise that resolves to the newly created company object.
 * @throws Will throw an error if the request fails or data is invalid.
 */
export const createCompany = async (companyData) => {
  // Βασικός έλεγχος δεδομένων πριν την αποστολή
  if (!companyData || !companyData.name || typeof companyData.name !== 'string' || companyData.name.trim() === '') {
    const validationError = { error: "Company name is required and must be a non-empty string." };
    console.error("Error creating company (adminService): Invalid companyData", companyData);
    throw validationError; // Κάνε throw ένα αντικείμενο με το σφάλμα για συνέπεια
  }
  // Αν περιμένεις owner_email, πρόσθεσε έλεγχο και για αυτό
  // if (!companyData.owner_email || !/\S+@\S+\.\S+/.test(companyData.owner_email)) {
  //   const validationError = { error: "A valid owner email is required to create a company." };
  //   throw validationError;
  // }

  try {
    const response = await adminApiClient.post('/companies', companyData);
    return response.data; // Περιμένουμε το αντικείμενο της νέας εταιρείας
  } catch (error) {
    console.error("Error creating company (adminService createCompany function):", error);
    throw error;
  }
};

/**
 * Fetches a list of all users in the system (superadmin view).
 * Requires superadmin authentication.
 * @param {object} params - Optional query parameters (e.g., { page: 1, per_page: 10, role: 'user', company_id: 1 })
 * @returns {Promise<object>} A promise that resolves to an object containing users list and pagination info.
 */
export const getAllUsers = async (params = {}) => {
  try {
    const response = await adminApiClient.get('/users', { params });
    return response.data; // Περιμένουμε { users: [...], total_users: X, ... }
  } catch (error) {
    console.error("Error fetching all users (adminService getAllUsers function):", error);
    throw error;
  }
};

/**
 * Creates a new user by a superadmin. Can assign to a company or make another superadmin.
 * Requires superadmin authentication.
 * @param {object} userData - Data for the new user (username, email, password, role, company_id?).
 * @returns {Promise<object>} A promise that resolves to the newly created user object.
 */
export const createUserBySuperadmin = async (userData) => {
  // Βασικοί έλεγχοι για userData
  if (!userData || !userData.username || !userData.email || !userData.password || !userData.role) {
      const validationError = { error: "Username, email, password, and role are required for user creation." };
      console.error("Error creating user by superadmin (adminService): Invalid userData", userData);
      throw validationError;
  }
  if (userData.role === 'company_admin' && !userData.company_id) {
      const validationError = { error: "Company ID is required when creating a company_admin." };
      throw validationError;
  }

  try {
    const response = await adminApiClient.post('/users', userData);
    return response.data; // Περιμένουμε το αντικείμενο του νέου χρήστη
  } catch (error) {
    console.error("Error creating user by superadmin (adminService createUserBySuperadmin function):", error);
    throw error;
  }
};

/**
 * Updates a user's details by a superadmin.
 * Requires superadmin authentication.
 * @param {number} userId - The ID of the user to update.
 * @param {object} userData - The data to update (e.g., email, role, company_id, is_active).
 * @returns {Promise<object>} A promise that resolves to the updated user object.
 */
export const updateUserBySuperadmin = async (userId, userData) => {
    if (!userId || !userData || Object.keys(userData).length === 0) {
        const validationError = { error: "User ID and update data are required." };
        console.error("Error updating user by superadmin (adminService): Invalid input", {userId, userData});
        throw validationError;
    }
    try {
        const response = await adminApiClient.put(`/users/${userId}`, userData);
        return response.data;
    } catch (error) {
        console.error(`Error updating user ${userId} by superadmin (adminService):`, error);
        throw error;
    }
};

/**
 * Deletes a user by a superadmin.
 * Requires superadmin authentication.
 * @param {number} userId - The ID of the user to delete.
 * @returns {Promise<object>} A promise that resolves to a success message.
 */
export const deleteUserBySuperadmin = async (userId) => {
    if (!userId) {
        const validationError = { error: "User ID is required for deletion." };
        throw validationError;
    }
    try {
        const response = await adminApiClient.delete(`/users/${userId}`);
        return response.data; // Περιμένουμε { message: "..." }
    } catch (error) {
        console.error(`Error deleting user ${userId} by superadmin (adminService):`, error);
        throw error;
    }
};

/**
 * Fetches details for a specific company by its ID.
 * Requires superadmin authentication.
 * @param {number} companyId - The ID of the company.
 * @returns {Promise<object>} A promise that resolves to the company object.
 */
export const getCompanyById = async (companyId) => {
    if (!companyId) {
        const validationError = { error: "Company ID is required." };
        throw validationError;
    }
    try {
        const response = await adminApiClient.get(`/companies/${companyId}`);
        return response.data;
    } catch (error) {
        console.error(`Error fetching company ${companyId} (adminService):`, error);
        throw error;
    }
};

/**
 * Updates a company's details by a superadmin.
 * Requires superadmin authentication.
 * @param {number} companyId - The ID of the company to update.
 * @param {object} companyData - The data to update (e.g., name, industry, owner_user_id).
 * @returns {Promise<object>} A promise that resolves to the updated company object.
 */
export const updateCompanyBySuperadmin = async (companyId, companyData) => {
    if (!companyId || !companyData || Object.keys(companyData).length === 0) {
        const validationError = { error: "Company ID and update data are required." };
        throw validationError;
    }
    try {
        const response = await adminApiClient.put(`/companies/${companyId}`, companyData);
        return response.data;
    } catch (error) {
        console.error(`Error updating company ${companyId} (adminService):`, error);
        throw error;
    }
};

const adminService = {
    getCompanies,
    createCompany,
    getAllUsers,
    createUserBySuperadmin,
    updateUserBySuperadmin,
    deleteUserBySuperadmin,
    getCompanyById,
    updateCompanyBySuperadmin,
    // Πρόσθεσε κι άλλες συναρτήσεις εδώ αν χρειαστεί
};

export default adminService;