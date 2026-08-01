"""
Content Agent — Step 4: Content Creation (Split Pipeline)
Generates content DIFFERENTLY for Reels vs. Static Posts.

Reel Content:
- Complete Reel script with hook, storytelling, CTA
- Scene-by-scene breakdown for video production

Static Content (LinkedIn Post / Instagram Post / Carousel):
- LinkedIn post (long-form, professional)
- Instagram caption (concise, engaging)
- Hashtags & SEO keywords
- Image requirement prompts
"""
import json
import logging
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import GeneratedPost, ContentBrief, PostStatusEnum
from app.services.ai.llm import call_llm

logger = logging.getLogger(__name__)

# ─── Reel Script Prompt ──────────────────────────────────────────────────────

REEL_SCRIPT_PROMPT = """You are an expert Instagram Reel scriptwriter for Elan Exports Consultancy.
You write 30-60 second Reels that are educational, visually compelling, and drive massive engagement.

=== APPROVED RESEARCH BRIEF ===
{research_data}

=== KEY TAKEAWAYS ===
{key_takeaways}

=== TOPIC ===
Title: {title}
Hook: {hook}

=== BRAND CONTEXT ===
Company: {company_name}
Tone: {writing_tone}
Target Audience: {target_audience}

=== INSTRUCTIONS ===
Create a complete Instagram Reel script. Return ONLY valid JSON:
{{
    "headline": "Compelling title (max 8 words)",
    "reel_script": {{
        "hook": "First 3 seconds — the attention-grabbing opening line (spoken to camera or as text overlay)",
        "problem": "Next 5-8 seconds — state the problem or pain point",
        "insight": "10-15 seconds — deliver the expert insight with specific data",
        "solution": "10-15 seconds — show the solution or framework",
        "cta": "Final 3-5 seconds — clear call to action"
    }},
    "spoken_script": "The complete word-for-word script that will be spoken (voiceover or on-camera). Max 150 words.",
    "text_overlays": ["Text 1 for screen", "Text 2 for screen", "Text 3"],
    "instagram_caption": "Full Instagram caption following the Personal Brand Scannable Template. Include hook, problem, bullet insights, outcome, and CTA.",
    "hashtags": ["hashtag1", "hashtag2", "hashtag3", "hashtag4", "hashtag5"],
    "suggested_music_mood": "energetic | calm | dramatic | inspiring",
    "estimated_duration_seconds": 30
}}"""

# ─── Static Post Prompt ──────────────────────────────────────────────────────

STATIC_POST_PROMPT = """You are an expert social media copywriter for Elan Exports Consultancy.
You write LinkedIn posts and Instagram content that builds thought leadership and drives engagement.

=== APPROVED RESEARCH BRIEF ===
{research_data}

=== KEY TAKEAWAYS ===
{key_takeaways}

=== STATISTICS ===
{statistics}

=== TOPIC ===
Title: {title}
Platform: {platform}
Category: {category}
Hook: {hook}

=== BRAND CONTEXT ===
Company: {company_name}
Tone: {writing_tone}
Target Audience: {target_audience}
Brand CTA: {brand_cta}

=== INSTRUCTIONS ===
Create complete social media content. Return ONLY valid JSON:
{{
    "headline": "Compelling headline (max 10 words)",
    {caption_instruction}
    "hashtags": ["hashtag1", "hashtag2", "hashtag3", "hashtag4", "hashtag5"],
    "cta": "Clear, non-spammy call-to-action",
    "image_requirements": "Detailed AI image generation prompt for a professional branded creative. Include: headline text to display, background style, color palette (brand colors), typography, and visual concept. Optimized for 1080x1080.",
    "seo_keywords": ["keyword1", "keyword2", "keyword3"]
}}"""


