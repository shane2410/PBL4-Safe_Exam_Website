"""initial_schema

Revision ID: 7b944b0e6ebd
Revises: 
Create Date: 2026-09-21 21:45:31.883573

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7b944b0e6ebd'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'roles',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('code', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
    )
    op.create_index(op.f('ix_roles_id'), 'roles', ['id'], unique=False)
    op.create_index(op.f('ix_roles_code'), 'roles', ['code'], unique=False)

    op.create_table(
        'subjects',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('code', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
    )
    op.create_index(op.f('ix_subjects_id'), 'subjects', ['id'], unique=False)
    op.create_index(op.f('ix_subjects_code'), 'subjects', ['code'], unique=False)

    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=100), nullable=False),
        sa.Column('email', sa.String(length=100), nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.Column('student_code', sa.String(length=20), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('username'),
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=False)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=False)
    op.create_index(op.f('ix_users_student_code'), 'users', ['student_code'], unique=False)

    op.create_table(
        'exams',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('subject_id', sa.Integer(), nullable=False),
        sa.Column('duration_minutes', sa.Integer(), nullable=False),
        sa.Column('total_score', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('is_shuffled', sa.Boolean(), nullable=False),
        sa.Column('max_violation_allowed', sa.Integer(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_exams_id'), 'exams', ['id'], unique=False)
    op.create_index(op.f('ix_exams_subject_id'), 'exams', ['subject_id'], unique=False)

    op.create_table(
        'questions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('type', sa.String(length=20), nullable=False),
        sa.Column('difficulty', sa.String(length=10), nullable=False),
        sa.Column('subject_id', sa.Integer(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('image_url', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_questions_id'), 'questions', ['id'], unique=False)
    op.create_index(op.f('ix_questions_subject_id'), 'questions', ['subject_id'], unique=False)

    op.create_table(
        'question_options',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('question_id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('is_correct', sa.Boolean(), nullable=False),
        sa.Column('order_index', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['question_id'], ['questions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_question_options_id'), 'question_options', ['id'], unique=False)
    op.create_index(op.f('ix_question_options_question_id'), 'question_options', ['question_id'], unique=False)

    op.create_table(
        'exam_questions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('exam_id', sa.Integer(), nullable=False),
        sa.Column('question_id', sa.Integer(), nullable=False),
        sa.Column('score', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('order_index', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['exam_id'], ['exams.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['question_id'], ['questions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_exam_questions_id'), 'exam_questions', ['id'], unique=False)
    op.create_index(op.f('ix_exam_questions_exam_id'), 'exam_questions', ['exam_id'], unique=False)
    op.create_index(op.f('ix_exam_questions_question_id'), 'exam_questions', ['question_id'], unique=False)

    op.create_table(
        'exam_schedules',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('exam_id', sa.Integer(), nullable=False),
        sa.Column('room_code', sa.String(length=20), nullable=False),
        sa.Column('start_time', sa.DateTime(), nullable=False),
        sa.Column('end_time', sa.DateTime(), nullable=False),
        sa.Column('supervised_by', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['exam_id'], ['exams.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['supervised_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('room_code'),
    )
    op.create_index(op.f('ix_exam_schedules_id'), 'exam_schedules', ['id'], unique=False)
    op.create_index(op.f('ix_exam_schedules_exam_id'), 'exam_schedules', ['exam_id'], unique=False)
    op.create_index(op.f('ix_exam_schedules_room_code'), 'exam_schedules', ['room_code'], unique=False)

    op.create_table(
        'exam_sessions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('schedule_id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('session_token', sa.String(length=255), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('submitted_at', sa.DateTime(), nullable=True),
        sa.Column('submit_type', sa.String(length=20), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('risk_score', sa.Integer(), nullable=False),
        sa.Column('tab_switch_count', sa.Integer(), nullable=False),
        sa.Column('fullscreen_exit_count', sa.Integer(), nullable=False),
        sa.Column('final_score', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['schedule_id'], ['exam_schedules.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('schedule_id', 'student_id', name='uq_schedule_student'),
        sa.UniqueConstraint('session_token'),
    )
    op.create_index(op.f('ix_exam_sessions_id'), 'exam_sessions', ['id'], unique=False)
    op.create_index(op.f('ix_exam_sessions_schedule_id'), 'exam_sessions', ['schedule_id'], unique=False)
    op.create_index(op.f('ix_exam_sessions_student_id'), 'exam_sessions', ['student_id'], unique=False)
    op.create_index(op.f('ix_exam_sessions_session_token'), 'exam_sessions', ['session_token'], unique=False)

    op.create_table(
        'student_answers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('question_id', sa.Integer(), nullable=False),
        sa.Column('selected_option_ids', sa.JSON(), nullable=True),
        sa.Column('fill_blank_text', sa.Text(), nullable=True),
        sa.Column('auto_score', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('manual_score', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['question_id'], ['questions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['session_id'], ['exam_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_id', 'question_id', name='uq_session_question'),
    )
    op.create_index(op.f('ix_student_answers_id'), 'student_answers', ['id'], unique=False)
    op.create_index(op.f('ix_student_answers_session_id'), 'student_answers', ['session_id'], unique=False)
    op.create_index(op.f('ix_student_answers_question_id'), 'student_answers', ['question_id'], unique=False)

    op.create_table(
        'violation_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(length=30), nullable=False),
        sa.Column('severity', sa.String(length=10), nullable=False),
        sa.Column('detail', sa.JSON(), nullable=True),
        sa.Column('client_timestamp', sa.DateTime(), nullable=False),
        sa.Column('server_timestamp', sa.DateTime(), nullable=False),
        sa.Column('reviewed_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['session_id'], ['exam_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_violation_logs_id'), 'violation_logs', ['id'], unique=False)
    op.create_index(op.f('ix_violation_logs_session_id'), 'violation_logs', ['session_id'], unique=False)
    op.create_index('idx_session_client_time', 'violation_logs', ['session_id', 'client_timestamp'], unique=False)

    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_audit_logs_id'), 'audit_logs', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_audit_logs_id'), table_name='audit_logs')
    op.drop_table('audit_logs')

    op.drop_index('idx_session_client_time', table_name='violation_logs')
    op.drop_index(op.f('ix_violation_logs_session_id'), table_name='violation_logs')
    op.drop_index(op.f('ix_violation_logs_id'), table_name='violation_logs')
    op.drop_table('violation_logs')

    op.drop_index(op.f('ix_student_answers_question_id'), table_name='student_answers')
    op.drop_index(op.f('ix_student_answers_session_id'), table_name='student_answers')
    op.drop_index(op.f('ix_student_answers_id'), table_name='student_answers')
    op.drop_table('student_answers')

    op.drop_index(op.f('ix_exam_sessions_session_token'), table_name='exam_sessions')
    op.drop_index(op.f('ix_exam_sessions_student_id'), table_name='exam_sessions')
    op.drop_index(op.f('ix_exam_sessions_schedule_id'), table_name='exam_sessions')
    op.drop_index(op.f('ix_exam_sessions_id'), table_name='exam_sessions')
    op.drop_table('exam_sessions')

    op.drop_index(op.f('ix_exam_schedules_room_code'), table_name='exam_schedules')
    op.drop_index(op.f('ix_exam_schedules_exam_id'), table_name='exam_schedules')
    op.drop_index(op.f('ix_exam_schedules_id'), table_name='exam_schedules')
    op.drop_table('exam_schedules')

    op.drop_index(op.f('ix_exam_questions_question_id'), table_name='exam_questions')
    op.drop_index(op.f('ix_exam_questions_exam_id'), table_name='exam_questions')
    op.drop_index(op.f('ix_exam_questions_id'), table_name='exam_questions')
    op.drop_table('exam_questions')

    op.drop_index(op.f('ix_question_options_question_id'), table_name='question_options')
    op.drop_index(op.f('ix_question_options_id'), table_name='question_options')
    op.drop_table('question_options')

    op.drop_index(op.f('ix_questions_subject_id'), table_name='questions')
    op.drop_index(op.f('ix_questions_id'), table_name='questions')
    op.drop_table('questions')

    op.drop_index(op.f('ix_exams_subject_id'), table_name='exams')
    op.drop_index(op.f('ix_exams_id'), table_name='exams')
    op.drop_table('exams')

    op.drop_index(op.f('ix_users_student_code'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_table('users')

    op.drop_index(op.f('ix_subjects_code'), table_name='subjects')
    op.drop_index(op.f('ix_subjects_id'), table_name='subjects')
    op.drop_table('subjects')

    op.drop_index(op.f('ix_roles_code'), table_name='roles')
    op.drop_index(op.f('ix_roles_id'), table_name='roles')
    op.drop_table('roles')
