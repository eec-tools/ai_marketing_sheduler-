"""
Approval Hub API Routes — Human-in-the-loop endpoints for the v3 workflow.

Endpoints:
- GET  /pipeline/status              — Dashboard: counts by status
- POST /pipeline/generate-strategy   — Kick off Step 1 (Audit + Strategy)
- GET  /pipeline/pending             — List all items pending human review
- POST /pipeline/research/{id}/approve  — Approve research brief
- POST /pipeline/research/{id}/reject   — Reject research (regenerate)
- POST /pipeline/content/{id}/approve   — Approve content
- POST /pipeline/content/{id}/reject    — Reject content (regenerate)
- POST /pipeline/prompts/{id}/approve   — Approve video prompts
- POST /pipeline/prompts/{id}/reject    — Reject video prompts (regenerate)
"""
import json
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.api.v1.deps import get_current_user, get_db
from app.models.models import (
    GeneratedPost, ContentBrief, VideoPrompt, MonthlyStrategy,
    BrandProfile, PostStatusEnum, User
)
from app.services.ai.agents.pipeline import (
    run_full_strategy_pipeline,
    run_research_pipeline,
    run_content_pipeline,
    run_video_prompt_pipeline,
)
from app.services.key_rotation import KeyRotator
from app.core.security import decrypt_value

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pipeline", tags=["Pipeline"])
_key_rotator = KeyRotator()


# ─── Schemas ──────────────────────────────────────────────────────────────────

class StrategyRequest(BaseModel):
    month: str  # e.g. "2025-08"
    target_format: str  # e.g. "instagram_reels", "instagram_posts", "linkedin"

class RejectRequest(BaseModel):
    feedback: str = ""

class PostEditRequest(BaseModel):
    title: Optional[str] = None
    hook: Optional[str] = None
    linkedin_caption: Optional[str] = None
    instagram_caption: Optional[str] = None
    image_requirements: Optional[str] = None
    key_takeaways: Optional[str] = None
    market_trends: Optional[str] = None
    voiceover: Optional[str] = None
    visual_prompt: Optional[str] = None


# ─── Helper: get Groq key for user ───────────────────────────────────────────

async def _get_groq_key(db: AsyncSession, user_id: str) -> str:
    try:
        key_record = await _key_rotator.get_next_key(user_id, "groq", db)
        return decrypt_value(key_record.encrypted_key)
    except Exception:
        raise HTTPException(status_code=400, detail="No active Groq API key found. Add one in API Keys page.")


async def _get_brand_context(db: AsyncSession, user_id: str) -> dict:
    result = await db.execute(select(BrandProfile).where(BrandProfile.user_id == user_id))
    brand = result.scalar_one_or_none()
    if not brand:
        raise HTTPException(status_code=400, detail="No brand profile found.")
    return {
        "company_name": brand.company_name or "",
        "industry": brand.industry or "",
        "target_audience": brand.target_audience or "",
        "writing_tone": brand.writing_tone or "",
        "cta": brand.cta or "",
        "primary_color": brand.primary_color or "#2563EB",
        "secondary_color": brand.secondary_color or "#64748B",
        "company_description": brand.company_description or "",
        "products_services": brand.products_services or "",
        "unique_value_proposition": brand.unique_value_proposition or "",
    }


# ─── Dashboard ────────────────────────────────────────────────────────────────

