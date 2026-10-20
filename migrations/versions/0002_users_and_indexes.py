"""Add staff accounts (users) and timestamp indexes for the admin lists.

Revision ID: 0002_users_and_indexes
Revises: 0001_initial_schema
Create Date: 2026-10-20 00:01:00
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0002_users_and_indexes'
down_revision = '0001_initial_schema'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=120), nullable=True),
        sa.Column('password_hash', sa.String(length=255), nullable=True),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('last_login_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_employer_responses_timestamp'), 'employer_responses', ['timestamp'], unique=False)
    op.create_index(op.f('ix_student_responses_timestamp'), 'student_responses', ['timestamp'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_student_responses_timestamp'), table_name='student_responses')
    op.drop_index(op.f('ix_employer_responses_timestamp'), table_name='employer_responses')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
