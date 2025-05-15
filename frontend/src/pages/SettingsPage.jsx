// frontend/src/pages/SettingsPage.jsx
import React, { useState, useEffect } from 'react'; // Αφαίρεσα το useCallback αν δεν χρησιμοποιείται
import { useAuth } from '../App'; 
import apiClient from '../api'; 

function SettingsPage() {
  const { currentUser, login: updateAuthContextUser } = useAuth(); 
  const [formData, setFormData] = useState({
    enable_email_interview_reminders: true, // Το όνομα πρέπει να ταιριάζει με το backend model/API
    interview_reminder_lead_time_minutes: 60, // Το όνομα πρέπει να ταιριάζει
    // email_interview_reminders: false, // Αυτό το είχες, αλλά δεν φαίνεται να υπάρχει στο backend settings endpoint
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  useEffect(() => {
    if (currentUser) {
      setFormData({
        // Βεβαιώσου ότι τα ονόματα των πεδίων ταιριάζουν με αυτά που στέλνει το backend στο /session και περιμένει το /settings PUT
        enable_interview_reminders: currentUser.enable_email_interview_reminders ?? true, // Αν το backend στέλνει enable_email_interview_reminders
        interview_reminder_lead_time_minutes: currentUser.interview_reminder_lead_time_minutes ?? 60,
      });
    }
  }, [currentUser]);

  const handleChange = (event) => {
    const { name, value, type, checked } = event.target;
    setFormData(prevData => ({
      ...prevData,
      [name]: type === 'checkbox' ? checked : (name === 'interview_reminder_lead_time_minutes' ? parseInt(value, 10) || 0 : value)
    }));
    setError('');
    setSuccessMessage('');
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setIsLoading(true);
    setError('');
    setSuccessMessage('');

    const payload = {
        enable_email_interview_reminders: formData.enable_interview_reminders, // Προσαρμογή ονόματος αν χρειάζεται
        interview_reminder_lead_time_minutes: formData.interview_reminder_lead_time_minutes
    };

    if (payload.interview_reminder_lead_time_minutes < 5 || payload.interview_reminder_lead_time_minutes > (2 * 24 * 60) /* 2 days */) {
        setError('Reminder lead time must be between 5 and 2880 minutes.');
        setIsLoading(false);
        return;
    }

    try {
      const response = await apiClient.put('/settings', payload); // Στέλνουμε το payload
      setSuccessMessage(response.data.message ||'Settings saved successfully!');
      
      if (response.data && response.data.settings) {
         if (currentUser) {
             const updatedUser = { ...currentUser, ...response.data.settings };
             updateAuthContextUser(updatedUser); 
         }
      }
    } catch (err) {
      const errorMessage = err.response?.data?.error || 'Failed to save settings.';
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  if (!currentUser) {
    return <div className="loading-placeholder card-style">Loading settings...</div>;
  }

  return (
    // Εφάρμοσε card-style από το App.css ή το DashboardPage.css
    <div className="settings-page-container card-style"> 
      <h1>User Settings</h1>
      <p>Configure your preferences for notifications and reminders.</p>

      <form onSubmit={handleSubmit} style={{ marginTop: '2rem' }}>
        {error && <p className="error-message">{error}</p>}
        {successMessage && <p className="success-message" style={{color: 'green', marginBottom: '1rem'}}>{successMessage}</p>}

        <div style={{ marginBottom: '1.5rem' }}>
          <label style={{ display: 'flex', alignItems: 'center', cursor: 'pointer', fontWeight: '500' }}>
            <input
              type="checkbox"
              name="enable_interview_reminders" // Το όνομα πρέπει να ταιριάζει με το state
              checked={formData.enable_interview_reminders}
              onChange={handleChange}
              disabled={isLoading}
              style={{ marginRight: '0.75rem', transform: 'scale(1.3)' }} 
            />
            <span>Enable Interview Reminders</span>
          </label>
          <small style={{ display: 'block', marginLeft: '2.2rem', color: 'var(--text-muted)'}}>
            Enable/disable all reminders for upcoming interviews.
          </small>
        </div>

        <div style={{ marginBottom: '1.5rem', opacity: formData.enable_interview_reminders ? 1 : 0.6 }}>
          <label htmlFor="interview_reminder_lead_time_minutes" style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500' }}>
            Reminder Lead Time (minutes):
          </label>
          <input
            type="number"
            id="interview_reminder_lead_time_minutes"
            name="interview_reminder_lead_time_minutes" // Το όνομα πρέπει να ταιριάζει με το state
            value={formData.interview_reminder_lead_time_minutes}
            onChange={handleChange}
            disabled={isLoading || !formData.enable_interview_reminders} 
            min="5" 
            max="2880" 
            required
            className="input-light-gray" // <<< ΕΦΑΡΜΟΓΗ ΚΛΑΣΗΣ
            style={{ maxWidth: '150px' }} // Περιορισμός πλάτους για να μην είναι τεράστιο
          />
          <small style={{ display: 'block', marginTop: '0.25rem', color: 'var(--text-muted)'}}>
            How many minutes before the interview you want to be reminded (e.g., 60).
          </small>
        </div>
        
        {/* Αν θέλεις να ξαναβάλεις το email reminder, θα πρέπει να υπάρχει και στο backend */}
        {/* <div style={{ marginBottom: '1.5rem', opacity: formData.enable_interview_reminders ? 1 : 0.5 }}> ... </div> */}

        <button
            type="submit"
            disabled={isLoading}
            className="button-action button-primary" // Χρήση global κλάσης
            style={{ minWidth: '150px', marginTop: '1rem' }} 
        >
          {isLoading ? 'Saving...' : 'Save Settings'}
        </button>
      </form>
    </div>
  );
}

export default SettingsPage;