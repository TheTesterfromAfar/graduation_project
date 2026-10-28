"""Admin-editable survey questions.

* `survey_configs`: one row per survey holding the admin's edits (questions, groups, wording, choices).
* `extra_answers` (JSON) on both response tables: answers to questions added from the web, which
  have no column of their own.

Nothing is changed or removed in existing data; with no `survey_configs` row the surveys look
exactly as defined in app/questions.py.

Revision ID: 0004_editable_questions
Revises: 0003_employer_intern_majors
Create Date: 2026-10-26 00:00:00
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0004_editable_questions'
down_revision = '0003_employer_intern_majors'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'survey_configs',
        sa.Column('survey_key', sa.String(length=20), nullable=False),
        sa.Column('data', sa.JSON(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('updated_by', sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint('survey_key'),
    )
    op.add_column('employer_responses', sa.Column('extra_answers', sa.JSON(none_as_null=True), nullable=True))
    op.add_column('student_responses', sa.Column('extra_answers', sa.JSON(none_as_null=True), nullable=True))


def downgrade():
    with op.batch_alter_table('student_responses') as batch_op:
        batch_op.drop_column('extra_answers')
    with op.batch_alter_table('employer_responses') as batch_op:
        batch_op.drop_column('extra_answers')
    op.drop_table('survey_configs')
