import logging
import json
import urllib.parse
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import GeneratedPost, PostStatusEnum

logger = logging.getLogger(__name__)

async def generate_media(db: AsyncSession, post: GeneratedPost) -> bool:
    """
    Generate media (Image/Video) using Pollinations.ai based on the approved prompt.
    Pollinations image API is a simple GET request. We generate the URL and save it.
    """
    try:
        reqs = json.loads(post.image_requirements) if post.image_requirements else {}
        if not isinstance(reqs, dict): reqs = {}
    except Exception:
        reqs = {}
        
    prompt = reqs.get("generated_prompt", "")
    if not prompt:
        logger.error(f"Post {post.id} missing generated_prompt.")
        return False
        
    encoded_prompt = urllib.parse.quote(prompt)
    
    # For now, if it's a Reel, we might want to use the video model. 
    # But Pollinations image API works great. We'll use the image endpoint for static, and video model for Reels if possible.
    if reqs.get("type") == "reel":
        # Using Pollinations gen API for video or just setting a placeholder if video is complex.
        # Pollinations text-to-video usually requires `model=video` or similar in URL?
        # A simple way for pollinations: `https://image.pollinations.ai/prompt/{prompt}?width=1080&height=1920&nologo=true` (vertical image for now, or if they have a video endpoint we'll use that)
        post.media_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1080&height=1920&nologo=true"
    else:
        post.media_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1080&height=1080&nologo=true"
    
    post.status = PostStatusEnum.creative_review_pending
    await db.commit()
    logger.info(f"Generated media for post {post.id}: {post.media_url}")
    return True

