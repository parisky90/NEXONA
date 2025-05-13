// frontend/src/pages/AdminLayout.jsx
import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../App'; 
import Sidebar from '../components/Sidebar'; 
// import Header from '../components/Header'; // <--- ΑΦΑΙΡΕΣΕ ΑΥΤΗ ΤΗ ΓΡΑΜΜΗ
import '../components/Layout.css'; 

const AdminLayout = () => {
  const { currentUser } = useAuth();

  if (!currentUser) {
    return <Navigate to="/login" replace />;
  }
  if (currentUser.role !== 'superadmin') {
    console.warn("AdminLayout: Access denied. User is not superadmin. Redirecting to /dashboard.");
    return <Navigate to="/dashboard" replace />;
  }

  return (
    <div className="layout-container"> 
      <Sidebar /> 
      <main className="main-content"> 
        {/* <Header /> */} {/* <--- ΑΦΑΙΡΕΣΕ ΚΑΙ ΑΥΤΗ ΤΗ ΓΡΑΜΜΗ */}
        <Outlet /> 
      </main>
    </div>
  );
};

export default AdminLayout;