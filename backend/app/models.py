# backend/app/models.py
import enum
from flask_login import UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from app import db
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.orm.attributes import flag_modified
import uuid
from datetime import datetime, timezone as dt_timezone, timedelta

candidate_position_association = db.Table('candidate_position_association',
                                          db.Column('candidate_id', UUID(as_uuid=True),
                                                    db.ForeignKey('candidates.candidate_id', ondelete='CASCADE'),
                                                    primary_key=True),
                                          db.Column('position_id', db.Integer,
                                                    db.ForeignKey('positions.position_id', ondelete='CASCADE'),
                                                    primary_key=True)
                                          )


class Company(db.Model):
    __tablename__ = 'companies'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    industry = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(dt_timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(dt_timezone.utc),
                           onupdate=lambda: datetime.now(dt_timezone.utc))

    # --- ΝΕΟ ΠΕΔΙΟ ---
    owner_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    # --- ΣΧΕΣΗ ΓΙΑ ΕΥΚΟΛΗ ΠΡΟΣΒΑΣΗ ΣΤΟΝ OWNER (ΠΡΟΑΙΡΕΤΙΚΟ ΑΛΛΑ ΧΡΗΣΙΜΟ) ---
    # Χρησιμοποιούμε primaryjoin για να αποφύγουμε ambiguity αν υπάρχουν άλλα FKs προς User
    owner = db.relationship('User', foreign_keys=[owner_user_id],
                            backref=db.backref('owned_company', uselist=False, lazy='joined'), lazy='joined')
    # --- ΤΕΛΟΣ ΝΕΩΝ ΠΡΟΣΘΗΚΩΝ ---

    users = db.relationship('User', foreign_keys='User.company_id', backref='company', lazy='dynamic',
                            cascade="all, delete-orphan")  # Διευκρίνιση foreign_keys για το users relationship
    candidates = db.relationship('Candidate', backref='company', lazy='dynamic', cascade="all, delete-orphan")
    positions = db.relationship('Position', backref='company', lazy='dynamic', cascade="all, delete-orphan")
    settings = db.relationship('CompanySettings', backref='company', uselist=False, cascade="all, delete-orphan")

    def to_dict(self):
        owner_username = self.owner.username if self.owner else None
        return {
            'company_id': self.id,  # Προτιμότερο να είναι 'id' για συνέπεια με άλλα models
            'name': self.name,
            'industry': self.industry,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'settings': self.settings.to_dict() if self.settings else None,
            'owner_user_id': self.owner_user_id,  # Προσθήκη του owner_user_id
            'owner_username': owner_username,  # Προσθήκη του ονόματος του owner
            'user_count': self.users.count(),  # Προσθήκη user_count
            'candidate_count': self.candidates.count()  # Προσθήκη candidate_count
        }


