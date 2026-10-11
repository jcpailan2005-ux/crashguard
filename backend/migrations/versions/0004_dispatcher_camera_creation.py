"""Allow dispatchers to add cameras from Live Monitor.

Revision ID: 0004_dispatcher_camera_creation
Revises: 0003_camera_permissions
"""

from alembic import op


revision = "0004_dispatcher_camera_creation"
down_revision = "0003_camera_permissions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r CROSS JOIN permissions p
        WHERE r.name = 'DISPATCHER' AND p.code = 'cameras.create'
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM role_permissions
        WHERE role_id = (SELECT id FROM roles WHERE name = 'DISPATCHER')
          AND permission_id = (SELECT id FROM permissions WHERE code = 'cameras.create')
        """
    )
