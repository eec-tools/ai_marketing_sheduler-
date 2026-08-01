"""
Video Agent — Step 6: Reel Production Pipeline
Converts approved Reel scripts into scene-by-scene cinematic prompts
for AI video generation (Flow AI or equivalent).

Pipeline:
6.1 Video Prompt Generation (this agent)
6.2 AI Prompt Review Agent (review_agent.py)
6.3 Human Prompt Review (Approval Hub)
6.4 AI Video Generation (Flow AI — future integration)
6.5 AI Video Review Agent (review_agent.py)
6.6 Human Video Review (Approval Hub)
6.7 Video Editing (manual for now)
"""
import json
import logging
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import GeneratedPost, VideoPrompt, PostStatusEnum
from app.services.ai.llm import call_llm

logger = logging.getLogger(__name__)

VIDEO_PROMPT_SYSTEM = """You are a cinematic director specializing in short-form vertical video content (Instagram Reels).
You convert scripts into precise, scene-by-scene AI video generation prompts.

Each scene prompt must include:
- Exact visual description (what the viewer sees)
- Camera angle and movement
- Lighting and color grading
- Character/subject appearance (consistent across scenes)
- Text overlays to display
- Duration in seconds
- Audio/voiceover line for that scene"""

VIDEO_PROMPT_USER = """Convert the following approved Reel script into scene-by-scene cinematic prompts 
for AI video generation.

=== REEL SCRIPT ===
{reel_script}

=== SPOKEN SCRIPT ===
{spoken_script}

=== TEXT OVERLAYS ===
{text_overlays}

=== BRAND CONTEXT ===
Company: {company_name}
Primary Color: {primary_color}
Secondary Color: {secondary_color}
Music Mood: {music_mood}

=== INSTRUCTIONS ===
Create 4-6 scenes that together form a cohesive 30-second vertical video.
Maintain ABSOLUTE visual consistency across all scenes (same character, same setting style, same color grading).

Return ONLY valid JSON:
{{
    "total_duration_seconds": 30,
    "aspect_ratio": "9:16",
    "color_grading": "Warm cinematic with brand colors",
    "scenes": [
        {{
            "scene_num": 1,
            "duration_seconds": 3,
            "visual_prompt": "Detailed cinematic prompt describing exactly what the AI should generate...",
            "camera": "Close-up, slight dolly in",
            "lighting": "Warm golden hour side lighting",
            "text_overlay": "Text to display on screen",
            "voiceover": "What is spoken during this scene",
            "transition_to_next": "Quick cut"
        }},
        ...
    ],
    "music_direction": "Upbeat corporate motivational track, 120 BPM",
    "overall_style_notes": "Notes on maintaining visual consistency"
}}"""


async def generate_video_prompts(
    db: AsyncSession,
    post: GeneratedPost,
    brand_context: dict,
    api_key: str,
    provider: str = "groq"
) -> VideoPrompt:
    """
    Step 6.1: Convert an approved Reel script into scene-by-scene cinematic prompts.
    The reel_script data is stored in post.image_requirements as JSON.
    """
    # Parse the stored reel data
    reel_data = {}
    if post.image_requirements:
        try:
            reel_data = json.loads(post.image_requirements)
        except json.JSONDecodeError:
            reel_data = {"spoken_script": post.image_requirements}

    prompt = VIDEO_PROMPT_USER.format(
        reel_script=json.dumps(reel_data.get("reel_script", {}), indent=2),
        spoken_script=reel_data.get("spoken_script", ""),
        text_overlays=json.dumps(reel_data.get("text_overlays", [])),
        company_name=brand_context.get("company_name", "Elan Exports"),
        primary_color=brand_context.get("primary_color", "#2563EB"),
        secondary_color=brand_context.get("secondary_color", "#64748B"),
        music_mood=reel_data.get("music_mood", "inspiring"),
    )

    logger.info(f"Generating video prompts for post {post.id}")

    raw = await call_llm(
        provider=provider,
        api_key=api_key,
        system_prompt=VIDEO_PROMPT_SYSTEM,
        user_prompt=prompt,
        temperature=0.6
    )

    text = raw.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    parsed = json.loads(text, strict=False)

    # Create or update VideoPrompt record
    video_prompt = VideoPrompt(
        post_id=post.id,
        scenes=parsed.get("scenes", []),
    )
    db.add(video_prompt)

    post.status = PostStatusEnum.prompt_review_pending
    await db.commit()
    await db.refresh(video_prompt)

    logger.info(f"Video prompts created: {len(parsed.get('scenes', []))} scenes for post {post.id}")
    return video_prompt
