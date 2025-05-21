"""Add eval interview statuses

Revision ID: NEW_REVISION_ID_GOES_HERE
Revises: fe1c9a5e8ed0
Create Date: [AUTO_GENERATED_DATE]

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'YOUR_NEW_REVISION_ID'  # <<< ΑΝΤΙΚΑΤΑΣΤΗΣΕ ΤΟ ΜΕ ΤΟ ΠΡΑΓΜΑΤΙΚΟ ID ΤΟΥ ΑΡΧΕΙΟΥ ΣΟΥ
down_revision = 'fe1c9a5e8ed0'
branch_labels = None
depends_on = None

enum_type_name = 'interviewstatus'
new_values = ('EVALUATION_POSITIVE', 'EVALUATION_NEGATIVE', 'CANCELLED_DUE_TO_REEVALUATION')

def upgrade():
    # Attempt to add values to the existing enum type
    # This syntax is for PostgreSQL 9.6+
    # For older versions, or if a value already exists and this specific syntax isn't supported
    # for idempotency, this might error if values are already present without "IF NOT EXISTS".
    # However, given it's a new migration after a reset, they shouldn't exist yet from this migration.
    print(f"Attempting to add new values to enum {enum_type_name}...")
    for value in new_values:
        try:
            op.execute(f"ALTER TYPE {enum_type_name} ADD VALUE IF NOT EXISTS '{value}'")
            print(f"Value '{value}' added or already exists in enum '{enum_type_name}'.")
        except Exception as e:
            # This might happen if the value truly cannot be added or IF NOT EXISTS is not supported
            # and the value was somehow added manually or by a previous failed attempt not fully rolled back.
            print(f"Warning/Error adding value '{value}' to enum '{enum_type_name}': {e}. This might be an issue if the value doesn't exist.")
            # If this fails consistently, the enum might need to be dropped and recreated,
            # which is more complex if data exists.

def downgrade():
    # Downgrading by removing enum values is complex and often not directly supported
    # by a simple "ALTER TYPE ... DROP VALUE". It typically requires recreating the type.
    # For simplicity, this downgrade might be a no-op or log a warning.
    print(f"Downgrade for enum {enum_type_name} to remove values {new_values} is not automatically implemented.")
    pass