class CompanySettings(db.Model):
    __tablename__ = 'company_settings'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False,
                           unique=True)
    rejection_email_template = db.Column(db.Text, nullable=True)
    interview_invitation_email_template = db.Column(db.Text, nullable=True)
    default_interview_reminder_timing_minutes = db.Column(db.Integer, default=1440, nullable=True)
    enable_reminders_feature_for_company = db.Column(db.Boolean, default=True, nullable=True)

    def to_dict(self):
        data = {
            'settings_id': self.id,
            'company_id': self.company_id,
            'rejection_email_template': self.rejection_email_template,
            'interview_invitation_email_template': self.interview_invitation_email_template,
            'default_interview_reminder_timing_minutes': self.default_interview_reminder_timing_minutes,
            'enable_reminders_feature_for_company': self.enable_reminders_feature_for_company
        }
        return data


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True, nullable=False)
    email = db.Column(db.String(120), index=True, unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    role = db.Column(db.String(20), nullable=False, default='user')  # Roles: 'user', 'company_admin', 'superadmin'
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id', ondelete='SET NULL'),
                           nullable=True)  # ondelete='SET NULL' αν θέλουμε ο user να μείνει αν διαγραφεί η εταιρεία
    is_active = db.Column(db.Boolean, default=True, nullable=False)  # Καλύτερα να μην είναι nullable
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(dt_timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(dt_timezone.utc),
                           onupdate=lambda: datetime.now(dt_timezone.utc))  # Αφαίρεσα το nullable=True
    enable_email_interview_reminders = db.Column(db.Boolean, default=True, nullable=False)
    interview_reminder_lead_time_minutes = db.Column(db.Integer, default=60, nullable=False)
    confirmed_on = db.Column(db.DateTime(timezone=True),
                             nullable=True)  # Προσθήκη confirmed_on για επιβεβαίωση email ή ενεργοποίηση

    # Η σχέση 'company' ορίζεται από το backref του Company.users

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash:  # Αν δεν έχει τεθεί ποτέ κωδικός
            return False
        return check_password_hash(self.password_hash, password)

    def to_dict(self, include_company_info=False):
        data = {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'company_id': self.company_id,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'enable_email_interview_reminders': self.enable_email_interview_reminders,
            'interview_reminder_lead_time_minutes': self.interview_reminder_lead_time_minutes,
            'confirmed_on': self.confirmed_on.isoformat() if self.confirmed_on else None
        }
        if include_company_info and self.company:
            data['company_name'] = self.company.name
            # Δεν χρειάζεται να στέλνουμε τα settings της εταιρείας μαζί με κάθε χρήστη συνήθως
            # if self.company.settings:
            #     data['company_settings'] = self.company.settings.to_dict()
        return data


class Candidate(db.Model):
    __tablename__ = 'candidates'
    candidate_id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False)
    first_name = db.Column(db.String(100), nullable=True)
    last_name = db.Column(db.String(100), nullable=True)
    email = db.Column(db.String(120), nullable=True, index=True)
    phone_number = db.Column(db.String(50), nullable=True)
    age = db.Column(db.Integer, nullable=True)
    education_summary = db.Column(db.Text, nullable=True)
    experience_summary = db.Column(db.Text, nullable=True)
    skills_summary = db.Column(db.Text, nullable=True)
    languages = db.Column(db.Text, nullable=True)
    seminars = db.Column(db.Text, nullable=True)
    cv_original_filename = db.Column(db.String(255), nullable=True)
    cv_storage_path = db.Column(db.String(512), nullable=True)
    current_status = db.Column(db.String(50), default='New', nullable=False, index=True)
    submission_date = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(dt_timezone.utc), index=True)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(dt_timezone.utc),
                           onupdate=lambda: datetime.now(dt_timezone.utc))
    interview_datetime = db.Column(db.DateTime(timezone=True), nullable=True)  # Παλιό πεδίο, ίσως καταργηθεί
    interview_location = db.Column(db.String(255), nullable=True)  # Παλιό πεδίο
    interview_type = db.Column(db.String(100), nullable=True)  # Παλιό πεδίο
    interviewers = db.Column(JSONB, nullable=True, default=list)  # Παλιό πεδίο
    offers = db.Column(JSONB, nullable=True, default=list)
    evaluation_rating = db.Column(db.String(50), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    hr_comments = db.Column(db.Text, nullable=True)
    confirmation_uuid = db.Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True,
                                  nullable=False)  # Για άλλη χρήση;
    candidate_confirmation_status = db.Column(db.String(20), nullable=True)  # Για interview confirmation;
    history = db.Column(JSONB, nullable=True, default=list)

    positions = db.relationship('Position', secondary=candidate_position_association, back_populates='candidates',
                                lazy='dynamic')
    # Η σχέση 'company' ορίζεται από το backref του Company.candidates

    __table_args__ = (
        UniqueConstraint('email', 'company_id', name='uq_candidates_email_company_id'),
    )

    def get_full_name(self):
        parts = [self.first_name, self.last_name]
        return " ".join(filter(None, parts)) or "N/A"

    full_name = property(get_full_name)

    def add_history_event(self, event_type: str, description: str, actor_id: int = None, actor_username: str = None,
                          details: dict = None):
        if self.history is None: self.history = []
        final_actor_id = actor_id
        final_actor_username = actor_username
        if final_actor_id is None and final_actor_username is None:
            if current_user and current_user.is_authenticated:
                final_actor_id = current_user.id
                final_actor_username = current_user.username
            else:
                final_actor_username = "System"
        event_entry = {
            "timestamp": datetime.now(dt_timezone.utc).isoformat(),
            "event_type": event_type, "description": description,
            "actor_id": final_actor_id, "actor_username": final_actor_username,
            "details": details or {}
        }
        if isinstance(self.history, list):
            self.history.append(event_entry)
        else:
            self.history = [event_entry]
        flag_modified(self, "history")

    def to_dict(self, include_cv_url=False, cv_url=None):
        data = {
            'candidate_id': str(self.candidate_id),
            'company_id': self.company_id,
            'first_name': self.first_name, 'last_name': self.last_name, 'full_name': self.full_name,
            'email': self.email, 'phone_number': self.phone_number, 'age': self.age,
            'education_summary': self.education_summary, 'experience_summary': self.experience_summary,
            'skills_summary': self.skills_summary, 'languages': self.languages, 'seminars': self.seminars,
            'cv_original_filename': self.cv_original_filename, 'cv_storage_path': self.cv_storage_path,
            'current_status': self.current_status,
            'submission_date': self.submission_date.isoformat() if self.submission_date else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'interview_datetime': self.interview_datetime.isoformat() if self.interview_datetime else None,
            'interview_location': self.interview_location, 'interview_type': self.interview_type,
            'interviewers': self.interviewers if self.interviewers else [],
            'offers': self.offers if self.offers else [],
            'evaluation_rating': self.evaluation_rating,
            'notes': self.notes, 'hr_comments': self.hr_comments,
            'confirmation_uuid': str(self.confirmation_uuid) if self.confirmation_uuid else None,
            'candidate_confirmation_status': self.candidate_confirmation_status,
            'history': self.history if self.history else [],
            'positions': [pos.position_name for pos in self.positions.all()] if self.positions else []
        }
        if include_cv_url and cv_url: data['cv_url'] = cv_url
        return data


