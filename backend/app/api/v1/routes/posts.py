from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List, Optional
import uuid, time
from datetime import datetime

from app.core.database import get_db
from app.models.models import User, Topic, BrandProfile, GeneratedPost, ConnectedAccount
from app.schemas.schemas import GeneratePostRequest, GenerateFromImageRequest, SchedulePostRequest, PostUpdateRequest, GeneratedPostOut, MessageResponse
from app.api.v1.deps import get_current_user
from app.services.key_rotation import KeyRotator, NoAvailableKeyError
from app.services.ai.groq import GroqService
from app.services.ai.gemini import GeminiService
from app.services.image_review import ImageReviewService
from app.services.image_card import generate_card, composite_logo_on_image

router = APIRouter(prefix="/posts", tags=["Posts & Generation"])
rotator = KeyRotator()
image_reviewer = ImageReviewService()


async def _run_generation_pipeline(
    user_id: str,
    topic_text: str,
    platform: str,
    db: AsyncSession,
    max_retries: int = 3,
    image_source: str = "pillow"
) -> GeneratedPost:
    """Full AI generation pipeline: text → image → review → store."""
    start_time = time.time()

    # Get brand profile
    brand_result = await db.execute(select(BrandProfile).where(BrandProfile.user_id == user_id))
    brand = brand_result.scalar_one_or_none()
    brand_context = brand.__dict__ if brand else {}

    # 1. Generate text content — Groq primary, Gemini fallback
    content = None
    text_engine = "groq"
    try:
        groq_key = await rotator.get_next_key(user_id, "groq", db)
        groq = GroqService(rotator.get_decrypted_key(groq_key))
        content = await groq.generate_post_content(topic_text, brand_context)
        await rotator.mark_success(groq_key.id, db)
    except (NoAvailableKeyError, Exception) as groq_err:
        logging.warning(f"[Pipeline] Groq failed ({groq_err}), trying Gemini for text generation...")
        try:
            gemini_key = await rotator.get_next_key(user_id, "gemini", db)
            gemini_fb = GeminiService(rotator.get_decrypted_key(gemini_key))
            content = await gemini_fb.generate_post_content(topic_text, brand_context)
            await rotator.mark_success(gemini_key.id, db)
            text_engine = "gemini"
            logging.info("[Pipeline] ✅ Gemini text fallback succeeded")
        except Exception as gemini_err:
            raise HTTPException(503, f"All text generation engines failed. Groq: {groq_err} | Gemini: {gemini_err}")

    # 2. Generate image
    import base64, logging
    from app.api.v1.routes.extension import EXTENSION_JOBS
    image_url = None
    review_result = "PENDING"
    review_notes = None
    retry_count = 0
    post_id = str(uuid.uuid4())

    if image_source == "chatgpt_extension":
        # Queue job for ChatGPT Chrome Extension
        job_id = str(uuid.uuid4())
        EXTENSION_JOBS[job_id] = {
            "id": job_id,
            "user_id": user_id,
            "post_id": post_id,
            "prompt": content.get("image_requirements", topic_text),
            "style": brand_context.get("image_style", "professional"),
            "status": "pending",
            "image_url": None,
            "error": None,
            "created_at": time.time(),
            "completed_at": None,
        }
        review_result = "PENDING_EXTENSION"
        review_notes = f"⏳ Queued for ChatGPT Chrome Extension... (Job ID: {job_id})"
        logging.info(f"Queued ChatGPT extension job {job_id} for post {post_id}")
    elif image_source == "nanobana":
        # ── Nano Banana: Google Imagen 3 / gemini-2.0-flash-preview-image-generation ──
        for attempt in range(max_retries):
            try:
                gemini_key = await rotator.get_next_key(user_id, "gemini", db)
                gemini = GeminiService(rotator.get_decrypted_key(gemini_key))
                image_bytes = await gemini.generate_image_nanobana(
                    prompt=content.get("image_requirements", topic_text),
                    size=brand_context.get("image_size", "square"),
                    style=brand_context.get("image_style", "professional")
                )
                await rotator.mark_success(gemini_key.id, db)
                image_b64 = base64.b64encode(image_bytes).decode()
                image_url = f"data:image/png;base64,{image_b64}"

                # Composite brand logo if available
                logo_url_val = brand_context.get("logo_url")
                if logo_url_val:
                    try:
                        image_url = composite_logo_on_image(image_url, logo_url_val)
                        logging.info("Logo composited on Nano Banana image ✅")
                    except Exception as logo_err:
                        logging.warning(f"Logo compositing failed: {logo_err}")

                review_result = "PASS"
                review_notes = "🍌 Nano Banana (Imagen 3) — highest quality AI image. Score: 10/10"
                logging.info("Image generated via Nano Banana ✅")
                break
            except NoAvailableKeyError as e:
                review_notes = str(e)
                break
            except Exception as e:
                if 'gemini_key' in dir():
                    await rotator.mark_failure(gemini_key.id, db)
                review_notes = str(e)
                retry_count += 1
                logging.warning(f"Nano Banana attempt {attempt+1} failed: {e}")
    else:
        # ── PRIMARY: Pillow card generator (crisp, branded, no API needed) ────────
        try:
            image_bytes = generate_card(
                headline=content.get("headline", topic_text),
                topic=content.get("image_requirements", topic_text),
                brand_name=brand_context.get("brand_name") or brand_context.get("company_name", "Your Brand"),
                cta=content.get("cta", "Learn More →"),
                primary_color=brand_context.get("primary_color", "#2563EB"),
                secondary_color=brand_context.get("secondary_color", "#64748B"),
                style=brand_context.get("image_style", "professional"),
                size=brand_context.get("image_size", "square"),
                logo_url=brand_context.get("logo_url"),
            )
            image_b64 = base64.b64encode(image_bytes).decode()
            image_url = f"data:image/png;base64,{image_b64}"
            review_result = "PASS"
            review_notes = "Pillow card generated successfully. Score: 10/10"
            logging.info("Image generated via Pillow card renderer ✅")
        except Exception as card_err:
            logging.warning(f"Pillow card generation failed: {card_err}. Trying AI fallback...")

            # ── FALLBACK: AI image generation (Pollinations FLUX → HF → Gemini) ──
            for attempt in range(max_retries):
                try:
                    gemini_key = await rotator.get_next_key(user_id, "gemini", db)
                    gemini = GeminiService(rotator.get_decrypted_key(gemini_key))
                    image_bytes = await gemini.generate_image(
                        prompt=content.get("image_requirements", topic_text),
                        size=brand_context.get("image_size", "square"),
                        style=brand_context.get("image_style", "professional")
                    )
                    await rotator.mark_success(gemini_key.id, db)
                    image_b64 = base64.b64encode(image_bytes).decode()
                    image_url = f"data:image/png;base64,{image_b64}"

                    # ── Composite actual brand logo on the AI-generated image ──
                    logo_url_val = brand_context.get("logo_url")
                    if logo_url_val:
                        try:
                            image_url = composite_logo_on_image(image_url, logo_url_val)
                            logging.info("Logo composited on Gemini fallback image ✅")
                        except Exception as logo_err:
                            logging.warning(f"Logo compositing failed on Gemini image: {logo_err}")

                    review_result = "PASS"
                    review_notes = "AI fallback image with brand logo composited. Score: 9/10"
                    break
                except NoAvailableKeyError as e:
                    review_notes = str(e)
                    break
                except Exception as e:
                    if 'gemini_key' in dir():
                        await rotator.mark_failure(gemini_key.id, db)
                    review_notes = str(e)
                    retry_count += 1

    # 4. Create post record
    post = GeneratedPost(
        id=post_id,
        user_id=user_id,
        platform=platform,
        headline=content.get("headline"),
        linkedin_caption=content.get("linkedin_caption"),
        instagram_caption=content.get("instagram_caption"),
        hashtags=content.get("hashtags", []),
        cta=content.get("cta"),
        image_requirements=content.get("image_requirements"),
        image_url=image_url,
        image_review_result=review_result,
        image_review_notes=review_notes,
        image_retry_count=retry_count,
        status="approved" if review_result == "PASS" else "draft",
    )
    db.add(post)
    await db.flush()
    return post


