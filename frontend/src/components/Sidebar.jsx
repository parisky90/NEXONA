// frontend/src/components/Sidebar.jsx
import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../App'; // Ελέγξτε το path αν το App.jsx είναι αλλού
import './Sidebar.css';

import {
  ChartBarSquareIcon,
  UsersIcon,
  Cog6ToothIcon,
  ArrowLeftOnRectangleIcon,
  BuildingOffice2Icon,
  ShieldCheckIcon,
  ClockIcon,
  UserPlusIcon,
  CheckBadgeIcon,
  FunnelIcon,
  AcademicCapIcon,
  GiftIcon,
  XCircleIcon,
  NoSymbolIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon
} from '@heroicons/react/24/outline';

import { CheckCircleIcon as CheckCircleSolidIcon } from '@heroicons/react/24/solid';

function Sidebar() {
  const { currentUser, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login', { replace: true });
  };

  if (!currentUser) {
    return null;
  }

  const iconClassName = "sidebar-icon";

  const renderNavLink = (to, IconComponent, text, isHired = false) => {
    return (
      <NavLink 
        to={to} 
        className={({ isActive }) => isActive ? "sidebar-link active-link" : "sidebar-link"}
      >
        <IconComponent className={`${iconClassName} ${isHired ? 'icon-hired' : ''}`} /> 
        <span className="sidebar-link-text">{text}</span>
      </NavLink>
    );
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-user-info">
        <p className="user-role-display">{currentUser.role}</p>
        {currentUser.company_name && <p className="company-name-display">{currentUser.company_name}</p>}
      </div>
      <nav className="sidebar-nav">
        {renderNavLink("/dashboard", ChartBarSquareIcon, "Dashboard")}

        <div className="sidebar-section-title">Candidates</div>
        {renderNavLink("/candidates/NeedsReview", ClockIcon, "Needs Review")}
        {renderNavLink("/candidates/Accepted", CheckBadgeIcon, "Accepted")}
        {renderNavLink("/candidates/Interested", FunnelIcon, "Interested")}
        {renderNavLink("/candidates/Interview", UserPlusIcon, "Interview")}
        {renderNavLink("/candidates/Evaluation", AcademicCapIcon, "Evaluation")}
        {renderNavLink("/candidates/OfferMade", GiftIcon, "Offer Made")}
        {renderNavLink("/candidates/Hired", CheckCircleSolidIcon, "Hired", true)}
        {renderNavLink("/candidates/Rejected", XCircleIcon, "Rejected")}
        {renderNavLink("/candidates/Declined", NoSymbolIcon, "Declined")}
        {renderNavLink("/candidates/Processing", ArrowPathIcon, "Processing")}
        {renderNavLink("/candidates/ParsingFailed", ExclamationTriangleIcon, "Parsing Failed")}

        {(currentUser.role === 'company_admin' || currentUser.role === 'superadmin') && (
          <>
            <div className="sidebar-section-title">Company Management</div>
            {renderNavLink("/company/users", UsersIcon, "Manage Users")}
          </>
        )}

        {currentUser.role === 'superadmin' && (
          <>
            <div className="sidebar-section-title">Super Admin</div>
            {renderNavLink("/admin/companies", BuildingOffice2Icon, "Manage Companies")}
            {renderNavLink("/admin/users", ShieldCheckIcon, "Manage All Users")}
          </>
        )}
        
        <div className="sidebar-section-title">Account</div>
        {renderNavLink("/settings", Cog6ToothIcon, "Settings")}
        
        <button onClick={handleLogout} className="sidebar-link logout-button">
          <ArrowLeftOnRectangleIcon className={iconClassName} /> 
          <span className="sidebar-link-text">Logout</span>
        </button>
      </nav>
    </aside>
  );
}

export default Sidebar;