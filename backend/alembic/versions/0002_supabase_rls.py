"""Enable Row Level Security when running on Supabase.

The FastAPI backend connects with a privileged database role and enforces per-user access in
application code. RLS is enabled so that Supabase's public PostgREST API (anon/authenticated
keys) cannot read or modify learner data directly. Owner-only read policies are added for
user-scoped tables as defence in depth.

Revision ID: 0002
Revises: 0001
"""

from alembic import op
from sqlalchemy import text

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

USER_TABLES = {
    "profiles": "id",
    "user_assessments": "user_id",
    "user_mastery": "user_id",
    "review_queue": "user_id",
    "lesson_attempts": "user_id",
    "exercise_attempts": "user_id",
    "conversation_sessions": "user_id",
    "api_usage_logs": "user_id",
}
OTHER_TABLES = [
    "local_users",
    "curriculum_units",
    "lessons",
    "exercises",
    "vocabulary",
    "grammar_concepts",
    "assessment_responses",
    "conversation_turns",
    "audio_assets",
]


def _on_supabase() -> bool:
    bind = op.get_bind()
    return bool(
        bind.execute(
            text("select exists(select 1 from pg_namespace where nspname = 'auth')")
        ).scalar()
        and bind.execute(
            text("select exists(select 1 from pg_roles where rolname = 'authenticated')")
        ).scalar()
    )


def upgrade() -> None:
    if not _on_supabase():
        return
    for table in [*USER_TABLES, *OTHER_TABLES]:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
    for table, column in USER_TABLES.items():
        op.execute(
            f'CREATE POLICY "{table}_owner_select" ON "{table}" FOR SELECT TO authenticated '
            f'USING (auth.uid() = "{column}")'
        )


def downgrade() -> None:
    if not _on_supabase():
        return
    for table in USER_TABLES:
        op.execute(f'DROP POLICY IF EXISTS "{table}_owner_select" ON "{table}"')
    for table in [*USER_TABLES, *OTHER_TABLES]:
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
