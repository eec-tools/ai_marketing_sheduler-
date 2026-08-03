import json
import logging
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import GeneratedPost, ContentBrief, PostStatusEnum
from app.services.ai.llm import call_llm

logger = logging.getLogger(__name__)

# --- Reel Script Prompt ---
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
    "hook_1": {{ "text": "First hook option (max 10 words)", "style": "question" }},
    "hook_2": {{ "text": "Second hook option (max 10 words)", "style": "statistic" }},
    "reel_script": {{
        "hook": "The chosen opening line (3-5 seconds)",
        "problem": "State the problem or pain point the audience faces (5-8 seconds)",
        "insight": "The expert insight with specific data from the research (10-15 seconds)",
        "solution": "The practical solution or framework (10-15 seconds)",
        "cta": "Clear, direct call to action (3-5 seconds)"
    }},
    "spoken_script": "The complete, word-for-word script. Max 150 words.",
    "text_overlays": ["Overlay 1", "Overlay 2", "Overlay 3"],
    "estimated_duration_seconds": 45
}}"""

# --- Reel Prompt Generation Prompt ---
REEL_PROMPT_GENERATION_PROMPT = """You are an expert AI video generation prompt engineer.
Your job is to create a detailed video generation prompt for an Instagram Reel based on an approved script.

=== APPROVED REEL SCRIPT ===
Spoken Script: {spoken_script}

=== BRAND CONTEXT ===
Company: {company_name}
Tone: {writing_tone}
Target Audience: {target_audience}

=== INSTRUCTIONS ===
Write a detailed video generation prompt. Return ONLY valid JSON:
{{
    "video_prompt": "Detailed AI video generation prompt describing the visual scene, lighting, action, and style. No text in the video, just the visual description."
}}"""

# --- Reel Caption Prompt ---
REEL_CAPTION_PROMPT = """You are an expert Instagram caption writer for {company_name}.
An approved Reel script and video already exist. Your job is ONLY to write the Instagram caption and hashtags.

