// frontend/src/App.jsx
import React, { useState, useEffect, createContext, useContext } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import './App.css';
import apiClient from './api'; // Need apiClient for session check and logout potentially

// Page Components
import Layout from './components/Layout';
import DashboardPage from './pages/DashboardPage';
import CandidateDetailPage from './pages/CandidateDetailPage';
import SettingsPage from './pages/SettingsPage';
import LoginPage from './pages/LoginPage';
import NotFoundPage from './pages/NotFoundPage';
import CandidateListPage from './pages/CandidateListPage';

// --- Auth Context ---
const AuthContext = createContext(null);
export const useAuth = () => useContext(AuthContext);

function App() {
  // --- Restore Auth State ---
  const [currentUser, setCurrentUser] = useState(null);
  const [isLoadingAuth, setIsLoadingAuth] = useState(true); // Start loading
  // --- End Restore ---

  // --- Restore Session Check ---
  useEffect(() => {
    const checkAuthStatus = async () => {
      // Don't re-check if already loaded and user is set (optional optimization)
      // if (currentUser && !isLoadingAuth) return;

      setIsLoadingAuth(true);
      try {
        const response = await apiClient.get('/session'); // Call backend session check
        if (response.data && response.data.authenticated) {
          setCurrentUser(response.data.user); // Set user if authenticated
          console.log("Session check: User authenticated", response.data.user);
        } else {
          setCurrentUser(null); // Clear user if not authenticated
          console.log("Session check: User not authenticated");
        }
      } catch (error) {
        console.error("Session check failed:", error);
        setCurrentUser(null); // Assume not logged in on error
      } finally {
        setIsLoadingAuth(false); // Finished loading check
      }
    };
    checkAuthStatus();
  }, []); // Run only on initial mount
  // --- End Restore ---


  // --- Real Auth Functions (passed via Context) ---
  const login = (userData) => {
    // Called by LoginPage upon successful login API call
    setCurrentUser(userData);
  };

  const logout = async () => {
    // Called by Sidebar/Layout logout button
    // No need for navigate here if ProtectedRoute handles redirect
    try {
      await apiClient.post('/logout'); // Call backend logout
      setCurrentUser(null); // Clear user state immediately
      console.log("Logout successful");
      // Navigation away from protected routes will happen automatically
      // because currentUser becomes null
    } catch (error) {
       console.error("Logout failed:", error);
       // Decide how to handle logout failure - maybe show error message?
       // Force clear user state anyway?
       setCurrentUser(null);
    }
  };
  // --- End Real Auth Functions ---

  // Display loading indicator while checking auth status
  if (isLoadingAuth) {
    return <div className="loading-placeholder">Initializing Application...</div>;
  }

  // Provide real auth state and functions via Context
  return (
    <AuthContext.Provider value={{ currentUser, login, logout }}>
      <Router>
        <Routes>
          {/* --- Restore conditional rendering based on currentUser --- */}
          {currentUser ? (
            // ---- Logged In Routes (Protected) ----
            <Route path="/" element={<Layout />}> {/* Layout includes Sidebar with logout */}
              <Route index element={<DashboardPage />} />
              <Route path="dashboard" element={<DashboardPage />} />
              <Route path="candidate/:candidateId" element={<CandidateDetailPage />} />
              <Route path="accepted" element={<CandidateListPage status="Accepted" />} />
              <Route path="interested" element={<CandidateListPage status="Interested" />} />
              <Route path="interview" element={<CandidateListPage status="Interview" />} />
              <Route path="evaluation" element={<CandidateListPage status="Evaluation" />} />
              <Route path="offer" element={<CandidateListPage status="OfferMade" />} />
              <Route path="hired" element={<CandidateListPage status="Hired" />} />
              <Route path="rejected" element={<CandidateListPage status="Rejected" />} />
              <Route path="declined" element={<CandidateListPage status="Declined" />} />
              <Route path="settings" element={<SettingsPage />} />
              {/* Redirect any other logged-in path to dashboard or 404 */}
              {/* Option 1: Redirect to Dashboard */}
              {/* <Route path="*" element={<Navigate to="/dashboard" replace />} /> */}
              {/* Option 2: Show 404 */}
               <Route path="*" element={<NotFoundPage />} />
            </Route> // End of parent Layout route

          ) : (
            // ---- Logged Out Routes ----
            <>
              <Route path="/login" element={<LoginPage />} />
              {/* Any other path redirects to /login */}
              <Route path="*" element={<Navigate to="/login" replace />} />
            </>
          )}
        </Routes>
      </Router>
    </AuthContext.Provider>
  );
}

export default App;