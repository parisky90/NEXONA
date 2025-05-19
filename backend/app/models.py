# backend/app/models.py
import enum
from flask_login import UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, s3_service_instance  # Βεβαιώσου ότι το s3_service_instance είναι διαθέσιμο εδώ
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.orm.attributes import flag_modified
import uuid
from datetime import datetime, timezone as dt_timezone, timedelta
from flask import current_app  # Για πρόσβαση στο s3_service_instance μέσω app context

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
            'user_count': self.users.count(),  # Μπορεί να είναι αργό για πολλές εταιρείες, ίσως με subquery
            'candidate_count': self.candidates.count()  # Ομοίως
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
        if include_company_info and self.company:  # Το self.company φορτώνεται μέσω backref
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
    status_last_changed_date = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(
        dt_timezone.utc))  # ΝΕΟ ΠΕΔΙΟ ΠΟΥ ΠΡΟΣΤΕΘΗΚΕ ΣΤΟ routes.py
    interview_datetime = db.Column(db.DateTime(timezone=True), nullable=True)
    interview_location = db.Column(db.String(255), nullable=True)
    interview_type = db.Column(db.String(100), nullable=True)
    interviewers = db.Column(JSONB, nullable=True, default=list)
    offers = db.Column(JSONB, nullable=True, default=list)
    evaluation_rating = db.Column(db.String(50), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    hr_comments = db.Column(db.Text, nullable=True)
    confirmation_uuid = db.Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
    candidate_confirmation_status = db.Column(db.String(50), nullable=True)  # ΑΛΛΑΓΗ string(50) από string(20)
    history = db.Column(JSONB, nullable=True, default=list)

    positions = db.relationship('Position', secondary=candidate_position_association, back_populates='candidates',
                                lazy='dynamic')
    # Το relationship 'interviews' ορίζεται στο Interview model μέσω backref

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
            # Προσπάθησε να πάρεις τον χρήστη από τη βάση αν υπάρχει ID
            # Χρειάζεται προσοχή εδώ αν εκτελείται εκτός app_context (π.χ. Celery task χωρίς context)
            try:
                actor = db.session.get(User, final_actor_id) if db.session else None  # Προσεκτικός έλεγχος για session
                if actor:
                    final_actor_username = actor.username
                else:
                    final_actor_username = f"User (ID: {final_actor_id})"
            except Exception:  # Ευρύ except για να μην σπάσει αν δεν υπάρχει session ή db
                final_actor_username = f"User (ID: {final_actor_id})"

        event_entry = {
            "timestamp": datetime.now(dt_timezone.utc).isoformat(),
            "event_type": event_type, "description": description,
            "actor_id": final_actor_id,  # Μπορεί να είναι None
            "actor_username": final_actor_username,  # Μπορεί να είναι "System" ή "User (ID: X)"
            "details": details or {}
        }
        if isinstance(self.history, list):
            self.history.append(event_entry)
        else:  # Αν για κάποιο λόγο δεν είναι λίστα (π.χ. null από τη βάση)
            self.history = [event_entry]
        flag_modified(self, "history")

    # *** ΔΙΟΡΘΩΜΕΝΗ ΜΕΘΟΔΟΣ to_dict ***
    def to_dict(self, include_cv_url=False, cv_url=None, include_history=False, include_interviews=False,
                include_company_info_for_candidate=False):
        data = {
            'candidate_id': str(self.candidate_id),
            'company_id': self.company_id,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'full_name': self.full_name,
            'email': self.email,
            'phone_number': self.phone_number,
            'age': self.age,
            'education_summary': self.education_summary,
            'experience_summary': self.experience_summary,
            'skills_summary': self.skills_summary,
            'languages': self.languages,
            'seminars': self.seminars,
            'cv_original_filename': self.cv_original_filename,
            'cv_storage_path': self.cv_storage_path,
            'current_status': self.current_status,
            'submission_date': self.submission_date.isoformat() if self.submission_date else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'status_last_changed_date': self.status_last_changed_date.isoformat() if hasattr(self,
                                                                                             'status_last_changed_date') and self.status_last_changed_date else None,
            # Αφαίρεση παλιών πεδίων συνέντευξης, θα έρχονται από το interview.to_dict()
            # 'interview_datetime': self.interview_datetime.isoformat() if self.interview_datetime else None,
            # 'interview_location': self.interview_location,
            # 'interview_type': self.interview_type,
            # 'interviewers': self.interviewers,
            'offers': self.offers if self.offers else [],
            'evaluation_rating': self.evaluation_rating,
            'notes': self.notes,
            'hr_comments': self.hr_comments,
            'candidate_confirmation_status': self.candidate_confirmation_status,
            'positions': [pos.to_dict() for pos in self.positions.all()] if self.positions else []
            # Καλεί το to_dict του Position
        }

        if include_company_info_for_candidate and self.company:
            data['company'] = self.company.to_dict()

        if include_cv_url:
            if cv_url:
                data['cv_url'] = cv_url
            elif self.cv_storage_path:
                try:
                    # Προσοχή: Το s3_service_instance πρέπει να είναι προσβάσιμο εδώ.
                    # Αν δεν είναι global, πρέπει να περαστεί ή να ληφθεί από το current_app.
                    # Για απλότητα, υποθέτουμε ότι είναι διαθέσιμο μέσω import.
                    data['cv_url'] = s3_service_instance.create_presigned_url(self.cv_storage_path)
                except Exception as e:
                    if current_app:  # Log μόνο αν υπάρχει app context
                        current_app.logger.error(
                            f"Error creating presigned URL for {self.cv_storage_path} in Candidate.to_dict: {e}")
                    data['cv_url'] = None  # Ασφαλής επιστροφή αν αποτύχει
            else:
                data['cv_url'] = None

        if include_history:
            data['history'] = self.history if isinstance(self.history, list) else []

        if include_interviews:
            # Η κλήση self.interviews.order_by(...) προϋποθέτει lazy='dynamic' στο relationship
            # Το relationship 'interviews' ορίζεται στο Interview model μέσω backref, οπότε η ταξινόμηση γίνεται εκεί.
            # Εδώ απλά παίρνουμε τα interviews.
            # Το self.interviews είναι ήδη λίστα (ή SQLAlchemy collection) αν το lazy loading είναι 'select' ή 'joined'.
            # Αν είναι 'dynamic', τότε self.interviews είναι query object.
            interviews_list = self.interviews.order_by(Interview.created_at.desc()).all() if hasattr(self.interviews,
                                                                                                     'order_by') else self.interviews
            data['interviews'] = [
                interview.to_dict(include_slots=True, include_candidate_info=False, include_recruiter_info=True,
                                  include_position_info=True) for interview in interviews_list]

        return data


class Position(db.Model):
    __tablename__ = 'positions'
    position_id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False)
    position_name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), default='Open', nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(dt_timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(dt_timezone.utc),
                           onupdate=lambda: datetime.now(dt_timezone.utc))

    candidates = db.relationship('Candidate', secondary=candidate_position_association, back_populates='positions',
                                 lazy='dynamic')
    # Το relationship 'interviews' ορίζεται στο Interview model μέσω backref

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
            'candidate_count': self.candidates.count()  # Μπορεί να είναι αργό
        }