async def generate_reel_content(
    db: AsyncSession,
    post: GeneratedPost,
    brief: ContentBrief,
    topic_data: dict,
    brand_context: dict,
    api_key: str,
    provider: str = "groq"
) -> dict:
    """Generate Reel script content from an approved research brief."""
    prompt = REEL_SCRIPT_PROMPT.format(
        research_data=brief.research_data or "",
        key_takeaways=brief.key_takeaways or "",
        title=topic_data.get("title", ""),
        hook=topic_data.get("hook", ""),
        company_name=brand_context.get("company_name", "Elan Exports"),
        writing_tone=brand_context.get("writing_tone", "professional"),
        target_audience=brand_context.get("target_audience", "International buyers"),
    )

    logger.info(f"Generating REEL content for: {topic_data.get('title', 'Unknown')}")

    raw = await call_llm(
        provider=provider,
        api_key=api_key,
        system_prompt="You are a world-class Instagram Reel scriptwriter. Always return valid JSON.",
        user_prompt=prompt
    )

    text = raw.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    content = json.loads(text, strict=False)

    # Update the post with generated content
    post.headline = content.get("headline", "")
    post.instagram_caption = content.get("instagram_caption", "")
    post.hashtags = content.get("hashtags", [])
    post.cta = content.get("reel_script", {}).get("cta", "")
    # Safely merge new content without destroying the original format
    try:
        reqs = json.loads(post.image_requirements) if post.image_requirements else {}
        if not isinstance(reqs, dict): reqs = {}
    except:
        reqs = {}
    
    reqs.update({
        "type": "reel",
        "reel_script": content.get("reel_script", {}),
        "spoken_script": content.get("spoken_script", ""),
        "text_overlays": content.get("text_overlays", []),
        "music_mood": content.get("suggested_music_mood", ""),
        "duration": content.get("estimated_duration_seconds", 30),
    })
    post.image_requirements = json.dumps(reqs)
    post.status = PostStatusEnum.content_review_pending
    await db.commit()

    logger.info(f"Reel content generated for post {post.id}")
    return content


async def generate_static_content(
    db: AsyncSession,
    post: GeneratedPost,
    brief: ContentBrief,
    topic_data: dict,
    brand_context: dict,
    api_key: str,
    provider: str = "groq"
) -> dict:
    """Generate static post/carousel content from an approved research brief."""
    format_val = topic_data.get("format", "")
    platform_val = topic_data.get("platform", "linkedin_post")
    
    if format_val == "linkedin" or "linkedin" in platform_val:
        caption_instruction = '"linkedin_caption": "Full LinkedIn post (500-800 words). Follow the Personal Brand Scannable Template: Hook → Problem → Expert Insight (bullet list) → Business Outcome → Specific CTA. Use real statistics from the research.",\n    "instagram_caption": ""'
    else:
        caption_instruction = '"instagram_caption": "Instagram caption (200-400 words). Follow the Personal Brand Scannable Template but adapted for Instagram (shorter, punchier, emoji bullets).",\n    "linkedin_caption": ""'

    prompt = STATIC_POST_PROMPT.format(
        research_data=brief.research_data or "",
        key_takeaways=brief.key_takeaways or "",
        statistics=json.dumps(brief.statistics or [], indent=2),
        title=topic_data.get("title", ""),
        platform=platform_val,
        category=topic_data.get("category", "educational"),
        hook=topic_data.get("hook", ""),
        company_name=brand_context.get("company_name", "Elan Exports"),
        writing_tone=brand_context.get("writing_tone", "professional"),
        target_audience=brand_context.get("target_audience", "International buyers"),
        brand_cta=brand_context.get("cta", "Visit elanexports.com"),
        caption_instruction=caption_instruction,
    )

    logger.info(f"Generating STATIC content for: {topic_data.get('title', 'Unknown')}")

    raw = await call_llm(
        provider=provider,
        api_key=api_key,
        system_prompt="You are a world-class B2B social media copywriter. Always return valid JSON.",
        user_prompt=prompt
    )

    text = raw.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    content = json.loads(text, strict=False)

    # Update the post with generated content
    post.headline = content.get("headline", "")
    post.linkedin_caption = content.get("linkedin_caption", "")
    post.instagram_caption = content.get("instagram_caption", "")
    post.hashtags = content.get("hashtags", [])
    post.cta = content.get("cta", "")
    # Safely merge new content without destroying the original format
    try:
        reqs = json.loads(post.image_requirements) if post.image_requirements else {}
        if not isinstance(reqs, dict): reqs = {}
    except:
        reqs = {}
        
    reqs["generated_prompt"] = content.get("image_requirements", "")
    post.image_requirements = json.dumps(reqs)
    post.status = PostStatusEnum.content_review_pending
    await db.commit()

    logger.info(f"Static content generated for post {post.id}")
    return content


