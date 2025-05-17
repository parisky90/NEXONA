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
  ExclamationTriangleIcon,
  CalendarDaysIcon // <-- ΝΕΟ ICON
} from '@heroicons/react/24/outline';

import { CheckCircleIcon as CheckCircleSolidIcon } from '@heroicons/react/24/solid';

function Sidebar() {
  const { currentUser, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login', { replace: true }); // Ανακατεύθυνση μετά το logout
  };

  if (!currentUser) {
    // Αν δεν υπάρχει currentUser, μην κάνεις render το sidebar
    // (το ProtectedRoute θα έπρεπε να έχει ήδη ανακατευθύνει στο login)
    return null;
  }

  const iconClassName = "sidebar-icon";

  // Helper function για δημιουργία NavLink
  const renderNavLink = (to, IconComponent, text, additionalCondition = true, isHired = false) => {
    if (!additionalCondition) {
      return null;
    }
    return (
      <li> {/* Κάθε NavLink τώρα είναι μέσα σε <li> για σωστή σημασιολογία λίστας */}
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
      <ul className="sidebar-nav"> {/* Χρήση <ul> για τη λίστα πλοήγησης */}
        {renderNavLink("/dashboard", ChartBarSquareIcon, "Dashboard")}

        <div className="sidebar-section-title">Candidates</div>
        {renderNavLink("/candidates/NeedsReview", ClockIcon, "Needs Review")}
        {renderNavLink("/candidates/Accepted", CheckBadgeIcon, "Accepted")}
        {renderNavLink("/candidates/Interested", FunnelIcon, "Interested")}
        {renderNavLink("/candidates/Interview", UserPlusIcon, "Interview")} {/* Αυτό μπορεί να γίνει Interview Scheduled */}
        {renderNavLink("/candidates/Evaluation", AcademicCapIcon, "Evaluation")}
        {renderNavLink("/candidates/OfferMade", GiftIcon, "Offer Made")}
        {renderNavLink("/candidates/Hired", CheckCircleSolidIcon, "Hired", true, true)} {/* isHired=true */}
        {renderNavLink("/candidates/Rejected", XCircleIcon, "Rejected")}
        {renderNavLink("/candidates/Declined", NoSymbolIcon, "Declined")}
        {renderNavLink("/candidates/Processing", ArrowPathIcon, "Processing")}
        {renderNavLink("/candidates/ParsingFailed", ExclamationTriangleIcon, "Parsing Failed")}

        {/* Company Management Section - Εμφανίζεται για company_admin και superadmin */}
        {(currentUser.role === 'company_admin' || currentUser.role === 'superadmin') && (
          <>
            <div className="sidebar-section-title">Company Management</div>
            {renderNavLink("/company/users", UsersIcon, "Manage Users")}
            {renderNavLink("/company/interviews", CalendarDaysIcon, "Company Interviews")} {/* <-- ΝΕΟ LINK */}
          </>
        )}

        {/* Super Admin Section - Εμφανίζεται μόνο για superadmin */}
        {renderNavLink("/admin/companies", BuildingOffice2Icon, "Manage Companies", currentUser.role === 'superadmin')}
        {renderNavLink("/admin/users", ShieldCheckIcon, "Manage All Users", currentUser.role === 'superadmin')}
        {/* Μπορείς να βάλεις τα παραπάνω δύο links κάτω από ένα <div className="sidebar-section-title">Super Admin</div> αν θέλεις */}
        {currentUser.role === 'superadmin' && !renderNavLink("/admin/companies", BuildingOffice2Icon, "Manage Companies", false) && ( // Hacky τρόπος για να μπει τίτλος μόνο αν υπάρχουν τα links
             <div className="sidebar-section-title" style={!renderNavLink("/admin/companies", BuildingOffice2Icon, "", currentUser.role === 'superadmin') ? {display: 'none'} : {}}>Super Admin</div>
        )}


        <div className="sidebar-section-title">Account</div>
        {renderNavLink("/settings", Cog6ToothIcon, "Settings")}
        
        <li> {/* Το κουμπί logout επίσης μέσα σε <li> */}
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