class Position(db.Model):
    __tablename__ = 'positions'
    position_id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False)
    position_name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), default='Open', nullable=True)  # π.χ. Open, Closed, OnHold
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(dt_timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(dt_timezone.utc),
                           onupdate=lambda: datetime.now(dt_timezone.utc))

    candidates = db.relationship('Candidate', secondary=candidate_position_association, back_populates='positions',
                                 lazy='dynamic')
    # Η σχέση 'company' ορίζεται από το backref του Company.positions

    __table_args__ = (
        UniqueConstraint('position_name', 'company_id', name='uq_position_name_company_id'),
    )

    def to_dict(self):
        return {
            'position_id': self.position_id,
            'company_id': self.company_id,
            'position_name': self.position_name,
            'description': self.description,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'candidate_count': self.candidates.count()  # Απλό count, μπορεί να γίνει πιο αποδοτικό αν χρειαστεί
        }


class InterviewStatus(enum.Enum):
    PROPOSED = "PROPOSED"
    SCHEDULED = "SCHEDULED"
    COMPLETED = "COMPLETED"
    CANDIDATE_REJECTED_ALL = "CANDIDATE_REJECTED_ALL"
    CANCELLED_BY_RECRUITER = "CANCELLED_BY_RECRUITER"
    CANCELLED_BY_CANDIDATE = "CANCELLED_BY_CANDIDATE"
    EXPIRED = "EXPIRED"


