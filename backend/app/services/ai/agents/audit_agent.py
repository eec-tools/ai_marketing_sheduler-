import os
import json
import logging
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import BrandProfile, MonthlyStrategy
from app.core.config import settings

logger = logging.getLogger(__name__)

AUDIT_SYSTEM_PROMPT = """You are an expert social media data analyst.
Analyze the provided raw campaign metrics and brand context to produce strategic insights.
Return ONLY a valid JSON object with EXACTLY these keys:
- competitor_insights: A string summarizing competitor landscape or general performance insights based on the data.
- top_performing_formats: An array of strings (e.g. ["Reels", "Carousels"]) indicating what works best.
- industry_trends: A string summarizing current content trends for this industry.
- content_gaps: A string identifying missing topics or formats the brand should try next.
No markdown block ticks. Just raw JSON.
"""

async def run_brand_audit(db: AsyncSession, brand_profile: BrandProfile, month: str, groq_api_key: str) -> MonthlyStrategy:
    """
    Step 1.1: Windsor AI Audit + Groq Analysis
    """
    windsor_key = settings.WINDSOR_API_KEY
    campaign_data = []

    if windsor_key and windsor_key != "your-windsor-api-key":
        logger.info(f"Running Windsor AI Audit for {brand_profile.company_name} using real API...")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    "https://connectors.windsor.ai/all",
                    params={
                        "api_key": windsor_key,
                        "date_preset": "last_30d",
                        "fields": "source,account_name,campaign,clicks,impressions,spend,likes,comments,reach"
                    }
                )
                if response.status_code == 200:
                    campaign_data = response.json().get("data", [])
                    logger.info(f"Successfully fetched {len(campaign_data)} rows of data from Windsor.")
                else:
                    logger.warning(f"Windsor AI returned status {response.status_code}")
        except Exception as e:
            logger.error(f"Windsor AI API failed: {e}. Proceeding without Windsor data.")
    else:
        logger.info("No valid WINDSOR_API_KEY found. Generating insights based on brand profile only.")

    # Call Groq to generate insights
    prompt = f"""
    Brand Name: {brand_profile.company_name}
    Industry: {brand_profile.industry}
    Target Audience: {brand_profile.target_audience}
    Recent Campaign Data (JSON):
    {json.dumps(campaign_data[:10]) if campaign_data else 'No campaign data available. Provide general industry insights based on the brand profile.'}
    """

    payload = {
        "model": "openai/gpt-oss-120b",
        "messages": [
            {"role": "system", "content": AUDIT_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.5,
        "max_tokens": 1000,
        "response_format": {"type": "json_object"}
    }

    logger.info(f"Generating AI Audit insights via Groq...")
    async with httpx.AsyncClient(timeout=90.0) as client:
        resp = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {groq_api_key}",
                "Content-Type": "application/json"
            },
            json=payload
        )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"]
    
    text = raw.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    try:
        parsed = json.loads(text, strict=False)
    except json.JSONDecodeError:
        logger.error(f"Failed to parse Groq response as JSON: {text}")
        parsed = {
            "competitor_insights": "Could not parse insights from AI.",
            "top_performing_formats": ["Reels"],
            "industry_trends": "General trends apply.",
            "content_gaps": "Review data manually."
        }

    audit_data = {
        "raw_campaign_metrics_last_30d": campaign_data,
        "competitor_insights": parsed.get("competitor_insights", "No insights available."),
        "top_performing_formats": parsed.get("top_performing_formats", ["Reels", "Carousels"]),
        "industry_trends": parsed.get("industry_trends", "No trends available."),
        "content_gaps": parsed.get("content_gaps", "No gaps identified.")
    }

    # Create the MonthlyStrategy record in the database
    strategy = MonthlyStrategy(
        user_id=brand_profile.user_id,
        month=month,
        audit_data=audit_data,
        status="audit_completed"
    )
    db.add(strategy)
    await db.commit()
    await db.refresh(strategy)
    
    return strategy
