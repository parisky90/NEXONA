# NEXONA - Advanced CV Management Platform

NEXONA is a web-based application designed to streamline and manage the job candidate lifecycle across various hiring stages. It features a Flask backend API and a React frontend, with functionalities for CV uploading, parsing (integration planned), candidate tracking, interview scheduling, and offer management.

## Project Status

Currently, the application supports core functionalities including user registration (with admin approval mécanisme), login, CV upload (to AWS S3), candidate status management through a defined pipeline, interview scheduling with email notifications to candidates (for confirmation/declination), and an HR rating system. A history log tracks changes to candidate status and associated notes.

**Latest Implemented Features:**
*   User Registration and Login System.
*   Admin approval for new user accounts (manual DB update for now).
*   Candidate lifecycle management through multiple statuses.
*   CV Upload to S3.
*   Interview Scheduling with automated email invitations to candidates.
*   Candidate interview confirmation/declination tracking.
*   HR-defined rating for candidates (dropdown selection).
*   Ability to "Re-evaluate" rejected/declined candidates.
*   Option to "Skip Interview" and move a candidate directly to Evaluation.
*   Management of multiple offers per candidate (amount, notes, date).
*   Notes per candidate, with notes at the time of status change saved to history.
*   Celery for background tasks (parsing, email sending).
*   Dockerized environment for development and deployment.

## Technologies Used

*   **Backend:**
    *   Python, Flask, SQLAlchemy, Flask-Migrate
    *   Flask-Login, Flask-CORS, Flask-Mail
    *   Celery, Redis
    *   Gunicorn
*   **Frontend:**
    *   React, Vite
    *   JavaScript (ES6+), JSX
    *   Axios, React Router
    *   CSS3 (using CSS Variables)
*   **Database:** PostgreSQL
*   **Storage:** AWS S3 (for CVs)
*   **Deployment:** Docker, Docker Compose

## Project Structure
Use code with caution.
Markdown
NEXONA/
├── backend/
│ ├── app/
│ │ ├── init.py # Flask app factory, extension initialization
│ │ ├── models.py # SQLAlchemy DB models (User, Candidate, Position, etc.)
│ │ ├── config.py # Configuration classes (loads from .env)
│ │ ├── tasks/ # Celery tasks
│ │ │ ├── parsing.py
│ │ │ ├── communication.py
│ │ │ └── reminders.py
│ │ ├── api/
│ │ │ ├── init.py
│ │ │ └── routes.py # API Blueprints and endpoints
│ │ ├── services/ # Business logic services (S3, Textkernel mock)
│ │ └── static/, templates/ (if any)
│ ├── migrations/ # Flask-Migrate scripts
│ ├── .env.example # Example environment variables (DO NOT COMMIT .env)
│ ├── celery_worker.py # Celery worker setup
│ ├── create_admin.py # Script to create initial admin user
│ ├── create_candidate.py # Script to create test candidate
│ ├── Dockerfile
│ ├── docker-compose.yml
│ └── requirements.txt
│
└── frontend/
├── public/ # Static assets for Vite build
├── src/
│ ├── assets/
│ ├── components/ # Reusable React components
│ ├── pages/ # Top-level page components
│ ├── App.css
│ ├── App.jsx # Main App component, routing
│ ├── api.js # Axios client setup
│ ├── AuthForm.css # Styles for Login/Register
│ ├── index.css
│ └── main.jsx # React app entry point
├── .gitignore
├── package.json
└── vite.config.js
## Setup & Installation

### Prerequisites
*   Docker & Docker Compose
*   Git
*   AWS S3 Bucket (and credentials)
*   Email Server/Service (for sending emails)

### Backend Setup
1.  Navigate to the `backend/` directory.
2.  Create a `.env` file by copying `.env.example` (`cp .env.example .env`).
3.  Fill in the required environment variables in `.env` (DATABASE_URL, SECRET_KEY, AWS credentials, S3_BUCKET, MAIL settings, APP_BASE_URL, COMPANY_DOMAINS etc.).
4.  Build and run the Docker containers:
    ```bash
    docker-compose up -d --build
    ```
5.  Apply database migrations:
    ```bash
    docker-compose exec web flask db upgrade
    ```
6.  Create an initial admin user:
    ```bash
    docker-compose exec web python create_admin.py
    ```
    (You might need to manually approve this user in the database: `UPDATE users SET is_active=true, is_approved_account=true WHERE username='your_admin_user';`)

### Frontend Setup
1.  Navigate to the `frontend/` directory.
2.  Install dependencies:
    ```bash
    npm install
    ```
3.  Start the development server:
    ```bash
    npm run dev
    ```
    The frontend will typically be available at `http://localhost:5173`.

## Current Next Steps (Roadmap - Excluding AI for now)

1.  **Admin Panel for User Management:**
    *   UI for SaaS admin to view registered users.
    *   Functionality to approve/revoke `is_approved_account` status for users.
2.  **Email Confirmation for New Registrations:**
    *   Backend task to send confirmation email with a unique token.
    *   Backend endpoint to handle token verification and set `user.is_active = true`.
3.  **Google Calendar Integration:**
    *   OAuth 2.0 flow for user authorization.
    *   API to create calendar events for scheduled interviews.
    *   Frontend UI for connecting Google Calendar and adding events.
4.  **Enhanced Notifications:**
    *   In-app dashboard notifications for interview reminders (for recruiters).
    *   Notifications (email/in-app) to recruiters when candidates confirm/decline interviews.
5.  **Advanced Filtering for Candidate Lists:**
    *   Backend API support for filtering by position, HR rating, etc.
    *   Frontend UI controls for applying these filters.
6.  **Full UI Localization (Greek).**
7.  **Comprehensive Testing (Unit, Integration).**
8.  **Deployment Preparation (Hetzner).**

## Known Issues / Points of Attention
*   The Textkernel API integration for CV parsing is currently dependent on a valid API key. If not available, CVs are stored but not auto-parsed.
*   The "continuous loading" issue on some frontend pages was recently addressed by ensuring `setIsUpdating(false)` is always called in `finally` blocks. Monitor for any recurrence.
*   S3 bucket name in `.env` must be correctly set for CV viewing/upload to function.

## Contributing
(Details on how to contribute if this were an open project)

## License
(Specify your license, e.g., MIT, Proprietary)