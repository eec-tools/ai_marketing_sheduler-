import asyncio
import logging
from sqlalchemy.future import select
from app.core.database import AsyncSessionLocal
from app.models.models import GeneratedPost, PostStatusEnum, ContentBrief, MonthlyStrategy

from app.services.ai.agents.pipeline import (
    run_research_pipeline,
    run_content_pipeline,
    run_video_prompt_pipeline,
    run_full_strategy_pipeline,
    run_reel_script_pipeline,
)

logger = logging.getLogger(__name__)


async def background_run_strategy_pipeline(user_id: str, month: str, target_format: str) -> None:
    """Run the full audit + strategy + draft creation pipeline in the background."""
    try:
        async with AsyncSessionLocal() as db:
            await run_full_strategy_pipeline(db, user_id, month, target_format)
            logger.info(f"Background strategy pipeline completed for {month} ({target_format})")
    except Exception as e:
        logger.error(f"Background strategy pipeline failed for {month}: {e}")


async def background_run_script_pipeline(post_id: str, brand_context: dict) -> None:
    """Run the reel script generation pipeline in the background (Step 3.5 — Reels only)."""
    try:
        async with AsyncSessionLocal() as db:
            post = await db.get(GeneratedPost, post_id)
            if not post or post.status != PostStatusEnum.research_approved:
                return
            # Get the content brief
            from sqlalchemy.future import select as sa_select
            result = await db.execute(
                sa_select(ContentBrief).where(ContentBrief.post_id == post_id).order_by(ContentBrief.created_at.desc())
            )
            brief = result.scalars().first()
            if not brief:
                logger.error(f"No brief found for post {post_id} in script pipeline")
                return
            await run_reel_script_pipeline(db, post, brief, brand_context)
    except Exception as e:
        logger.error(f"Background reel script pipeline failed for {post_id}: {e}")
        await _mark_failed(post_id, e)


async def _mark_failed(post_id: str, error: Exception) -> None:
    """Helper: open a fresh session and mark a post as failed with the error message."""
    try:
        async with AsyncSessionLocal() as err_db:
            failed_post = await err_db.get(GeneratedPost, post_id)
            if failed_post:
                failed_post.status = PostStatusEnum.failed
                failed_post.error_message = str(error)[:500]
                await err_db.commit()
    except Exception as inner:
        logger.error(f"Could not mark post {post_id} as failed: {inner}")


async def process_all_research_background(user_id: str, brand_context: dict):
    # Fetch all draft posts
    draft_ids = []
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(GeneratedPost.id).where(
                GeneratedPost.user_id == user_id,
                GeneratedPost.status == PostStatusEnum.draft
            )
        )
        draft_ids = result.scalars().all()

    # Process each one sequentially with its own session
    for post_id in draft_ids:
        try:
            async with AsyncSessionLocal() as db:
                post = await db.get(GeneratedPost, post_id)
                if post and post.status == PostStatusEnum.draft:
                    await run_research_pipeline(db, post, brand_context)
        except Exception as e:
            logger.error(f"Background research failed for post {post_id}: {e}")
            await _mark_failed(post_id, e)


async def process_all_content_background(user_id: str, brand_context: dict):
    # Fetch all research_pending posts that have an approved brief
    pending_ids = []
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(GeneratedPost.id).where(
                GeneratedPost.user_id == user_id,
                GeneratedPost.status == PostStatusEnum.research_approved
            )
        )
        pending_ids = result.scalars().all()

    for post_id in pending_ids:
        try:
            async with AsyncSessionLocal() as db:
                post = await db.get(GeneratedPost, post_id)
                if post and post.status == PostStatusEnum.research_approved:
                    # check if brief is ready
                    result = await db.execute(select(ContentBrief).where(ContentBrief.post_id == post.id))
                    brief = result.scalar_one_or_none()
                    if brief and brief.ai_review_notes and "PASS" in brief.ai_review_notes:
                        await run_content_pipeline(db, post, brief, brand_context)
        except Exception as e:
            logger.error(f"Background content failed for post {post_id}: {e}")
            await _mark_failed(post_id, e)


async def process_all_video_prompt_background(user_id: str, brand_context: dict):
    pending_ids = []
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(GeneratedPost.id).where(
                GeneratedPost.user_id == user_id,
                GeneratedPost.status == PostStatusEnum.content_approved
            )
        )
        pending_ids = result.scalars().all()

    for post_id in pending_ids:
        try:
            async with AsyncSessionLocal() as db:
                post = await db.get(GeneratedPost, post_id)
                if post and post.status == PostStatusEnum.content_approved:
                    await run_video_prompt_pipeline(db, post, brand_context)
        except Exception as e:
            logger.error(f"Background video prompt failed for post {post_id}: {e}")
            await _mark_failed(post_id, e)


async def background_run_content_pipeline(post_id: str, brand_context: dict):
    """Run content generation for a single post."""
    try:
        async with AsyncSessionLocal() as db:
            post = await db.get(GeneratedPost, post_id)
            if post and post.status == PostStatusEnum.research_approved:
                result = await db.execute(select(ContentBrief).where(ContentBrief.post_id == post.id))
                brief = result.scalar_one_or_none()
                if brief:
                    await run_content_pipeline(db, post, brief, brand_context)
    except Exception as e:
        logger.error(f"Background content generation failed for {post_id}: {e}")
        await _mark_failed(post_id, e)


async def background_run_research_pipeline(post_id: str, brand_context: dict):
    """Run research generation for a single post."""
    try:
        async with AsyncSessionLocal() as db:
            post = await db.get(GeneratedPost, post_id)
            if post and post.status == PostStatusEnum.research_pending:
                await run_research_pipeline(db, post, brand_context)
    except Exception as e:
        logger.error(f"Background research generation failed for {post_id}: {e}")
        await _mark_failed(post_id, e)


async def background_run_video_prompt_pipeline(post_id: str, brand_context: dict):
    """Run video prompt generation for a single post."""
    try:
        async with AsyncSessionLocal() as db:
            post = await db.get(GeneratedPost, post_id)
            if post and post.status == PostStatusEnum.content_approved:
                await run_video_prompt_pipeline(db, post, brand_context)
    except Exception as e:
        logger.error(f"Background video prompt generation failed for {post_id}: {e}")
        await _mark_failed(post_id, e)