class InterviewStatus(enum.Enum):
    PROPOSED = "PROPOSED"
    SCHEDULED = "SCHEDULED"
    COMPLETED = "COMPLETED"  # Ολοκληρώθηκε η συνέντευξη, αναμονή αξιολόγησης
    CANDIDATE_REJECTED_ALL = "CANDIDATE_REJECTED_ALL"  # Ο υποψήφιος απέρριψε όλα τα slots
    CANCELLED_BY_RECRUITER = "CANCELLED_BY_RECRUITER"
    CANCELLED_BY_CANDIDATE = "CANCELLED_BY_CANDIDATE"
    EXPIRED = "EXPIRED"  # Η πρόταση έληξε χωρίς απάντηση
    EVALUATION_POSITIVE = "EVALUATION_POSITIVE"  # Αξιολόγηση θετική
    EVALUATION_NEGATIVE = "EVALUATION_NEGATIVE"  # Αξιολόγηση αρνητική
    CANCELLED_DUE_TO_REEVALUATION = "CANCELLED_DUE_TO_REEVALUATION"  # Νέο status


class InterviewSlot(db.Model):
    __tablename__ = 'interview_slots'
    id = db.Column(db.Integer, primary_key=True)
    interview_id = db.Column(db.Integer, db.ForeignKey('interviews.id', ondelete='CASCADE'), nullable=False)
    start_time = db.Column(db.DateTime(timezone=True), nullable=False)
    end_time = db.Column(db.DateTime(timezone=True), nullable=False)
    is_selected = db.Column(db.Boolean, default=False, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'interview_id': self.interview_id,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'is_selected': self.is_selected
        }


