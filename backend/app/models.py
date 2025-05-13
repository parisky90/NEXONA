# backend/app/models.py
import uuid
from datetime import datetime, timezone as dt_timezone # Renamed to avoid conflict with celery.timezone
from app import db # Assuming db is initialized in app/__init__.py
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import UniqueConstraint, event
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin


class Company(db.Model):
    __tablename__ = 'companies'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True, index=True)

    owner_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(dt_timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(dt_timezone.utc),
                           onupdate=lambda: datetime.now(dt_timezone.utc))

    # Relationships
    # Explicitly define foreign_keys for clarity if User.company_id is the link
    users = db.relationship('User', foreign_keys='User.company_id', back_populates='company', lazy='dynamic')
    candidates = db.relationship('Candidate', back_populates='company', lazy='dynamic')
    positions = db.relationship('Position', back_populates='company', lazy='dynamic')
    settings = db.relationship('CompanySettings', back_populates='company', uselist=False,
                               cascade="all, delete-orphan") # company backref is implicitly created

    def __repr__(self):
        return f'<Company {self.name} (ID: {self.id})>'


class CompanySettings(db.Model):
    __tablename__ = 'company_settings'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, unique=True,
                           index=True)

    # Templates and company-wide settings (managed by superadmin/company_admin)
    rejection_email_template = db.Column(db.Text, nullable=True)
    interview_invitation_email_template = db.Column(db.Text, nullable=True)
    # This could be a company-level default or override for reminder timing
    default_interview_reminder_timing_minutes = db.Column(db.Integer, default=60, nullable=False)
    # Company-wide toggle for enabling/disabling the reminder feature for its users
    # (individual users still need their own setting enabled)
    enable_reminders_feature_for_company = db.Column(db.Boolean, default=True, nullable=False)


    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(dt_timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(dt_timezone.utc),
                           onupdate=lambda: datetime.now(dt_timezone.utc))

    # Relationship
    company = db.relationship('Company', back_populates='settings')


    def __repr__(self):
        return f'<CompanySettings for Company ID: {self.company_id}>'


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True, nullable=False)
    email = db.Column(db.String(120), index=True, unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=True) # Nullable if using external auth or invited users

    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=True) # Nullable for superadmin

    is_active = db.Column(db.Boolean, nullable=False, default=False) # Default to False, activate upon confirmation/approval
    role = db.Column(db.String(50), nullable=False, default='user') # e.g., 'superadmin', 'company_admin', 'user'

    # User-specific preferences for interview reminders
    enable_email_interview_reminders = db.Column(db.Boolean, default=True, nullable=False)
    interview_reminder_lead_time_minutes = db.Column(db.Integer, default=60, nullable=False) # e.g., 60 minutes before

    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(dt_timezone.utc))
    confirmed_on = db.Column(db.DateTime(timezone=True), nullable=True) # If email confirmation is used

    # Relationships
    company = db.relationship('Company', foreign_keys=[company_id], back_populates='users')

    def set_password(self, password):
        if password:
            self.password_hash = generate_password_hash(password)
        else:
            self.password_hash = None # Allows for passwordless accounts initially if needed

    def check_password(self, password):
        if self.password_hash and password:
            return check_password_hash(self.password_hash, password)
        return False

    def __repr__(self):
        return f'<User {self.username} (Role: {self.role})>'

    def to_dict(self, include_company_info=False): # Basic to_dict, expand as needed
        data = {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'company_id': self.company_id,
            'role': self.role,
            'is_active': self.is_active,
            'enable_email_interview_reminders': self.enable_email_interview_reminders,
            'interview_reminder_lead_time_minutes': self.interview_reminder_lead_time_minutes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'confirmed_on': self.confirmed_on.isoformat() if self.confirmed_on else None,
        }
        if include_company_info and self.company:
            data['company_name'] = self.company.name
        return data


candidate_position_association = db.Table('candidate_position_association',
    db.Column('candidate_id', db.String(36), db.ForeignKey('candidates.candidate_id', ondelete='CASCADE'), primary_key=True),
    db.Column('position_id', db.Integer, db.ForeignKey('positions.position_id', ondelete='CASCADE'), primary_key=True)
)


