from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from ..core.config import settings

# Creating the async engines
user_engine = create_async_engine(
    url = settings.user_db_url,
    echo = False
)

analysis_engine = create_async_engine(
    url = settings.analysis_db_url,
    echo = False
)

# Session Factories
user_session = async_sessionmaker(
    user_engine,
    class_ = AsyncSession,
    expire_on_commit = False
)

analysis_session = async_sessionmaker(
    analysis_engine,
    class_ = AsyncSession,
    expire_on_commit = False
)

# Dependencies
async def get_user_db():
    async with user_session() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise

async def get_analysis_db():
    async with analysis_session() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise