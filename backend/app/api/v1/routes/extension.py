import time
import uuid
import logging
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Body, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.models import GeneratedPost, User, BrandProfile
from app.api.v1.deps import get_current_user
from app.core.security import decode_token
from app.services.image_card import composite_logo_on_image

router = APIRouter(tags=["extension"])

# In-memory ephemeral storage for active extension jobs
EXTENSION_JOBS: Dict[str, dict] = {}


class CreateJobRequest(BaseModel):
    prompt: str
    post_id: Optional[str] = None
    style: Optional[str] = "chatgpt"


class CompleteJobRequest(BaseModel):
    image_data: str  # Base64 data URL or external URL
    notes: Optional[str] = "Generated via ChatGPT / DALL-E Chrome Extension"


async def get_optional_user(request: Request, db: AsyncSession = Depends(get_db)) -> Optional[User]:
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        return None
    try:
        token = auth.split(" ")[1]
        payload = decode_token(token)
        if not payload or payload.get("type") != "access":
            return None
        user_id = payload.get("sub")
        if not user_id:
            return None
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
    except Exception:
        return None


@router.post("/jobs", status_code=201)
async def create_extension_job(
    request: CreateJobRequest,
    user: Optional[User] = Depends(get_optional_user),
):
    """Create a new image generation request for the Chrome Extension."""
    job_id = str(uuid.uuid4())
    user_id = user.id if user else "extension-test-user"
    job = {
        "id": job_id,
        "user_id": user_id,
        "post_id": request.post_id,
        "prompt": request.prompt,
        "style": request.style,
        "status": "pending",
        "image_url": None,
        "error": None,
        "created_at": time.time(),
        "completed_at": None,
    }
    EXTENSION_JOBS[job_id] = job
    logging.info(f"Created ChatGPT extension job {job_id} for prompt: {request.prompt[:60]}...")
    return job


@router.get("/jobs/pending")
async def get_pending_jobs(db: AsyncSession = Depends(get_db)):
    """Polled by the Chrome Extension background worker to discover new pending jobs.
    Note: Publicly accessible locally so the browser extension can poll without auth token hurdles."""
    # Auto-unstick jobs that have been in 'processing' for > 120 seconds without completion
    now = time.time()
    for job in EXTENSION_JOBS.values():
        if job["status"] == "processing" and (now - job.get("created_at", now)) > 120:
            logging.warning(f"Job {job['id']} stuck in processing for >120s, resetting to pending.")
            job["status"] = "pending"
            job["created_at"] = now

    pending = [
        job for job in EXTENSION_JOBS.values()
        if job["status"] == "pending"
    ]
    # Also discover any waiting posts from the DB that aren't already in EXTENSION_JOBS
    existing_job_ids = set(EXTENSION_JOBS.keys())
    try:
        result = await db.execute(
            select(GeneratedPost).where(
                GeneratedPost.image_review_notes.contains("Job ID: "),
                GeneratedPost.image_url.is_(None)
            )
        )
        db_posts = result.scalars().all()
        for post in db_posts:
            job_id = post.id
            if post.image_review_notes and "Job ID: " in post.image_review_notes:
                try:
                    job_id = post.image_review_notes.split("Job ID: ")[-1].strip().rstrip(")")
                except Exception:
                    job_id = post.id
            if job_id not in existing_job_ids:
                job = {
                    "id": job_id,
                    "user_id": post.user_id,
                    "post_id": post.id,
                    "prompt": post.image_requirements or post.headline or "High quality social media graphic",
                    "style": "professional",
                    "status": "pending",
                    "image_url": None,
                    "error": None,
                    "created_at": time.time(),
                    "completed_at": None,
                }
                EXTENSION_JOBS[job_id] = job
                pending.append(job)
                existing_job_ids.add(job_id)
    except Exception as e:
        logging.error(f"Error checking DB for pending extension posts: {e}")

    # Sort by created_at ascending (FIFO)
    pending.sort(key=lambda x: x["created_at"])
    return pending


@router.post("/jobs/{job_id}/claim")
async def claim_job(job_id: str, db: AsyncSession = Depends(get_db)):
    """Called when the extension starts processing a job."""
    if job_id not in EXTENSION_JOBS:
        # Check if we can recover from DB
        try:
            result = await db.execute(
                select(GeneratedPost).where(GeneratedPost.image_review_notes.contains(job_id))
            )
            post = result.scalar_one_or_none()
            if not post:
                result = await db.execute(select(GeneratedPost).where(GeneratedPost.id == job_id))
                post = result.scalar_one_or_none()
            if post:
                EXTENSION_JOBS[job_id] = {
                    "id": job_id,
                    "user_id": post.user_id,
                    "post_id": post.id,
                    "prompt": post.image_requirements or post.headline or "High quality social media graphic",
                    "style": "professional",
                    "status": "processing",
                    "image_url": None,
                    "error": None,
                    "created_at": time.time(),
                    "completed_at": None,
                }
        except Exception:
            pass

    if job_id not in EXTENSION_JOBS:
        raise HTTPException(status_code=404, detail="Job not found")
    EXTENSION_JOBS[job_id]["status"] = "processing"
    return EXTENSION_JOBS[job_id]


