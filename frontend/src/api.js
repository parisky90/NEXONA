// frontend/src/api.js
import axios from 'axios';

const getApiBaseUrl = () => {
    if (import.meta.env.DEV) {
        // Όταν είμαστε σε development και το Vite proxy είναι ενεργό για το /api/v1,
        // τότε το frontend στέλνει αιτήματα στο ίδιο του το origin (localhost:5173/api/v1)
        // και το Vite τα προωθεί στο backend (localhost:5001/api/v1).
        return '/api/v1';
    } else {
        // Για production, υποθέτουμε ότι το frontend και το backend σερβίρονται
        // έτσι ώστε τα αιτήματα στο /api/v1 να φτάνουν σωστά στο backend
        // (π.χ. μέσω Nginx reverse proxy που δρομολογεί το /api/v1 στο backend container).
        return '/api/v1';
    }
};

const apiClient = axios.create({
    baseURL: getApiBaseUrl(),
    withCredentials: true, // Σημαντικό για cookies/session
    headers: {
        'Content-Type': 'application/json',
    },
});

apiClient.interceptors.response.use(
    response => response,
    error => {
     console.error("API call error (interceptor):", {
            message: error.message,
            configUrl: error.config?.url,
            responseStatus: error.response?.status,
            responseData: error.response?.data,
            isAxiosError: error.isAxiosError,
            fullErrorObject: error 
        });
        // --- ΤΕΛΟΣ ΠΡΟΣΘΗΚΗΣ ---
        if (error.response && error.response.status === 401) {
            // ...
        }
        return Promise.reject(error);
    }
);   

// --- ΥΠΑΡΧΟΥΣΑ ΣΥΝΑΡΤΗΣΗ ---
export const uploadCV = (formData) => {
    return apiClient.post('/upload', formData, { // Το URL είναι σχετικό με το baseURL, άρα /api/v1/upload
        headers: {
            'Content-Type': 'multipart/form-data',
        },
    });
};

export default apiClient;