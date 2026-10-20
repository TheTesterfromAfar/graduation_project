"""Initial schema: the three tables created by the original prototype (db.create_all()).

Existing databases that already contain these tables should NOT run this migration; mark them as
up to date instead:   flask db stamp 0001_initial_schema   and then   flask db upgrade

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-10-20 00:00:00
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'employer_responses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
        sa.Column('company_name', sa.String(length=200), nullable=False),
        sa.Column('respondent_name', sa.String(length=100), nullable=False),
        sa.Column('position', sa.String(length=100), nullable=False),
        sa.Column('phone', sa.String(length=50), nullable=False),
        sa.Column('email', sa.String(length=100), nullable=False),
        sa.Column('reg_number', sa.String(length=50), nullable=True),
        sa.Column('aimag_city', sa.String(length=100), nullable=True),
        sa.Column('sum_district', sa.String(length=100), nullable=True),
        sa.Column('legal_form', sa.String(length=100), nullable=True),
        sa.Column('property_form', sa.String(length=100), nullable=True),
        sa.Column('economic_sector', sa.String(length=200), nullable=True),
        sa.Column('employee_count', sa.String(length=50), nullable=True),
        sa.Column('q2_1_1', sa.Integer(), nullable=True),
        sa.Column('q2_1_2', sa.Integer(), nullable=True),
        sa.Column('q2_1_3', sa.Integer(), nullable=True),
        sa.Column('q2_1_4', sa.Integer(), nullable=True),
        sa.Column('q2_1_5', sa.Integer(), nullable=True),
        sa.Column('q2_1_6', sa.Integer(), nullable=True),
        sa.Column('q2_1_7', sa.Integer(), nullable=True),
        sa.Column('q2_1_8', sa.Integer(), nullable=True),
        sa.Column('q2_1_9', sa.Integer(), nullable=True),
        sa.Column('rehire_interest', sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'student_responses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
        sa.Column('gender', sa.String(length=20), nullable=True),
        sa.Column('age', sa.Integer(), nullable=True),
        sa.Column('major', sa.String(length=150), nullable=False),
        sa.Column('study_type', sa.String(length=100), nullable=True),
        sa.Column('company_name', sa.String(length=200), nullable=False),
        sa.Column('env_1', sa.Integer(), nullable=True),
        sa.Column('env_2', sa.Integer(), nullable=True),
        sa.Column('env_3', sa.Integer(), nullable=True),
        sa.Column('env_4', sa.Integer(), nullable=True),
        sa.Column('env_5', sa.Integer(), nullable=True),
        sa.Column('env_6', sa.Integer(), nullable=True),
        sa.Column('env_7', sa.Integer(), nullable=True),
        sa.Column('soft_1', sa.Integer(), nullable=True),
        sa.Column('soft_2', sa.Integer(), nullable=True),
        sa.Column('soft_3', sa.Integer(), nullable=True),
        sa.Column('soft_4', sa.Integer(), nullable=True),
        sa.Column('soft_5', sa.Integer(), nullable=True),
        sa.Column('soft_6', sa.Integer(), nullable=True),
        sa.Column('soft_7', sa.Integer(), nullable=True),
        sa.Column('tech_1', sa.Integer(), nullable=True),
        sa.Column('tech_2', sa.Integer(), nullable=True),
        sa.Column('tech_3', sa.Integer(), nullable=True),
        sa.Column('tech_4', sa.Integer(), nullable=True),
        sa.Column('tech_5', sa.Integer(), nullable=True),
        sa.Column('quality_1', sa.Integer(), nullable=True),
        sa.Column('quality_2', sa.Integer(), nullable=True),
        sa.Column('recommend_company', sa.String(length=50), nullable=True),
        sa.Column('received_salary', sa.String(length=50), nullable=True),
        sa.Column('daily_salary_amount', sa.String(length=50), nullable=True),
        sa.Column('job_offer_received', sa.String(length=50), nullable=True),
        sa.Column('job_offer_details', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'admin_data_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(length=150), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('admin_data_entries')
    op.drop_table('student_responses')
    op.drop_table('employer_responses')
