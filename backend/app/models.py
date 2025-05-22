# backend/app/models.py
import enum
from flask_login import UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, s3_service_instance
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.orm.attributes import flag_modified, instance_state
from sqlalchemy import event
import uuid
from datetime import datetime, timezone as dt_timezone, timedelta
from flask import current_app
import pytz

candidate_branch_association = db.Table('candidate_branch_association',
                                        db.Column('candidate_id', UUID(as_uuid=True),
                                                  db.ForeignKey('candidates.candidate_id', ondelete='CASCADE'),
                                                  primary_key=True),
                                        db.Column('branch_id', db.Integer,
                                                  db.ForeignKey('branches.id', ondelete='CASCADE'), primary_key=True),
                                        db.UniqueConstraint('candidate_id', 'branch_id', name='uq_candidate_branch')
                                        )

candidate_position_association = db.Table('candidate_position_association',
                                          db.Column('candidate_id', UUID(as_uuid=True),
                                                    db.ForeignKey('candidates.candidate_id', ondelete='CASCADE'),
                                                    primary_key=True),
                                          db.Column('position_id', db.Integer,
                                                    db.ForeignKey('positions.position_id', ondelete='CASCADE'),
                                                    primary_key=True),
                                          db.UniqueConstraint('candidate_id', 'position_id',
                                                              name='uq_candidate_position')
                                          )


