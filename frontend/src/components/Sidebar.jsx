// frontend/src/components/Sidebar.jsx
import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../App';
import './Sidebar.css';

// ΣΩΣΤΕΣ ΕΙΣΑΓΩΓΕΣ ΓΙΑ HEROICONS (v2 - @heroicons/react)
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
} from '@heroicons/react/24/outline'; // Χρησιμοποιούμε outline icons 24px

import { CheckCircleIcon as CheckCircleSolidIcon } from '@heroicons/react/24/solid'; // Για το Hired

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

  const iconClassName = "sidebar-icon"; // Κλάση για styling των icons

  return (
    <aside className="sidebar">
      <div className="sidebar-user-info">
        <p className="user-role-display">{currentUser.role}</p>
        {currentUser.company_name && <p className="company-name-display">{currentUser.company_name}</p>}
      </div>
      <nav className="sidebar-nav">
        <NavLink to="/dashboard" className={({ isActive }) => isActive ? "sidebar-link active-link" : "sidebar-link"}>
          <ChartBarSquareIcon className={iconClassName} /> Dashboard
        </NavLink>

        <div className="sidebar-section-title">Candidates</div>
        <NavLink to="/candidates/NeedsReview" className={({ isActive }) => isActive ? "sidebar-link active-link" : "sidebar-link"}>
            <ClockIcon className={iconClassName} /> Needs Review
        </NavLink>
        <NavLink to="/candidates/Accepted" className={({ isActive }) => isActive ? "sidebar-link active-link" : "sidebar-link"}>
            <CheckBadgeIcon className={iconClassName} /> Accepted
        </NavLink>
        <NavLink to="/candidates/Interested" className={({ isActive }) => isActive ? "sidebar-link active-link" : "sidebar-link"}>
            <FunnelIcon className={iconClassName} /> Interested
        </NavLink>
        <NavLink to="/candidates/Interview" className={({ isActive }) => isActive ? "sidebar-link active-link" : "sidebar-link"}>
            <UserPlusIcon className={iconClassName} /> Interview
        </NavLink>
        <NavLink to="/candidates/Evaluation" className={({ isActive }) => isActive ? "sidebar-link active-link" : "sidebar-link"}>
            <AcademicCapIcon className={iconClassName} /> Evaluation
        </NavLink>
        <NavLink to="/candidates/OfferMade" className={({ isActive }) => isActive ? "sidebar-link active-link" : "sidebar-link"}>
            <GiftIcon className={iconClassName} /> Offer Made
        </NavLink>
        <NavLink to="/candidates/Hired" className={({ isActive }) => isActive ? "sidebar-link active-link" : "sidebar-link"}>
            <CheckCircleSolidIcon className={`${iconClassName} icon-hired`} /> Hired
        </NavLink>
        <NavLink to="/candidates/Rejected" className={({ isActive }) => isActive ? "sidebar-link active-link" : "sidebar-link"}>
            <XCircleIcon className={iconClassName} /> Rejected
        </NavLink>
        <NavLink to="/candidates/Declined" className={({ isActive }) => isActive ? "sidebar-link active-link" : "sidebar-link"}>
            <NoSymbolIcon className={iconClassName} /> Declined
        </NavLink>
         <NavLink to="/candidates/Processing" className={({ isActive }) => isActive ? "sidebar-link active-link" : "sidebar-link"}>
            <ArrowPathIcon className={iconClassName} /> Processing
        </NavLink>
        <NavLink to="/candidates/ParsingFailed" className={({ isActive }) => isActive ? "sidebar-link active-link" : "sidebar-link"}>
            <ExclamationTriangleIcon className={iconClassName} /> Parsing Failed
        </NavLink>

        {(currentUser.role === 'company_admin' || currentUser.role === 'superadmin') && (
          <>
            <div className="sidebar-section-title">Company Management</div>
            <NavLink to="/company/users" className={({ isActive }) => isActive ? "sidebar-link active-link" : "sidebar-link"}>
              <UsersIcon className={iconClassName} /> Manage Users
            </NavLink>
          </>
        )}

        {currentUser.role === 'superadmin' && (
          <>
            <div className="sidebar-section-title">Super Admin</div>
            <NavLink to="/admin/companies" className={({ isActive }) => isActive ? "sidebar-link active-link" : "sidebar-link"}>
              <BuildingOffice2Icon className={iconClassName} /> Manage Companies
            </NavLink>
            <NavLink to="/admin/users" className={({ isActive }) => isActive ? "sidebar-link active-link" : "sidebar-link"}>
              <ShieldCheckIcon className={iconClassName} /> Manage All Users
            </NavLink>
          </>
        )}
        
        <div className="sidebar-section-title">Account</div>
        <NavLink to="/settings" className={({ isActive }) => isActive ? "sidebar-link active-link" : "sidebar-link"}>
          <Cog6ToothIcon className={iconClassName} /> Settings
        </NavLink>
        <button onClick={handleLogout} className="sidebar-link logout-button">
          <ArrowLeftOnRectangleIcon className={iconClassName} /> Logout
        </button>
      </nav>
    </aside>
  );
}

export default Sidebar;