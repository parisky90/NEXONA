import React from 'react';
import { Outlet } from 'react-router-dom'; // Renders the matched child route component
import Sidebar from './Sidebar'; // We'll create this next
import './Layout.css'; // Styles for the layout

function Layout() {
  return (
    <div className="layout-container">
      <Sidebar />
      <main className="main-content">
        {/* Child route components (DashboardPage, CandidateDetailPage, etc.) render here */}
        <Outlet />
      </main>
    </div>
  );
}

export default Layout;