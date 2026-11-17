"""TimescaleDB hypertables for price_history and weather (Postgres only)

Revision ID: 0002
Revises: 0001
"""
from alembic import op
from sqlalchemy import text

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

HYPERTABLES = {"price_history": "date", "weather": "date"}


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return  # SQLite dev/test: plain tables
    has_ts = bind.execute(text("SELECT 1 FROM pg_available_extensions WHERE name = 'timescaledb'")).scalar()
    if not has_ts:
        return  # vanilla Postgres still works, just without hypertables/compression
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
    for table, col in HYPERTABLES.items():
        op.execute(f"SELECT create_hypertable('{table}', '{col}', chunk_time_interval => INTERVAL '90 days', "
                   f"if_not_exists => TRUE, migrate_data => TRUE)")
    # Compress history older than 180 days (segment by series) - big storage win for daily prices.
    op.execute("ALTER TABLE price_history SET (timescaledb.compress, timescaledb.compress_segmentby = 'crop_id, mandi_id')")
    op.execute("SELECT add_compression_policy('price_history', INTERVAL '180 days', if_not_exists => TRUE)")


def downgrade() -> None:
    pass  # hypertables cannot be converted back in place; drop via 0001 downgrade
