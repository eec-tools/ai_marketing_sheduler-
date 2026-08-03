import asyncio
import sys
import os

# Ensure app is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import AsyncSessionLocal
from app.models.models import GeneratedPost, PostStatusEnum
from sqlalchemy import select, update

async def run():
    async with AsyncSessionLocal() as db:
        # Get stuck script_approved -> script_review_pending
        res = await db.execute(select(GeneratedPost).where(GeneratedPost.status == PostStatusEnum.script_approved))
        for p in res.scalars():
            print(f"Resetting script_approved: {p.headline}")
            p.status = PostStatusEnum.script_review_pending
        
        # Get stuck research_approved -> research_pending
        res = await db.execute(select(GeneratedPost).where(GeneratedPost.status == PostStatusEnum.research_approved))
        for p in res.scalars():
            print(f"Resetting research_approved: {p.headline}")
            p.status = PostStatusEnum.research_pending

        # Get stuck prompt_review_pending? Wait, prompt_review_pending shows the approve button.
        
        await db.commit()
        print("Done!")

if __name__ == "__main__":
    asyncio.run(run())