@router.post("/jobs/{job_id}/complete")
async def complete_job(
    job_id: str,
    request: CompleteJobRequest,
    db: AsyncSession = Depends(get_db),
):
    """Called by the Chrome Extension when ChatGPT finishes drawing the image."""
    job = EXTENSION_JOBS.get(job_id)
    post_id = job["post_id"] if job and job.get("post_id") else None

    # If job not in memory, try finding the post directly via job_id or DB search
    if not post_id:
        try:
            result = await db.execute(
                select(GeneratedPost).where(GeneratedPost.image_review_notes.contains(job_id))
            )
            post = result.scalar_one_or_none()
            if not post:
                result = await db.execute(select(GeneratedPost).where(GeneratedPost.id == job_id))
                post = result.scalar_one_or_none()
            if post:
                post_id = post.id
        except Exception as e:
            logging.error(f"Error recovering post for job {job_id}: {e}")

    if job:
        job["status"] = "completed"
        job["image_url"] = request.image_data
        job["completed_at"] = time.time()
    else:
        job = {
            "id": job_id,
            "status": "completed",
            "image_url": request.image_data,
            "completed_at": time.time(),
            "post_id": post_id
        }
        EXTENSION_JOBS[job_id] = job

    # Update the post in the database directly
    if post_id:
        try:
            result = await db.execute(
                select(GeneratedPost).where(GeneratedPost.id == post_id)
            )
            post = result.scalar_one_or_none()
            if post:
                final_image = request.image_data

                # ── Composite actual brand logo on the ChatGPT/DALL-E image ──
                try:
                    brand_result = await db.execute(
                        select(BrandProfile).where(BrandProfile.user_id == post.user_id)
                    )
                    brand = brand_result.scalar_one_or_none()
                    if brand and brand.logo_url:
                        final_image = composite_logo_on_image(final_image, brand.logo_url)
                        logging.info(f"Brand logo composited on ChatGPT image for post {post_id} ✅")
                except Exception as logo_err:
                    logging.warning(f"Logo compositing failed for post {post_id}: {logo_err}")

                post.image_url = final_image
                post.image_review_result = "PASS"
                post.image_review_notes = request.notes
                post.status = "approved"
                await db.commit()
                logging.info(f"Updated database post {post_id} with ChatGPT image and set status to approved.")
        except Exception as e:
            logging.error(f"Error updating linked post {post_id}: {e}")

    return {"status": "success", "job": job}


@router.post("/jobs/{job_id}/fail")
async def fail_job(
    job_id: str,
    error: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
):
    """Called if ChatGPT generation encounters an error."""
    job = EXTENSION_JOBS.get(job_id)
    post_id = job["post_id"] if job and job.get("post_id") else None

    if not post_id:
        try:
            result = await db.execute(
                select(GeneratedPost).where(GeneratedPost.image_review_notes.contains(job_id))
            )
            post = result.scalar_one_or_none()
            if not post:
                result = await db.execute(select(GeneratedPost).where(GeneratedPost.id == job_id))
                post = result.scalar_one_or_none()
            if post:
                post_id = post.id
        except Exception:
            pass

    if job:
        job["status"] = "failed"
        job["error"] = error
        job["completed_at"] = time.time()
    else:
        job = {"id": job_id, "status": "failed", "error": error, "completed_at": time.time(), "post_id": post_id}
        EXTENSION_JOBS[job_id] = job

    if post_id:
        try:
            result = await db.execute(
                select(GeneratedPost).where(GeneratedPost.id == post_id)
            )
            post = result.scalar_one_or_none()
            if post:
                post.image_review_result = "FAIL"
                post.image_review_notes = f"ChatGPT Extension failed: {error}"
                post.status = "failed"
                await db.commit()
        except Exception as e:
            logging.error(f"Error updating failed post {post_id}: {e}")

    return {"status": "failed", "job": job}


@router.get("/jobs/{job_id}/status")
async def get_job_status(job_id: str):
    """Called by the frontend to check real-time completion of a job."""
    if job_id not in EXTENSION_JOBS:
        raise HTTPException(status_code=404, detail="Job not found")
    return EXTENSION_JOBS[job_id]
