import asyncio
import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine

from app.models.models import Base
# Import all models to ensure they are registered with Base
from app.models.models import User, ApiKey, BrandProfile, ConnectedAccount, Schedule, Topic, GeneratedPost, PublishingHistory, Log, MonthlyStrategy, ContentBrief, VideoPrompt

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "")

async def migrate():
    print(f"🔗 Connecting to DB: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else DATABASE_URL}")
    engine = create_async_engine(DATABASE_URL)
    
    async with engine.begin() as conn:
        print("📦 Creating new v3 tables if they don't exist...")
        await conn.run_sync(Base.metadata.create_all)
        print("✅ Migration complete!")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(migrate())
