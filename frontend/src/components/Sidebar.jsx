// frontend/src/components/Sidebar.jsx
import React from 'react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../App';
import './Sidebar.css';

const candidateStatuses = [
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
  const { logout } = useAuth();

  const handleLogout = async () => {
    console.log("Logout button clicked");
    await logout();
  };

  return (
    <div className="sidebar">
      {/* --- LOGO ADDED HERE --- */}
      <div className="sidebar-logo-container">
        <img src="/nexona_logo.png" alt="NEXONA Logo" className="sidebar-logo" />
        {/* Or use /logo.png if you named it that */}
      </div>
      {/* --- END LOGO --- */}

      <nav>
        <ul>
          {/* Dashboard Link (Needs Review) */}
          <li>
            <NavLink
              to="/dashboard"
              className={({ isActive }) => isActive ? 'active-link' : ''}
              end
            >
              Needs Review
            </NavLink>
          </li>

          {/* Other Candidate Status Links */}
          {candidateStatuses.filter(s => s.name !== 'Needs Review').map((status) => (
            <li key={status.statusParam}>
              <NavLink
                to={status.path}
                className={({ isActive }) => isActive ? 'active-link' : ''}
              >
                {status.name}
              </NavLink>
            </li>
          ))}

          {/* Separator */}
          <li className="separator"><hr /></li>

           {/* Settings Link */}
           <li>
             <NavLink
                 to="/settings"
                 className={({ isActive }) => isActive ? 'active-link' : ''}
             >
                 Settings
             </NavLink>
           </li>


          {/* Logout Button */}
          <li>
            <button onClick={handleLogout} className="logout-button">
              Logout
            </button>
          </li>
        </ul>
      </nav>
    </div>
  );
}

export default Sidebar;