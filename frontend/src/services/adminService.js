// frontend/src/services/adminService.js
import apiClient from './apiClient'; // Το apiClient σου από το frontend/src/api.js

// === Company Management ===
export const getCompanies = () => {
  return apiClient.get('/admin/companies');
};

export const createCompany = (companyData) => {
  // companyData should be an object, e.g., { name: "New Company LLC" }
  return apiClient.post('/admin/companies', companyData);
};

export const getCompanyDetails = (companyId) => {
  return apiClient.get(`/admin/companies/${companyId}`);
};

export const updateCompany = (companyId, companyData) => {
  return apiClient.put(`/admin/companies/${companyId}`, companyData);
};

// export const deleteCompany = (companyId) => {
//   return apiClient.delete(`/admin/companies/${companyId}`);
// };


// === User Management by Superadmin ===
export const getAllUsers = (params) => {
  // params could be { page: 1, per_page: 10, role: 'user', company_id: 5 }
  return apiClient.get('/admin/users', { params });
};

export const createUserByAdmin = (userData) => {
  // userData: { username, email, password, role, company_id, is_active }
  return apiClient.post('/admin/users', userData);
};

export const getUserDetailsForAdmin = (userId) => {
  // Αν και δεν έχουμε ξεχωριστό endpoint για GET user by ID στο admin,
  // θα μπορούσαμε να το προσθέσουμε στο backend αν χρειαστεί.
  // Προς το παρόν, η λίστα χρηστών επιστρέφει αρκετές πληροφορίες.
  // Ή, το update user επιστρέφει τον ενημερωμένο χρήστη.
  console.warn("getUserDetailsForAdmin: Endpoint not explicitly defined yet, consider if needed.");
  return Promise.reject("Endpoint not available");
};

export const updateUserByAdmin = (userId, userData) => {
  return apiClient.put(`/admin/users/${userId}`, userData);
};

// export const deleteUserByAdmin = (userId) => {
//   return apiClient.delete(`/admin/users/${userId}`);
// };

// Θα μπορούσαμε να προσθέσουμε και κλήσεις για CompanySettings εδώ αν ο superadmin τις διαχειρίζεται
// μέσω ξεχωριστών admin endpoints αντί για το γενικό /settings?company_id=X
// export const getCompanySettingsForAdmin = (companyId) => {
//   return apiClient.get(`/admin/settings`, { params: { company_id: companyId } });
// };
// export const updateCompanySettingsForAdmin = (companyId, settingsData) => {
//   return apiClient.put(`/admin/settings?company_id=${companyId}`, settingsData);
// };

const adminService = {
  getCompanies,
  createCompany,
  getCompanyDetails,
  updateCompany,
  getAllUsers,
  createUserByAdmin,
  // getUserDetailsForAdmin, // Ας το αφήσουμε εκτός προς το παρόν
  updateUserByAdmin,
};

export default adminService;