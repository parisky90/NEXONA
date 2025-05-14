// frontend/src/components/Sidebar.jsx
import React from 'react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../App'; // Βεβαιώσου ότι το import είναι σωστό
import './Sidebar.css';

const candidateStatuses = [
  // ... (παραμένει ίδιο) ...
  { name: 'Needs Review', path: '/dashboard', statusParam: 'NeedsReview', exact: true },
  { name: 'Accepted', path: '/accepted', statusParam: 'Accepted' },
  { name: 'Interested', path: '/interested', statusParam: 'Interested' },
  { name: 'Interview', path: '/interview', statusParam: 'Interview' },
  { name: 'Evaluation', path: '/evaluation', statusParam: 'Evaluation' },
  { name: 'Offer Made', path: '/offer', statusParam: 'OfferMade' },
  { name: 'Hired', path: '/hired', statusParam: 'Hired' },
  { name: 'Rejected', path: '/rejected', statusParam: 'Rejected' },
  { name: 'Declined', path: '/declined', statusParam: 'Declined' },
];

function Sidebar() {
  const { currentUser, logout } = useAuth(); // Πάρε και το currentUser

  const handleLogout = async () => {
    console.log("Logout button clicked");
    await logout();
  };

  return (
    <div className="sidebar">
      <div className="sidebar-logo-container">
        <img src="/nexona_logo.png" alt="NEXONA Logo" className="sidebar-logo" />
      </div>

      <nav>
        <ul>
          {/* Candidate Status Links (παραμένουν ίδια) */}
          <li><NavLink to="/dashboard" className={({ isActive }) => isActive ? 'active-link' : ''} end>Needs Review</NavLink></li>
          {candidateStatuses.filter(s => s.name !== 'Needs Review').map((status) => (
            <li key={status.statusParam}><NavLink to={status.path} className={({ isActive }) => isActive ? 'active-link' : ''}>{status.name}</NavLink></li>
          ))}
          
          <li className="separator"><hr /></li>

          {/* --- Links βάσει Ρόλου --- */}
          {currentUser && currentUser.role === 'superadmin' && (
            <>
              <li><NavLink to="/admin/companies" className={({ isActive }) => isActive ? 'active-link' : ''}>Manage Companies</NavLink></li>
              <li><NavLink to="/admin/users" className={({ isActive }) => isActive ? 'active-link' : ''}>Manage All Users</NavLink></li>
              <li className="separator"><hr /></li>
            </>
          )}

          {currentUser && currentUser.role === 'company_admin' && (
            <>
              <li><NavLink to="/company/users" className={({ isActive }) => isActive ? 'active-link' : ''}>Manage My Users</NavLink></li>
              {/* Εδώ μπορείς να προσθέσεις link για Company Settings αν θέλεις */}
              {/* <li><NavLink to="/company/settings" className={({ isActive }) => isActive ? 'active-link' : ''}>My Company Settings</NavLink></li> */}
              <li className="separator"><hr /></li>
            </>
          )}
          {/* --- Τέλος Links βάσει Ρόλου --- */}


          <li><NavLink to="/settings" className={({ isActive }) => isActive ? 'active-link' : ''}>My Settings</NavLink></li>
          <li><button onClick={handleLogout} className="logout-button">Logout</button></li>
        </ul>
      </nav>
    </div>
  );
}

export default Sidebar;