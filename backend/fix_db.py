import asyncio
from sqlalchemy import text
from app.core.database import engine

async def fix():
    async with engine.begin() as conn:
        try:
            await conn.execute(text("ALTER TABLE generated_posts DROP CONSTRAINT IF EXISTS generated_posts_status_check;"))
            print("Dropped constraint on generated_posts.")
        except Exception as e:
            print(e)
            
        try:
            await conn.execute(text("ALTER TABLE generated_posts DROP CONSTRAINT IF EXISTS poststatusenum;"))
        except:
            pass

asyncio.run(fix())
