// frontend/src/pages/AdminLayout.jsx
import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../App'; 
import Sidebar from '../components/Sidebar'; 
import '../components/Layout.css'; // ΣΗΜΑΝΤΙΚΟ: Εισάγει το σωστό CSS

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
    // Χρησιμοποιεί τις ίδιες κλάσεις με το κυρίως Layout
    <div className="app-container"> {/* ΑΣ ΑΛΛΑΞΟΥΜΕ ΑΥΤΟ ΓΙΑ ΔΟΚΙΜΗ */}
      {/* Header δεν υπάρχει εδώ, σωστά */}
      <div className="main-layout-container"> 
        <Sidebar /> 
        <main className="main-content-area"> 
          <Outlet /> 
        </main>
      </div>
    </div>
  );
};

export default AdminLayout;