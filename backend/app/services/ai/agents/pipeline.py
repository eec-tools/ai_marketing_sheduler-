"""
Pipeline Orchestrator — Ties all agents together into the v3 workflow.

This is the BRAIN that orchestrates:
  Audit → Strategy → Research → AI Review (loop) → Human Review →
  [Reels only] Script → Script Review → Human Review →
  Content → AI Review (loop) → Human Review →
  Video Prompts (reels only) → AI Review (loop) → Human Review →
  Scheduling & Publishing

Each function advances the state machine by exactly one step.

Rate Limit Strategy:
  All AI calls use an INFINITE retry loop with smart backoff.
  On a 429 rate limit, we read Groq's `retry-after` header and sleep
  for exactly that long before retrying. We NEVER give up due to a rate limit.
  Only genuine errors (bad API key, server crash) will stop the loop.
"""
import json
import logging
import asyncio
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.models import (
    BrandProfile, MonthlyStrategy, GeneratedPost, ContentBrief,
    VideoPrompt, PostStatusEnum, PlatformEnum, Topic, TopicSourceEnum, User
)
from app.services.key_rotation import KeyRotator, NoAvailableKeyError
from app.services.ai.agents.audit_agent import run_brand_audit
from app.services.ai.agents.strategy_agent import generate_monthly_strategy
from app.services.ai.agents.research_agent import research_topic
from app.services.ai.agents.review_agent import review_research, review_content, review_video_prompts, MAX_RETRIES
from app.services.ai.agents.content_agent import (
    generate_reel_content, generate_static_content,
    generate_reel_script, generate_reel_content_from_script
)
from app.services.ai.agents.video_agent import generate_video_prompts

logger = logging.getLogger(__name__)

# How many times the AI review loop can reject content before giving up on quality (not rate limits)
QUALITY_MAX_RETRIES = 5
_key_rotator = KeyRotator()


async def _llm_call_with_retry(db: AsyncSession, user_id: str, provider: str, coro_factory, label: str):
    """
    Executes an awaitable returned by `coro_factory(api_key)` in an infinite retry loop.
    
    - Fetches the next available API key from the KeyRotator.
    - On 429 (Rate Limit): Marks the current key as failed (triggers cooldown) and immediately loops to try the next key.
    - On other HTTP errors (401, 500 etc.): raises immediately — those are real errors.
    - On any other exception: retries with exponential backoff up to 5 times.
    """
    attempt = 0
    while True:
        attempt += 1
        
        # 1. Fetch the next available key (will raise NoAvailableKeyError if all are cooling down)
        try:
            key_record = await _key_rotator.get_next_key(user_id, provider, db)
            api_key = _key_rotator.get_decrypted_key(key_record)
        except NoAvailableKeyError as e:
            # If ALL keys are on cooldown, we must sleep for 30s before retrying key fetch
            # We don't want to hold the DB connection open forever, but since this loop
            # is typically inside a context manager, we'll sleep and hope it resolves.
            logger.warning(f"[{label}] All API keys exhausted/cooling down. Sleeping 30s...")
            await asyncio.sleep(30.0)
            continue
            
        try:
            # Execute with the dynamic key
            result = await coro_factory(api_key)
            
            # If successful, mark the key as successfully used
            await _key_rotator.mark_success(key_record.id, db)
            await db.commit()
            return result
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                # We hit a rate limit on THIS specific key. 
                logger.warning(
                    f"[{label}] {provider} rate limit hit on key '{key_record.label}' (attempt {attempt}). "
                    f"Marking as failed and cycling to next key..."
                )
                await _key_rotator.mark_failure(key_record.id, db)
                await db.commit()
                # Immediately loop to grab the next key, do not sleep!
                continue
            else:
                # A real error (bad key, wrong model, server error) — mark failed and do not retry
                logger.error(f"[{label}] Fatal HTTP error {e.response.status_code}: {e}")
                await _key_rotator.mark_failure(key_record.id, db)
                await db.commit()
                raise
        except Exception as e:
            if attempt >= 5:
                logger.error(f"[{label}] Gave up after {attempt} non-rate-limit errors: {e}")
                raise
            wait = min(2 ** attempt, 60)
            logger.warning(f"[{label}] Attempt {attempt} failed with: {e}. Retrying in {wait}s...")
            await asyncio.sleep(wait)


