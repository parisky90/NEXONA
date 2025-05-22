"""Consolidate offer_sent_at and eval_statuses branches

Revision ID: da429559eba5
Revises: 0e064af42b1c, 87fe6ea2bedf
Create Date: 2025-05-22 11:43:58.485129

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'da429559eba5'
down_revision = ('0e064af42b1c', '87fe6ea2bedf')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