class Interview(db.Model):
    __tablename__ = 'interviews'
    id = db.Column(db.Integer, primary_key=True)
    candidate_id = db.Column(UUID(as_uuid=True), db.ForeignKey('candidates.candidate_id', ondelete='CASCADE'),
                             nullable=False)
    position_id = db.Column(db.Integer, db.ForeignKey('positions.position_id', ondelete='SET NULL'), nullable=True)
    recruiter_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'),
                             nullable=False)  # SET NULL αν ο recruiter διαγραφεί

    proposed_slot_1_start = db.Column(db.DateTime(timezone=True), nullable=True)
    proposed_slot_1_end = db.Column(db.DateTime(timezone=True), nullable=True)
    proposed_slot_2_start = db.Column(db.DateTime(timezone=True), nullable=True)
    proposed_slot_2_end = db.Column(db.DateTime(timezone=True), nullable=True)
    proposed_slot_3_start = db.Column(db.DateTime(timezone=True), nullable=True)
    proposed_slot_3_end = db.Column(db.DateTime(timezone=True), nullable=True)

    scheduled_start_time = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    scheduled_end_time = db.Column(db.DateTime(timezone=True), nullable=True)

    location = db.Column(db.String(255), nullable=True)
    interview_type = db.Column(db.String(50), nullable=True)
    notes_for_candidate = db.Column(db.Text, nullable=True)
    internal_notes = db.Column(db.Text, nullable=True)
    cancellation_reason_candidate = db.Column(db.Text, nullable=True)

    status = db.Column(db.Enum(InterviewStatus), default=InterviewStatus.PROPOSED, nullable=False, index=True)
    confirmation_token = db.Column(db.String(36), unique=True, nullable=True, index=True)
    token_expiration = db.Column(db.DateTime(timezone=True), nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(dt_timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(dt_timezone.utc),
                           onupdate=lambda: datetime.now(dt_timezone.utc))

    candidate = db.relationship('Candidate',
                                backref=db.backref('interviews', lazy='dynamic', cascade='all, delete-orphan'))
    position = db.relationship('Position', backref=db.backref('interviews', lazy='dynamic'))
    recruiter = db.relationship('User', foreign_keys=[recruiter_id],
                                backref=db.backref('scheduled_interviews', lazy='dynamic'))

    def generate_confirmation_token(self, days_valid=7):
        self.confirmation_token = str(uuid.uuid4())
        self.token_expiration = datetime.now(dt_timezone.utc) + timedelta(days=days_valid)

    def is_token_valid(self):
        if self.status == InterviewStatus.EXPIRED: return False
        if self.confirmation_token and self.token_expiration:
            return datetime.now(dt_timezone.utc) < self.token_expiration
        return False

    def __repr__(self):
        return f'<Interview {self.id} for Candidate {self.candidate_id} - Status: {self.status.name if self.status else "N/A"}>'

    def to_dict(self, include_sensitive=False):
        proposed_slots_list = []
        if self.proposed_slot_1_start and self.proposed_slot_1_end:
            proposed_slots_list.append(
                {'start': self.proposed_slot_1_start.isoformat(), 'end': self.proposed_slot_1_end.isoformat(),
                 'slot_number': 1})
        if self.proposed_slot_2_start and self.proposed_slot_2_end:
            proposed_slots_list.append(
                {'start': self.proposed_slot_2_start.isoformat(), 'end': self.proposed_slot_2_end.isoformat(),
                 'slot_number': 2})
        if self.proposed_slot_3_start and self.proposed_slot_3_end:
            proposed_slots_list.append(
                {'start': self.proposed_slot_3_start.isoformat(), 'end': self.proposed_slot_3_end.isoformat(),
                 'slot_number': 3})

        data = {
            'id': self.id,
            'candidate_id': str(self.candidate_id) if self.candidate_id else None,
            'candidate_name': self.candidate.full_name if self.candidate else None,
            'position_id': self.position_id,
            'position_name': self.position.position_name if self.position else None,
            'recruiter_id': self.recruiter_id,
            'recruiter_name': self.recruiter.username if self.recruiter else None,
            'proposed_slots': proposed_slots_list,
            'scheduled_start_time': self.scheduled_start_time.isoformat() if self.scheduled_start_time else None,
            'scheduled_end_time': self.scheduled_end_time.isoformat() if self.scheduled_end_time else None,
            'location': self.location, 'interview_type': self.interview_type,
            'notes_for_candidate': self.notes_for_candidate,
            'status': self.status.value if self.status else None,
            'cancellation_reason_candidate': self.cancellation_reason_candidate,
            'confirmation_token_active': self.is_token_valid(),
            'token_expires_at': self.token_expiration.isoformat() if self.token_expiration else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        if include_sensitive: data['internal_notes'] = self.internal_notes
        return data


print("Models.py loaded (Company.owner_user_id and relationship added).")  # Ενημερωμένο μήνυμα