# ═══════════════════════════════════════════════════════════════════════════════
# Step 1: Full Audit + Strategy
# ═══════════════════════════════════════════════════════════════════════════════

async def run_full_strategy_pipeline(
    db: AsyncSession,
    user_id: str,
    month: str,
    target_format: str
) -> MonthlyStrategy:
    """
    Runs Step 1 end-to-end:
    1.1 Windsor AI Audit → 1.2 Groq Strategy Generation → Calendar of 30 ideas
    Then creates GeneratedPost records for each idea.
    """
    # Get brand profile
    result = await db.execute(select(BrandProfile).where(BrandProfile.user_id == user_id))
    brand = result.scalar_one_or_none()
    if not brand:
        raise ValueError("No brand profile found. Please set up your brand profile first.")
        
    user_res = await db.execute(select(User).where(User.id == user_id))
    user = user_res.scalar_one_or_none()
    provider = user.preferred_ai_provider if user else "groq"

    # Step 1.1: Audit
    strategy = await _llm_call_with_retry(
        db, user_id, "groq", # Audit always uses Groq currently, wait, I can use provider here if audit supports it, but let's stick to provider
        lambda key: run_brand_audit(db, brand, month, key),
        label="BrandAudit"
    )

    # Step 1.2: Strategy generation
    strategy = await _llm_call_with_retry(
        db, user_id, provider,
        lambda key: generate_monthly_strategy(db, strategy, brand, key, target_format, provider),
        label="StrategyGen"
    )

    # Create GeneratedPost + Topic for each calendar item
    for item in (strategy.calendar or []):
        if target_format == "linkedin":
            platform = PlatformEnum.linkedin
        else:
            platform = PlatformEnum.instagram
        
        item["platform"] = target_format
        item["format"] = target_format

        # Create topic
        topic = Topic(
            user_id=user_id,
            topic=item.get("title", "Untitled"),
            source=TopicSourceEnum.ai,
            category=item.get("category", "general"),
        )
        db.add(topic)
        await db.flush()

        # Create post
        post = GeneratedPost(
            user_id=user_id,
            topic_id=topic.id,
            platform=platform,
            headline=item.get("title", ""),
            status=PostStatusEnum.draft,
        )
        post.image_requirements = json.dumps(item)  # Store the full calendar item
        db.add(post)

    await db.commit()
    logger.info(f"Created {len(strategy.calendar or [])} posts from strategy for {month}")
    return strategy


# ═══════════════════════════════════════════════════════════════════════════════
# Step 2 + 3: Research + AI Review Loop
# ═══════════════════════════════════════════════════════════════════════════════

async def run_research_pipeline(
    db: AsyncSession,
    post: GeneratedPost,
    brand_context: dict,
    max_retries: int = QUALITY_MAX_RETRIES
) -> ContentBrief:
    """
    Runs Step 2 (Research) + Step 3.1 (AI Review) in a quality loop.
    - Rate limit 429 errors: automatically retried forever via _groq_call_with_retry.
    - AI Review FAIL: regenerates research up to max_retries times.
    - If quality loop exhausted: post reverts to draft.
    """
    topic_data = {}
    if post.image_requirements:
        try:
            topic_data = json.loads(post.image_requirements)
        except json.JSONDecodeError:
            topic_data = {"title": post.headline or ""}

    for attempt in range(1, max_retries + 1):
        logger.info(f"Research quality attempt {attempt}/{max_retries} for post {post.id}")

        user_res = await db.execute(select(User).where(User.id == post.user_id))
        user = user_res.scalar_one_or_none()
        provider = user.preferred_ai_provider if user else "groq"

        # Step 2: Research — infinite retry on rate limits
        brief = await _llm_call_with_retry(
            db, post.user_id, provider,
            lambda key: research_topic(db, post, topic_data, brand_context, key, provider),
            label=f"Research[{post.id[:8]}]"
        )

        # Step 3.1: AI Review — infinite retry on rate limits
        review = await _llm_call_with_retry(
            db, post.user_id, provider,
            lambda key: review_research(
                research_data=brief.research_data or "",
                statistics=brief.statistics or [],
                references=brief.references or [],
                api_key=key,
                provider=provider
            ),
            label=f"ResearchReview[{post.id[:8]}]"
        )

        brief.ai_review_notes = json.dumps(review)
        await db.commit()

        if review.get("verdict") == "PASS":
            post.status = PostStatusEnum.research_pending  # Ready for human review
            await db.commit()
            logger.info(f"Research PASSED for post {post.id} (score: {review.get('score')})")
            return brief
        else:
            logger.warning(f"Research quality FAILED (attempt {attempt}): {review.get('feedback', '')[:100]}")
            if attempt < max_retries:
                await db.delete(brief)
                await db.commit()

    # Quality loop exhausted — revert to draft so user can retry
    post.status = PostStatusEnum.draft
    await db.commit()
    logger.error(f"Research exhausted {max_retries} quality retries for post {post.id}. Reverting to draft.")
    return None


