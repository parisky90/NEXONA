// frontend/src/components/Sidebar.jsx
import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../App';
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
  ExclamationTriangleIcon,
  CalendarDaysIcon,
  ChatBubbleLeftRightIcon,
  BuildingStorefrontIcon,
  BriefcaseIcon // <<< ΝΕΟ ΕΙΚΟΝΙΔΙΟ ΓΙΑ POSITIONS
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

  const renderNavLink = (to, IconComponent, text, additionalCondition = true, isHired = false) => {
    if (!additionalCondition) {
        return null;
    }
    return (
      <li>
        <NavLink
          to={to}
          className={({ isActive }) => isActive ? "sidebar-link active-link" : "sidebar-link"}
        >
          <IconComponent className={`${iconClassName} ${isHired ? 'icon-hired' : ''}`} />
          <span className="sidebar-link-text">{text}</span>
        </NavLink>
      </li>
    );
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-user-info">
        <p className="user-role-display">{currentUser.role.replace('_', ' ')}</p>
        {currentUser.company_name && <p className="company-name-display">{currentUser.company_name}</p>}
      </div>
      <ul className="sidebar-nav">
        {renderNavLink("/dashboard", ChartBarSquareIcon, "Dashboard")}

        <div className="sidebar-section-title">Candidates</div>
        {renderNavLink("/candidates/NeedsReview", ClockIcon, "Needs Review")}
        {renderNavLink("/candidates/Accepted", CheckBadgeIcon, "Accepted")}
        {renderNavLink("/candidates/Interested", FunnelIcon, "Interested")}
        {renderNavLink("/candidates/InterviewProposed", ChatBubbleLeftRightIcon, "Interview Proposed")}
        {renderNavLink("/candidates/InterviewScheduled", UserPlusIcon, "Interview Scheduled")}
        {renderNavLink("/candidates/Evaluation", AcademicCapIcon, "Evaluation")}
        {renderNavLink("/candidates/OfferMade", GiftIcon, "Offer Made")}
        {renderNavLink("/candidates/Hired", CheckCircleSolidIcon, "Hired", true, true)}
        {renderNavLink("/candidates/Rejected", XCircleIcon, "Rejected")}
        {renderNavLink("/candidates/Declined", NoSymbolIcon, "Declined")}
        {renderNavLink("/candidates/Processing", ArrowPathIcon, "Processing")}
        {renderNavLink("/candidates/ParsingFailed", ExclamationTriangleIcon, "Parsing Failed")}

        {/* Company Management Section */}
        {(currentUser.role === 'company_admin' || currentUser.role === 'superadmin') && (
          <>
            <div className="sidebar-section-title">Company Management</div>
            {renderNavLink("/company/users", UsersIcon, "Manage Users", currentUser.role === 'company_admin')}
            {renderNavLink("/company/branches", BuildingStorefrontIcon, "Manage Branches", currentUser.role === 'company_admin')}
            {renderNavLink("/company/positions", BriefcaseIcon, "Manage Positions", currentUser.role === 'company_admin')} {/* <<< ΝΕΟ LINK ΓΙΑ POSITIONS */}
            {renderNavLink("/company/interviews", CalendarDaysIcon, "Company Interviews")}
          </>
        )}

        {/* Super Admin Section */}
        {currentUser.role === 'superadmin' && (
          <>
            <div className="sidebar-section-title">Super Admin</div>
            {renderNavLink("/admin/companies", BuildingOffice2Icon, "Manage Companies")}
            {renderNavLink("/admin/users", ShieldCheckIcon, "Manage All Users")}
          </>
        )}

        <div className="sidebar-section-title">Account</div>
        {renderNavLink("/settings", Cog6ToothIcon, "Settings")}

        <li>
          <button onClick={handleLogout} className="sidebar-link logout-button">
            <ArrowLeftOnRectangleIcon className={iconClassName} />
            <span className="sidebar-link-text">Logout</span>
          </button>
        </li>
      </ul>
    </aside>
  );
}

export default Sidebar;