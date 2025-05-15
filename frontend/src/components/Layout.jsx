// frontend/src/components/Layout.jsx
import React from 'react';
import { Outlet, Link } from 'react-router-dom';
import Sidebar from './Sidebar';
import './Layout.css';

function Layout() {
  return (
    <div className="app-container">
      <header className="app-header">
        <Link to="/dashboard">
          <img src="/NEXONA_LOGO.png" alt="NEXONA Logo" className="app-logo" />
          {/* Βεβαιώσου ότι το NEXONA_LOGO.png είναι στο public folder */}
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