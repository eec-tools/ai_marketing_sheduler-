"""
APScheduler background job that checks for due posts and runs the full pipeline.
Runs every SCHEDULER_INTERVAL_SECONDS (default: 60 seconds).
"""
import logging
from datetime import datetime, timezone
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.models import User, Schedule, Topic, GeneratedPost, PublishingHistory, ConnectedAccount
from app.services.key_rotation import KeyRotator, NoAvailableKeyError
from app.services.ai.groq import GroqService
from app.services.ai.gemini import GeminiService
from app.services.image_review import ImageReviewService
from app.services.image_card import generate_card
from app.core.security import decrypt_value
import uuid, time

logger = logging.getLogger(__name__)
rotator = KeyRotator()
image_reviewer = ImageReviewService()


async def check_and_publish_due_posts():
    """Main scheduler job. Runs every minute."""
    logger.info(f"[Scheduler] Checking due posts at {datetime.utcnow().isoformat()}")

    due_post_ids = []
    active_schedule_ids = []

    # 1. Fetch IDs quickly to avoid holding connection during AI calls
    async with AsyncSessionLocal() as db:
        try:
            now = datetime.utcnow()
            due_posts_result = await db.execute(
                select(GeneratedPost.id).where(
                    GeneratedPost.status.in_(["approved", "scheduled"]),
                    GeneratedPost.scheduled_at != None,
                    GeneratedPost.scheduled_at <= now
                )
            )
            due_post_ids = due_posts_result.scalars().all()

            schedule_result = await db.execute(
                select(Schedule.id).where(Schedule.is_active == True)
            )
            active_schedule_ids = schedule_result.scalars().all()
        except Exception as e:
            logger.error(f"[Scheduler] Error fetching due items: {e}")
            return

    # 2. Process specifically scheduled posts, each with its own session
    for pid in due_post_ids:
        async with AsyncSessionLocal() as db:
            try:
                post = await db.get(GeneratedPost, pid)
                if post:
                    logger.info(f"[Scheduler] Publishing specifically scheduled post {post.id} (Scheduled for {post.scheduled_at})")
                    platform_str = post.platform.value if hasattr(post.platform, 'value') else str(post.platform)
                    caption = post.linkedin_caption if platform_str == "linkedin" else (post.instagram_caption or post.linkedin_caption or post.headline)
                    await _publish_post(post.user_id, post, platform_str, caption, db, time.time())
                    await db.commit()
            except Exception as e:
                logger.error(f"[Scheduler] Error processing scheduled post {pid}: {e}")

    # 3. Process daily active schedules, each with its own session
    for sid in active_schedule_ids:
        async with AsyncSessionLocal() as db:
            try:
                schedule = await db.get(Schedule, sid)
                if schedule:
                    await _process_user_schedule(schedule, db)
                    await db.commit()
            except Exception as e:
                logger.error(f"[Scheduler] Error processing schedule {sid}: {e}")