class Candidate(db.Model):
    __tablename__ = 'candidates'
    candidate_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False, index=True)

    first_name = db.Column(db.String(100), nullable=True)
    last_name = db.Column(db.String(100), nullable=True)
    email = db.Column(db.String(255), nullable=True, index=True, unique=False) # Not globally unique, but per company
    phone_number = db.Column(db.String(50), nullable=True)
    age = db.Column(db.Integer, nullable=True) # Consider if age is truly needed (GDPR)

    cv_original_filename = db.Column(db.String(255), nullable=True) # Changed to nullable if CV is not always present initially
    cv_storage_path = db.Column(db.String(512), nullable=True, unique=True) # Changed to nullable, unique if present

    # Fields for parsed CV data (TextKernel or other)
    education_summary = db.Column(db.Text, nullable=True) # Renamed from 'education' for clarity
    experience_summary = db.Column(db.Text, nullable=True) # Renamed from 'work_experience'
    skills_summary = db.Column(db.Text, nullable=True) # New field for skills
    languages = db.Column(db.Text, nullable=True)
    seminars = db.Column(db.Text, nullable=True) # Or certifications

    submission_date = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(dt_timezone.utc), index=True)
    current_status = db.Column(db.String(50), nullable=False, default='New', index=True) # e.g., New, Screening, Interview, Offer
    notes = db.Column(db.Text, nullable=True)
    history = db.Column(JSONB, nullable=True, default=list) # Stores status changes, actions, etc.

    # Interview specific fields
    interview_datetime = db.Column(db.DateTime(timezone=True), nullable=True)
    interview_location = db.Column(db.String(255), nullable=True) # Could be physical or virtual link
    interview_type = db.Column(db.String(100), nullable=True) # e.g., "Phone Screen", "Technical Interview"
    interviewers = db.Column(JSONB, nullable=True, default=list) # List of User IDs or names

    # Candidate confirmation for interviews
    candidate_confirmation_status = db.Column(db.String(50), nullable=True, default='Pending', index=True) # Pending, Confirmed, Declined
    confirmation_uuid = db.Column(db.String(36), unique=True, nullable=True, default=lambda: str(uuid.uuid4()), index=True)

    evaluation_rating = db.Column(db.String(50), nullable=True) # e.g., Strong Hire, Hire, No Hire
    offers = db.Column(JSONB, nullable=True, default=list) # [{position_id, offer_date, salary, status}]

    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(dt_timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(dt_timezone.utc),
                           onupdate=lambda: datetime.now(dt_timezone.utc))

    # Relationships
    company = db.relationship('Company', back_populates='candidates')
    positions = db.relationship('Position', secondary=candidate_position_association, back_populates='candidates', lazy='select')

    # Unique constraint for email within a company
    __table_args__ = (UniqueConstraint('email', 'company_id', name='uq_candidate_email_company'),)

    def __repr__(self):
        return f'<Candidate {self.get_full_name()} ({self.candidate_id}) for Company ID {self.company_id}>'

    def get_full_name(self):
        parts = [self.first_name, self.last_name]
        return " ".join(filter(None, parts)).strip() or "N/A"

    def get_position_names(self):
        return [pos.position_name for pos in self.positions] if self.positions else []

    def add_history_event(self, event_type, description, actor_id=None, details=None):
        if self.history is None: self.history = []
        event_entry = {
            "timestamp": datetime.now(dt_timezone.utc).isoformat(),
            "event_type": event_type, # e.g., "status_change", "note_added", "interview_scheduled"
            "description": description,
            "actor_id": actor_id, # User ID who performed the action
            "details": details or {} # Any additional structured data
        }
        # Ensure history is treated as a mutable list by SQLAlchemy
        self.history = self.history + [event_entry]


    def to_dict(self, include_cv_url=False, cv_url=None):
        data = {
            'candidate_id': self.candidate_id,
            'company_id': self.company_id,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'full_name': self.get_full_name(),
            'email': self.email,
            'phone_number': self.phone_number,
            'age': self.age,
            'cv_original_filename': self.cv_original_filename,
            'education_summary': self.education_summary,
            'experience_summary': self.experience_summary,
            'skills_summary': self.skills_summary,
            'languages': self.languages,
            'seminars': self.seminars,
            'submission_date': self.submission_date.isoformat() if self.submission_date else None,
            'current_status': self.current_status,
            'positions': self.get_position_names(),
            'notes': self.notes,
            'history': self.history or [],
            'interview_datetime': self.interview_datetime.isoformat() if self.interview_datetime else None,
            'interview_location': self.interview_location,
            'interview_type': self.interview_type,
            'interviewers': self.interviewers or [],
            'candidate_confirmation_status': self.candidate_confirmation_status,
            'evaluation_rating': self.evaluation_rating,
            'offers': self.offers or [],
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_cv_url and cv_url:
            data['cv_url'] = cv_url
        return data

# SQLAlchemy event listener to automatically update 'updated_at' for Candidate
@event.listens_for(Candidate, 'before_update', propagate=True)
def candidate_before_update(mapper, connection, target):
    target.updated_at = datetime.now(dt_timezone.utc)


class Position(db.Model):
    __tablename__ = 'positions'
    position_id = db.Column(db.Integer, primary_key=True) # Using Integer PK for simplicity here
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False, index=True)
    position_name = db.Column(db.String(255), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), default="Open", nullable=False) # e.g., Open, Closed, On Hold

    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(dt_timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(dt_timezone.utc),
                           onupdate=lambda: datetime.now(dt_timezone.utc))

    # Relationships
    company = db.relationship('Company', back_populates='positions')
    candidates = db.relationship('Candidate', secondary=candidate_position_association, back_populates='positions', lazy='select')

    __table_args__ = (UniqueConstraint('position_name', 'company_id', name='uq_position_name_company'),)

    def __repr__(self):
        return f'<Position {self.position_name} (ID: {self.position_id}) for Company ID {self.company_id}>'

    def to_dict(self):
        return {
            'position_id': self.position_id,
            'company_id': self.company_id,
            'position_name': self.position_name,
            'description': self.description,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'candidate_count': len(self.candidates) if self.candidates else 0 # Example of derived info
        }

# SQLAlchemy event listener to automatically update 'updated_at' for Position
@event.listens_for(Position, 'before_update', propagate=True)
def position_before_update(mapper, connection, target):
    target.updated_at = datetime.now(dt_timezone.utc)