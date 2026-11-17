from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def _make_engine(url: str):
    if url.startswith("sqlite"):
        eng = create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(eng, "connect")
        def _fk_on(dbapi_conn, _):  # pragma: no cover - trivial
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.close()

        return eng
    return create_engine(url, pool_pre_ping=True, pool_size=10, max_overflow=20)


engine = _make_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def configure(url: str) -> None:
    """Re-point the global engine (used by tests)."""
    global engine
    engine = _make_engine(url)
    SessionLocal.configure(bind=engine)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def upsert(db: Session, model, rows: list[dict], index_elements: list[str], update_cols: list[str] | None = None) -> int:
    """Dialect-aware INSERT .. ON CONFLICT DO UPDATE. Idempotent bulk write."""
    if not rows:
        return 0
    dialect = db.get_bind().dialect.name
    ins = (postgresql if dialect == "postgresql" else sqlite).insert(model)
    cols = update_cols if update_cols is not None else [c for c in rows[0] if c not in index_elements]
    total = 0
    for i in range(0, len(rows), 2000):
        chunk = rows[i : i + 2000]
        stmt = ins.values(chunk)
        if cols:
            stmt = stmt.on_conflict_do_update(index_elements=index_elements, set_={c: stmt.excluded[c] for c in cols})
        else:
            stmt = stmt.on_conflict_do_nothing(index_elements=index_elements)
        db.execute(stmt)
        total += len(chunk)
    return total