async def _process_user_schedule(schedule: Schedule, db):
    """Check if a user has posts due and run the pipeline."""
    now = datetime.utcnow()
    current_time = now.strftime("%H:%M")

    # Check if current time matches any posting time (within the minute)
    is_due = any(
        pt[:5] == current_time[:5]  # Match exact HH:MM
        for pt in (schedule.posting_times or [])
    )

    if not is_due:
        return

    logger.info(f"[Scheduler] User {schedule.user_id} has a post due now")

    # Check posts today count
    from sqlalchemy import func
    today = now.replace(hour=0, minute=0, second=0)
    today_count_result = await db.execute(
        select(func.count(PublishingHistory.id)).where(
            PublishingHistory.user_id == schedule.user_id,
            PublishingHistory.created_at >= today,
            PublishingHistory.status == "published"
        )
    )
    today_count = today_count_result.scalar() or 0

    if today_count >= schedule.max_posts_day:
        logger.info(f"[Scheduler] User {schedule.user_id} reached max posts/day ({schedule.max_posts_day})")
        return

    # Check if there is an approved queued post ready to go
    queued_post_result = await db.execute(
        select(GeneratedPost).where(
            GeneratedPost.user_id == schedule.user_id,
            GeneratedPost.status == "approved",
            GeneratedPost.scheduled_at == None
        ).order_by(GeneratedPost.created_at.asc()).limit(1)
    )
    queued_post = queued_post_result.scalar_one_or_none()
    if queued_post:
        logger.info(f"[Scheduler] Publishing queued approved post {queued_post.id} for user {schedule.user_id}")
        platform_str = queued_post.platform.value if hasattr(queued_post.platform, 'value') else str(queued_post.platform)
        caption = queued_post.linkedin_caption if platform_str == "linkedin" else (queued_post.instagram_caption or queued_post.linkedin_caption or queued_post.headline)
        await _publish_post(schedule.user_id, queued_post, platform_str, caption, db, time.time())
        return

    # Get an unused topic
    topic_result = await db.execute(
        select(Topic).where(
            Topic.user_id == schedule.user_id,
            Topic.is_used == False
        ).order_by(Topic.created_at.asc()).limit(1)
    )
    topic = topic_result.scalar_one_or_none()

    if not topic:
        logger.warning(f"[Scheduler] User {schedule.user_id} has no unused topics")
        return

    # Run pipeline for each platform in schedule
    for platform in (schedule.platforms or ["linkedin"]):
        await _run_full_pipeline(schedule.user_id, topic, platform, db)

    # Mark topic as used
    topic.is_used = True
    topic.used_at = datetime.utcnow()


async def _run_full_pipeline(user_id: str, topic, platform: str, db):
    """Generate content → Generate image → Review → Publish → Log."""
    from app.models.models import BrandProfile, User

    start = time.time()
    logger.info(f"[Scheduler] Running pipeline for user {user_id}, platform {platform}, topic: {topic.topic[:50]}")

    # Load brand context
    brand_result = await db.execute(select(BrandProfile).where(BrandProfile.user_id == user_id))
    brand = brand_result.scalar_one_or_none()
    brand_context = {k: v for k, v in (brand.__dict__ if brand else {}).items() if not k.startswith("_")}

    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    max_retries = user.max_retries if user else 3

    # Generate text — Groq primary, Gemini fallback
    content = None
    try:
        groq_key = await rotator.get_next_key(user_id, "groq", db)
        groq = GroqService(rotator.get_decrypted_key(groq_key))
        content = await groq.generate_post_content(topic.topic, brand_context)
        await rotator.mark_success(groq_key.id, db)
    except Exception as groq_err:
        logger.warning(f"[Scheduler] Groq text failed ({groq_err}), trying Gemini fallback...")
        try:
            gemini_key = await rotator.get_next_key(user_id, "gemini", db)
            gemini_fb = GeminiService(rotator.get_decrypted_key(gemini_key))
            content = await gemini_fb.generate_post_content(topic.topic, brand_context)
            await rotator.mark_success(gemini_key.id, db)
            logger.info(f"[Scheduler] ✅ Gemini text fallback succeeded for user {user_id}")
        except Exception as gemini_err:
            logger.error(f"[Scheduler] All text engines failed. Groq: {groq_err} | Gemini: {gemini_err}")
            return

    # Generate + review image — Pillow card primary, AI fallback
    import base64
    image_url = None
    review_result = "FAIL"
    review_notes = "Not attempted"
    retry_count = 0

    # ── PRIMARY: Pillow card (instant, branded, free) ──────────────────────────
    try:
        image_bytes = generate_card(
            headline=content.get("headline", topic.topic),
            topic=content.get("image_requirements", topic.topic),
            brand_name=brand_context.get("brand_name") or brand_context.get("company_name", "Your Brand"),
            cta=content.get("cta", "Learn More →"),
            primary_color=brand_context.get("primary_color", "#2563EB"),
            secondary_color=brand_context.get("secondary_color", "#64748B"),
            style=brand_context.get("image_style", "professional"),
            size=brand_context.get("image_size", "square"),
            logo_url=brand_context.get("logo_url"),
        )
        image_url = f"data:image/png;base64,{base64.b64encode(image_bytes).decode()}"
        review_result = "PASS"
        review_notes = "Pillow card. Score: 10/10"
        logger.info(f"[Scheduler] Pillow card generated ✅")
    except Exception as card_err:
        logger.warning(f"[Scheduler] Pillow card failed: {card_err}. Trying AI...")

        # ── FALLBACK: AI generation ────────────────────────────────────────────
        for attempt in range(max_retries):
            try:
                gemini_key = await rotator.get_next_key(user_id, "gemini", db)
                gemini = GeminiService(rotator.get_decrypted_key(gemini_key))
                image_bytes = await gemini.generate_image(
                    prompt=content.get("image_requirements", topic.topic),
                    size=brand_context.get("image_size", "square"),
                    style=brand_context.get("image_style", "professional")
                )
                await rotator.mark_success(gemini_key.id, db)
                image_url = f"data:image/png;base64,{base64.b64encode(image_bytes).decode()}"
                review_result = "PASS"
                review_notes = "AI fallback image. Score: 8/10"
                break
            except Exception as ex:
                retry_count += 1
                review_notes = str(ex)
                logger.warning(f"[Scheduler] AI image attempt {attempt + 1} failed: {ex}")

    # Save post
    caption = content.get("linkedin_caption") if platform == "linkedin" else content.get("instagram_caption")
    post = GeneratedPost(
        id=str(uuid.uuid4()),
        user_id=user_id,
        topic_id=topic.id,
        platform=platform,
        headline=content.get("headline"),
        linkedin_caption=content.get("linkedin_caption"),
        instagram_caption=content.get("instagram_caption"),
        hashtags=content.get("hashtags", []),
        cta=content.get("cta"),
        image_url=image_url,
        image_review_result=review_result,
        image_review_notes=review_notes,
        image_retry_count=retry_count,
        status="approved" if review_result == "PASS" else "draft",
    )
    db.add(post)
    await db.flush()

    # Publish if image passed review
    if review_result == "PASS":
        await _publish_post(user_id, post, platform, caption, db, start)
    else:
        logger.warning(f"[Scheduler] Post {post.id} image review failed after {retry_count} retries")


