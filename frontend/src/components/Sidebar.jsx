// frontend/src/components/Sidebar.jsx
import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../App'; // Import useAuth
import './Sidebar.css';

// Define statuses for sidebar links
const candidateStatuses = [
  { name: 'Needs Review', path: '/dashboard', statusParam: 'NeedsReview', exact: true }, // Dashboard shows NeedsReview
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
  const { logout } = useAuth(); // Get the logout function from context
  const navigate = useNavigate();

  // --- Restore Logout Handler ---
  const handleLogout = async () => {
    console.log("Logout button clicked");
    // Call the logout function provided by AuthContext in App.jsx
    await logout();
    // No need to navigate here, App.jsx routing handles redirect when currentUser becomes null
    // navigate('/login'); // This navigation is now handled by App.jsx's router
  };
  // --- End Restore Logout Handler ---

  return (
    <div className="sidebar">
      <nav>
        <ul>
          {/* Dashboard Link */}
          <li>
            <NavLink
              to="/dashboard" // Main link for Needs Review
              className={({ isActive }) => isActive ? 'active-link' : ''}
              end // Use 'end' prop for exact matching of index/dashboard route
            >
              Needs Review
            </NavLink>
          </li>

          {/* Candidate Status Links */}
          {candidateStatuses.filter(s => s.name !== 'Needs Review').map((status) => ( // Filter out Needs Review as it's covered by Dashboard
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
            {/* Changed from NavLink to button for semantic correctness */}
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