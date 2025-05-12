// frontend/src/pages/LoginPage.jsx
import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom'; // Πρόσθεσα το Link
import apiClient from '../api';
import { useAuth } from '../App'; // Για να καλέσεις τη login συνάρτηση του context
import '../AuthForm.css'; // Ένα επίπεδο πάνω από το 'pages'

function LoginPage() {
  const [username, setUsername] = useState(''); // Μπορεί να είναι username ή email
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();
  const { login } = useAuth(); // Πάρε τη login από το context

  const handleLogin = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');
    try {
      const response = await apiClient.post('/login', { username, password });
      // Το backend επιστρέφει το user object στο response.data.user
      login(response.data.user); // Ενημέρωσε το context με τα στοιχεία του χρήστη
      navigate('/dashboard'); // Πήγαινε στο dashboard μετά το επιτυχές login
    } catch (err) {
      console.error("Login error:", err);
      setError(err.response?.data?.error || 'Login failed. Please check your credentials.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="auth-container card-style"> {/* Χρησιμοποίησε το κοινό class */}
      <h2>Login to NEXONA</h2>
      <form onSubmit={handleLogin} className="auth-form">
        {error && <p className="error-message">{error}</p>}
        <div className="form-group">
          <label htmlFor="username">Username or Email:</label>
          <input
            type="text"
            id="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            className="input-light-gray"
            autoComplete="username"
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
            className="input-light-gray"
            autoComplete="current-password"
          />
        </div>
        <button type="submit" disabled={isLoading} className="button-action button-primary auth-button">
          {isLoading ? 'Logging in...' : 'Login'}
        </button>
      </form>
      {/* --- ΠΡΟΣΘΗΚΗ LINK ΓΙΑ REGISTER --- */}
      <p className="auth-link">
        Don't have an account? <Link to="/register">Register here</Link>
      </p>
      {/* --- ΤΕΛΟΣ ΠΡΟΣΘΗΚΗΣ LINK --- */}
    </div>
  );
}

export default LoginPage;