class Interview(db.Model):
    __tablename__ = 'interviews'
    id = db.Column(db.Integer, primary_key=True)
    candidate_id = db.Column(UUID(as_uuid=True), db.ForeignKey('candidates.candidate_id', ondelete='CASCADE'),
                             nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False)
    position_id = db.Column(db.Integer, db.ForeignKey('positions.position_id', ondelete='SET NULL'), nullable=True)
    recruiter_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'),
                             nullable=True)  # Nullable αν ο recruiter διαγραφεί

    scheduled_start_time = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    scheduled_end_time = db.Column(db.DateTime(timezone=True), nullable=True)

    location = db.Column(db.String(255), nullable=True)
    interview_type = db.Column(db.String(50), nullable=True)
    notes_for_candidate = db.Column(db.Text, nullable=True)
    internal_notes = db.Column(db.Text, nullable=True)
    cancellation_reason_candidate = db.Column(db.Text, nullable=True)

    evaluation_notes = db.Column(db.Text, nullable=True)
    evaluation_rating_interview = db.Column(db.String(50), nullable=True)  # Αξιολόγηση συγκεκριμένης συνέντευξης

    status = db.Column(db.Enum(InterviewStatus), default=InterviewStatus.PROPOSED, nullable=False, index=True)

    confirmation_token = db.Column(db.String(64), unique=True, nullable=True,
                                   index=True)  # Αύξηση μεγέθους για token_urlsafe
    token_expiration = db.Column(db.DateTime(timezone=True), nullable=True)

    # Νέα πεδία για cancellation token
    cancellation_token = db.Column(db.String(64), unique=True, nullable=True, index=True)
    cancellation_token_expiration = db.Column(db.DateTime(timezone=True), nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(dt_timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(dt_timezone.utc),
                           onupdate=lambda: datetime.now(dt_timezone.utc))

    # Relationships
    candidate = db.relationship('Candidate',
                                backref=db.backref('interviews', lazy='dynamic', cascade='all, delete-orphan',
                                                   order_by="desc(Interview.created_at)"))
    position = db.relationship('Position',
                               backref=db.backref('interviews', lazy='dynamic'))  # Ένα Interview ανήκει σε μία Position
    recruiter = db.relationship('User', foreign_keys=[recruiter_id],
                                backref=db.backref('recruited_interviews', lazy='dynamic'))  # Άλλαξα το backref name

    slots = db.relationship('InterviewSlot', backref='interview', lazy='dynamic', cascade="all, delete-orphan",
                            order_by="InterviewSlot.start_time")

    company = db.relationship('Company',
                              backref=db.backref('company_interviews', lazy='dynamic'))  # Relationship με Company

    def is_token_valid(self, token_type='confirmation'):  # token_type can be 'confirmation' or 'cancellation'
        now = datetime.now(dt_timezone.utc)
        if token_type == 'confirmation':
            return self.confirmation_token is not None and \
                self.token_expiration is not None and \
                self.token_expiration > now
        elif token_type == 'cancellation':
            return self.cancellation_token is not None and \
                self.cancellation_token_expiration is not None and \
                self.cancellation_token_expiration > now
        return False

    def __repr__(self):
        return f'<Interview {self.id} for Candidate {self.candidate_id} - Status: {self.status.name if self.status else "N/A"}>'

    def to_dict(self, include_slots=False, include_sensitive=False, include_candidate_info=True,
                include_recruiter_info=True, include_position_info=True, include_company_info=True):
        data = {
            'id': self.id,
            'candidate_id': str(self.candidate_id) if self.candidate_id else None,
            'company_id': self.company_id,
            'position_id': self.position_id,
            'recruiter_id': self.recruiter_id,
            'scheduled_start_time': self.scheduled_start_time.isoformat() if self.scheduled_start_time else None,
            'scheduled_end_time': self.scheduled_end_time.isoformat() if self.scheduled_end_time else None,
            'location': self.location,
            'interview_type': self.interview_type,
            'notes_for_candidate': self.notes_for_candidate,
            'status': self.status.value if self.status else None,
            'cancellation_reason_candidate': self.cancellation_reason_candidate,
            'confirmation_token_active': self.is_token_valid(token_type='confirmation'),  # Check confirmation token
            'cancellation_token_active': self.is_token_valid(token_type='cancellation'),  # Check cancellation token
            'token_expires_at': self.token_expiration.isoformat() if self.token_expiration else None,
            # Για το confirmation token
            'cancellation_token_expires_at': self.cancellation_token_expiration.isoformat() if self.cancellation_token_expiration else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'evaluation_rating_interview': self.evaluation_rating_interview
        }
        if include_candidate_info and self.candidate:
            # Καλεί το Candidate.to_dict() χωρίς include_interviews για να αποφύγει το loop
            data['candidate'] = self.candidate.to_dict(include_interviews=False, include_history=False,
                                                       include_cv_url=True)

        if include_recruiter_info and self.recruiter:
            data['recruiter'] = self.recruiter.to_dict()  # Υποθέτοντας ότι το User.to_dict() είναι απλό

        if include_position_info and self.position:
            data['position'] = self.position.to_dict()

        if include_company_info and self.company:  # Για να έχουμε και το όνομα της εταιρείας
            data['company_name'] = self.company.name

        if include_slots:
            data['slots'] = [slot.to_dict() for slot in self.slots.all()]

        if include_sensitive:  # Πληροφορίες που δεν θέλουμε να στέλνονται πάντα
            data['internal_notes'] = self.internal_notes
            data['evaluation_notes'] = self.evaluation_notes
            # data['confirmation_token'] = self.confirmation_token # Προσοχή με την αποστολή tokens
            # data['cancellation_token'] = self.cancellation_token # Προσοχή
        return data


print("Models.py loaded (InterviewSlot added, Interview model updated).")