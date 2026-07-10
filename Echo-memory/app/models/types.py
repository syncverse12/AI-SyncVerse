"""Database-agnostic column types.

Echo can run against PostgreSQL (recommended for production) or fall back
to a local SQLite file when no `DATABASE_URL` is configured (handy for a
zero-config Hugging Face Spaces deploy). Postgres-only types like
`UUID` and `JSONB` don't exist in SQLite, so this module provides thin
cross-dialect equivalents used everywhere instead.
"""
import uuid

from sqlalchemy.types import CHAR, TypeDecorator


class GUID(TypeDecorator):
    """Platform-independent UUID column.

    Uses PostgreSQL's native UUID type when available, otherwise stores
    the value as a CHAR(36) string (e.g. on SQLite).
    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import UUID as PG_UUID

            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return str(value)
        if not isinstance(value, uuid.UUID):
            value = uuid.UUID(str(value))
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))
