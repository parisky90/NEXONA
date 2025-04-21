# backend/app/models.py

import uuid
from datetime import datetime, timezone # Use timezone-aware datetime
from app import db # Import db instance from app package (__init__.py)
from sqlalchemy.dialects.postgresql import JSONB # Use JSONB for PostgreSQL history field
from werkzeug.security import generate_password_hash, check_password_hash # For passwords
from flask_login import UserMixin # Inherit from UserMixin for Flask-Login

# --- User Model (Includes Notification Prefs) ---
# Implement UserMixin for Flask-Login compatibility
class User(UserMixin, db.Model):
    __tablename__ = 'users' # Explicit table name recommended
    id = db.Column(db.Integer, primary_key=True) # Simple integer ID for users
    username = db.Column(db.String(64), index=True, unique=True, nullable=False)
    email = db.Column(db.String(120), index=True, unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=True) # Store hash

    # Notification Preference Fields
    enable_interview_reminders = db.Column(db.Boolean, default=True, nullable=False)
    reminder_lead_time_minutes = db.Column(db.Integer, default=60, nullable=False) # Default to 60 minutes
    email_interview_reminders = db.Column(db.Boolean, default=False, nullable=False) # Default OFF for email reminders

    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def set_password(self, password):
        """Hashes the password and stores it."""
        if password:
            self.password_hash = generate_password_hash(password)
        else:
            self.password_hash = None

    def check_password(self, password):
        """Checks if the provided password matches the stored hash."""
        if self.password_hash and password:
            return check_password_hash(self.password_hash, password)
        return False

    def __repr__(self):
        return f'<User {self.username}>'

    # Flask-Login required methods are inherited from UserMixin.
    # get_id uses the 'id' primary key by default.

# --- End User Model ---


# Helper table for many-to-many relationship between candidates and positions
candidate_position_association = db.Table('candidate_position_association',
    db.Column('candidate_id', db.String(36), db.ForeignKey('candidates.candidate_id', ondelete='CASCADE'), primary_key=True),
    db.Column('position_id', db.Integer, db.ForeignKey('positions.position_id', ondelete='CASCADE'), primary_key=True)
)

class Candidate(db.Model):
    """Model representing a job candidate."""
    __tablename__ = 'candidates'

    # Core Candidate Info
    candidate_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    first_name = db.Column(db.String(100), nullable=True)
    last_name = db.Column(db.String(100), nullable=True)
    email = db.Column(db.String(255), nullable=True, index=True, unique=False)
    phone_number = db.Column(db.String(50), nullable=True)
    age = db.Column(db.Integer, nullable=True)

    # CV File Info
    cv_original_filename = db.Column(db.String(255), nullable=False)
    cv_storage_path = db.Column(db.String(512), nullable=False, unique=True)

    # Parsed Content Fields
    education = db.Column(db.Text, nullable=True)
    work_experience = db.Column(db.Text, nullable=True)
    languages = db.Column(db.Text, nullable=True)
    seminars = db.Column(db.Text, nullable=True)

    # Application Tracking Info
    submission_date = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    current_status = db.Column(db.String(50), nullable=False, default='Processing', index=True)
    notes = db.Column(db.Text, nullable=True) # General/Evaluation notes
    history = db.Column(JSONB, nullable=True) # Store status changes etc.

    # Interview Fields
    interview_datetime = db.Column(db.DateTime(timezone=True), nullable=True)
    interview_location = db.Column(db.String(255), nullable=True)

    # Evaluation Field
    evaluation_rating = db.Column(db.String(50), nullable=True)

    # Offer Fields
    offer_details = db.Column(db.Text, nullable=True)
    offer_response_date = db.Column(db.DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # --- Relationships ---
    positions = db.relationship(
        'Position', secondary=candidate_position_association,
        back_populates='candidates', lazy='select'
    )

    # --- Methods ---
    def __repr__(self):
        return f'<Candidate {self.get_full_name()} ({self.candidate_id})>'

    def get_full_name(self):
        parts = [self.first_name, self.last_name]
        return " ".join(filter(None, parts)).strip() or "N/A"

    def get_position_names(self):
        return [pos.position_name for pos in self.positions] if self.positions else []

    def to_dict(self, include_cv_url=False, cv_url=None):
        """Serializes the Candidate object to a dictionary for API responses."""
        data = {
            'candidate_id': self.candidate_id, 'first_name': self.first_name, 'last_name': self.last_name,
            'full_name': self.get_full_name(), 'email': self.email, 'phone_number': self.phone_number, 'age': self.age,
            'cv_original_filename': self.cv_original_filename,
            'education': self.education, 'work_experience': self.work_experience, 'languages': self.languages, 'seminars': self.seminars,
            'submission_date': self.submission_date.isoformat() if self.submission_date else None,
            'current_status': self.current_status, 'positions': self.get_position_names(),
            'notes': self.notes, 'history': self.history,
            'interview_datetime': self.interview_datetime.isoformat() if self.interview_datetime else None,
            'interview_location': self.interview_location, 'evaluation_rating': self.evaluation_rating,
            'offer_details': self.offer_details, 'offer_response_date': self.offer_response_date.isoformat() if self.offer_response_date else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_cv_url and cv_url: data['cv_url'] = cv_url
        return data


class Position(db.Model):
    """Model representing a job position candidates can apply for."""
    __tablename__ = 'positions'
    position_id = db.Column(db.Integer, primary_key=True)
    position_name = db.Column(db.String(255), nullable=False, unique=True, index=True)

    candidates = db.relationship(
        'Candidate', secondary=candidate_position_association,
        back_populates='positions', lazy='select'
    )

    def __repr__(self):
        return f'<Position {self.position_name}>'

    def to_dict(self):
        return {'position_id': self.position_id, 'position_name': self.position_name}