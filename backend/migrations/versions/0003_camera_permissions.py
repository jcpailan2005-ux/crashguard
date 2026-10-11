"""Add explicit camera monitoring and credential permissions.

Revision ID: 0003_camera_permissions
Revises: 0002_user_preferences
"""

from alembic import op


revision = "0003_camera_permissions"
down_revision = "0002_user_preferences"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO permissions (code, description) VALUES
          ('cameras.monitor', 'Monitor live camera streams'),
          ('cameras.manage_credentials', 'Manage protected camera credentials')
        ON CONFLICT (code) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r CROSS JOIN permissions p
        WHERE
          (r.name = 'ADMIN' AND p.code IN ('cameras.monitor', 'cameras.manage_credentials'))
          OR (r.name = 'DISPATCHER' AND p.code = 'cameras.monitor')
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM role_permissions
        WHERE permission_id IN (
          SELECT id FROM permissions
          WHERE code IN ('cameras.monitor', 'cameras.manage_credentials')
        )
        """
    )
    op.execute(
        "DELETE FROM permissions WHERE code IN ('cameras.monitor', 'cameras.manage_credentials')"
    )
