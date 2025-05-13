# backend/app/models.py
import uuid
from datetime import datetime, timezone
from app import db
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import UniqueConstraint
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin


class Company(db.Model):
    __tablename__ = 'companies'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True, index=True)

    owner_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    # --- ΔΙΟΡΘΩΣΗ ΕΔΩ ---
    users = db.relationship('User', foreign_keys='User.company_id', backref='company', lazy='dynamic')
    # --- ΤΕΛΟΣ ΔΙΟΡΘΩΣΗΣ ---

    candidates = db.relationship('Candidate', backref='company', lazy='dynamic')
    positions = db.relationship('Position', backref='company', lazy='dynamic')
    settings = db.relationship('CompanySettings', backref=db.backref('company', uselist=False), uselist=False,
                               cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Company {self.name} (ID: {self.id})>'


class CompanySettings(db.Model):
    __tablename__ = 'company_settings'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, unique=True,
                           index=True)

    rejection_email_template = db.Column(db.Text, nullable=True)
    reminder_email_template = db.Column(db.Text, nullable=True)
    interview_invitation_email_template = db.Column(db.Text, nullable=True)
    interview_reminder_timing_minutes = db.Column(db.Integer, default=60, nullable=False)

    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f'<CompanySettings for Company ID: {self.company_id}>'


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True, nullable=False)
    email = db.Column(db.String(120), index=True, unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=True)

    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=True)

    is_active = db.Column(db.Boolean, nullable=False, default=False)
    role = db.Column(db.String(50), nullable=False, default='user')

    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    confirmed_on = db.Column(db.DateTime(timezone=True), nullable=True)

    # Relationship for companies owned by this user (if a user can own multiple, otherwise owner_user_id on Company is enough)
    # owned_companies = db.relationship('Company', foreign_keys='Company.owner_user_id', backref='owner_user', lazy='dynamic')

    def set_password(self, password):
        if password:
            self.password_hash = generate_password_hash(password)
        else:
            self.password_hash = None

    def check_password(self, password):
        if self.password_hash and password: return check_password_hash(self.password_hash, password)
        return False

    def __repr__(self):
        return f'<User {self.username}>'


candidate_position_association = db.Table('candidate_position_association',
                                          db.Column('candidate_id', db.String(36),
                                                    db.ForeignKey('candidates.candidate_id', ondelete='CASCADE'),
                                                    primary_key=True),
                                          db.Column('position_id', db.Integer,
                                                    db.ForeignKey('positions.position_id', ondelete='CASCADE'),
                                                    primary_key=True)
                                          )


class Candidate(db.Model):
    __tablename__ = 'candidates'
    candidate_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False, index=True)
    first_name = db.Column(db.String(100), nullable=True)
    last_name = db.Column(db.String(100), nullable=True)
    email = db.Column(db.String(255), nullable=True, index=True, unique=False)
    phone_number = db.Column(db.String(50), nullable=True)
    age = db.Column(db.Integer, nullable=True)
    cv_original_filename = db.Column(db.String(255), nullable=False)
    cv_storage_path = db.Column(db.String(512), nullable=False, unique=True)
    education = db.Column(db.Text, nullable=True)
    work_experience = db.Column(db.Text, nullable=True)
    languages = db.Column(db.Text, nullable=True)
    seminars = db.Column(db.Text, nullable=True)
    submission_date = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    current_status = db.Column(db.String(50), nullable=False, default='Processing', index=True)
    notes = db.Column(db.Text, nullable=True)
    history = db.Column(JSONB, nullable=True, default=lambda: [])
    interview_datetime = db.Column(db.DateTime(timezone=True), nullable=True)
    interview_location = db.Column(db.String(255), nullable=True)
    candidate_confirmation_status = db.Column(db.String(50), nullable=True, default='Pending', index=True)
    confirmation_uuid = db.Column(db.String(36), unique=True, nullable=True, default=lambda: str(uuid.uuid4()),
                                  index=True)
    evaluation_rating = db.Column(db.String(50), nullable=True)
    offers = db.Column(JSONB, nullable=True, default=lambda: [])
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))
    positions = db.relationship('Position', secondary=candidate_position_association, back_populates='candidates',
                                lazy='select')
    __table_args__ = (UniqueConstraint('email', 'company_id', name='uq_candidate_email_company'),)

    def __repr__(self): return f'<Candidate {self.get_full_name()} ({self.candidate_id})>'

    def get_full_name(self): parts = [self.first_name, self.last_name]; return " ".join(
        filter(None, parts)).strip() or "N/A"

    def get_position_names(self): return [pos.position_name for pos in self.positions] if self.positions else []

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
            'education': self.education,
            'work_experience': self.work_experience,
            'languages': self.languages,
            'seminars': self.seminars,
            'submission_date': self.submission_date.isoformat() if self.submission_date else None,
            'current_status': self.current_status,
            'positions': self.get_position_names(),
            'notes': self.notes,
            'history': self.history or [],
            'interview_datetime': self.interview_datetime.isoformat() if self.interview_datetime else None,
            'interview_location': self.interview_location,
            'candidate_confirmation_status': self.candidate_confirmation_status,
            'evaluation_rating': self.evaluation_rating,
            'offers': self.offers or [],
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_cv_url and cv_url: data['cv_url'] = cv_url
        return data


class Position(db.Model):
    __tablename__ = 'positions'
    position_id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False, index=True)
    position_name = db.Column(db.String(255), nullable=False, index=True)
    candidates = db.relationship('Candidate', secondary=candidate_position_association, back_populates='positions',
                                 lazy='select')
    __table_args__ = (UniqueConstraint('position_name', 'company_id', name='uq_position_name_company'),)

    def __repr__(self): return f'<Position {self.position_name}>'

    def to_dict(self):
        return {
            'position_id': self.position_id,
            'company_id': self.company_id,
            'position_name': self.position_name
        }