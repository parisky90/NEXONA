"""Add eval interview statuses

Revision ID: 87fe6ea2bedf
Revises: fe1c9a5e8ed0
Create Date: [AUTO_GENERATED_DATE_FROM_YOUR_FILE] # Η ημερομηνία που είχε αρχικά

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '87fe6ea2bedf'
down_revision = 'fe1c9a5e8ed0'
branch_labels = None
depends_on = None

enum_type_name = 'interviewstatus'
new_values = ('EVALUATION_POSITIVE', 'EVALUATION_NEGATIVE', 'CANCELLED_DUE_TO_REEVALUATION')

def upgrade():
    print(f"Attempting to add new values to enum {enum_type_name}...")
    for value in new_values:
        try:
            op.execute(f"ALTER TYPE {enum_type_name} ADD VALUE IF NOT EXISTS '{value}'")
            print(f"Value '{value}' added or already exists in enum '{enum_type_name}'.")
        except Exception as e:
            print(f"Warning/Error adding value '{value}' to enum '{enum_type_name}': {e}. This might be an issue if the value doesn't exist.")

def downgrade():
    print(f"Downgrade for enum {enum_type_name} to remove values {new_values} is not automatically implemented.")
    pass