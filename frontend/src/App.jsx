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
import CompanyInterviewsPage from './pages/CompanyInterviewsPage';
import CompanyBranchesPage from './pages/CompanyBranchesPage';
import CompanyPositionsPage from './pages/CompanyPositionsPage'; // <<< ΝΕΟ IMPORT ΓΙΑ POSITIONS

export const AuthContext = createContext(null);
export const useAuth = () => useContext(AuthContext);

const ProtectedRoute = ({ children, allowedRoles }) => {
  const { currentUser, isLoadingAuth } = useAuth();

  if (isLoadingAuth) {
    return <div className="loading-placeholder" style={{display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh'}}>Checking authentication...</div>;
  }

  if (!currentUser) {
    return <Navigate to="/login" replace />;
  }
  if (allowedRoles && !allowedRoles.includes(currentUser.role)) {
    console.warn(`User role '${currentUser.role}' not in allowed roles: [${allowedRoles.join(', ')}]. Redirecting to /dashboard.`);
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
        if (response.data && response.data.user && response.data.is_authenticated) {
          setCurrentUser(response.data.user);
          console.log("App.jsx: User loaded from session:", response.data.user);
        } else {
          setCurrentUser(null);
          console.log("App.jsx: Session check - no authenticated user.");
        }
      } catch (error) {
        if (error.response && error.response.status === 401) {
          console.log("App.jsx: Session check - User not authenticated (401).");
        } else {
          console.error("App.jsx: Session check failed with error:", error.response?.data || error.message);
        }
        setCurrentUser(null);
      } finally {
        setIsLoadingAuth(false);
      }
    };
    checkAuthStatus();
  }, []);

  const login = (userData) => {
    setCurrentUser(userData);
    console.log("App.jsx: User logged in:", userData);
  };

  const logout = async () => {
    try {
      await apiClient.post('/logout');
    } catch (error) {
      console.error("App.jsx: Logout API call failed:", error);
    } finally {
      setCurrentUser(null);
      setIsLoadingAuth(false);
      console.log("App.jsx: User logged out");
    }
  };

  return (
    <AuthContext.Provider value={{ currentUser, login, logout, isLoadingAuth, setCurrentUser }}>
      <Router>
        <Routes>
          {/* Public Routes */}
          <Route path="/login" element={!currentUser && !isLoadingAuth ? <LoginPage /> : <Navigate to="/dashboard" replace />} />
          <Route path="/register" element={!currentUser && !isLoadingAuth ? <RegisterPage /> : <Navigate to="/dashboard" replace />} />

          {/* Protected Routes */}
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<Layout />}>
              <Route index element={<Navigate to="/dashboard" replace />} />
              <Route path="dashboard" element={<DashboardPage />} />
              <Route path="candidate/:candidateId" element={<CandidateDetailPage />} />
              <Route path="candidates/:status" element={<CandidateListPage />} />
              <Route path="settings" element={<SettingsPage />} />

              {/* Company Admin Specific Routes (also accessible by Superadmin if included in allowedRoles) */}
              <Route
                path="company"
                element={<ProtectedRoute allowedRoles={['company_admin', 'superadmin']}><Outlet /></ProtectedRoute>}
              >
                <Route path="users" element={<CompanyUsersPage />} />
                <Route path="interviews" element={<CompanyInterviewsPage />} />
                <Route path="branches" element={<CompanyBranchesPage />} />
                <Route path="positions" element={<CompanyPositionsPage />} /> {/* <<< ΝΕΟ ROUTE ΓΙΑ POSITIONS */}
              </Route>
            </Route>

            {/* Superadmin Specific Routes */}
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

          <Route
            path="*"
            element={
              isLoadingAuth ? <div className="loading-placeholder">Loading...</div> :
              (currentUser ? <Layout><NotFoundPage /></Layout> : <NotFoundPage />)
            }
          />
        </Routes>
      </Router>
    </AuthContext.Provider>
  );
}
export default App;