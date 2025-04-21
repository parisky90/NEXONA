// frontend/src/api.js
import axios from 'axios';

// Determine the base URL dynamically
const getApiBaseUrl = () => {
    // For development using Vite's proxy or direct connection to backend service
    if (import.meta.env.DEV) {
        // Assuming backend runs on host port 5001 as exposed in docker-compose
        // Use relative path if Vite proxy is set up, otherwise explicit origin
        // return '/api/v1'; // Use this if you set up Vite proxy
        return 'http://localhost:5001/api/v1'; // Use explicit origin if no proxy
    } else {
        // For production, assume API is served from the same origin or configure appropriately
        return '/api/v1'; // Adjust if your production setup is different
    }
};

const apiClient = axios.create({
    baseURL: getApiBaseUrl(),
    withCredentials: true, // Send cookies with requests (important for session auth)
    headers: {
        'Content-Type': 'application/json',
        // Add other common headers if needed
    },
});

// Optional: Add interceptors for request/response handling (e.g., error logging)
apiClient.interceptors.response.use(
    response => response, // Simply return successful responses
    error => {
        console.error("API call error:", error.response || error.message || error);
        // Optionally handle specific error codes (e.g., 401 Unauthorized) globally
        // if (error.response && error.response.status === 401) {
        //     // Handle unauthorized access, e.g., redirect to login
        //     console.log("Redirecting to login due to 401");
        //     // window.location.href = '/login'; // Be careful with SPA routing
        // }
        return Promise.reject(error); // Propagate the error
    }
);

export default apiClient;

// Example helper function (add more as needed)
export const uploadCV = (formData) => {
    return apiClient.post('/upload', formData, {
        headers: {
            'Content-Type': 'multipart/form-data', // Important for file uploads
        },
        // Optional: Add progress tracking
        // onUploadProgress: progressEvent => {
        //   console.log('Upload Progress: ' + Math.round((progressEvent.loaded / progressEvent.total) * 100) + '%');
        // }
    });
};

// Add other API helper functions here...
// export const getCandidates = (status) => apiClient.get(`/candidates/${status}`);
// export const getCandidateDetails = (id) => apiClient.get(`/candidate/${id}`);
// etc.