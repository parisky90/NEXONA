// frontend/src/pages/RegisterPage.jsx
import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import apiClient from '../api'; // Βεβαιώσου ότι το path είναι σωστό (../api αν το RegisterPage είναι στο pages/)
import '../AuthForm.css'; // Βεβαιώσου ότι το path είναι σωστό

function RegisterPage() {
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
    company_name: '', // << ΠΡΟΣΘΗΚΗ ΠΕΔΙΟΥ company_name
  });
  const [error, setError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    setError(''); 
    setSuccessMessage(''); 
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccessMessage('');

    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match.');
      return;
    }
    if (formData.password.length < 8) { // Παράδειγμα ελάχιστου μήκους
      setError('Password must be at least 8 characters long.');
      return;
    }
    if (!formData.company_name.trim()) { // Έλεγχος αν το company_name είναι κενό
        setError('Company name is required.');
        return;
    }

    setIsLoading(true);
    try {
      // Αφαίρεσε το confirmPassword από το payload που στέλνεται στο backend
      // Το company_name θα είναι ήδη στο formData και θα συμπεριληφθεί στο payload
      const { confirmPassword, ...payload } = formData; 
      
      const response = await apiClient.post('/register', payload); // Το endpoint είναι /api/v1/register μέσω του apiClient
      
      setSuccessMessage(response.data.message || 'Registration successful! You can now login.');
      // Καθαρισμός φόρμας μετά την επιτυχία
      setFormData({ username: '', email: '', password: '', confirmPassword: '', company_name: '' });
      
      // Προαιρετικά, κάνε redirect στο login μετά από λίγο ή δείξε link
      setTimeout(() => {
        navigate('/login');
      }, 3000); // Redirect after 3 seconds
    } catch (err) {
      setError(err.response?.data?.error || 'Registration failed. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="auth-container card-style">
      <h2>Register New Account</h2>
      <form onSubmit={handleSubmit} className="auth-form">
        {error && <p className="error-message">{error}</p>}
        {successMessage && <p className="success-message" style={{color: 'green', marginBottom: '1rem'}}>{successMessage}</p>}
        
        <div className="form-group">
          <label htmlFor="username">Username:</label>
          <input
            type="text"
            id="username"
            name="username"
            value={formData.username}
            onChange={handleChange}
            required
            className="input-light-gray" // Χρησιμοποίησε την κλάση από το App.css
          />
        </div>
        <div className="form-group">
          <label htmlFor="email">Email:</label>
          <input
            type="email"
            id="email"
            name="email"
            value={formData.email}
            onChange={handleChange}
            required
            className="input-light-gray"
          />
        </div>
        
        {/* --- ΠΡΟΣΘΗΚΗ ΠΕΔΙΟΥ COMPANY NAME --- */}
        <div className="form-group">
          <label htmlFor="company_name">Company Name:</label>
          <input
            type="text"
            id="company_name"
            name="company_name" // Σημαντικό: το όνομα του input
            value={formData.company_name}
            onChange={handleChange}
            required
            className="input-light-gray"
          />
        </div>
        {/* --- ΤΕΛΟΣ ΠΡΟΣΘΗΚΗΣ --- */}

        <div className="form-group">
          <label htmlFor="password">Password:</label>
          <input
            type="password"
            id="password"
            name="password"
            value={formData.password}
            onChange={handleChange}
            required
            minLength="8"
            className="input-light-gray"
          />
        </div>
        <div className="form-group">
          <label htmlFor="confirmPassword">Confirm Password:</label>
          <input
            type="password"
            id="confirmPassword"
            name="confirmPassword"
            value={formData.confirmPassword}
            onChange={handleChange}
            required
            minLength="8"
            className="input-light-gray"
          />
        </div>
       
        <button type="submit" disabled={isLoading} className="button-action button-primary auth-button">
          {isLoading ? 'Registering...' : 'Register'}
        </button>
      </form>
      <p className="auth-link">
        Already have an account? <Link to="/login">Login here</Link>
      </p>
    </div>
  );
}

export default RegisterPage;