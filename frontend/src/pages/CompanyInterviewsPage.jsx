// frontend/src/pages/CompanyInterviewsPage.jsx
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Calendar, momentLocalizer, Views } from 'react-big-calendar';
import moment from 'moment';
import 'react-big-calendar/lib/css/react-big-calendar.css';
import companyAdminService from '../services/companyAdminService';
import { useAuth } from '../App';
import { useNavigate } from 'react-router-dom';
import CustomCalendarEvent from '../components/CustomCalendarEvent'; // <<< ΝΕΟ IMPORT

const localizer = momentLocalizer(moment);

function CompanyInterviewsPage() {
  const { currentUser } = useAuth();
  const navigate = useNavigate();
  const [events, setEvents] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  
  const [currentDate, setCurrentDate] = useState(new Date());
  const [currentView, setCurrentView] = useState(Views.MONTH);

  const companyIdForFetch = useMemo(() => {
      if (!currentUser) return null;
      return currentUser.role === 'superadmin' ? null : currentUser.company_id; 
  }, [currentUser]);

  const fetchCalendarEvents = useCallback(async (fetchRange) => {
    if (!currentUser) {
        setIsLoading(false);
        setError("User not authenticated.");
        setEvents([]);
        return;
    }
    
    let companyIdToSend = companyIdForFetch; 
    if (currentUser.role === 'superadmin' && !companyIdToSend){
        // This should be handled by a UI where superadmin selects a company
        // For now, if no company is selected by SA, the backend will likely require company_id param.
        // Let's assume the backend will handle returning an error or empty list if SA doesn't provide company_id.
        console.warn("Superadmin viewing interviews without a selected company. Backend might require company_id param for GET /company/interviews.");
    }

    setIsLoading(true);
    setError('');
    try {
      const params = {
        start: fetchRange.start.toISOString(),
        end: fetchRange.end.toISOString(),
      };
      // Send company_id only if it's explicitly set (e.g., for SA who has selected a company,
      // or if it's derived from a non-SA user).
      // For company_admin, the backend determines company_id from current_user.
      if (currentUser.role === 'superadmin' && companyIdToSend) { 
          params.company_id = companyIdToSend;
      }

      const interviewData = await companyAdminService.getCompanyInterviews(params);
      const formattedEvents = interviewData.map(event => ({
        ...event, // The backend already sends title, start, end, resource
        start: new Date(event.start), 
        end: new Date(event.end),     
      }));
      setEvents(formattedEvents);
    } catch (err) {
      console.error("Error fetching interviews for calendar:", err);
      setError(err.error || 'Failed to load interviews.');
      setEvents([]);
    } finally {
      setIsLoading(false);
    }
  }, [currentUser, companyIdForFetch]); // Removed fetchCalendarEvents from dependency array of itself

  const handleNavigate = useCallback((newDate) => {
    setCurrentDate(newDate);
  }, []);

  const handleViewChange = useCallback((newView) => {
    setCurrentView(newView);
  }, []);

  const handleRangeChange = useCallback((range) => {
    let startDate, endDate;
    if (Array.isArray(range)) { // For week/day view
        startDate = moment(range[0]).startOf('day').toDate();
        // For day view, range can be a single date, so range[range.length-1] is safe.
        // For week view, it's an array of dates in the week.
        endDate = moment(range[range.length - 1]).endOf('day').toDate();
    } else if (range.start && range.end) { // For month view (usually an object)
        startDate = moment(range.start).toDate();
        endDate = moment(range.end).toDate();
    } else { 
        console.warn("Unexpected range format from onRangeChange:", range);
        // Fallback to current view's range if range format is unknown
        const M = moment(currentDate);
        startDate = M.clone().startOf(currentView.toLowerCase()).toDate();
        endDate = M.clone().endOf(currentView.toLowerCase()).toDate();
    }
    fetchCalendarEvents({ start: startDate, end: endDate });
  }, [fetchCalendarEvents, currentDate, currentView]); // Added currentDate and currentView to deps of handleRangeChange

  useEffect(() => {
    // Initial fetch based on default view and date
    const M = moment(currentDate);
    let start, end;
    if (currentView === Views.MONTH) {
        start = M.clone().startOf('month').startOf('week').toDate(); // Get the full displayed range for month
        end = M.clone().endOf('month').endOf('week').toDate();
    } else if (currentView === Views.WEEK) {
        start = M.clone().startOf('week').toDate();
        end = M.clone().endOf('week').toDate();
    } else if (currentView === Views.DAY) {
        start = M.clone().startOf('day').toDate();
        end = M.clone().endOf('day').toDate();
    } else { // Agenda or other views
        start = M.clone().startOf('week').toDate(); // Default for agenda (can be refined)
        end = M.clone().add(1, 'month').endOf('week').toDate(); // Fetch a bit more for agenda
    }
    fetchCalendarEvents({ start, end });
  }, [fetchCalendarEvents, currentDate, currentView]); // Fetch when currentDate or currentView changes.

  const handleSelectEvent = (event) => {
    if (event.resource && event.resource.candidate_id) {
        navigate(`/candidate/${event.resource.candidate_id}`);
    }
  };
  
  const { views: calendarViews } = useMemo(() => ({ // Renamed to avoid conflict
    views: [Views.MONTH, Views.WEEK, Views.DAY, Views.AGENDA],
  }), []);

  if (!currentUser && !isLoading) {
    return <div className="admin-page-container card-style error-message">Please log in to view company interviews.</div>;
  }
  
  // Removed superadmin specific message here, as fetchCalendarEvents will handle it or backend will respond.

  return (
    <div className="admin-page-container card-style" style={{ height: 'calc(100vh - 100px)' }}> {/* Adjusted height slightly */}
      <h1 style={{ textAlign: 'center', marginBottom: '1rem' }}>Company Interview Calendar</h1>
      
      {error && <div className="notification is-danger" role="alert" style={{marginBottom: '1rem'}}>{error}</div>}
      {isLoading && <div className="loading-placeholder" style={{textAlign: 'center', padding: '1rem'}}>Loading calendar events...</div>}

      <Calendar
        localizer={localizer}
        events={events}
        startAccessor="start"
        endAccessor="end"
        views={calendarViews} // Use renamed variable
        date={currentDate} 
        view={currentView}   
        onNavigate={handleNavigate}
        onView={handleViewChange}
        onRangeChange={handleRangeChange} 
        style={{ height: '100%' }}
        onSelectEvent={handleSelectEvent}
        selectable={false} 
        components={{
            event: CustomCalendarEvent // <<< ΧΡΗΣΗ ΤΟΥ CUSTOM EVENT COMPONENT
        }}
        eventPropGetter={(event) => { // Αυτό μπορεί να συνδυαστεί με το styling στο CustomCalendarEvent
            let style = {}; // Το βασικό styling θα είναι στο CSS του CustomCalendarEvent
            // Μπορείς να προσθέσεις custom background color εδώ αν θέλεις, το οποίο θα περαστεί στο style του event wrapper
            if (event.resource?.interview_type?.toLowerCase().includes('technical')) {
                style.backgroundColor = '#5cb85c'; 
            } else if (event.resource?.interview_type?.toLowerCase().includes('hr')) {
                style.backgroundColor = '#f0ad4e'; 
            } else {
                style.backgroundColor = '#3174ad'; // Default
            }
            // Το custom component θα πάρει αυτό το style μέσω του wrapper του react-big-calendar
            return { style };
        }}
        messages={{ 
            today: 'Today', previous: 'Back', next: 'Next',
            month: 'Month', week: 'Week', day: 'Day', agenda: 'Agenda',
            noEventsInRange: 'There are no interviews in this range.'
        }}
      />
    </div>
  );
}
export default CompanyInterviewsPage;