// frontend/src/App.jsx
import React, { useState, useEffect, createContext, useContext } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import './App.css';
import apiClient from './api';
import Layout from './components/Layout';
import DashboardPage from './pages/DashboardPage';
import CandidateDetailPage from './pages/CandidateDetailPage';
import SettingsPage from './pages/SettingsPage';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import NotFoundPage from './pages/NotFoundPage';
import CandidateListPage from './pages/CandidateListPage';

const AuthContext = createContext(null);
export const useAuth = () => useContext(AuthContext);

function App() {
  const [currentUser, setCurrentUser] = useState(null);
  const [isLoadingAuth, setIsLoadingAuth] = useState(true);

  useEffect(() => {
    const checkAuthStatus = async () => {
      setIsLoadingAuth(true);
      try {
        const response = await apiClient.get('/session');
        if (response.data && response.data.authenticated) { setCurrentUser(response.data.user); }
        else { setCurrentUser(null); }
      } catch (error) { console.error("Session check failed:", error); setCurrentUser(null);
      } finally { setIsLoadingAuth(false); }
    };
    checkAuthStatus();
  }, []);

  const login = (userData) => { setCurrentUser(userData); };
  const logout = async () => {
    try { await apiClient.post('/logout'); setCurrentUser(null);
    } catch (error) { console.error("Logout failed:", error); setCurrentUser(null); }
  };

  if (isLoadingAuth) { return <div className="loading-placeholder">Initializing Application...</div>; }

  return (
    <AuthContext.Provider value={{ currentUser, login, logout }}>
      <Router>
        <Routes>
          {currentUser ? (
            <Route path="/" element={<Layout />}>
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
              <Route path="needs-review" element={<CandidateListPage status="NeedsReview" />} />
              <Route path="processing" element={<CandidateListPage status="Processing" />} />
              <Route path="settings" element={<SettingsPage />} />
              <Route path="*" element={<NotFoundPage />} />
            </Route>
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