=== APPROVED REEL SCRIPT ===
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
    "instagram_caption": "Full Instagram caption. 150-300 words.",
    "hashtags": ["hashtag1", "hashtag2", "hashtag3", "hashtag4", "hashtag5"],
    "cta": "Short standalone call-to-action line"
}}"""

# --- Static Prompt Generation Prompt ---
STATIC_PROMPT_GENERATION_PROMPT = """You are an expert AI image generation prompt engineer.
Your job is to create a detailed image generation prompt for a social media post.

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
Create a detailed image generation prompt. Return ONLY valid JSON:
{{
    "image_requirements": "Detailed AI image generation prompt for a professional branded creative. Include: background style, color palette (brand colors), typography/text to display (if any), and visual concept. Optimized for 1080x1080."
}}"""

# --- Static Caption Prompt ---
STATIC_CAPTION_PROMPT = """You are an expert social media copywriter for {company_name}.
The image for this post has already been generated. Your job is ONLY to write the caption.

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
Create the social media caption. Return ONLY valid JSON:
{{
    "headline": "Compelling headline (max 10 words)",
    {caption_instruction}
    "hashtags": ["hashtag1", "hashtag2", "hashtag3", "hashtag4", "hashtag5"],
    "cta": "Clear, non-spammy call-to-action",
    "seo_keywords": ["keyword1", "keyword2", "keyword3"]
}}"""


async def generate_reel_script(db, post, brief, topic_data: dict, brand_context: dict, api_key: str, provider: str = "groq") -> dict:
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
    raw = await call_llm(provider, api_key, "You are a world-class Instagram Reel scriptwriter. Always return valid JSON.", prompt)
    
    text = raw.strip()
    if "```json" in text: text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text: text = text.split("```")[1].split("```")[0].strip()
    script_data = json.loads(text, strict=False)

    try: reqs = json.loads(post.image_requirements) if post.image_requirements else {}
    except: reqs = {}
    if not isinstance(reqs, dict): reqs = {}
    
    reqs.update({
        "type": "reel",
        "hook_1": script_data.get("hook_1", {}),
        "hook_2": script_data.get("hook_2", {}),
        "reel_script": script_data.get("reel_script", {}),
        "spoken_script": script_data.get("spoken_script", ""),
        "text_overlays": script_data.get("text_overlays", []),
        "estimated_duration_seconds": script_data.get("estimated_duration_seconds", 45),
    })
    post.image_requirements = json.dumps(reqs)
    post.status = PostStatusEnum.script_review_pending
    await db.commit()
    return script_data

async def generate_reel_prompt_from_script(db, post, topic_data: dict, brand_context: dict, api_key: str, provider: str = "groq") -> dict:
    spoken_script = topic_data.get("spoken_script", "")
    prompt = REEL_PROMPT_GENERATION_PROMPT.format(
        spoken_script=spoken_script,
        company_name=brand_context.get("company_name", "Elan Exports"),
        writing_tone=brand_context.get("writing_tone", "professional"),
        target_audience=brand_context.get("target_audience", "International buyers"),
    )
    logger.info(f"Generating REEL PROMPT for post {post.id}")
    raw = await call_llm(provider, api_key, "You are an expert AI video prompt engineer. Always return valid JSON.", prompt)
    
    text = raw.strip()
    if "```json" in text: text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text: text = text.split("```")[1].split("```")[0].strip()
    content = json.loads(text, strict=False)

    try: reqs = json.loads(post.image_requirements) if post.image_requirements else {}
    except: reqs = {}
    
    reqs["generated_prompt"] = content.get("video_prompt", "")
    post.image_requirements = json.dumps(reqs)
    post.status = PostStatusEnum.prompt_review_pending
    await db.commit()
    return content

async def generate_static_prompt(db, post, brief, topic_data: dict, brand_context: dict, api_key: str, provider: str = "groq") -> dict:
    prompt = STATIC_PROMPT_GENERATION_PROMPT.format(
        research_data=brief.research_data or "",
        key_takeaways=brief.key_takeaways or "",
        title=topic_data.get("title", ""),
        hook=topic_data.get("hook", ""),
        company_name=brand_context.get("company_name", "Elan Exports"),
        writing_tone=brand_context.get("writing_tone", "professional"),
        target_audience=brand_context.get("target_audience", "International buyers"),
    )
    logger.info(f"Generating STATIC PROMPT for: {topic_data.get('title', 'Unknown')}")
    raw = await call_llm(provider, api_key, "You are a world-class AI prompt engineer. Always return valid JSON.", prompt)
    
    text = raw.strip()
    if "```json" in text: text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text: text = text.split("```")[1].split("```")[0].strip()
    content = json.loads(text, strict=False)

    try: reqs = json.loads(post.image_requirements) if post.image_requirements else {}
    except: reqs = {}
    reqs["generated_prompt"] = content.get("image_requirements", "")
    reqs["type"] = "static"
    post.image_requirements = json.dumps(reqs)
    post.status = PostStatusEnum.prompt_review_pending
    await db.commit()
    return content

async def generate_reel_caption(db, post, brief, topic_data: dict, brand_context: dict, api_key: str, provider: str = "groq") -> dict:
    prompt = REEL_CAPTION_PROMPT.format(
        spoken_script=topic_data.get("spoken_script", ""),
        research_data=brief.research_data or "",
        company_name=brand_context.get("company_name", "Elan Exports"),
        writing_tone=brand_context.get("writing_tone", "professional"),
        target_audience=brand_context.get("target_audience", "International buyers"),
        brand_cta=brand_context.get("cta", "Visit elanexports.com"),
    )
    logger.info(f"Generating REEL CAPTION for post {post.id}")
    raw = await call_llm(provider, api_key, "You are a world-class Instagram caption writer. Always return valid JSON.", prompt)
    
    text = raw.strip()
    if "```json" in text: text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text: text = text.split("```")[1].split("```")[0].strip()
    content = json.loads(text, strict=False)

    post.headline = content.get("headline", "")
    post.instagram_caption = content.get("instagram_caption", "")
    post.hashtags = content.get("hashtags", [])
    post.cta = content.get("cta", "")
    post.status = PostStatusEnum.content_review_pending
    await db.commit()
    return content

async def generate_static_caption(db, post, brief, topic_data: dict, brand_context: dict, api_key: str, provider: str = "groq") -> dict:
    platform_val = topic_data.get("platform", "linkedin_post")
    format_val = topic_data.get("format", "")
    if format_val == "linkedin" or "linkedin" in platform_val:
        caption_instruction = '"linkedin_caption": "Full LinkedIn post (500-800 words).",\n    "instagram_caption": ""'
    else:
        caption_instruction = '"instagram_caption": "Instagram caption (200-400 words).",\n    "linkedin_caption": ""'

    prompt = STATIC_CAPTION_PROMPT.format(
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
    logger.info(f"Generating STATIC CAPTION for: {topic_data.get('title', 'Unknown')}")
    raw = await call_llm(provider, api_key, "You are a world-class B2B social media copywriter. Always return valid JSON.", prompt)
    
    text = raw.strip()
    if "```json" in text: text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text: text = text.split("```")[1].split("```")[0].strip()
    content = json.loads(text, strict=False)

    post.headline = content.get("headline", "")
    post.linkedin_caption = content.get("linkedin_caption", "")
    post.instagram_caption = content.get("instagram_caption", "")
    post.hashtags = content.get("hashtags", [])
    post.cta = content.get("cta", "")
    post.status = PostStatusEnum.content_review_pending
    await db.commit()
    return content

