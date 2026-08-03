import asyncio
from app.core.database import AsyncSessionLocal
from app.models.models import GeneratedPost
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(GeneratedPost).where(GeneratedPost.status == 'research_approved'))
        posts = res.scalars().all()
        for p in posts:
            print(f"Resetting {p.headline}")
            p.status = 'research_pending'
        await db.commit()

asyncio.run(main())
