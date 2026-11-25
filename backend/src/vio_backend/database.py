from collections.abc import AsyncIterator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine


def make_engine(database_url: str) -> AsyncEngine:
    if database_url.startswith("postgres://"):
        database_url = "postgresql+asyncpg://" + database_url.removeprefix("postgres://")
    elif database_url.startswith("postgresql://"):
        database_url = "postgresql+asyncpg://" + database_url.removeprefix("postgresql://")

    # Neon connection strings include libpq-only query params (sslmode,
    # channel_binding) that asyncpg's connect() rejects outright. Strip them
    # and request TLS explicitly via connect_args instead, since Neon
    # requires an encrypted connection regardless of this parameter.
    parts = urlsplit(database_url)
    query_pairs = dict(parse_qsl(parts.query))
    sslmode = query_pairs.pop("sslmode", None)
    query_pairs.pop("channel_binding", None)
    database_url = urlunsplit(parts._replace(query=urlencode(query_pairs)))

    connect_args = {"ssl": "require"} if sslmode and sslmode != "disable" else {}
    return create_async_engine(database_url, pool_pre_ping=True, connect_args=connect_args)


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def session_dependency(request: Request) -> AsyncIterator[AsyncSession]:
    factory = getattr(request.app.state, "session_factory", None)
    if factory is None:
        raise HTTPException(status_code=503, detail="Database is not configured")
    async with factory() as session:
        yield session
