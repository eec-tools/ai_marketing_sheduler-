"""
Run this script once to create all tables on AWS RDS.
Usage: python run_schema.py
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")

# Convert SQLAlchemy URL to raw asyncpg DSN
# postgresql+asyncpg://user:pass@host:port/db  →  postgresql://user:pass@host:port/db
dsn = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

SCHEMA_FILE = os.path.join(os.path.dirname(__file__), "schema.sql")


async def run():
    print(f"🔗 Connecting to: {dsn.split('@')[1] if '@' in dsn else dsn}")
    try:
        conn = await asyncpg.connect(dsn)
        print("✅ Connected to AWS RDS successfully!")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("\n💡 Check that:")
        print("   1. Your password in .env is correct")
        print("   2. AWS Security Group allows port 5432 from your IP")
        return

    with open(SCHEMA_FILE, "r") as f:
        sql = f.read()

    # Remove Supabase-specific RLS commands — RDS does not support them
    lines = []
    skip_keywords = [
        "ENABLE ROW LEVEL SECURITY",
        "CREATE POLICY",
        "ALTER TABLE users ENABLE",
    ]
    for line in sql.splitlines():
        if any(kw in line.upper() for kw in skip_keywords):
            print(f"  ⏭ Skipping RLS (not needed on RDS): {line.strip()}")
        else:
            lines.append(line)
    clean_sql = "\n".join(lines)

    print("\n📦 Running schema on RDS...")
    try:
        await conn.execute(clean_sql)
        print("\n" + "="*50)
        print("✅ All tables created successfully!")
        print("🚀 Your AWS RDS database is fully set up!")
    except Exception as e:
        print(f"\n❌ Schema error: {e}")
        print("\nTrying statement-by-statement fallback...")
        
        # Fallback: split on double newlines between statements
        import re
        stmts = re.split(r';\s*\n', clean_sql)
        ok, err = 0, 0
        for stmt in stmts:
            stmt = stmt.strip()
            if not stmt or stmt.startswith("--") or stmt.startswith("SELECT '"):
                continue
            try:
                await conn.execute(stmt + ";")
                ok += 1
            except Exception as e2:
                msg = str(e2)
                if "already exists" in msg:
                    print(f"  ⏭ Already exists: {stmt[:50]}...")
                    ok += 1
                else:
                    print(f"  ⚠ {msg[:100]} → {stmt[:50]}...")
                    err += 1
        print(f"\n{'='*50}")
        print(f"Done: {ok} OK, {err} errors")

    await conn.close()



if __name__ == "__main__":
    asyncio.run(run())