# --- Reel Script Generation Prompt (Step 3.5 - Script Stage) -----------------

REEL_SCRIPT_GENERATION_PROMPT = """You are an elite Instagram Reel scriptwriter for {company_name}.
You create high-converting, educational Reels that stop the scroll and drive engagement.

=== APPROVED RESEARCH BRIEF ===
{research_data}

=== KEY TAKEAWAYS ===
{key_takeaways}

=== TOPIC ===
Title: {title}
Original Hook Idea: {hook}

=== BRAND CONTEXT ===
Company: {company_name}
Tone: {writing_tone}
Target Audience: {target_audience}

=== INSTRUCTIONS ===
Create two competing hooks and a complete, professional Reel script.
Return ONLY valid JSON:
{{
    "hook_1": {{
        "text": "First hook option — question-based or curiosity-gap (max 10 words, spoken in first 3 seconds)",
        "style": "question"
    }},
    "hook_2": {{
        "text": "Second hook option — statistic or bold statement (max 10 words, contrarian or surprising)",
        "style": "statistic"
    }},
    "reel_script": {{
        "hook": "The chosen opening line (3-5 seconds)",
        "problem": "State the problem or pain point the audience faces (5-8 seconds)",
        "insight": "The expert insight with specific data from the research (10-15 seconds)",
        "solution": "The practical solution or framework (10-15 seconds)",
        "cta": "Clear, direct call to action (3-5 seconds)"
    }},
    "spoken_script": "The complete, word-for-word script to be spoken on camera or as voiceover. Must flow naturally when read aloud. Max 150 words.",
    "text_overlays": ["Overlay 1 (bold key stat)", "Overlay 2 (key term)", "Overlay 3 (CTA text)"],
    "estimated_duration_seconds": 45
}}"""

# --- Reel Caption Prompt (Step 4 - uses approved script) ----------------------

REEL_CAPTION_PROMPT = """You are an expert Instagram caption writer for {company_name}.
An approved Reel script already exists. Your job is ONLY to write the Instagram caption and hashtags.

=== APPROVED REEL SCRIPT ===
Hook Option 1: {hook_1}
Hook Option 2: {hook_2}
Spoken Script: {spoken_script}

=== ORIGINAL RESEARCH ===
{research_data}

=== BRAND CONTEXT ===
Company: {company_name}
Tone: {writing_tone}
Target Audience: {target_audience}
Brand CTA: {brand_cta}

=== INSTRUCTIONS ===
Write the Instagram caption for this Reel. Return ONLY valid JSON:
{{
    "headline": "Compelling Reel title for the caption (max 8 words)",
    "instagram_caption": "Full Instagram caption. Start with the best hook. Then expand the insight. Use line breaks and emojis. End with a strong CTA. 150-300 words.",
    "hashtags": ["hashtag1", "hashtag2", "hashtag3", "hashtag4", "hashtag5", "hashtag6", "hashtag7"],
    "cta": "Short standalone call-to-action line"
}}"""