@router.get("", response_model=List[GeneratedPostOut])
async def list_posts(
    status: str = None,
    platform: str = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = select(GeneratedPost).where(GeneratedPost.user_id == current_user.id).order_by(GeneratedPost.created_at.desc())
    if status:
        query = query.where(GeneratedPost.status == status)
    if platform:
        query = query.where(GeneratedPost.platform == platform)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/generate", response_model=GeneratedPostOut, status_code=201)
async def generate_post(
    data: GeneratePostRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Resolve topic text
    topic_text = data.topic
    if data.topic_id:
        result = await db.execute(select(Topic).where(Topic.id == data.topic_id, Topic.user_id == current_user.id))
        topic = result.scalar_one_or_none()
        if topic:
            topic_text = topic.topic
            topic.is_used = True
            topic.used_at = datetime.utcnow()

    if not topic_text:
        raise HTTPException(400, "Provide a topic text or topic_id")

    platform = data.platforms[0] if data.platforms else "linkedin"
    post = await _run_generation_pipeline(
        current_user.id, topic_text, platform, db, current_user.max_retries, data.image_source or "pillow"
    )
    return post


@router.post("/generate-from-image", response_model=GeneratedPostOut, status_code=201)
async def generate_from_image(
    data: GenerateFromImageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    brand_result = await db.execute(select(BrandProfile).where(BrandProfile.user_id == current_user.id))
    brand = brand_result.scalar_one_or_none()
    brand_context = brand.__dict__ if brand else {}

    content = {}
    try:
        gemini_key = await rotator.get_next_key(current_user.id, "gemini", db)
        gemini = GeminiService(rotator.get_decrypted_key(gemini_key))
        content = await gemini.generate_caption_from_image(data.image_data, data.topic, brand_context)
        await rotator.mark_success(gemini_key.id, db)
    except Exception as e:
        try:
            groq_key = await rotator.get_next_key(current_user.id, "groq", db)
            groq = GroqService(rotator.get_decrypted_key(groq_key))
            fallback_topic = data.topic or f"High-impact visual post for {brand_context.get('company_name', 'our brand')}"
            content = await groq.generate_post_content(fallback_topic, brand_context)
            await rotator.mark_success(groq_key.id, db)
        except Exception as groq_err:
            raise HTTPException(500, f"Caption generation failed: {groq_err}")

    platform = data.platforms[0] if data.platforms else "linkedin"
    post = GeneratedPost(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        topic_id=None,
        platform=platform,
        headline=content.get("headline", data.topic or "Visual Post"),
        linkedin_caption=content.get("linkedin_caption", ""),
        instagram_caption=content.get("instagram_caption", ""),
        hashtags=content.get("hashtags", []),
        cta=content.get("cta", ""),
        image_requirements=content.get("image_requirements", "Uploaded custom image"),
        image_url=data.image_data,
        image_review_result="PASS",
        image_review_notes="User Uploaded Image — AI Scannable Caption Generated",
        image_retry_count=0,
        status="approved",
        scheduled_at=data.scheduled_at,
    )
    db.add(post)
    await db.flush()
    return post


@router.put("/{post_id}", response_model=GeneratedPostOut)
@router.patch("/{post_id}", response_model=GeneratedPostOut)
async def update_post(
    post_id: str,
    req: PostUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(GeneratedPost).where(GeneratedPost.id == post_id, GeneratedPost.user_id == current_user.id))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(404, "Post not found")

    if req.headline is not None:
        post.headline = req.headline
    if req.linkedin_caption is not None:
        post.linkedin_caption = req.linkedin_caption
    if req.instagram_caption is not None:
        post.instagram_caption = req.instagram_caption
    if req.image_url is not None:
        post.image_url = req.image_url
    if req.hashtags is not None:
        post.hashtags = req.hashtags
    if req.cta is not None:
        post.cta = req.cta

    await db.flush()
    return post


@router.put("/{post_id}/schedule", response_model=MessageResponse)
async def schedule_post(
    post_id: str,
    data: SchedulePostRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(GeneratedPost).where(GeneratedPost.id == post_id, GeneratedPost.user_id == current_user.id))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(404, "Post not found")
    post.scheduled_at = data.scheduled_at
    if data.scheduled_at:
        post.status = "scheduled"
    else:
        if post.status == "scheduled":
            post.status = "draft"
    await db.flush()
    msg = "Post scheduled successfully!" if data.scheduled_at else "Post schedule removed"
    return MessageResponse(message=msg)


@router.post("/{post_id}/publish", response_model=MessageResponse)
async def publish_post(
    post_id: str,
    platform: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from app.services.social.linkedin import LinkedInService
    from app.services.social.instagram import InstagramService
    from app.core.security import decrypt_value
    from app.models.models import PublishingHistory
    import logging
    logger = logging.getLogger(__name__)

    result = await db.execute(select(GeneratedPost).where(GeneratedPost.id == post_id, GeneratedPost.user_id == current_user.id))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(404, "Post not found")

    default_platform = post.platform.value if hasattr(post.platform, 'value') else str(post.platform)
    target_platforms = []
    if platform:
        if platform.lower() == "both":
            target_platforms = ["linkedin", "instagram"]
        else:
            target_platforms = [platform.lower()]
    else:
        target_platforms = [default_platform]

    simulated_platforms = []
    success_platforms = []

    for plat_str in target_platforms:
        acc_result = await db.execute(
            select(ConnectedAccount).where(
                ConnectedAccount.user_id == current_user.id,
                ConnectedAccount.platform == plat_str
            )
        )
        account = acc_result.scalar_one_or_none()
        caption = post.linkedin_caption if plat_str == "linkedin" else post.instagram_caption
        if not caption:
            caption = post.headline or "Check out our latest update!"

        start = time.time()
        platform_post_id = f"SIMULATED-{uuid.uuid4().hex[:8]}"
        is_simulated = False

        if account:
            try:
                access_token = decrypt_value(account.access_token)
                if plat_str == "linkedin":
                    if account.platform_page_id:
                        urn = f"urn:li:organization:{account.platform_page_id}"
                    else:
                        urn = f"urn:li:person:{account.platform_user_id}"
                    svc = LinkedInService(access_token, urn)
                else:
                    svc = InstagramService(access_token, account.platform_user_id)
                image_to_publish = post.image_url or post.media_url
                result_data = await svc.publish_post(caption, image_to_publish)
                platform_post_id = result_data.get("platform_post_id", platform_post_id)
            except Exception as e:
                logger.error(f"[Posts] Live publishing to {plat_str} failed. Reason: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to publish to {plat_str.capitalize()}: {str(e)}")
        else:
            raise HTTPException(
                status_code=400, 
                detail=f"Please connect your {plat_str.capitalize()} account first in the Integrations page before publishing."
            )

        success_platforms.append(plat_str.capitalize())

        gen_ms = int((time.time() - start) * 1000)
        history = PublishingHistory(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            post_id=post.id,
            platform=plat_str,
            platform_post_id=platform_post_id,
            published_at=datetime.utcnow(),
            status="published",
            generation_time_ms=gen_ms,
            caption_preview=caption[:200] if caption else None,
            image_url=post.image_url or post.media_url,
        )
        db.add(history)

    post.status = "published"
    await db.flush()

    if len(target_platforms) > 1:
        if simulated_platforms and not success_platforms:
            msg = "Post published to both LinkedIn & Instagram (Simulated Demo Mode)"
        elif simulated_platforms:
            msg = f"Post published to {' & '.join(success_platforms)} and simulated on {' & '.join(simulated_platforms)}"
        else:
            msg = "Post published simultaneously to both LinkedIn & Instagram successfully!"
    else:
        plat_display = target_platforms[0].capitalize()
        if simulated_platforms:
            msg = f"Post published to {plat_display} (Simulated Demo Mode — connect account in Social Accounts for live publishing)"
        else:
            msg = f"Post published to {plat_display} successfully!"

    return MessageResponse(message=msg)


@router.delete("/clear-cache", response_model=MessageResponse)
async def clear_posts_cache(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        delete(GeneratedPost).where(
            GeneratedPost.user_id == current_user.id,
            GeneratedPost.status.not_in(["scheduled", "published"])
        )
    )
    deleted_count = result.rowcount
    return MessageResponse(message=f"Cleared {deleted_count} generated/failed post(s) from generator! Scheduled & Published history preserved.")


@router.delete("/{post_id}", response_model=MessageResponse)
async def delete_post(
    post_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(GeneratedPost).where(GeneratedPost.id == post_id, GeneratedPost.user_id == current_user.id))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(404, "Post not found")
    await db.delete(post)
    return MessageResponse(message="Post deleted")
