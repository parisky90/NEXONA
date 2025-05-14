// frontend/src/pages/LoginPage.jsx
import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import apiClient from '../api';
import { useAuth } from '../App';
import '../AuthForm.css'; // Βεβαιώσου ότι το path είναι σωστό (ένα επίπεδο πάνω)

function LoginPage() {
  // --- ΑΛΛΑΓΗ ΟΝΟΜΑΤΟΣ STATE VARIABLE ---
  const [loginIdentifier, setLoginIdentifier] = useState(''); // Από username σε loginIdentifier
  // --- ΤΕΛΟΣ ΑΛΛΑΓΗΣ ---
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();
  const { login } = useAuth();

  const handleLogin = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');
    try {
      // --- ΑΛΛΑΓΗ ΣΤΟ PAYLOAD ---
      const response = await apiClient.post('/login', {
        login_identifier: loginIdentifier, // Στέλνουμε login_identifier
        password: password
      });
      // --- ΤΕΛΟΣ ΑΛΛΑΓΗΣ ---
      
      if (response.data && response.data.user) {
        login(response.data.user);
        navigate('/dashboard');
      } else {
        // Αυτό δεν θα έπρεπε να συμβεί αν το backend επιστρέφει σωστά το user object
        setError('Login successful, but no user data received.');
        console.error("Login successful but no user data in response:", response.data);
      }
    } catch (err) {
      console.error("Login error object:", err);
      if (err.response) {
        console.error("Login error response data:", err.response.data);
        setError(err.response.data?.error || `Login failed. Status: ${err.response.status}`);
      } else if (err.request) {
        setError('Login failed: No response from server. Please check network connection and if the backend is running.');
      } else {
        setError('Login failed: An unexpected error occurred.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    // Το AuthForm.css θα πρέπει να είναι ένα επίπεδο πάνω (../AuthForm.css)
    // ή να προσαρμόσεις το import path ανάλογα με τη δομή σου.
    // Υποθέτοντας ότι το AuthForm.css είναι στο src/AuthForm.css
    // και το LoginPage.jsx είναι στο src/pages/LoginPage.jsx, τότε το ../AuthForm.css είναι σωστό.
    <div className="auth-container card-style">
      <h2>Login to NEXONA</h2>
      <form onSubmit={handleLogin} className="auth-form">
        {error && <p className="error-message">{error}</p>}
        <div className="form-group">
          <label htmlFor="loginIdentifier">Username or Email:</label> {/* Άλλαξε και το htmlFor */}
          <input
            type="text"
            id="loginIdentifier" // Άλλαξε και το id
            value={loginIdentifier} // Χρησιμοποιεί το νέο state
            onChange={(e) => setLoginIdentifier(e.target.value)} // Ενημερώνει το νέο state
            required
            className="input-light-gray" // Εφάρμοσε το style σου
            autoComplete="username" // Το autocomplete μπορεί να παραμείνει username
          />
        </div>
        <div className="form-group">
          <label htmlFor="password">Password:</label>
          <input
            type="password"
            id="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            className="input-light-gray" // Εφάρμοσε το style σου
            autoComplete="current-password"
          />
        </div>
        <button type="submit" disabled={isLoading} className="button-action button-primary auth-button">
          {isLoading ? 'Logging in...' : 'Login'}
        </button>
      </form>
      <p className="auth-link">
        Don't have an account? <Link to="/register">Register here</Link>
      </p>
    </div>
  );
}

export default LoginPage;