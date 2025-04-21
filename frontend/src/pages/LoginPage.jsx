// frontend/src/pages/LoginPage.jsx
import React, { useState } from 'react';
import { useNavigate, Navigate } from 'react-router-dom'; // Added Navigate for potential logged-in redirect
import { useAuth } from '../App'; // Import useAuth hook from App context
import apiClient from '../api';
import './LoginPage.css'; // Make sure styles exist

function LoginPage() {
  const [username, setUsername] = useState(''); // Can be username or email
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();
  const { currentUser, login } = useAuth(); // Get login function and currentUser from context

  // --- Restore Login Handler ---
  const handleLogin = async (event) => {
    event.preventDefault(); // Prevent default form submission
    setError(''); // Clear previous errors
    setIsLoading(true);

    try {
      const response = await apiClient.post('/login', {
        username: username, // Send username (or email)
        password: password,
        // remember: true // Optional: add a checkbox for this
      });

      if (response.data && response.data.user) {
        login(response.data.user); // Update auth context with user data
        console.log("Login successful, navigating to dashboard.");
        navigate('/dashboard', { replace: true }); // Redirect to dashboard after login
      } else {
        // Should not happen if API returns 200 with user data
        setError('Login failed: Invalid response from server.');
      }
    } catch (err) {
        console.error("Login error:", err);
        if (err.response && err.response.data && err.response.data.error) {
            setError(err.response.data.error); // Show error from backend (e.g., "Invalid username or password")
        } else if (err.request) {
             setError('Login failed: No response from server.');
        }
        else {
            setError('Login failed: An unexpected error occurred.');
        }
    } finally {
      setIsLoading(false);
    }
  };
  // --- End Restore Login Handler ---

  // --- Add Redirect If Already Logged In ---
  // If the user somehow lands here but IS authenticated, redirect them
  if (currentUser) {
    console.log("LoginPage reached, but user is already logged in. Redirecting.");
    return <Navigate to="/dashboard" replace />;
  }
  // --- End Redirect ---


  // --- Restore Login Form JSX ---
  return (
    <div className="login-page-container">
      <div className="login-box">
        <h2>CV Manager Login</h2>
        <form onSubmit={handleLogin}>
          <div className="input-group">
            <label htmlFor="username">Username or Email</label>
            <input
              type="text"
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              disabled={isLoading}
            />
          </div>
          <div className="input-group">
            <label htmlFor="password">Password</label>
            <input
              type="password"
              id="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              disabled={isLoading}
            />
          </div>
          {error && <p className="error-message">{error}</p>}
          <button type="submit" disabled={isLoading} className="login-button">
            {isLoading ? 'Logging in...' : 'Login'}
          </button>
        </form>
      </div>
    </div>
  );
  // --- End Restore Login Form JSX ---

}

export default LoginPage;