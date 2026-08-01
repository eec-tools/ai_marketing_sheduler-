"""
Review Agent — Step 3.1 & 5.1: AI Quality Gate
This is the RECURSIVE AI REVIEWER that sits between every AI generation step
and the human review step. If it fails the content, it sends it back
to the originating agent to be remade automatically.

Handles:
- Research Review (Step 3.1)
- Content Review (Step 5.1)
- Prompt Review (Step 6.2)
- Video Review (Step 6.5)
"""
import json
import logging
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.ai.llm import call_llm

logger = logging.getLogger(__name__)

MAX_RETRIES = 3

# ─── Review Prompts ──────────────────────────────────────────────────────────

RESEARCH_REVIEW_PROMPT = """You are a strict AI Research Quality Auditor for Elan Exports Consultancy.

Review the following research brief and grade it on these criteria:
1. **Accuracy** — Are the statistics plausible and the claims factual?
2. **Source Reliability** — Are the referenced sources legitimate?
3. **Completeness** — Does the research cover all key points?
4. **Business Relevance** — Is this directly useful for content creation?
5. **Brand Alignment** — Does this match the brand voice and target audience?

=== RESEARCH BRIEF ===
{research_data}

=== STATISTICS ===
{statistics}

=== REFERENCES ===
{references}

Return ONLY valid JSON:
{{
    "verdict": "PASS" or "FAIL",
    "score": 0-100,
    "feedback": "Detailed feedback explaining the verdict",
    "issues": ["Issue 1", "Issue 2"],
    "suggestions": ["Improvement suggestion 1", "..."]
}}"""

CONTENT_REVIEW_PROMPT = """You are a strict AI Content Quality Auditor for Elan Exports Consultancy.

Review the following social media content and grade it on these criteria:
1. **Brand Consistency** — Does it match the company voice?
2. **Grammar & Clarity** — Is the writing clean and professional?
3. **Hook Strength** — Does the opening line grab attention?
4. **Storytelling** — Does it follow a logical narrative?
5. **Engagement Potential** — Will this drive comments, shares, saves?
6. **CTA Effectiveness** — Is the call-to-action clear and non-spammy?
7. **Platform Optimization** — Is the format right for {platform}?
8. **Accuracy** — Are all claims backed by the research brief?

=== CONTENT ===
Headline: {headline}
LinkedIn Caption: {linkedin_caption}
Instagram Caption: {instagram_caption}
Hashtags: {hashtags}
CTA: {cta}

=== ORIGINAL RESEARCH BRIEF ===
{research_data}

Return ONLY valid JSON:
{{
    "verdict": "PASS" or "FAIL",
    "score": 0-100,
    "feedback": "Detailed feedback",
    "issues": ["Issue 1", "Issue 2"],
    "suggestions": ["Improvement 1", "..."]
}}"""

PROMPT_REVIEW_PROMPT = """You are a strict AI Video Prompt Auditor.

Review the following scene-by-scene cinematic prompts and grade them on:
1. **Prompt Clarity** — Is each scene description unambiguous?
2. **Visual Consistency** — Will the scenes look coherent together?
3. **Character Consistency** — Are characters described consistently?
4. **Camera Directions** — Are camera angles and movements specified?
5. **Brand Accuracy** — Do the visuals match the brand identity?
6. **AI Generation Compatibility** — Will these prompts produce good results with Flow AI?

=== SCENE PROMPTS ===
{scenes}

Return ONLY valid JSON:
{{
    "verdict": "PASS" or "FAIL",
    "score": 0-100,
    "feedback": "Detailed feedback",
    "issues": ["Issue 1", "..."],
    "suggestions": ["Improvement 1", "..."]
}}"""


# ─── Core Review Function ────────────────────────────────────────────────────

async def _call_llm_review(prompt: str, api_key: str, provider: str = "groq") -> dict:
    """Internal: calls LLM with a review prompt and returns parsed JSON."""
    raw = await call_llm(
        provider=provider,
        api_key=api_key,
        system_prompt="You are a strict quality auditor. Always return valid JSON.",
        user_prompt=prompt,
        temperature=0.3
    )

    text = raw.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    return json.loads(text, strict=False)


# ─── Public Review Functions ─────────────────────────────────────────────────

async def review_research(
    research_data: str,
    statistics: list,
    references: list,
    api_key: str,
    provider: str = "groq"
) -> dict:
    """
    Step 3.1 — AI Research Review Agent.
    Returns {"verdict": "PASS"|"FAIL", "score": int, "feedback": str, ...}
    """
    prompt = RESEARCH_REVIEW_PROMPT.format(
        research_data=research_data,
        statistics=json.dumps(statistics, indent=2),
        references=json.dumps(references, indent=2),
    )
    result = await _call_llm_review(prompt, api_key, provider)
    logger.info(f"Research review: {result.get('verdict')} (score: {result.get('score')})")
    return result


async def review_content(
    headline: str,
    linkedin_caption: str,
    instagram_caption: str,
    hashtags: list,
    cta: str,
    platform: str,
    research_data: str,
    api_key: str,
    provider: str = "groq"
) -> dict:
    """
    Step 5.1 — AI Content Review Agent.
    Returns {"verdict": "PASS"|"FAIL", "score": int, "feedback": str, ...}
    """
    prompt = CONTENT_REVIEW_PROMPT.format(
        headline=headline,
        linkedin_caption=linkedin_caption,
        instagram_caption=instagram_caption,
        hashtags=json.dumps(hashtags),
        cta=cta,
        platform=platform,
        research_data=research_data,
    )
    result = await _call_llm_review(prompt, api_key, provider)
    logger.info(f"Content review: {result.get('verdict')} (score: {result.get('score')})")
    return result


async def review_video_prompts(
    scenes: list,
    api_key: str,
    provider: str = "groq"
) -> dict:
    """
    Step 6.2 — AI Prompt Review Agent.
    Returns {"verdict": "PASS"|"FAIL", "score": int, "feedback": str, ...}
    """
    prompt = PROMPT_REVIEW_PROMPT.format(
        scenes=json.dumps(scenes, indent=2),
    )
    result = await _call_llm_review(prompt, api_key, provider)
    logger.info(f"Prompt review: {result.get('verdict')} (score: {result.get('score')})")
    return result
