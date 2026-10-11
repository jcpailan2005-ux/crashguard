"""Add current-user profile and preference permissions.

Revision ID: 0002_user_preferences
Revises: 0001_phase3
"""

from alembic import op


revision = "0002_user_preferences"
down_revision = "0001_phase3"
branch_labels = None
depends_on = None


PERMISSIONS = (
    ("profile.view_own", "View own profile"),
    ("profile.update_own", "Update own profile"),
    ("preferences.view_own", "View own preferences"),
    ("preferences.update_own", "Update own preferences"),
    ("password.change_own", "Change own password"),
    ("notifications.preferences_own", "Manage own notification preferences"),
)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE user_preferences (
            user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            theme TEXT NOT NULL DEFAULT 'system' CHECK (theme IN ('light','dark','system')),
            notification_preferences JSONB NOT NULL DEFAULT '{}'::jsonb,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    values = ",".join(
        f"('{code}','{description}')" for code, description in PERMISSIONS
    )
    op.execute(
        f"INSERT INTO permissions (code,description) VALUES {values} ON CONFLICT (code) DO NOTHING"
    )
    codes = ",".join(f"'{code}'" for code, _ in PERMISSIONS)
    op.execute(
        f"""
        INSERT INTO role_permissions (role_id,permission_id)
        SELECT r.id,p.id
        FROM roles r CROSS JOIN permissions p
        WHERE r.name IN ('ADMIN','DISPATCHER','RESPONDER') AND p.code IN ({codes})
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    codes = ",".join(f"'{code}'" for code, _ in PERMISSIONS)
    op.execute(
        f"DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE code IN ({codes}))"
    )
    op.execute(f"DELETE FROM permissions WHERE code IN ({codes})")
    op.execute("DROP TABLE user_preferences")