class Branch(db.Model):
    __tablename__ = 'branches'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    city = db.Column(db.String(100), nullable=True)
    address = db.Column(db.String(255), nullable=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False)

    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(dt_timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(dt_timezone.utc),
                           onupdate=lambda: datetime.now(dt_timezone.utc))

    candidates = db.relationship(
        'Candidate',
        secondary=candidate_branch_association,
        back_populates='branches',
        lazy='dynamic'
    )

    __table_args__ = (
        UniqueConstraint('name', 'company_id', name='uq_branch_name_company_id'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'city': self.city,
            'address': self.address,
            'company_id': self.company_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self):
        return f'<Branch {self.name} (ID: {self.id}) Company: {self.company_id}>'


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
    branches = db.relationship('Branch', backref='company', lazy='dynamic', cascade="all, delete-orphan")
    interviews = db.relationship('Interview', backref='company', lazy='dynamic', cascade="all, delete-orphan",
                                 order_by="desc(Interview.created_at)")

    def to_dict(self):
        owner_username = self.owner.username if self.owner else None
        return {
            'company_id': self.id,
            'name': self.name,
            'industry': self.industry,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'settings': self.settings.to_dict() if self.settings else None,
            'owner_user_id': self.owner.id if self.owner else None,
            'owner_username': owner_username,
            'user_count': self.users.count(),
            'candidate_count': self.candidates.count(),
            'branch_count': self.branches.count()
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
    status_last_changed_date = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(dt_timezone.utc))
    offers = db.Column(JSONB, nullable=True, default=list)
    evaluation_rating = db.Column(db.String(50), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    hr_comments = db.Column(db.Text, nullable=True)
    candidate_confirmation_status = db.Column(db.String(50), nullable=True)
    history = db.Column(JSONB, nullable=True, default=list)
    offer_acceptance_token = db.Column(db.String(64), unique=True, nullable=True, index=True)
    offer_acceptance_token_expiration = db.Column(db.DateTime(timezone=True), nullable=True)
    offer_sent_at = db.Column(db.DateTime(timezone=True), nullable=True, index=True)

    cv_content_type = db.Column(db.String(100), nullable=True)
    cv_pdf_storage_key = db.Column(db.String(512), nullable=True)

    positions = db.relationship('Position', secondary=candidate_position_association, back_populates='candidates',
                                lazy='dynamic')
    interviews = db.relationship('Interview', backref='candidate', lazy='dynamic', cascade='all, delete-orphan',
                                 order_by="desc(Interview.created_at)")
    branches = db.relationship(
        'Branch',
        secondary=candidate_branch_association,
        back_populates='candidates',
        lazy='dynamic'
    )

    __table_args__ = (
        UniqueConstraint('email', 'company_id', name='uq_candidates_email_company_id'),
    )

    def get_full_name(self):
        parts = [self.first_name, self.last_name]
        return " ".join(filter(None, parts)) or "N/A"

    full_name = property(get_full_name)

    @property
    def offer_expires_in_days(self):
        if self.current_status == 'OfferMade' and self.offer_sent_at:
            try:
                offer_sent_at_utc = self.offer_sent_at
                if offer_sent_at_utc.tzinfo is None:
                    offer_sent_at_utc = pytz.utc.localize(offer_sent_at_utc)
                expiration_moment_utc = offer_sent_at_utc + timedelta(days=7)
                now_utc = datetime.now(dt_timezone.utc)
                expiration_date_only = expiration_moment_utc.date()
                today_date_only = now_utc.date()
                delta = expiration_date_only - today_date_only
                if delta.days < 0:
                    return "Expired"
                return delta.days
            except Exception as e:
                if current_app:
                    current_app.logger.error(
                        f"Error calculating offer_expires_in_days for candidate {self.candidate_id}: {e}")
                return None
        return None

    @property
    def is_docx(self):
        if self.cv_original_filename and self.cv_original_filename.lower().endswith('.docx'):
            return True
        if self.cv_content_type and 'officedocument.wordprocessingml.document' in self.cv_content_type.lower():
            return True
        return False

    @property
    def is_pdf_original(self):
        if self.cv_original_filename and self.cv_original_filename.lower().endswith('.pdf'):
            return True
        if self.cv_content_type and 'application/pdf' in self.cv_content_type.lower():
            return True
        return False

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
            try:
                actor = db.session.get(User, final_actor_id) if db.session else None
                if actor:
                    final_actor_username = actor.username
                else:
                    final_actor_username = f"User (ID: {final_actor_id})"
            except Exception:
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

    def is_offer_token_valid(self):
        now = datetime.now(dt_timezone.utc)
        return self.offer_acceptance_token is not None and \
            self.offer_acceptance_token_expiration is not None and \
            self.offer_acceptance_token_expiration > now

    def to_dict(self, include_cv_url=False, cv_url_param=None,
                include_history=False, include_interviews=False,
                include_company_info_for_candidate=False, include_branches=True):
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
            'offers': self.offers if self.offers else [],
            'evaluation_rating': self.evaluation_rating,
            'notes': self.notes,
            'hr_comments': self.hr_comments,
            'candidate_confirmation_status': self.candidate_confirmation_status,
            'positions': [pos.to_dict() for pos in self.positions.all()] if self.positions else [],
            'offer_sent_at': self.offer_sent_at.isoformat() if self.offer_sent_at else None,
            'offer_expires_in_days': self.offer_expires_in_days,
            'cv_content_type': self.cv_content_type,
            'is_docx': self.is_docx,
            'is_pdf_original': self.is_pdf_original,
            'cv_pdf_storage_key': self.cv_pdf_storage_key,
            'cv_pdf_url': None
        }

        if include_company_info_for_candidate and self.company:
            data['company'] = self.company.to_dict()

        if include_cv_url:
            if cv_url_param:
                data['cv_url'] = cv_url_param
            elif self.cv_storage_path:
                try:
                    if s3_service_instance:
                        data['cv_url'] = s3_service_instance.create_presigned_url(self.cv_storage_path)
                    else:
                        if current_app: current_app.logger.warning(
                            "s3_service_instance is None, cannot create presigned_url for original CV.")
                        data['cv_url'] = None
                except Exception as e:
                    if current_app: current_app.logger.error(
                        f"Error creating presigned URL for original CV {self.cv_storage_path}: {e}")
                    data['cv_url'] = None
            else:
                data['cv_url'] = None

        if self.cv_pdf_storage_key:
            try:
                if s3_service_instance:
                    data['cv_pdf_url'] = s3_service_instance.create_presigned_url(self.cv_pdf_storage_key)
                else:
                    if current_app: current_app.logger.warning(
                        "s3_service_instance is None, cannot create presigned_url for PDF CV.")
            except Exception as e:
                if current_app: current_app.logger.error(
                    f"Error creating presigned URL for PDF CV {self.cv_pdf_storage_key}: {e}")

        if include_history:
            data['history'] = self.history if isinstance(self.history, list) else []
        if include_interviews:
            interviews_list = self.interviews.order_by(Interview.created_at.desc()).all() if hasattr(self.interviews,
                                                                                                     'order_by') else self.interviews
            data['interviews'] = [
                interview.to_dict(
                    include_slots=True, include_candidate_info=False,
                    include_recruiter_info=True, include_position_info=True,
                    include_company_info=True
                ) for interview in interviews_list
            ]
        if include_branches:
            data['branches'] = [branch.to_dict() for branch in self.branches.all()] if self.branches else []
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
    interviews = db.relationship('Interview', backref='position', lazy='select')

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
    CANCELLED_DUE_TO_REEVALUATION = "CANCELLED_DUE_TO_REEVALUATION"


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
    recruiter_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)

    scheduled_start_time = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    scheduled_end_time = db.Column(db.DateTime(timezone=True), nullable=True)

    location = db.Column(db.String(255), nullable=True)
    interview_type = db.Column(db.String(50), nullable=True)
    notes_for_candidate = db.Column(db.Text, nullable=True)
    internal_notes = db.Column(db.Text, nullable=True)
    cancellation_reason_candidate = db.Column(db.Text, nullable=True)

    evaluation_notes = db.Column(db.Text, nullable=True)
    evaluation_rating_interview = db.Column(db.String(50), nullable=True)

    status = db.Column(db.Enum(InterviewStatus), default=InterviewStatus.PROPOSED, nullable=False, index=True)

    confirmation_token = db.Column(db.String(64), unique=True, nullable=True, index=True)
    token_expiration = db.Column(db.DateTime(timezone=True), nullable=True)

    cancellation_token = db.Column(db.String(64), unique=True, nullable=True, index=True)
    cancellation_token_expiration = db.Column(db.DateTime(timezone=True), nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(dt_timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(dt_timezone.utc),
                           onupdate=lambda: datetime.now(dt_timezone.utc))

    recruiter = db.relationship('User', foreign_keys=[recruiter_id],
                                backref=db.backref('recruited_interviews', lazy='select'))
    slots = db.relationship('InterviewSlot', backref='interview', lazy='select',
                            cascade="all, delete-orphan",
                            order_by="InterviewSlot.start_time")

    def is_token_valid(self, token_type='confirmation'):
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

    def to_dict(self, include_slots=False, include_sensitive=False,
                include_candidate_info=True,
                include_recruiter_info=True,
                include_position_info=True,
                include_company_info=True):
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
            'status': self.status.value if self.status else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_candidate_info and self.candidate:
            data['candidate'] = {
                'candidate_id': str(self.candidate.candidate_id),
                'full_name': self.candidate.get_full_name(),
                'email': self.candidate.email,
                'current_status': self.candidate.current_status,
                'confirmation_status': self.candidate.candidate_confirmation_status
            }
        if include_recruiter_info and self.recruiter:
            data['recruiter'] = {
                'id': self.recruiter.id,
                'username': self.recruiter.username
            }
        else:
            data['recruiter'] = {'username': 'N/A'}

        if include_position_info and self.position:
            data['position'] = {
                'position_id': self.position.position_id,
                'position_name': self.position.position_name
            }
        else:
            data['position'] = {'position_name': 'N/A'}

        if include_company_info and self.company:
            data['company_name'] = self.company.name

        if include_slots:
            slots_list = self.slots if isinstance(self.slots, list) else self.slots.all()
            data['slots'] = [slot.to_dict() for slot in slots_list]

        if include_sensitive:
            data['internal_notes'] = self.internal_notes
            data['evaluation_notes'] = self.evaluation_notes
            data['notes_for_candidate'] = self.notes_for_candidate
            data['cancellation_reason_candidate'] = self.cancellation_reason_candidate
            data['confirmation_token_active'] = self.is_token_valid(token_type='confirmation')
            data['cancellation_token_active'] = self.is_token_valid(token_type='cancellation')
            data['token_expires_at'] = self.token_expiration.isoformat() if self.token_expiration else None
            data[
                'cancellation_token_expires_at'] = self.cancellation_token_expiration.isoformat() if self.cancellation_token_expiration else None
            data['evaluation_rating_interview'] = self.evaluation_rating_interview
        return data


@event.listens_for(Candidate.current_status, 'set', propagate=True)
def candidate_current_status_set_listener(target: Candidate, value: str, oldvalue: str, initiator):
    if not isinstance(target, Candidate) or not instance_state(target).has_identity:
        return

    now_utc = datetime.now(dt_timezone.utc)

    if hasattr(target, 'status_last_changed_date'):
        target.status_last_changed_date = now_utc
    else:
        if current_app:
            current_app.logger.warning(
                f"Candidate {target.candidate_id} is missing 'status_last_changed_date' attribute.")

    if value == 'OfferMade':
        if oldvalue != 'OfferMade' or target.offer_sent_at is None:
            target.offer_sent_at = now_utc
    elif oldvalue == 'OfferMade' and value != 'OfferMade':
        target.offer_sent_at = None


print(
    "Models.py loaded (Branch model and associations added, Interview relationships fully defined and corrected, Candidate model updated for CV PDF conversion).")