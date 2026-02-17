"""Add performance indexes to foreign keys

Revision ID: 448c213c5d36
Revises: fb1a573ea24e
Create Date: 2026-02-16 20:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '448c213c5d36'
down_revision = 'fb1a573ea24e'
branch_labels = None
depends_on = None


def upgrade():
    # Adding indexes to foreign keys
    with op.batch_alter_table('friendship', schema=None) as batch_op:
        batch_op.create_index('ix_friendship_user_id', ['user_id'], unique=False)
        batch_op.create_index('ix_friendship_friend_id', ['friend_id'], unique=False)

    with op.batch_alter_table('study_room', schema=None) as batch_op:
        batch_op.create_index('ix_study_room_host_id', ['host_id'], unique=False)

    with op.batch_alter_table('task', schema=None) as batch_op:
        batch_op.create_index('ix_task_user_id', ['user_id'], unique=False)

    with op.batch_alter_table('subtask', schema=None) as batch_op:
        batch_op.create_index('ix_subtask_task_id', ['task_id'], unique=False)

    with op.batch_alter_table('project_member', schema=None) as batch_op:
        batch_op.create_index('ix_project_member_user_id', ['user_id'], unique=False)
        batch_op.create_index('ix_project_member_project_id', ['project_id'], unique=False)

    with op.batch_alter_table('project_section', schema=None) as batch_op:
        batch_op.create_index('ix_project_section_project_id', ['project_id'], unique=False)

    with op.batch_alter_table('project_activity', schema=None) as batch_op:
        batch_op.create_index('ix_project_activity_user_id', ['user_id'], unique=False)
        batch_op.create_index('ix_project_activity_project_id', ['project_id'], unique=False)

    with op.batch_alter_table('project_invite', schema=None) as batch_op:
        batch_op.create_index('ix_project_invite_project_id', ['project_id'], unique=False)

    with op.batch_alter_table('focus_session', schema=None) as batch_op:
        batch_op.create_index('ix_focus_session_user_id', ['user_id'], unique=False)

    with op.batch_alter_table('event', schema=None) as batch_op:
        batch_op.create_index('ix_event_user_id', ['user_id'], unique=False)

    with op.batch_alter_table('event_completion', schema=None) as batch_op:
        batch_op.create_index('ix_event_completion_user_id', ['user_id'], unique=False)

    with op.batch_alter_table('notification', schema=None) as batch_op:
        batch_op.create_index('ix_notification_user_id', ['user_id'], unique=False)

    with op.batch_alter_table('habit', schema=None) as batch_op:
        batch_op.create_index('ix_habit_user_id', ['user_id'], unique=False)

    with op.batch_alter_table('habit_completion', schema=None) as batch_op:
        batch_op.create_index('ix_habit_completion_habit_id', ['habit_id'], unique=False)

    with op.batch_alter_table('user_achievement', schema=None) as batch_op:
        batch_op.create_index('ix_user_achievement_user_id', ['user_id'], unique=False)

    with op.batch_alter_table('chat_message', schema=None) as batch_op:
        batch_op.create_index('ix_chat_message_user_id', ['user_id'], unique=False)


def downgrade():
    with op.batch_alter_table('chat_message', schema=None) as batch_op:
        batch_op.drop_index('ix_chat_message_user_id')

    with op.batch_alter_table('user_achievement', schema=None) as batch_op:
        batch_op.drop_index('ix_user_achievement_user_id')

    with op.batch_alter_table('habit_completion', schema=None) as batch_op:
        batch_op.drop_index('ix_habit_completion_habit_id')

    with op.batch_alter_table('habit', schema=None) as batch_op:
        batch_op.drop_index('ix_habit_user_id')

    with op.batch_alter_table('notification', schema=None) as batch_op:
        batch_op.drop_index('ix_notification_user_id')

    with op.batch_alter_table('event_completion', schema=None) as batch_op:
        batch_op.drop_index('ix_event_completion_user_id')

    with op.batch_alter_table('event', schema=None) as batch_op:
        batch_op.drop_index('ix_event_user_id')

    with op.batch_alter_table('focus_session', schema=None) as batch_op:
        batch_op.drop_index('ix_focus_session_user_id')

    with op.batch_alter_table('project_invite', schema=None) as batch_op:
        batch_op.drop_index('ix_project_invite_project_id')

    with op.batch_alter_table('project_activity', schema=None) as batch_op:
        batch_op.drop_index('ix_project_activity_project_id')
        batch_op.drop_index('ix_project_activity_user_id')

    with op.batch_alter_table('project_section', schema=None) as batch_op:
        batch_op.drop_index('ix_project_section_project_id')

    with op.batch_alter_table('project_member', schema=None) as batch_op:
        batch_op.drop_index('ix_project_member_project_id')
        batch_op.drop_index('ix_project_member_user_id')

    with op.batch_alter_table('subtask', schema=None) as batch_op:
        batch_op.drop_index('ix_subtask_task_id')

    with op.batch_alter_table('task', schema=None) as batch_op:
        batch_op.drop_index('ix_task_user_id')

    with op.batch_alter_table('study_room', schema=None) as batch_op:
        batch_op.drop_index('ix_study_room_host_id')

    with op.batch_alter_table('friendship', schema=None) as batch_op:
        batch_op.drop_index('ix_friendship_friend_id')
        batch_op.drop_index('ix_friendship_user_id')