@router.get("/status")
async def pipeline_status(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get counts of posts in each pipeline state."""
    counts = {}
    for status in PostStatusEnum:
        result = await db.execute(
            select(func.count(GeneratedPost.id)).where(
                GeneratedPost.user_id == user.id,
                GeneratedPost.status == status
            )
        )
        counts[status.value] = result.scalar() or 0

    # Get latest strategy
    result = await db.execute(
        select(MonthlyStrategy)
        .where(MonthlyStrategy.user_id == user.id)
        .order_by(MonthlyStrategy.created_at.desc())
        .limit(1)
    )
    latest_strategy = result.scalar_one_or_none()

    return {
        "counts": counts,
        "latest_strategy": {
            "id": latest_strategy.id,
            "month": latest_strategy.month,
            "status": latest_strategy.status,
            "total_ideas": len(latest_strategy.calendar or []),
            "created_at": str(latest_strategy.created_at),
            "audit_data": latest_strategy.audit_data,
        } if latest_strategy else None
    }


# ─── Step 1: Generate Strategy ───────────────────────────────────────────────

@router.post("/generate-strategy")
async def generate_strategy(
    req: StrategyRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Kick off the full Step 1 pipeline (Audit + Strategy + Calendar creation) in the background."""

    # Check brand profile exists before queuing
    from sqlalchemy import select as sa_select
    result = await db.execute(sa_select(BrandProfile).where(BrandProfile.user_id == user.id))
    brand = result.scalar_one_or_none()
    if not brand:
        raise HTTPException(status_code=400, detail="No brand profile found. Please set up your brand profile first.")

    from app.services.background import background_run_strategy_pipeline
    background_tasks.add_task(background_run_strategy_pipeline, user.id, req.month, req.target_format)

    return {
        "message": f"Strategy generation started for {req.month}. Drafts will appear shortly — the page auto-refreshes every 10s.",
        "month": req.month,
        "format": req.target_format,
        "status": "generating",
    }


# ─── Pending Items ────────────────────────────────────────────────────────────

@router.get("/pending")
async def get_pending_items(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get all items across all review stages for the Approval Hub."""
    result = await db.execute(
        select(GeneratedPost)
        .options(selectinload(GeneratedPost.brief))
        .where(
            GeneratedPost.user_id == user.id,
            GeneratedPost.status.notin_([PostStatusEnum.published, PostStatusEnum.scheduled, PostStatusEnum.failed])
        )
    )
    posts = result.scalars().all()

    def serialize_post(p):
        format_val = None
        reqs_data = {}
        if p.image_requirements:
            try:
                reqs_data = json.loads(p.image_requirements)
                format_val = reqs_data.get("format")
            except Exception:
                pass

        # Safe access: brief is a backref list, not a scalar
        _brief = p.brief[0] if getattr(p, "brief", None) and len(p.brief) > 0 else None

        return {
            "id": p.id,
            "headline": p.headline,
            "platform": p.platform.value if p.platform else None,
            "format": format_val or (p.platform.value if p.platform else None),
            "status": p.status.value if p.status else None,
            "error_message": p.error_message,
            "linkedin_caption": p.linkedin_caption,
            "instagram_caption": p.instagram_caption,
            "hook": getattr(p, "hook", None),
            "hashtags": getattr(p, "hashtags", []),
            "cta": p.cta,
            "created_at": str(p.created_at),
            # Reel script fields (populated after script generation)
            "hook_1": reqs_data.get("hook_1"),
            "hook_2": reqs_data.get("hook_2"),
            "reel_script": reqs_data.get("reel_script"),
            "spoken_script": reqs_data.get("spoken_script"),
            "text_overlays": reqs_data.get("text_overlays", []),
            "estimated_duration": reqs_data.get("estimated_duration_seconds"),
            "brief": {
                "research_data": _brief.research_data,
                "statistics": _brief.statistics or [],
                "references": _brief.references or [],
                "market_trends": _brief.market_trends,
                "key_takeaways": _brief.key_takeaways,
            } if _brief else None,
        }

    return [serialize_post(p) for p in posts]


# ─── Drafts Approve/Reject ───────────────────────────────────────────────────

@router.post("/drafts/{post_id}/approve")
async def approve_draft(
    post_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Start research for a specific draft post (non-blocking background task)."""
    post = await db.get(GeneratedPost, post_id)
    if not post or post.user_id != user.id or post.status != PostStatusEnum.draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    brand_context = await _get_brand_context(db, user.id)

    # Optimistic status update so the UI immediately reflects the transition
    post.status = PostStatusEnum.research_pending
    post.error_message = None
    await db.commit()

    from app.services.background import background_run_research_pipeline
    background_tasks.add_task(background_run_research_pipeline, post_id, brand_context)
    return {"message": "Research started in background", "post_id": post_id}

@router.delete("/drafts/{post_id}")
async def delete_draft(
    post_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Delete a specific draft idea."""
    post = await db.get(GeneratedPost, post_id)
    if not post or post.user_id != user.id or post.status != PostStatusEnum.draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    await db.delete(post)
    await db.commit()
    return {"message": "Draft deleted successfully"}

@router.delete("/clear")
async def clear_stage(
    stage: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Delete all posts for the user in a specific stage."""
    # Map front-end stage to backend enum
    status_map = {
        'draft': PostStatusEnum.draft,
        'research_pending': PostStatusEnum.research_pending,
        'content_review_pending': PostStatusEnum.content_review_pending,
        'prompt_review_pending': PostStatusEnum.prompt_review_pending,
        'video_review_pending': PostStatusEnum.video_review_pending,
        'failed': PostStatusEnum.failed,
    }
    target_status = status_map.get(stage)
    if not target_status:
        raise HTTPException(status_code=400, detail="Invalid stage")

    result = await db.execute(
        select(GeneratedPost).where(
            GeneratedPost.user_id == user.id,
            GeneratedPost.status == target_status
        )
    )
    posts = result.scalars().all()
    for post in posts:
        await db.delete(post)
    await db.commit()
    return {"message": f"Deleted {len(posts)} items"}

@router.post("/content/start-all")
async def start_all_content(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Kick off content generation for all research_approved posts."""
    brand_context = await _get_brand_context(db, user.id)

    # Optimistically mark them as content_review_pending
    result = await db.execute(select(GeneratedPost).where(GeneratedPost.user_id == user.id, GeneratedPost.status == PostStatusEnum.research_pending))
    posts = result.scalars().all()
    for p in posts:
        p.status = PostStatusEnum.research_approved
    await db.commit()

    from app.services.background import process_all_content_background
    background_tasks.add_task(process_all_content_background, user.id, brand_context)
    return {"message": "Content generation started for all approved research"}

@router.post("/prompts/start-all")
async def start_all_prompts(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Kick off video prompt generation for all content_approved posts."""
    brand_context = await _get_brand_context(db, user.id)

    # Optimistically mark them as prompt_review_pending
    result = await db.execute(select(GeneratedPost).where(GeneratedPost.user_id == user.id, GeneratedPost.status == PostStatusEnum.content_review_pending))
    posts = result.scalars().all()
    for p in posts:
        p.status = PostStatusEnum.content_approved
    await db.commit()

    from app.services.background import process_all_video_prompt_background
    background_tasks.add_task(process_all_video_prompt_background, user.id, brand_context)
    return {"message": "Video prompt generation started for all approved content"}

# ─── Edit Content ────────────────────────────────────────────────────────────

@router.put("/posts/{post_id}")
async def update_post_content(
    post_id: str,
    req: PostEditRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Save manual inline edits made in the Approval Hub."""
    post = await db.get(GeneratedPost, post_id)
    if not post or post.user_id != user.id:
        raise HTTPException(status_code=404, detail="Post not found")
        
    # Update GeneratedPost fields
    if req.title is not None:
        post.title = req.title
    if req.hook is not None:
        post.hook = req.hook
    if req.linkedin_caption is not None:
        post.linkedin_caption = req.linkedin_caption
    if req.instagram_caption is not None:
        post.instagram_caption = req.instagram_caption
    if req.image_requirements is not None:
        post.image_requirements = req.image_requirements
        
    # Update latest ContentBrief fields if provided
    if req.key_takeaways is not None or req.market_trends is not None:
        result = await db.execute(select(ContentBrief).where(ContentBrief.post_id == post_id).order_by(ContentBrief.created_at.desc()))
        brief = result.scalars().first()
        if brief:
            if req.key_takeaways is not None:
                brief.key_takeaways = req.key_takeaways
            if req.market_trends is not None:
                brief.market_trends = req.market_trends

    # Update latest VideoPrompt fields if provided
    if req.voiceover is not None or req.visual_prompt is not None:
        result = await db.execute(select(VideoPrompt).where(VideoPrompt.post_id == post_id).order_by(VideoPrompt.created_at.desc()))
        prompt = result.scalars().first()
        if prompt:
            if req.voiceover is not None:
                prompt.voiceover = req.voiceover
            if req.visual_prompt is not None:
                prompt.visual_prompt = req.visual_prompt

    await db.commit()
    return {"message": "Post updated successfully", "post_id": post_id}

# ─── Research Approve/Reject ─────────────────────────────────────────────────

@router.post("/research/{post_id}/approve")
async def approve_research(
    post_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Human approves the research brief.
    - For Instagram Reels: triggers Reel Script generation (Step 3.5).
    - For static posts (LinkedIn, Instagram Posts): triggers content generation directly.
    """
    post = await db.get(GeneratedPost, post_id)
    if not post or post.user_id != user.id:
        raise HTTPException(status_code=404, detail="Post not found")

    brand_context = await _get_brand_context(db, user.id)

    # Detect if this is a reel
    is_reel = False
    if post.image_requirements:
        try:
            reqs = json.loads(post.image_requirements)
            is_reel = reqs.get("content_type") == "reel"
        except Exception:
            pass

    post.status = PostStatusEnum.research_approved
    await db.commit()

    if is_reel:
        from app.services.background import background_run_script_pipeline
        background_tasks.add_task(background_run_script_pipeline, post_id, brand_context)
        return {"message": "Research approved. Reel script generation started.", "post_id": post_id}
    else:
        from app.services.background import background_run_content_pipeline
        background_tasks.add_task(background_run_content_pipeline, post_id, brand_context)
        return {"message": "Research approved. Content generation started.", "post_id": post_id}


@router.post("/research/{post_id}/reject")
async def reject_research(
    post_id: str,
    req: RejectRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Human rejects research → triggers re-research."""
    post = await db.get(GeneratedPost, post_id)
    if not post or post.user_id != user.id:
        raise HTTPException(status_code=404, detail="Post not found")

    brand_context = await _get_brand_context(db, user.id)

    # Delete old brief
    result = await db.execute(select(ContentBrief).where(ContentBrief.post_id == post_id).order_by(ContentBrief.created_at.desc()))
    old_brief = result.scalars().first()
    if old_brief:
        old_brief.human_feedback = req.feedback
        await db.commit()
        await db.delete(old_brief)
        await db.commit()

    post.status = PostStatusEnum.research_pending
    await db.commit()

    from app.services.background import background_run_research_pipeline
    background_tasks.add_task(background_run_research_pipeline, post_id, brand_context)

    return {"message": "Research rejected. Re-research triggered.", "post_id": post_id}


# Script Approve/Reject (Reels Only) ─────────────────────────────────────────

@router.post("/script/{post_id}/approve")
async def approve_script(
    post_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Human approves the Reel script → triggers Instagram caption + hashtag generation."""
    post = await db.get(GeneratedPost, post_id)
    if not post or post.user_id != user.id:
        raise HTTPException(status_code=404, detail="Post not found")

    brand_context = await _get_brand_context(db, user.id)

    post.status = PostStatusEnum.script_approved
    await db.commit()

    from app.services.background import background_run_content_pipeline
    background_tasks.add_task(background_run_content_pipeline, post_id, brand_context)

    return {"message": "Script approved. Caption generation started.", "post_id": post_id}


@router.post("/script/{post_id}/reject")
async def reject_script(
    post_id: str,
    req: RejectRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Human rejects the Reel script → triggers script regeneration."""
    post = await db.get(GeneratedPost, post_id)
    if not post or post.user_id != user.id:
        raise HTTPException(status_code=404, detail="Post not found")

    brand_context = await _get_brand_context(db, user.id)

    # Revert to research_approved so the script pipeline can re-run
    post.status = PostStatusEnum.research_approved
    post.error_message = req.feedback or "Script rejected by reviewer"
    await db.commit()

    from app.services.background import background_run_script_pipeline
    background_tasks.add_task(background_run_script_pipeline, post_id, brand_context)

    return {"message": "Script rejected. Regeneration triggered.", "post_id": post_id}


# Content Approve/Reject ──────────────────────────────────────────────────────

@router.post("/content/{post_id}/approve")
async def approve_content(
    post_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Human approves content → for reels, triggers video prompt gen. For static, marks as scheduled-ready."""
    post = await db.get(GeneratedPost, post_id)
    if not post or post.user_id != user.id:
        raise HTTPException(status_code=404, detail="Post not found")

    # Check if it's a reel
    topic_data = {}
    if post.image_requirements:
        try:
            topic_data = json.loads(post.image_requirements)
        except json.JSONDecodeError:
            pass

    content_type = topic_data.get("content_type", topic_data.get("type", "static"))

    if content_type == "reel":
        brand_context = await _get_brand_context(db, user.id)
        post.status = PostStatusEnum.content_approved
        await db.commit()
        # Trigger video prompt pipeline
        from app.services.background import background_run_video_prompt_pipeline
        background_tasks.add_task(background_run_video_prompt_pipeline, post_id, brand_context)
        return {"message": "Content approved. Video prompt generation started.", "post_id": post_id}
    else:
        post.status = PostStatusEnum.content_approved
        await db.commit()
        return {"message": "Content approved. Ready for scheduling.", "post_id": post_id}


@router.post("/content/{post_id}/reject")
async def reject_content(
    post_id: str,
    req: RejectRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Human rejects content → triggers content regeneration."""
    post = await db.get(GeneratedPost, post_id)
    if not post or post.user_id != user.id:
        raise HTTPException(status_code=404, detail="Post not found")

    brand_context = await _get_brand_context(db, user.id)

    result = await db.execute(select(ContentBrief).where(ContentBrief.post_id == post_id).order_by(ContentBrief.created_at.desc()))
    brief = result.scalars().first()
    if not brief:
        raise HTTPException(status_code=400, detail="No research brief found")

    # Re-run content pipeline
    post.status = PostStatusEnum.content_review_pending
    await db.commit()
    from app.services.background import background_run_content_pipeline
    background_tasks.add_task(background_run_content_pipeline, post_id, brand_context)

    return {"message": "Content rejected. Regenerating.", "post_id": post_id}


# ─── Video Prompt Approve/Reject ─────────────────────────────────────────────

@router.post("/prompts/{post_id}/approve")
async def approve_prompts(
    post_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Human approves cinematic prompts → ready for Flow AI video generation."""
    post = await db.get(GeneratedPost, post_id)
    if not post or post.user_id != user.id:
        raise HTTPException(status_code=404, detail="Post not found")

    post.status = PostStatusEnum.prompt_approved
    await db.commit()

    return {"message": "Video prompts approved. Ready for video generation.", "post_id": post_id}


@router.post("/prompts/{post_id}/reject")
async def reject_prompts(
    post_id: str,
    req: RejectRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Human rejects prompts → regenerate."""
    post = await db.get(GeneratedPost, post_id)
    if not post or post.user_id != user.id:
        raise HTTPException(status_code=404, detail="Post not found")

    brand_context = await _get_brand_context(db, user.id)

    # Delete old prompts
    result = await db.execute(select(VideoPrompt).where(VideoPrompt.post_id == post_id).order_by(VideoPrompt.created_at.desc()))
    old_prompt = result.scalars().first()
    if old_prompt:
        old_prompt.human_feedback = req.feedback
        await db.commit()
        await db.delete(old_prompt)
        await db.commit()

    post.status = PostStatusEnum.prompt_review_pending
    await db.commit()
    from app.services.background import background_run_video_prompt_pipeline
    background_tasks.add_task(background_run_video_prompt_pipeline, post_id, brand_context)

    return {"message": "Video prompts rejected. Regenerating.", "post_id": post_id}


# ─── Bulk Research Trigger ────────────────────────────────────────────────────

@router.post("/research/start-all")
async def start_all_research(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Kick off research for ALL draft posts (from the latest strategy) in the background."""
    brand_context = await _get_brand_context(db, user.id)

    from app.services.background import process_all_research_background
    background_tasks.add_task(process_all_research_background, user.id, brand_context)

    return {"message": "Research started for all drafts in the background"}
