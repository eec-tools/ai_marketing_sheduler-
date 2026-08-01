import asyncio
import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

load_dotenv()

async def main():
    engine = create_async_engine(os.getenv('DATABASE_URL'))
    async with engine.begin() as conn:
        await conn.execute(text("UPDATE users SET preferred_ai_provider = 'groq' WHERE preferred_ai_provider IS NULL"))
    print('Done')

if __name__ == "__main__":
    asyncio.run(main())
