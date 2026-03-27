import asyncio
from sqlalchemy import text
from ..db.session import analysis_engine, user_engine
from ..db.base import UserBase, AnalysisBase
from ..models import user_models, analysis_models


async def init():
    async with analysis_engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        await conn.run_sync(AnalysisBase.metadata.create_all)

    async with user_engine.begin() as conn:
        await conn.run_sync(UserBase.metadata.create_all)

    print("All tables created successfully.")


if __name__ == "__main__":
    asyncio.run(init())