# =============================================================================
# Step 3.5: Reel Script Generation (Reels Only — between Research and Content)
# =============================================================================

async def run_reel_script_pipeline(
    db: AsyncSession,
    post: GeneratedPost,
    brief: ContentBrief,
    brand_context: dict,
    max_retries: int = QUALITY_MAX_RETRIES
) -> GeneratedPost:
    """
    Generates 2 hooks + a professional reel script from an approved research brief.
    Only runs for Instagram Reels (content_type == 'reel').
    Sets post.status = script_review_pending on success.
    """
    topic_data = {}
    if post.image_requirements:
        try:
            topic_data = json.loads(post.image_requirements)
        except json.JSONDecodeError:
            topic_data = {}

    user_res = await db.execute(select(User).where(User.id == post.user_id))
    user = user_res.scalar_one_or_none()
    provider = user.preferred_ai_provider if user else "groq"

    for attempt in range(1, max_retries + 1):
        logger.info(f"Reel script attempt {attempt}/{max_retries} for post {post.id}")
        await _llm_call_with_retry(
            db, post.user_id, provider,
            lambda key: generate_reel_script(db, post, brief, topic_data, brand_context, key, provider),
            label=f"ReelScript[{post.id[:8]}]"
        )
        if post.status == PostStatusEnum.script_review_pending:
            logger.info(f"Reel script ready for human review: post {post.id}")
            return post

    post.status = PostStatusEnum.research_pending
    await db.commit()
    logger.error(f"Reel script exhausted {max_retries} retries for post {post.id}. Reverting to research_pending.")
    return post


# ═══════════════════════════════════════════════════════════════════════════════
# Step 4 + 5: Content Creation + AI Review Loop
# ═══════════════════════════════════════════════════════════════════════════════