async def generate_reel_script(
    db,
    post,
    brief,
    topic_data: dict,
    brand_context: dict,
    api_key: str,
    provider: str = "groq"
) -> dict:
    """Generate 2 hooks + professional script for a Reel (Step 3.5 - new script stage)."""
    import json as _json
    prompt = REEL_SCRIPT_GENERATION_PROMPT.format(
        research_data=brief.research_data or "",
        key_takeaways=brief.key_takeaways or "",
        title=topic_data.get("title", ""),
        hook=topic_data.get("hook", ""),
        company_name=brand_context.get("company_name", "Elan Exports"),
        writing_tone=brand_context.get("writing_tone", "professional"),
        target_audience=brand_context.get("target_audience", "International buyers"),
    )

    logger.info(f"Generating REEL SCRIPT for: {topic_data.get('title', 'Unknown')}")

    raw = await call_llm(
        provider=provider,
        api_key=api_key,
        system_prompt="You are a world-class Instagram Reel scriptwriter. Always return valid JSON.",
        user_prompt=prompt
    )

    text = raw.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    script_data = _json.loads(text, strict=False)

    # Merge script into image_requirements JSON store
    try:
        reqs = _json.loads(post.image_requirements) if post.image_requirements else {}
        if not isinstance(reqs, dict): reqs = {}
    except Exception:
        reqs = {}

    reqs.update({
        "hook_1": script_data.get("hook_1", {}),
        "hook_2": script_data.get("hook_2", {}),
        "reel_script": script_data.get("reel_script", {}),
        "spoken_script": script_data.get("spoken_script", ""),
        "text_overlays": script_data.get("text_overlays", []),
        "estimated_duration_seconds": script_data.get("estimated_duration_seconds", 45),
    })
    post.image_requirements = _json.dumps(reqs)
    post.status.__class__  # lazy import guard
    from app.models.models import PostStatusEnum as _PSE
    post.status = _PSE.script_review_pending
    await db.commit()

    logger.info(f"Reel script generated for post {post.id}")
    return script_data


async def generate_reel_content_from_script(
    db,
    post,
    brief,
    topic_data: dict,
    brand_context: dict,
    api_key: str,
    provider: str = "groq"
) -> dict:
    """Generate Instagram caption + hashtags using an already-approved reel script (Step 4)."""
    import json as _json

    hook_1 = topic_data.get("hook_1", {}).get("text", "")
    hook_2 = topic_data.get("hook_2", {}).get("text", "")
    spoken_script = topic_data.get("spoken_script", "")

    prompt = REEL_CAPTION_PROMPT.format(
        hook_1=hook_1,
        hook_2=hook_2,
        spoken_script=spoken_script,
        research_data=brief.research_data or "",
        company_name=brand_context.get("company_name", "Elan Exports"),
        writing_tone=brand_context.get("writing_tone", "professional"),
        target_audience=brand_context.get("target_audience", "International buyers"),
        brand_cta=brand_context.get("cta", "Visit elanexports.com"),
    )

    logger.info(f"Generating REEL CAPTION from approved script for post {post.id[:8]}")

    raw = await call_llm(
        provider=provider,
        api_key=api_key,
        system_prompt="You are a world-class Instagram caption writer. Always return valid JSON.",
        user_prompt=prompt
    )

    text = raw.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    content = _json.loads(text, strict=False)

    post.headline = content.get("headline", "")
    post.instagram_caption = content.get("instagram_caption", "")
    post.hashtags = content.get("hashtags", [])
    post.cta = content.get("cta", "")

    # Merge back into image_requirements (keep the script data intact)
    try:
        reqs = _json.loads(post.image_requirements) if post.image_requirements else {}
        if not isinstance(reqs, dict): reqs = {}
    except Exception:
        reqs = {}
    reqs["type"] = "reel"
    reqs["reel_script_used"] = spoken_script
    post.image_requirements = _json.dumps(reqs)

    from app.models.models import PostStatusEnum as _PSE
    post.status = _PSE.content_review_pending
    await db.commit()

    logger.info(f"Reel caption generated for post {post.id}")
    return content
