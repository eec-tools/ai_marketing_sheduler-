import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def main():
    db_url = "postgresql+asyncpg://postgres:Aimarketingscheduler235$@ai-marketing-scheduler.c3yesuu4ev29.ap-south-1.rds.amazonaws.com:5432/postgres?ssl=require"
    engine = create_async_engine(db_url)
    async with engine.connect() as conn:
        posts = await conn.execute(text("SELECT id, platform, status, image_requirements FROM generated_posts ORDER BY created_at DESC LIMIT 5;"))
        for p in posts.fetchall():
            print(p)

asyncio.run(main())
