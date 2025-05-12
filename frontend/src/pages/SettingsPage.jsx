import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../App'; // Import the useAuth hook to access currentUser
import apiClient from '../api'; // Import the configured axios instance
// Optional: Import a notification library (e.g., react-toastify)
// import { toast } from 'react-toastify';

function SettingsPage() {
  const { currentUser, login: updateAuthContextUser } = useAuth(); // Get user and the login function (to update context)
  const [formData, setFormData] = useState({
    enable_interview_reminders: true,
    reminder_lead_time_minutes: 60,
    email_interview_reminders: false,
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  // Initialize form data from currentUser when the component mounts or user changes
  useEffect(() => {
    if (currentUser) {
      setFormData({
        enable_interview_reminders: currentUser.enable_interview_reminders ?? true,
        reminder_lead_time_minutes: currentUser.reminder_lead_time_minutes ?? 60,
        email_interview_reminders: currentUser.email_interview_reminders ?? false,
      });
    }
  }, [currentUser]);

  // Handle changes in form inputs
  const handleChange = (event) => {
    const { name, value, type, checked } = event.target;
    setFormData(prevData => ({
      ...prevData,
      [name]: type === 'checkbox' ? checked : (type === 'number' ? parseInt(value, 10) || 0 : value)
    }));
    // Clear messages on change
    setError('');
    setSuccessMessage('');
  };

  // Handle form submission
  const handleSubmit = async (event) => {
    event.preventDefault();
    setIsLoading(true);
    setError('');
    setSuccessMessage('');

    // Basic validation (optional, backend validates too)
    if (formData.reminder_lead_time_minutes < 5 || formData.reminder_lead_time_minutes > 1440) {
        setError('Η υπενθύμιση πρέπει να είναι μεταξύ 5 και 1440 λεπτών.');
        // toast.error('Η υπενθύμιση πρέπει να είναι μεταξύ 5 και 1440 λεπτών.');
        setIsLoading(false);
        return;
    }

    try {
      const response = await apiClient.put('/settings', formData);
      setSuccessMessage('Οι ρυθμίσεις αποθηκεύτηκαν επιτυχώς!');
      // toast.success('Οι ρυθμίσεις αποθηκεύτηκαν επιτυχώς!');

      // --- Update Auth Context ---
      // It's good practice to update the context so the rest of the app
      // sees the changes immediately without needing a refresh.
      // We merge the updated settings into the existing currentUser object.
      if (response.data && response.data.settings) {
         // Make sure currentUser exists before trying to spread it
         if (currentUser) {
             const updatedUser = {
                 ...currentUser,
                 ...response.data.settings // Overwrite with the settings returned from backend
             };
             updateAuthContextUser(updatedUser); // Update the context
             console.log("Auth context updated with new settings:", updatedUser);
         } else {
            console.warn("CurrentUser context was null, cannot update settings in context.");
         }
      }
      // --- End Update Auth Context ---

    } catch (err) {
      console.error("Failed to update settings:", err);
      const errorMessage = err.response?.data?.error || 'Αποτυχία αποθήκευσης ρυθμίσεων. Παρακαλώ δοκιμάστε ξανά.';
      setError(errorMessage);
      // toast.error(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  // Render loading state if currentUser is not yet available
  if (!currentUser) {
    return <div className="loading-placeholder">Φόρτωση ρυθμίσεων...</div>;
  }

  return (
    <div className="page-container card-style"> {/* Add card-style for consistency */}
      <h1>Ρυθμίσεις Χρήστη</h1>
      <p>Εδώ μπορείτε να διαμορφώσετε τις προτιμήσεις σας για τις ειδοποιήσεις.</p>

      <form onSubmit={handleSubmit} style={{ marginTop: '2rem' }}>
        {/* Display messages */}
        {error && <p className="error-message">{error}</p>}
        {successMessage && <p style={{ color: 'green', marginBottom: '1rem' }}>{successMessage}</p>} {/* Simple success message */}

        {/* Enable Reminders Checkbox */}
        <div style={{ marginBottom: '1.5rem' }}>
          <label style={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}>
            <input
              type="checkbox"
              name="enable_interview_reminders"
              checked={formData.enable_interview_reminders}
              onChange={handleChange}
              disabled={isLoading}
              style={{ marginRight: '0.5rem', transform: 'scale(1.2)' }} // Slightly larger checkbox
            />
            <span>Ενεργοποίηση Υπενθυμίσεων για Συνεντεύξεις</span>
          </label>
          <small style={{ display: 'block', marginLeft: '1.7rem', color: 'var(--text-light-gray)'}}>
            Ενεργοποιεί/απενεργοποιεί όλες τις υπενθυμίσεις για επερχόμενες συνεντεύξεις.
          </small>
        </div>

        {/* Reminder Lead Time */}
        <div style={{ marginBottom: '1.5rem', opacity: formData.enable_interview_reminders ? 1 : 0.5 }}> {/* Dim if disabled */}
          <label htmlFor="reminder_lead_time_minutes" style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500' }}>
            Υπενθύμιση Πριν από (λεπτά):
          </label>
          <input
            type="number"
            id="reminder_lead_time_minutes"
            name="reminder_lead_time_minutes"
            value={formData.reminder_lead_time_minutes}
            onChange={handleChange}
            disabled={isLoading || !formData.enable_interview_reminders} // Disable if main toggle is off
            min="5" // Set min/max for browser validation hint
            max="1440" // e.g., 1 day
            required
            className="input-light-gray" // Use existing style from App.css
            style={{ width: '100px' }} // Adjust width as needed
          />
          <small style={{ display: 'block', marginTop: '0.25rem', color: 'var(--text-light-gray)'}}>
            Πόσα λεπτά πριν τη συνέντευξη θέλετε να λαμβάνετε υπενθύμιση (π.χ., 60).
          </small>
        </div>

        {/* Email Reminders Checkbox */}
        <div style={{ marginBottom: '1.5rem', opacity: formData.enable_interview_reminders ? 1 : 0.5 }}> {/* Dim if disabled */}
          <label style={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}>
            <input
              type="checkbox"
              name="email_interview_reminders"
              checked={formData.email_interview_reminders}
              onChange={handleChange}
              disabled={isLoading || !formData.enable_interview_reminders} // Disable if main toggle is off
              style={{ marginRight: '0.5rem', transform: 'scale(1.2)' }}
            />
            <span>Αποστολή Υπενθύμισης και με Email</span>
          </label>
          <small style={{ display: 'block', marginLeft: '1.7rem', color: 'var(--text-light-gray)'}}>
            Αν είναι ενεργοποιημένο, θα λαμβάνετε υπενθύμιση και στο email σας ({currentUser.email}).
          </small>
        </div>

        {/* Submit Button */}
        <button
            type="submit"
            disabled={isLoading}
            className="button-save button-action" // Use existing styles
            style={{ minWidth: '120px' }} // Ensure minimum width
        >
          {isLoading ? 'Αποθήκευση...' : 'Αποθήκευση Ρυθμίσεων'}
        </button>
      </form>
    </div>
  );
}

export default SettingsPage;