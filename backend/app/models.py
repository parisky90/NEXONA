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
    owner_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    owner = db.relationship('User', foreign_keys=[owner_user_id],
                            backref=db.backref('owned_company', uselist=False, lazy='joined'), lazy='joined')

    users = db.relationship('User', foreign_keys='User.company_id', backref='company', lazy='dynamic',
                            cascade="all, delete-orphan")
    candidates = db.relationship('Candidate', backref='company', lazy='dynamic', cascade="all, delete-orphan")
    positions = db.relationship('Position', backref='company', lazy='dynamic', cascade="all, delete-orphan")
    settings = db.relationship('CompanySettings', backref='company', uselist=False, cascade="all, delete-orphan")

    def to_dict(self):
        owner_username = self.owner.username if self.owner else None
        return {
            'company_id': self.id,
            'name': self.name,
            'industry': self.industry,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'settings': self.settings.to_dict() if self.settings else None,
            'owner_user_id': self.owner_user_id,
            'owner_username': owner_username,
            'user_count': self.users.count(),
            'candidate_count': self.candidates.count()
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
        return {
            'settings_id': self.id,
            'company_id': self.company_id,
            'rejection_email_template': self.rejection_email_template,
            'interview_invitation_email_template': self.interview_invitation_email_template,
            'default_interview_reminder_timing_minutes': self.default_interview_reminder_timing_minutes,
            'enable_reminders_feature_for_company': self.enable_reminders_feature_for_company
        }


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True, nullable=False)
    email = db.Column(db.String(120), index=True, unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    role = db.Column(db.String(20), nullable=False, default='user')
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id', ondelete='SET NULL'), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(dt_timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(dt_timezone.utc),
                           onupdate=lambda: datetime.now(dt_timezone.utc))
    enable_email_interview_reminders = db.Column(db.Boolean, default=True, nullable=False)
    interview_reminder_lead_time_minutes = db.Column(db.Integer, default=60, nullable=False)
    confirmed_on = db.Column(db.DateTime(timezone=True), nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash:
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
    # --- ΠΑΛΙΑ ΠΕΔΙΑ ΣΥΝΕΝΤΕΥΞΗΣ - ΜΠΟΡΟΥΝ ΝΑ ΑΦΑΙΡΕΘΟΥΝ ΜΕΛΛΟΝΤΙΚΑ ---
    interview_datetime = db.Column(db.DateTime(timezone=True), nullable=True)
    interview_location = db.Column(db.String(255), nullable=True)
    interview_type = db.Column(db.String(100),
                               nullable=True)  # Αυτό μπορεί να παραμείνει ως default type αν δεν οριστεί στο Interview
    interviewers = db.Column(JSONB, nullable=True, default=list)  # Αυτό ίσως μεταφερθεί στο Interview model
    # --- ΤΕΛΟΣ ΠΑΛΙΩΝ ΠΕΔΙΩΝ ---
    offers = db.Column(JSONB, nullable=True, default=list)
    evaluation_rating = db.Column(db.String(50), nullable=True)  # Γενική αξιολόγηση υποψηφίου
    notes = db.Column(db.Text, nullable=True)
    hr_comments = db.Column(db.Text, nullable=True)
    confirmation_uuid = db.Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True,
                                  nullable=False)  # Για παλιές επιβεβαιώσεις, ίσως αχρείαστο
    candidate_confirmation_status = db.Column(db.String(20), nullable=True)  # Γενικό status επιβεβαίωσης
    history = db.Column(JSONB, nullable=True, default=list)

    positions = db.relationship('Position', secondary=candidate_position_association, back_populates='candidates',
                                lazy='dynamic')

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
        elif final_actor_id and not final_actor_username:
            actor = db.session.get(User, final_actor_id)
            if actor:
                final_actor_username = actor.username
            else:
                final_actor_username = f"User (ID: {final_actor_id})"

        event_entry = {
            "timestamp": datetime.now(dt_timezone.utc).isoformat(),
            "event_type": event_type, "description": description,
            "actor_id": final_actor_id,
            "actor_username": final_actor_username,
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
            # Αφαίρεση παλιών πεδίων συνέντευξης από το candidate.to_dict(), θα έρχονται από το interview.to_dict()
            'offers': self.offers if self.offers else [],
            'evaluation_rating': self.evaluation_rating,  # Γενική αξιολόγηση
            'notes': self.notes, 'hr_comments': self.hr_comments,
            'candidate_confirmation_status': self.candidate_confirmation_status,  # Γενικό status
            'history': self.history if self.history else [],
            'positions': [pos.position_name for pos in self.positions.all()] if self.positions else [],
            'interviews': [interview.to_dict(include_slots=True) for interview in  # include_slots=True
                           self.interviews.order_by(Interview.created_at.desc()).all()] if self.interviews else []
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

    __table_args__ = (
        UniqueConstraint('position_name', 'company_id', name='uq_position_name_company_id'),
    )

    def to_dict(self):
        return {
            'position_id': self.position_id,  # Χρησιμοποίησε position_id αντί για id για συνέπεια
            'company_id': self.company_id,
            'position_name': self.position_name,  # Χρησιμοποίησε position_name αντί για name
            'description': self.description,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'candidate_count': self.candidates.count()
        }


class InterviewStatus(enum.Enum):
    PROPOSED = "PROPOSED"
    SCHEDULED = "SCHEDULED"
    COMPLETED = "COMPLETED"
    CANDIDATE_REJECTED_ALL = "CANDIDATE_REJECTED_ALL"
    CANCELLED_BY_RECRUITER = "CANCELLED_BY_RECRUITER"
    CANCELLED_BY_CANDIDATE = "CANCELLED_BY_CANDIDATE"
    EXPIRED = "EXPIRED"
    EVALUATION_POSITIVE = "EVALUATION_POSITIVE"
    EVALUATION_NEGATIVE = "EVALUATION_NEGATIVE"


# --- ΝΕΟ MODEL: InterviewSlot ---
class InterviewSlot(db.Model):
    __tablename__ = 'interview_slots'
    id = db.Column(db.Integer, primary_key=True)
    interview_id = db.Column(db.Integer, db.ForeignKey('interviews.id', ondelete='CASCADE'), nullable=False)
    start_time = db.Column(db.DateTime(timezone=True), nullable=False)  # Αποθήκευση πάντα σε UTC
    end_time = db.Column(db.DateTime(timezone=True), nullable=False)  # Αποθήκευση πάντα σε UTC
    is_selected = db.Column(db.Boolean, default=False, nullable=False)  # True αν ο υποψήφιος επέλεξε αυτό το slot

    # Δεν χρειάζεται backref εδώ αν δεν το καλείς από το InterviewSlot προς το Interview object.
    # Το relationship είναι στο Interview model (interview.slots).

    def to_dict(self):
        return {
            'id': self.id,
            'interview_id': self.interview_id,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'is_selected': self.is_selected
        }


# --- ΤΕΛΟΣ ΝΕΟΥ MODEL ---

class Interview(db.Model):
    __tablename__ = 'interviews'
    id = db.Column(db.Integer, primary_key=True)
    candidate_id = db.Column(UUID(as_uuid=True), db.ForeignKey('candidates.candidate_id', ondelete='CASCADE'),
                             nullable=False)
    # --- ΠΡΟΣΘΗΚΗ company_id στο Interview ---
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False)
    # --- ΤΕΛΟΣ ΠΡΟΣΘΗΚΗΣ ---
    position_id = db.Column(db.Integer, db.ForeignKey('positions.position_id', ondelete='SET NULL'), nullable=True)
    recruiter_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=False)

    # Αφαίρεση των proposed_slot_X_start/end από εδώ, θα είναι στο InterviewSlot
    # proposed_slot_1_start = db.Column(db.DateTime(timezone=True), nullable=True)
    # ...

    scheduled_start_time = db.Column(db.DateTime(timezone=True), nullable=True,
                                     index=True)  # Αυτό θα οριστεί όταν ο υποψήφιος επιλέξει ένα slot
    scheduled_end_time = db.Column(db.DateTime(timezone=True), nullable=True)

    location = db.Column(db.String(255), nullable=True)
    interview_type = db.Column(db.String(50), nullable=True)
    notes_for_candidate = db.Column(db.Text, nullable=True)
    internal_notes = db.Column(db.Text, nullable=True)
    cancellation_reason_candidate = db.Column(db.Text, nullable=True)

    evaluation_notes = db.Column(db.Text, nullable=True)
    evaluation_rating_interview = db.Column(db.String(50), nullable=True)

    status = db.Column(db.Enum(InterviewStatus), default=InterviewStatus.PROPOSED, nullable=False, index=True)
    confirmation_token = db.Column(db.String(36), unique=True, nullable=True,
                                   index=True)  # Για την επιβεβαίωση από τον υποψήφιο
    token_expiration = db.Column(db.DateTime(timezone=True), nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(dt_timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(dt_timezone.utc),
                           onupdate=lambda: datetime.now(dt_timezone.utc))

    candidate = db.relationship('Candidate',
                                backref=db.backref('interviews', lazy='dynamic', cascade='all, delete-orphan',
                                                   order_by="desc(Interview.created_at)"))
    position = db.relationship('Position', backref=db.backref('interviews', lazy='dynamic'))
    recruiter = db.relationship('User', foreign_keys=[recruiter_id],
                                backref=db.backref('scheduled_interviews', lazy='dynamic'))
    # --- ΝΕΟ RELATIONSHIP ΜΕ InterviewSlot ---
    slots = db.relationship('InterviewSlot', backref='interview', lazy='dynamic', cascade="all, delete-orphan",
                            order_by="InterviewSlot.start_time")  # Ταξινόμηση των slots

    # --- ΤΕΛΟΣ ΝΕΟΥ RELATIONSHIP ---

    # --- Σχέση με Company (για ευκολότερη αναζήτηση συνεντεύξεων ανά εταιρεία) ---
    # Το company_id υπάρχει ήδη, οπότε το backref είναι στο Company model
    # company = db.relationship('Company', backref=db.backref('interviews_direct', lazy='dynamic'))
    # Δεν χρειάζεται relationship εδώ αν έχουμε το company_id στο Interview model.

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

    def to_dict(self, include_slots=False, include_sensitive=False, include_candidate_info=True,
                include_recruiter_info=True, include_position_info=True):
        data = {
            'id': self.id,
            'candidate_id': str(self.candidate_id) if self.candidate_id else None,
            'company_id': self.company_id,  # Προσθήκη company_id
            'position_id': self.position_id,
            'recruiter_id': self.recruiter_id,
            'scheduled_start_time': self.scheduled_start_time.isoformat() if self.scheduled_start_time else None,
            'scheduled_end_time': self.scheduled_end_time.isoformat() if self.scheduled_end_time else None,
            'location': self.location,
            'interview_type': self.interview_type,
            'notes_for_candidate': self.notes_for_candidate,
            'status': self.status.value if self.status else None,
            'cancellation_reason_candidate': self.cancellation_reason_candidate,
            'confirmation_token_active': self.is_token_valid(),
            'token_expires_at': self.token_expiration.isoformat() if self.token_expiration else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'evaluation_rating_interview': self.evaluation_rating_interview
        }
        if include_candidate_info and self.candidate:
            data['candidate_name'] = self.candidate.full_name
            data['candidate_email'] = self.candidate.email  # Προσθήκη email υποψηφίου
        if include_recruiter_info and self.recruiter:
            data['recruiter_name'] = self.recruiter.username
        if include_position_info and self.position:
            data['position_name'] = self.position.position_name

        if include_slots:
            data['slots'] = [slot.to_dict() for slot in self.slots.all()]  # .all() αν είναι lazy='dynamic'

        if include_sensitive:
            data['internal_notes'] = self.internal_notes
            data['evaluation_notes'] = self.evaluation_notes
        return data


print("Models.py loaded (InterviewSlot added, Interview model updated).")