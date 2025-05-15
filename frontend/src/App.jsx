// frontend/src/App.jsx
import React, { useState, useEffect, createContext, useContext } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, Outlet } from 'react-router-dom';
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
import AdminLayout from './pages/AdminLayout';
import AdminCompaniesPage from './pages/AdminCompaniesPage';
import AdminUsersPage from './pages/AdminUsersPage';
import CompanyUsersPage from './pages/CompanyUsersPage';

export const AuthContext = createContext(null);
export const useAuth = () => useContext(AuthContext);

const ProtectedRoute = ({ children, allowedRoles }) => {
  const { currentUser } = useAuth();
  if (!currentUser) {
    return <Navigate to="/login" replace />;
  }
  if (allowedRoles && !allowedRoles.includes(currentUser.role)) {
    return <Navigate to="/dashboard" replace />;
  }
  return children ? children : <Outlet />;
};

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
          console.log("User loaded from session:", response.data.user);
        } else {
          setCurrentUser(null);
        }
      } catch (error) {
        console.error("Session check failed:", error.response?.data || error.message);
        setCurrentUser(null);
      } finally {
        setIsLoadingAuth(false);
      }
    };
    checkAuthStatus();
  }, []);

  const login = (userData) => {
    setCurrentUser(userData);
    console.log("User logged in:", userData);
  };

  const logout = async () => {
    try {
      await apiClient.post('/logout');
    } catch (error) {
      console.error("Logout API call failed:", error);
    } finally {
      setCurrentUser(null);
      console.log("User logged out");
    }
  };

  if (isLoadingAuth) {
    return <div className="loading-placeholder" style={{display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh'}}>Initializing Application...</div>;
  }

  return (
    <AuthContext.Provider value={{ currentUser, login, logout, setCurrentUser }}>
      <Router>
        <Routes>
          <Route path="/login" element={!currentUser ? <LoginPage /> : <Navigate to="/dashboard" replace />} />
          <Route path="/register" element={!currentUser ? <RegisterPage /> : <Navigate to="/dashboard" replace />} />
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<Layout />}>
              <Route index element={<Navigate to="/dashboard" replace />} />
              <Route path="dashboard" element={<DashboardPage />} />
              <Route path="candidate/:candidateId" element={<CandidateDetailPage />} />
              <Route path="candidates/:status" element={<CandidateListPage />} />
              {/* Η παρακάτω γραμμή είναι περιττή αν το /candidates/:status καλύπτει και το ParsingFailed */}
              {/* <Route path="parsing-failed" element={<CandidateListPage status="ParsingFailed" />} /> */}
              <Route path="settings" element={<SettingsPage />} />
              <Route
                path="company/users"
                element={
                  <ProtectedRoute allowedRoles={['company_admin', 'superadmin']}>
                    <CompanyUsersPage />
                  </ProtectedRoute>
                }
              />
            </Route>
            <Route
              path="/admin"
              element={
                <ProtectedRoute allowedRoles={['superadmin']}>
                  <AdminLayout />
                </ProtectedRoute>
              }
            >
              <Route index element={<Navigate to="companies" replace />} />
              <Route path="companies" element={<AdminCompaniesPage />} />
              <Route path="users" element={<AdminUsersPage />} />
            </Route>
          </Route>
          <Route path="*" element={currentUser ? <Layout><NotFoundPage /></Layout> : <NotFoundPage />} />
        </Routes>
      </Router>
    </AuthContext.Provider>
  );
}
export default App;