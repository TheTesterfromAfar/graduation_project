"""Employer survey: which majors' students do an internship at the employer.

Existing rows keep NULL (they were collected before the question existed); they simply do not
appear in the results-by-major tables.

Revision ID: 0003_employer_intern_majors
Revises: 0002_users_and_indexes
Create Date: 2026-10-21 00:00:00
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0003_employer_intern_majors'
down_revision = '0002_users_and_indexes'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('employer_responses', sa.Column('intern_majors', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('employer_responses') as batch_op:
        batch_op.drop_column('intern_majors')
