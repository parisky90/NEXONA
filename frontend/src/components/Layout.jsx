// frontend/src/components/Layout.jsx
import React from 'react';
import { Outlet, Link } from 'react-router-dom';
import Sidebar from './Sidebar';
// ΔΕΝ ΧΡΕΙΑΖΕΤΑΙ IMPORT ΓΙΑ ΕΙΚΟΝΕΣ ΑΠΟ ΤΟΝ PUBLIC ΦΑΚΕΛΟ
import './Layout.css'; 

function Layout() {
  return (
    <div className="app-container">
      <header className="app-header">
        <Link to="/dashboard" className="app-logo-link">
          {/* ΔΙΟΡΘΩΣΗ: Όνομα αρχείου με μικρά γράμματα */}
          <img src="/nexona_logo.png" alt="NEXONA Logo" className="app-logo" />
        </Link>
      </header>
      <div className="main-layout-container">
        <Sidebar />
        <main className="main-content-area">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
export default Layout;