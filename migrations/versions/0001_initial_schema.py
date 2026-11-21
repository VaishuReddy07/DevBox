"""Create DevBox schema and adopt earlier local databases."""
from alembic import op
import sqlalchemy as sa

from app.config import Base
from app import models  # noqa: F401

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "events" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("events")}
        if "scheduled_at" not in columns:
            op.add_column("events", sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True))
        if "request_key" not in columns:
            op.add_column("events", sa.Column("request_key", sa.String(length=200), nullable=True))
            op.create_unique_constraint("uq_events_request_key", "events", ["request_key"])
    Base.metadata.create_all(bind=bind, checkfirst=True)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "outbox_messages" in inspector.get_table_names():
        op.drop_table("outbox_messages")
    if "notifications" in inspector.get_table_names():
        op.drop_table("notifications")
    # Keep event data when rolling back a local schema migration.
