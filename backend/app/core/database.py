import ssl
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings


def _build_engine():
    """Build the SQLAlchemy async engine with correct SSL for AWS RDS."""
    url = settings.DATABASE_URL
    kwargs = {"echo": settings.DEBUG}

    if url.startswith("postgresql"):
        # AWS RDS requires SSL. Pass an ssl context via connect_args.
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        kwargs.update({
            "pool_pre_ping": True,
            "pool_size": 5,
            "max_overflow": 10,
            "connect_args": {"ssl": ssl_ctx},
        })
        # Strip any ?ssl=... from the URL — we handle it via connect_args
        if "?ssl=" in url:
            url = url.split("?ssl=")[0]

    return create_async_engine(url, **kwargs)


engine = _build_engine()

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
