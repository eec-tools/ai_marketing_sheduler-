"""
Strategy Agent — Step 1.2: Monthly Content Strategy Generation
Uses Groq (LLaMA 3 70B) to generate a 1-month content calendar
based on the Windsor AI audit data and brand profile.
"""
import json
import logging
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import MonthlyStrategy, BrandProfile
from app.services.ai.llm import call_llm

logger = logging.getLogger(__name__)

STRATEGY_SYSTEM_PROMPT = """You are a world-class social media strategist for Elan Exports Consultancy, 
a global export-import consultancy. You create hyper-specific, research-driven monthly content calendars 
that drive engagement, build thought leadership, and generate inbound leads.

You understand export regulations, global trade, buyer-seller dynamics, compliance, logistics, 
and B2B marketing for the export industry."""

STRATEGY_USER_PROMPT = """Based on the following brand audit and brand profile, create a comprehensive 
1-MONTH content calendar focused ENTIRELY on {target_format}.

=== CRITICAL FORMAT RESTRICTIONS ===
You must strictly adhere to the {target_format}:
- If "instagram_posts": Generate ONLY static posts and carousels. NO video, NO reel concepts.
- If "instagram_reels": Generate ONLY short-form video concepts. NO static post ideas.
- If "linkedin": Generate ONLY text or image posts tailored for LinkedIn professionals.

=== BRAND AUDIT DATA ===
{audit_data}

=== BRAND PROFILE ===
Company: {company_name}
Industry: {industry}
Target Audience: {target_audience}
Writing Tone: {writing_tone}
Company Description: {company_description}
Products/Services: {products_services}
Unique Value Proposition: {unique_value_proposition}

=== INSTRUCTIONS ===
Generate exactly 30 content ideas for the month. For EACH idea, specify:
- day: Day number (1-30)
- title: A specific, compelling topic title
- hook: The opening hook line
- key_points: 3-4 bullet points of what this content should cover

All 30 ideas MUST be for {target_format}.

Return ONLY a valid JSON object with a single key 'calendar' containing an array of 30 ideas. No markdown, no explanation.
{{
  "calendar": [
    {{
      "day": 1,
      "title": "...",
      "hook": "...",
      "key_points": ["...", "..."]
    }},
    ...
  ]
}}"""


async def generate_monthly_strategy(
    db: AsyncSession,
    strategy: MonthlyStrategy,
    brand_profile: BrandProfile,
    api_key: str,
    target_format: str,
    provider: str = "groq"
) -> MonthlyStrategy:
    """
    Step 1.2: Generate the content calendar (30 ideas) for the target format using Groq.
    """
    audit_data = json.dumps(strategy.audit_data, indent=2) if strategy.audit_data else "{}"

    prompt = STRATEGY_USER_PROMPT.format(
        target_format=target_format,
        audit_data=audit_data,
        company_name=brand_profile.company_name or "Elan Exports Consultancy",
        industry=brand_profile.industry or "Export-Import Consultancy",
        target_audience=brand_profile.target_audience or "International buyers, exporters, trade businesses",
        writing_tone=brand_profile.writing_tone or "professional",
        company_description=brand_profile.company_description or "",
        products_services=brand_profile.products_services or "",
        unique_value_proposition=brand_profile.unique_value_proposition or "",
    )

    logger.info(f"Generating monthly strategy for {brand_profile.company_name}...")

    raw = await call_llm(
        provider=provider,
        api_key=api_key,
        system_prompt=STRATEGY_SYSTEM_PROMPT,
        user_prompt=prompt
    )

    # Parse the JSON response
    text = raw.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    parsed = json.loads(text, strict=False)

    # Handle both {"calendar": [...]} and bare [...] formats
    if isinstance(parsed, dict) and "calendar" in parsed:
        calendar_items = parsed["calendar"]
    elif isinstance(parsed, list):
        calendar_items = parsed
    else:
        calendar_items = list(parsed.values())[0] if parsed else []

    strategy.calendar = calendar_items
    strategy.strategy_content = raw
    strategy.status = "strategy_generated"
    await db.commit()
    await db.refresh(strategy)

    logger.info(f"Generated {len(calendar_items)} content ideas for {strategy.month}")
    return strategy
