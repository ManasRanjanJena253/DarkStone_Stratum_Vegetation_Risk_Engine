import asyncio
from sqlalchemy import text
from ..db.session import analysis_engine, user_engine
# UserBase and AnalysisBase imports removed since we aren't using create_all anymore
from ..models import user_models, analysis_models


async def init():
    async with analysis_engine.begin() as conn:
        # Keep this! We still need the extension initialized before migrations run.
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))

        # REMOVED: await conn.run_sync(AnalysisBase.metadata.create_all)

    # REMOVED: The entire user_engine block, as it was only creating tables.
    # async with user_engine.begin() as conn:
    #     await conn.run_sync(UserBase.metadata.create_all)

    print("Database extensions initialized. Leaving table creation to Alembic.")


if __name__ == "__main__":
    asyncio.run(init())