async def run_content_pipeline(
    db: AsyncSession,
    post: GeneratedPost,
    brief: ContentBrief,
    brand_context: dict,
    max_retries: int = QUALITY_MAX_RETRIES
) -> GeneratedPost:
    """
    Runs Step 4 (Content Creation) + Step 5.1 (AI Review) in a quality loop.
    - Rate limit 429 errors: automatically retried forever via _groq_call_with_retry.
    - AI Review FAIL: regenerates content up to max_retries times.
    - If quality loop exhausted: post reverts to research_pending.
    """
    topic_data = {}
    if post.image_requirements:
        try:
            topic_data = json.loads(post.image_requirements)
        except json.JSONDecodeError:
            topic_data = {}

    content_type = topic_data.get("content_type", "static")
    is_reel = content_type == "reel"

    for attempt in range(1, max_retries + 1):
        logger.info(f"Content quality attempt {attempt}/{max_retries} for post {post.id} (type: {content_type})")

        user_res = await db.execute(select(User).where(User.id == post.user_id))
        user = user_res.scalar_one_or_none()
        provider = user.preferred_ai_provider if user else "groq"

        # Step 4: Generate content — infinite retry on rate limits
        if is_reel:
            # If we have an approved script (hook_1 present), use caption-from-script flow
            has_approved_script = bool(topic_data.get("spoken_script"))
            if has_approved_script:
                await _llm_call_with_retry(
                    db, post.user_id, provider,
                    lambda key: generate_reel_content_from_script(db, post, brief, topic_data, brand_context, key, provider),
                    label=f"ReelCaptionFromScript[{post.id[:8]}]"
                )
            else:
                # Legacy fallback: generate full reel content without pre-approved script
                await _llm_call_with_retry(
                    db, post.user_id, provider,
                    lambda key: generate_reel_content(db, post, brief, topic_data, brand_context, key, provider),
                    label=f"ReelContent[{post.id[:8]}]"
                )
        else:
            await _llm_call_with_retry(
                db, post.user_id, provider,
                lambda key: generate_static_content(db, post, brief, topic_data, brand_context, key, provider),
                label=f"StaticContent[{post.id[:8]}]"
            )

        # Step 5.1: AI Content Review — infinite retry on rate limits
        review = await _llm_call_with_retry(
            db, post.user_id, provider,
            lambda key: review_content(
                headline=post.headline or "",
                linkedin_caption=post.linkedin_caption or "",
                instagram_caption=post.instagram_caption or "",
                hashtags=post.hashtags or [],
                cta=post.cta or "",
                platform=str(post.platform.value if post.platform else "linkedin"),
                research_data=brief.research_data or "",
                api_key=key,
                provider=provider
            ),
            label=f"ContentReview[{post.id[:8]}]"
        )

        if review.get("verdict") == "PASS":
            post.status = PostStatusEnum.content_review_pending  # Ready for human review
            await db.commit()
            logger.info(f"Content PASSED for post {post.id} (score: {review.get('score')})")
            return post
        else:
            logger.warning(f"Content quality FAILED (attempt {attempt}): {review.get('feedback', '')[:100]}")

    # Quality loop exhausted — revert to research_pending so user can retry
    post.status = PostStatusEnum.research_pending
    await db.commit()
    logger.error(f"Content exhausted {max_retries} quality retries for post {post.id}. Reverting to research_pending.")
    return post


# ═══════════════════════════════════════════════════════════════════════════════
# Step 6: Video Prompt Generation + AI Review Loop (Reels Only)
# ═══════════════════════════════════════════════════════════════════════════════

async def run_video_prompt_pipeline(
    db: AsyncSession,
    post: GeneratedPost,
    brand_context: dict,
    max_retries: int = QUALITY_MAX_RETRIES
) -> VideoPrompt:
    """
    Runs Step 6.1 (Video Prompt Gen) + Step 6.2 (AI Prompt Review) in a quality loop.
    - Rate limit 429 errors: automatically retried forever via _groq_call_with_retry.
    - AI Review FAIL: regenerates prompts up to max_retries times.
    - Only runs for Reel-type content.
    """
    for attempt in range(1, max_retries + 1):
        logger.info(f"Video prompt quality attempt {attempt}/{max_retries} for post {post.id}")

        user_res = await db.execute(select(User).where(User.id == post.user_id))
        user = user_res.scalar_one_or_none()
        provider = user.preferred_ai_provider if user else "groq"

        # Step 6.1: Generate cinematic prompts — infinite retry on rate limits
        video_prompt = await _llm_call_with_retry(
            db, post.user_id, provider,
            lambda key: generate_video_prompts(db, post, brand_context, key, provider),
            label=f"VideoPromptGen[{post.id[:8]}]"
        )

        # Step 6.2: AI Prompt Review — infinite retry on rate limits
        review = await _llm_call_with_retry(
            db, post.user_id, provider,
            lambda key: review_video_prompts(
                scenes=video_prompt.scenes or [],
                api_key=key,
                provider=provider
            ),
            label=f"VideoPromptReview[{post.id[:8]}]"
        )

        video_prompt.ai_review_notes = json.dumps(review)
        await db.commit()

        if review.get("verdict") == "PASS":
            post.status = PostStatusEnum.prompt_review_pending  # Ready for human review
            await db.commit()
            logger.info(f"Video prompts PASSED for post {post.id}")
            return video_prompt
        else:
            logger.warning(f"Video prompts quality FAILED (attempt {attempt}): {review.get('feedback', '')[:100]}")
            if attempt < max_retries:
                await db.delete(video_prompt)
                await db.commit()

    post.status = PostStatusEnum.content_review_pending
    await db.commit()
    logger.error(f"Video prompts exhausted {max_retries} quality retries for post {post.id}. Reverting to content_review_pending.")
    return None
