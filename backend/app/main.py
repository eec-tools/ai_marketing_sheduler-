from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from sqlalchemy import text
from app.core.config import settings
from app.core.database import engine, Base
# Explicitly import ALL models so SQLAlchemy registers them with Base.metadata
# before create_all() is called on startup. Missing imports = missing tables.
from app.models.models import (  # noqa: F401
    User, ApiKey, BrandProfile, ConnectedAccount, Schedule,
    Topic, GeneratedPost, PublishingHistory, Log,
    MonthlyStrategy, ContentBrief, VideoPrompt
)
from app.api.v1.routes import auth, keys, brand, social, topics, posts, analytics, schedule, users, extension, pipeline
from app.scheduler.runner import start_scheduler, stop_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting AI Social Media Manager API...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    alterations = [
        "ALTER TABLE brand_profiles ADD COLUMN image_instructions TEXT",
        "ALTER TABLE brand_profiles ADD COLUMN caption_template TEXT",
        "ALTER TABLE brand_profiles ADD COLUMN avoid_words JSON",
        "ALTER TABLE brand_profiles ADD COLUMN keywords JSON",
        "ALTER TABLE brand_profiles ADD COLUMN company_description TEXT",
        "ALTER TABLE brand_profiles ADD COLUMN products_services TEXT",
        "ALTER TABLE brand_profiles ADD COLUMN unique_value_proposition TEXT",
        "ALTER TABLE brand_profiles ADD COLUMN customer_pain_points TEXT",
        "ALTER TABLE brand_profiles ADD COLUMN competitors_differentiators TEXT",
        "ALTER TABLE generated_posts DROP CONSTRAINT IF EXISTS generated_posts_image_review_result_check",
        "ALTER TABLE generated_posts ADD COLUMN error_message TEXT",
    ]
    
    for stmt in alterations:
        try:
            async with engine.begin() as conn:
                await conn.execute(text(stmt))
        except Exception:
            pass
            
    start_scheduler()
    logger.info("✅ Ready")
    yield
    # Shutdown
    stop_scheduler()
    await engine.dispose()
    logger.info("API shutdown complete")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered social media content generation and publishing platform",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
PREFIX = "/api/v1"
app.include_router(auth.router, prefix=PREFIX)
app.include_router(users.router, prefix=PREFIX)
app.include_router(keys.router, prefix=PREFIX)
app.include_router(brand.router, prefix=PREFIX)
app.include_router(social.router, prefix=PREFIX)
app.include_router(topics.router, prefix=PREFIX)
app.include_router(posts.router, prefix=PREFIX)
app.include_router(schedule.router, prefix=PREFIX)
app.include_router(analytics.router, prefix=PREFIX)
app.include_router(extension.router, prefix=f"{PREFIX}/extension")
app.include_router(pipeline.router, prefix=PREFIX)


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": settings.APP_VERSION}
