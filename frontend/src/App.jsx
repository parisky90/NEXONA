// frontend/src/App.jsx
import React, { useState, useEffect, createContext, useContext } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import './App.css';
import apiClient from './api';
import Layout from './components/Layout'; // Το υπάρχον Layout
import DashboardPage from './pages/DashboardPage';
import CandidateDetailPage from './pages/CandidateDetailPage';
import SettingsPage from './pages/SettingsPage';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import NotFoundPage from './pages/NotFoundPage';
import CandidateListPage from './pages/CandidateListPage';

// --- ΝΕΑ IMPORTS ΓΙΑ ADMIN ---
import AdminLayout from './pages/AdminLayout'; // Το νέο Admin Layout
import AdminCompaniesPage from './pages/AdminCompaniesPage'; // Θα το φτιάξουμε
import AdminUsersPage from './pages/AdminUsersPage';     // Θα το φτιάξουμε
// -----------------------------

export const AuthContext = createContext(null); // Μετακίνησε το export εδώ για να είναι πιο σαφές
export const useAuth = () => useContext(AuthContext);

function App() {
  const [currentUser, setCurrentUser] = useState(null);
  const [isLoadingAuth, setIsLoadingAuth] = useState(true);

  useEffect(() => {
    const checkAuthStatus = async () => {
      setIsLoadingAuth(true);
      try {
        const response = await apiClient.get('/session');
        if (response.data && response.data.authenticated) {
          setCurrentUser(response.data.user);
          console.log("User loaded from session:", response.data.user); // Debug log
        } else {
          setCurrentUser(null);
        }
      } catch (error) {
        console.error("Session check failed:", error);
        setCurrentUser(null);
      } finally {
        setIsLoadingAuth(false);
      }
    };
    checkAuthStatus();
  }, []);

  const login = (userData) => {
    setCurrentUser(userData);
    console.log("User logged in:", userData); // Debug log
  };
  const logout = async () => {
    try {
      await apiClient.post('/logout');
      setCurrentUser(null);
      console.log("User logged out"); // Debug log
    } catch (error) {
      console.error("Logout failed:", error);
      setCurrentUser(null); // Βεβαιώσου ότι ο χρήστης αποσυνδέεται ακόμα κι αν το API call αποτύχει
    }
  };

  if (isLoadingAuth) {
    return <div className="loading-placeholder">Initializing Application...</div>;
  }

  return (
    <AuthContext.Provider value={{ currentUser, login, logout }}>
      <Router>
        <Routes>
          {currentUser ? (
            <>
              {/* Κύριες Διαδρομές Εφαρμογής */}
              <Route path="/" element={<Layout />}>
                <Route index element={<Navigate to="/dashboard" replace />} /> {/* Redirect από / σε /dashboard */}
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
                <Route path="needs-review" element={<CandidateListPage status="NeedsReview" />} />
                <Route path="processing" element={<CandidateListPage status="Processing" />} />
                <Route path="settings" element={<SettingsPage />} />
                {/* Μην βάζεις το NotFoundPage εδώ μέσα αν το Layout έχει δικό του χειρισμό ή αν το θες εκτός */}
              </Route>

              {/* --- ADMIN ΔΙΑΔΡΟΜΕΣ --- */}
              {/* Ο AdminLayout θα ελέγξει αν ο χρήστης είναι superadmin */}
              <Route path="/admin" element={<AdminLayout />}>
                {/* Default admin page, e.g., redirect to companies or a specific admin dashboard */}
                <Route index element={<Navigate to="companies" replace />} /> 
                <Route path="companies" element={<AdminCompaniesPage />} />
                <Route path="users" element={<AdminUsersPage />} />
                {/* Πρόσθεσε κι άλλες admin υπο-διαδρομές εδώ αργότερα */}
              </Route>
              {/* -------------------- */}
              
              {/* Το NotFoundPage καλύτερα να είναι εκτός των layouts για να πιάνει όλες τις άγνωστες διαδρομές */}
              <Route path="*" element={<Layout><NotFoundPage /></Layout>} /> 
              {/* Ή απλώς <Route path="*" element={<NotFoundPage />} /> αν δεν θες το Layout στο NotFound */}

            </>
          ) : (
            <>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />
              <Route path="*" element={<Navigate to="/login" replace />} />
            </>
          )}
        </Routes>
      </Router>
    </AuthContext.Provider>
  );
}
export default App;