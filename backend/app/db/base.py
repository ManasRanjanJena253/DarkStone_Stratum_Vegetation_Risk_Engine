from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
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

