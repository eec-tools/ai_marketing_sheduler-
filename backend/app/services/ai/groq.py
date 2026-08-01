import httpx
from app.services.ai.base import AIProvider
from app.services.ai.prompts import SOCIAL_MEDIA_STRATEGIST_PROMPT


class GroqService(AIProvider):
    """Groq LLM service for text generation."""

    BASE_URL = "https://api.groq.com/openai/v1"
    DEFAULT_MODEL = "llama-3.3-70b-versatile"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def generate_text(self, prompt: str, json_mode: bool = False) -> str:
        payload = {
            "model": self.DEFAULT_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": SOCIAL_MEDIA_STRATEGIST_PROMPT
                },
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 2048,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

    async def generate_image(self, prompt: str, size: str = "square") -> bytes:
        raise NotImplementedError("Groq does not support image generation. Use Gemini.")


    async def generate_post_content(self, topic: str, brand_context: dict) -> dict:
        """Generate complete post content using Lyra 4-D Methodology & Personal Brand Scannable Template."""
        from app.services.ai.prompts import PERSONAL_BRAND_SCANNABLE_TEMPLATE
        custom_caption_template = brand_context.get('caption_template', '').strip()
        custom_image_instructions = brand_context.get('image_instructions', '').strip()

        has_logo = bool(brand_context.get('logo_url'))
        prompt = f"""Apply Lyra's 4-D Methodology (Deconstruct, Diagnose, Develop, Deliver) to create precision social media content for this topic: "{topic}"

Brand Context:
- Company: {brand_context.get('company_name', 'Unknown')}
- Industry: {brand_context.get('industry', 'General')}
- Target Audience: {brand_context.get('target_audience', 'General public')}
- Writing Tone: {brand_context.get('writing_tone', 'professional')}
- Language: {brand_context.get('preferred_language', 'English')}
- Primary Color: {brand_context.get('primary_color', '#2563EB')}
- Secondary Color: {brand_context.get('secondary_color', '#64748B')}
- Image Style: {brand_context.get('image_style', 'professional')}
- CTA: {brand_context.get('cta', '')}
- Keywords: {', '.join(brand_context.get('keywords', []))}
- Avoid Words: {', '.join(brand_context.get('avoid_words', []))}
- Hashtags: {', '.join(brand_context.get('hashtags', []))}

{f"""=== COMPANY INTELLIGENCE (use this to write specific, authentic content) ===
- What the company does: {brand_context.get('company_description', '')}
- Key products/services: {brand_context.get('products_services', '')}
- Unique value proposition: {brand_context.get('unique_value_proposition', '')}
- Customer pain points solved: {brand_context.get('customer_pain_points', '')}
- vs. competitors: {brand_context.get('competitors_differentiators', '')}
IMPORTANT: Reference specific products, real pain points, and concrete differentiators in the content. Avoid vague, generic statements. Write as if you work at this company.
=========================================================================""" if any([brand_context.get(k) for k in ['company_description','products_services','unique_value_proposition','customer_pain_points','competitors_differentiators']]) else ""}

{PERSONAL_BRAND_SCANNABLE_TEMPLATE}

{f"=== STRICT USER CUSTOM CAPTION TEMPLATE / RULES ===\\nThe user has specified these exact company style instructions for captions. You MUST follow these above all else:\\n{custom_caption_template}\\n====================================================" if custom_caption_template else ""}

{f"=== STRICT USER CUSTOM IMAGE CREATION INSTRUCTIONS ===\\nThe user has specified these exact company style instructions for images/cards. You MUST embed these into image_requirements:\\n{custom_image_instructions}\\n====================================================" if custom_image_instructions else ""}

CRITICAL INSTRUCTION ON CTAs: DO NOT add generic spam CTAs such as "DM me SCHEDULER", "DM me AUDIT", or "schedule a consultation" unless the user's custom template or brand CTA explicitly asks for it. If a CTA is needed, use ONLY the exact brand CTA provided above or the company name/website.

Return ONLY valid JSON in this exact format:
{{
    "headline": "Compelling headline (max 10 words)",
    "linkedin_caption": "Full LinkedIn post following the 5-part Personal Brand Scannable Template (or the custom caption template above). Do NOT add generic DM/consultation spam.",
    "instagram_caption": "Instagram caption formatted cleanly following the template and constraints.",
    "hashtags": ["hashtag1", "hashtag2", "hashtag3", "hashtag4", "hashtag5"],
    "cta": "Clear call-to-action sentence using actual brand CTA without generic spam",
    "image_requirements": "Craft a highly detailed, cinematic, premium social media image prompt. This prompt will be used as a DALL-E/AI image prompt.\\n\\nCOMPOSITION REQUIREMENTS (follow ALL of these):\\n1. HEADLINE TEXT: Display a short, bold, impactful headline (3-6 words max) in the center or upper third of the card using large, high-contrast white or brand-color typography. Use heavy/black font weight.\\n2. BACKGROUND: Use a sophisticated, editorial background — either high-quality stock photography (cinematic, professional lighting), or a premium abstract graphic design using the brand's primary color.\\n3. OVERLAY: Apply a semi-transparent dark gradient overlay so text is fully readable.\\n4. NO UI ELEMENTS: DO NOT generate or draw any UI elements, 'Learn More' buttons, or call-to-action strips in the image itself. The CTA will be handled in the post caption.\\n5. BRAND PALETTE: Use the brand's primary and secondary colors throughout.\\n6. TYPOGRAPHY HIERARCHY: Establish two tiers — (a) bold 80px+ headline, (b) 32px subtext/tagline below the headline.\\n7. VISUAL QUALITY BAR: STRICTLY FORBIDDEN elements — NO generic floating globes, NO blurry 3D network diagrams, NO cliché neon grids, NO overused handshake stock photos, NO corporate clipart.\\n8. CONTENT ALIGNMENT: Every visual element must be semantically relevant to the post topic.\\n9. FINAL RESOLUTION: Optimized for 1080x1080 square (Instagram), with safe zones maintained."
}}"""

        import json
        text = await self.generate_text(prompt, json_mode=True)
        text = text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        return json.loads(text, strict=False)

    async def generate_topics(self, brand_context: dict, count: int = 5, category: str = None) -> list:
        """Generate topic ideas based on brand context."""
        import json
        prompt = f"""Generate {count} unique, engaging social media post topics for:
Company: {brand_context.get('company_name', '')}
Industry: {brand_context.get('industry', 'General')}
Audience: {brand_context.get('target_audience', 'General')}
Category: {category or 'general'}

Return ONLY a JSON array of strings. No explanation, just the array.
["Topic 1", "Topic 2", ...]"""

        text = await self.generate_text(prompt)
        text = text.strip()
        if "```" in text:
            text = text.split("```")[1].replace("json", "").strip()
        return json.loads(text, strict=False)
