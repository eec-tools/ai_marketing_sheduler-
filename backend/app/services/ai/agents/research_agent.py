"""
Research Agent — Step 2: Topic Research & Content Brief
Uses Groq to deeply research each topic idea and produce a
research-backed content brief with statistics, references, and key insights.
"""
import json
import logging
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import GeneratedPost, ContentBrief, PostStatusEnum
from app.services.ai.llm import call_llm

logger = logging.getLogger(__name__)

RESEARCH_SYSTEM_PROMPT = """You are an expert research analyst specializing in the global export-import 
industry, international trade regulations, buyer-seller dynamics, logistics, and compliance.

Your job is to take a content topic and produce a DEEP, AUTHORITATIVE research brief that includes:
- Real statistics and data points (use your training data for plausible industry figures)
- Market trends and insights
- Key regulatory or compliance angles
- Case study references or industry examples
- Actionable takeaways

Your research must be SPECIFIC to the export/import/trade industry. No generic filler."""

RESEARCH_USER_PROMPT = """Research the following topic thoroughly and produce a detailed content brief.

=== TOPIC ===
Title: {title}
Platform: {platform}
Category: {category}
Hook: {hook}
Key Points to Cover: {key_points}

=== BRAND CONTEXT ===
Company: {company_name}
Industry: {industry}
Target Audience: {target_audience}

=== INSTRUCTIONS ===
Produce a comprehensive research brief. Return ONLY valid JSON:
{{
    "key_insights": "3-5 paragraphs of deep insights about this topic",
    "statistics": [
        {{"stat": "85% of export delays...", "source": "World Trade Organization, 2024"}},
        {{"stat": "...", "source": "..."}}
    ],
    "references": [
        {{"title": "Report/Article title", "source": "Organization/Publication", "relevance": "Why this matters"}},
        ...
    ],
    "market_trends": "Current market trends relevant to this topic",
    "key_takeaways": "5 bullet-point takeaways for the content creator",
    "suggested_messaging": "How to position this topic for maximum engagement on {platform}"
}}"""


async def research_topic(
    db: AsyncSession,
    post: GeneratedPost,
    topic_data: dict,
    brand_context: dict,
    api_key: str,
    provider: str = "groq"
) -> ContentBrief:
    """
    Takes a GeneratedPost and its topic data, performs deep research,
    and creates a ContentBrief in the database.
    """
    prompt = RESEARCH_USER_PROMPT.format(
        title=topic_data.get("title", ""),
        platform=topic_data.get("platform", ""),
        category=topic_data.get("category", ""),
        hook=topic_data.get("hook", ""),
        key_points=json.dumps(topic_data.get("key_points", [])),
        company_name=brand_context.get("company_name", "Elan Exports Consultancy"),
        industry=brand_context.get("industry", "Export-Import"),
        target_audience=brand_context.get("target_audience", "International buyers"),
    )

    logger.info(f"Researching topic: {topic_data.get('title', 'Unknown')}")

    raw = await call_llm(
        provider=provider,
        api_key=api_key,
        system_prompt=RESEARCH_SYSTEM_PROMPT,
        user_prompt=prompt,
        temperature=0.6
    )

    text = raw.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    parsed = json.loads(text, strict=False)

    def safe_str(val):
        if isinstance(val, list):
            return "\n- " + "\n- ".join([str(v) for v in val]) if val else ""
        if isinstance(val, dict):
            return json.dumps(val)
        return str(val) if val else ""

    # Upsert ContentBrief — update existing if one already exists (handles retries)
    from sqlalchemy import select as sa_select
    existing_result = await db.execute(sa_select(ContentBrief).where(ContentBrief.post_id == post.id))
    brief = existing_result.scalar_one_or_none()

    if brief:
        brief.research_data = safe_str(parsed.get("key_insights", ""))
        brief.statistics = parsed.get("statistics", [])
        brief.references = parsed.get("references", [])
        brief.market_trends = safe_str(parsed.get("market_trends", ""))
        brief.key_takeaways = safe_str(parsed.get("key_takeaways", ""))
    else:
        brief = ContentBrief(
            post_id=post.id,
            research_data=safe_str(parsed.get("key_insights", "")),
            statistics=parsed.get("statistics", []),
            references=parsed.get("references", []),
            market_trends=safe_str(parsed.get("market_trends", "")),
            key_takeaways=safe_str(parsed.get("key_takeaways", "")),
        )
        db.add(brief)

    # Update post status (but don't commit yet, pipeline.py will commit after review)
    post.status = PostStatusEnum.research_pending
    await db.flush()

    logger.info(f"Research brief created for post {post.id}")
    return brief
