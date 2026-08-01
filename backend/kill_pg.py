import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import ssl
from dotenv import load_dotenv

load_dotenv()

async def kill_connections():
    url = os.getenv("DATABASE_URL")
    if "?ssl=" in url:
        url = url.split("?ssl=")[0]
    
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    engine = create_async_engine(url, connect_args={"ssl": ssl_ctx})

    async with engine.begin() as conn:
        print("Terminating other backends...")
        await conn.execute(text("""
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = 'postgres' AND pid <> pg_backend_pid();
        """))
        print("Done")

asyncio.run(kill_connections())