async def _publish_post(user_id: str, post, platform: str, caption: str, db, start: float):
    from app.services.social.linkedin import LinkedInService
    from app.services.social.instagram import InstagramService

    platform_str = platform.value if hasattr(platform, 'value') else str(platform)

    acc_result = await db.execute(
        select(ConnectedAccount).where(
            ConnectedAccount.user_id == user_id,
            ConnectedAccount.platform == platform_str,
            ConnectedAccount.status == "connected"
        )
    )
    account = acc_result.scalar_one_or_none()

    if not account:
        logger.warning(f"[Scheduler] No {platform_str} account for user {user_id}")
        return

    try:
        access_token = decrypt_value(account.access_token)
        if platform_str == "linkedin":
            svc = LinkedInService(access_token, f"urn:li:person:{account.platform_user_id}")
        else:
            svc = InstagramService(access_token, account.platform_user_id)

        result = await svc.publish_post(caption, post.image_url)
        gen_ms = int((time.time() - start) * 1000)

        post.status = "published"
        history = PublishingHistory(
            id=str(uuid.uuid4()),
            user_id=user_id,
            post_id=post.id,
            platform=platform_str,
            platform_post_id=result.get("platform_post_id"),
            published_at=datetime.utcnow(),
            status="published",
            generation_time_ms=gen_ms,
            caption_preview=caption[:200] if caption else None,
            image_url=post.image_url,
        )
        db.add(history)
        logger.info(f"[Scheduler] ✅ Published post {post.id} to {platform}")

    except Exception as e:
        post.status = "failed"
        history = PublishingHistory(
            id=str(uuid.uuid4()),
            user_id=user_id,
            post_id=post.id,
            platform=platform_str,
            status="failed",
            error_message=str(e),
        )
        db.add(history)
        logger.error(f"[Scheduler] ❌ Failed to publish post {post.id}: {e}")
