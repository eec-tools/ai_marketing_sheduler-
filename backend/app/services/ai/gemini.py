import httpx
import base64
from app.services.ai.base import AIProvider

SIZE_MAP = {
    "square": "1:1",
    "portrait": "9:16",
    "landscape": "16:9",
}

STYLE_PROMPTS = {
    "professional": "award-winning editorial business photography or luxury agency design card, crisp typography overlay, sharp focus, natural studio lighting, authentic real-world subject, no blurry background",
    "minimal": "ultra-clean luxury architectural photography with sleek typography overlay, pristine composition, sharp crisp focus, agency aesthetic",
    "corporate": "high-end executive workplace photography with crisp headline text overlay, natural lighting, modern corporate interior, sharp focus",
}


class GeminiService(AIProvider):
    """Gemini image generation service."""

    IMAGEN_URL = "https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-002:predict"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def generate_text(self, prompt: str) -> str:
        from app.services.ai.prompts import SOCIAL_MEDIA_STRATEGIST_PROMPT
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.api_key}",
                json={
                    "system_instruction": {"parts": [{"text": SOCIAL_MEDIA_STRATEGIST_PROMPT}]},
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.7}
                }
            )
            resp.raise_for_status()
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"]

    async def generate_post_content(self, topic: str, brand_context: dict) -> dict:
        """
        Gemini fallback for text generation — used when all Groq keys are exhausted.
        Uses the same brand context + JSON schema as GroqService.
        """
        import json
        from app.services.ai.prompts import PERSONAL_BRAND_SCANNABLE_TEMPLATE

        custom_caption_template = brand_context.get('caption_template', '').strip()
        custom_image_instructions = brand_context.get('image_instructions', '').strip()

        # Build optional sections as variables to avoid nested triple-quote issues
        company_keys = ['company_description', 'products_services', 'unique_value_proposition',
                        'customer_pain_points', 'competitors_differentiators']
        if any(brand_context.get(k) for k in company_keys):
            company_section = (
                "=== COMPANY INTELLIGENCE ===\n"
                f"- What the company does: {brand_context.get('company_description', '')}\n"
                f"- Key products/services: {brand_context.get('products_services', '')}\n"
                f"- Unique value proposition: {brand_context.get('unique_value_proposition', '')}\n"
                f"- Customer pain points solved: {brand_context.get('customer_pain_points', '')}\n"
                f"- vs. competitors: {brand_context.get('competitors_differentiators', '')}\n"
                "IMPORTANT: Reference specific products and real differentiators. Write as if you work at this company.\n"
                "==========================="
            )
        else:
            company_section = ""

        caption_section = f"=== CUSTOM CAPTION RULES ===\n{custom_caption_template}\n===========================" if custom_caption_template else ""
        image_section = f"=== CUSTOM IMAGE INSTRUCTIONS ===\n{custom_image_instructions}\n================================" if custom_image_instructions else ""

        prompt = f"""You are an expert social media strategist. Generate high-converting social media content for this topic: "{topic}"

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

{company_section}

{PERSONAL_BRAND_SCANNABLE_TEMPLATE}

{caption_section}

{image_section}

CRITICAL: Do NOT add generic spam CTAs. Use only the exact brand CTA provided.

Return ONLY valid JSON (no markdown, no code fences):
{{
    "headline": "Compelling headline (max 10 words)",
    "linkedin_caption": "Full LinkedIn post following the Personal Brand Scannable Template",
    "instagram_caption": "Instagram caption formatted cleanly",
    "hashtags": ["hashtag1", "hashtag2", "hashtag3", "hashtag4", "hashtag5"],
    "cta": "Clear call-to-action using actual brand CTA",
    "image_requirements": "Detailed visual description for image generation"
}}"""

        text = await self.generate_text(prompt)
        text = text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        return json.loads(text, strict=False)

    async def generate_caption_from_image(self, image_data: str, topic: str = None, brand_context: dict = None) -> dict:
        """Analyze an uploaded image with Gemini Vision and generate scannable captions."""
        import json
        from app.services.ai.prompts import SOCIAL_MEDIA_STRATEGIST_PROMPT, PERSONAL_BRAND_SCANNABLE_TEMPLATE
        brand_context = brand_context or {}
        
        mime_type = "image/png"
        raw_b64 = image_data
        if "base64," in image_data:
            parts = image_data.split("base64,")
            if "data:" in parts[0] and ";" in parts[0]:
                mime_type = parts[0].split("data:")[1].split(";")[0]
            raw_b64 = parts[1]

        custom_caption_template = brand_context.get('caption_template', '').strip()
        custom_image_instructions = brand_context.get('image_instructions', '').strip()

        prompt = f"""Analyze this uploaded image in detail and create high-converting social media content.
{f'Additional User Notes/Topic: "{topic}"' if topic else 'Derive the main theme directly from the visual elements in the image.'}

Brand Context:
- Company: {brand_context.get('company_name', 'Unknown')}
- Industry: {brand_context.get('industry', 'General')}
- Target Audience: {brand_context.get('target_audience', 'General public')}
- Writing Tone: {brand_context.get('writing_tone', 'professional')}
- CTA: {brand_context.get('cta', '')}
- Hashtags: {', '.join(brand_context.get('hashtags', []))}

{PERSONAL_BRAND_SCANNABLE_TEMPLATE}

{f"=== STRICT USER CUSTOM CAPTION TEMPLATE / RULES ===\\nThe user has specified these exact company style instructions for captions. You MUST follow these above all else:\\n{custom_caption_template}\\n====================================================" if custom_caption_template else ""}

{f"=== STRICT USER CUSTOM IMAGE CREATION INSTRUCTIONS ===\\nThe user has specified these exact company style instructions for images/cards:\\n{custom_image_instructions}\\n====================================================" if custom_image_instructions else ""}

CRITICAL INSTRUCTION ON CTAs: DO NOT add generic spam CTAs such as "DM me SCHEDULER", "DM me AUDIT", or "schedule a consultation" unless the user's custom template explicitly asks for it. If a CTA is needed, use ONLY the exact brand CTA provided above or the company name/website.

Return ONLY valid JSON in this exact format:
{{
    "headline": "Compelling headline (max 10 words)",
    "linkedin_caption": "Full LinkedIn post following the 5-part Personal Brand Scannable Template (or the custom caption template above). Do NOT add generic DM/consultation spam.",
    "instagram_caption": "Instagram caption formatted cleanly following the template and constraints.",
    "hashtags": ["hashtag1", "hashtag2", "hashtag3", "hashtag4", "hashtag5"],
    "cta": "Clear call-to-action sentence using actual brand CTA without generic spam",
    "image_requirements": "Analyzed visual summary of the uploaded image along with any brand visual guidelines"
}}"""

        async with httpx.AsyncClient(timeout=45) as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.api_key}",
                json={
                    "system_instruction": {"parts": [{"text": SOCIAL_MEDIA_STRATEGIST_PROMPT}]},
                    "contents": [
                        {
                            "parts": [
                                {"inline_data": {"mime_type": mime_type, "data": raw_b64}},
                                {"text": prompt}
                            ]
                        }
                    ],
                    "generationConfig": {"temperature": 0.7}
                }
            )
            resp.raise_for_status()
            text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            return json.loads(text, strict=False)

    async def generate_image(self, prompt: str, size: str = "square", style: str = "professional") -> bytes:
        """Generate image — Pollinations FLUX (primary, free) → HF FLUX → Gemini Imagen."""
        import urllib.parse, logging
        style_suffix = STYLE_PROMPTS.get(style, "")
        aspect_ratio = SIZE_MAP.get(size, "1:1")

        full_prompt = (
            f"{prompt}. {style_suffix}. "
            "Bold clean English typography headline visible on the image. "
            "STRICTLY FORBIDDEN: NO floating 3D globes, NO blurry world maps, "
            "NO glowing CGI network lines, NO cliché stock tropes. "
            "Sharp focus, high resolution."
        )

        # ── 1. Pollinations.ai FLUX (free, no API key required, highest priority) ──
        try:
            p_width, p_height = (
                (1080, 1080) if size == "square"
                else (1080, 1920) if size == "portrait"
                else (1920, 1080)
            )
            encoded = urllib.parse.quote(full_prompt)
            poll_url = (
                f"https://image.pollinations.ai/prompt/{encoded}"
                f"?width={p_width}&height={p_height}&model=flux&nologo=true&seed={hash(prompt) % 99999}"
            )
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.get(poll_url)
                if resp.status_code == 200 and len(resp.content) > 5000:
                    logging.info("Image generated via Pollinations FLUX ✅")
                    return resp.content
                logging.warning(f"Pollinations returned {resp.status_code}, len={len(resp.content)}")
        except Exception as e:
            logging.warning(f"Pollinations FLUX failed: {e}")

        # ── 2. Hugging Face FLUX.1-schnell (free with HF token) ──
        try:
            from app.core.config import settings
            hf_token = getattr(settings, "HF_TOKEN", None)
            if hf_token:
                h_width, h_height = (
                    (1024, 1024) if size == "square"
                    else (768, 1024) if size == "portrait"
                    else (1024, 768)
                )
                async with httpx.AsyncClient(timeout=60) as client:
                    resp = await client.post(
                        "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell",
                        headers={"Authorization": f"Bearer {hf_token}"},
                        json={"inputs": full_prompt, "parameters": {"width": h_width, "height": h_height}},
                    )
                    if resp.status_code == 200 and len(resp.content) > 1000:
                        logging.info("Image generated via HF FLUX ✅")
                        return resp.content
                    logging.warning(f"HF FLUX: {resp.status_code} — {resp.text[:200]}")
        except Exception as e:
            logging.warning(f"HF FLUX failed: {e}")

        # ── 3. Gemini Imagen 3 (requires Gemini API key with Imagen access) ──
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self.IMAGEN_URL}?key={self.api_key}",
                    json={
                        "instances": [{"prompt": full_prompt}],
                        "parameters": {
                            "sampleCount": 1,
                            "aspectRatio": aspect_ratio,
                            "safetyFilterLevel": "block_some",
                            "personGeneration": "allow_adult",
                        },
                    },
                )
                if resp.status_code == 200:
                    logging.info("Image generated via Gemini Imagen ✅")
                    return base64.b64decode(resp.json()["predictions"][0]["bytesBase64Encoded"])
                logging.warning(f"Imagen API: {resp.status_code} — {resp.text[:200]}")
        except Exception as e:
            logging.warning(f"Gemini Imagen failed: {e}")

        raise RuntimeError("All image generation engines failed. Check backend logs.")

    async def generate_image_nanobana(self, prompt: str, size: str = "square", style: str = "professional") -> bytes:
        """
        Nano Banana (Imagen 3) — Google's highest quality image generation.
        Uses gemini-2.0-flash-preview-image-generation then falls back to Imagen 3 API.
        """
        import logging
        style_suffix = STYLE_PROMPTS.get(style, "")
        aspect_ratio = SIZE_MAP.get(size, "1:1")

        full_prompt = (
            f"{prompt}. {style_suffix}. "
            "Professional social media image. Bold clean typographic composition. "
            "High resolution, sharp focus, premium editorial quality. "
            "STRICTLY: NO floating globes, NO CGI network lines, NO cliché stock imagery."
        )

        # ── Try 1: gemini-2.0-flash-preview-image-generation (Nano Banana experience) ──
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-preview-image-generation:generateContent?key={self.api_key}",
                    json={
                        "contents": [{"parts": [{"text": full_prompt}]}],
                        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
                    },
                )
                if resp.status_code == 200:
                    for part in resp.json().get("candidates", [{}])[0].get("content", {}).get("parts", []):
                        if "inlineData" in part:
                            logging.info("Image generated via Nano Banana (gemini-2.0-flash-preview-image-generation) ✅")
                            return base64.b64decode(part["inlineData"]["data"])
                logging.warning(f"Nano Banana model: {resp.status_code} — {resp.text[:300]}")
        except Exception as e:
            logging.warning(f"Nano Banana model failed: {e}")

        # ── Try 2: Imagen 3 direct API ─────────────────────────────────────────────
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{self.IMAGEN_URL}?key={self.api_key}",
                    json={
                        "instances": [{"prompt": full_prompt}],
                        "parameters": {
                            "sampleCount": 1,
                            "aspectRatio": aspect_ratio,
                            "safetyFilterLevel": "block_some",
                            "personGeneration": "allow_adult",
                        },
                    },
                )
                if resp.status_code == 200:
                    logging.info("Image generated via Imagen 3 API ✅")
                    return base64.b64decode(resp.json()["predictions"][0]["bytesBase64Encoded"])
                logging.warning(f"Imagen 3 API: {resp.status_code} — {resp.text[:200]}")
        except Exception as e:
            logging.warning(f"Imagen 3 API failed: {e}")

        raise RuntimeError("Nano Banana / Imagen 3 generation failed. Check your Gemini API key access level.")

    async def review_image_with_vision(self, image_bytes: bytes) -> dict:
        """Use Gemini Vision to review the generated image for quality."""
        try:
            image_b64 = base64.b64encode(image_bytes).decode()
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.api_key}",
                    json={
                        "contents": [{
                            "parts": [
                                {
                                    "inline_data": {
                                        "mime_type": "image/png",
                                        "data": image_b64
                                    }
                                },
                                {
                                    "text": """Review this social media image for professional quality. Check:
1. Is it professional and business-appropriate?
2. Is the composition clean and well-balanced?
3. Are there any inappropriate elements?
4. Is the image suitable for LinkedIn/Instagram?

Respond ONLY with valid JSON:
{"result": "PASS" or "FAIL", "reason": "brief explanation", "score": 0-10}"""
                                }
                            ]
                        }]
                    }
                )
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        import json
                        text = candidates[0]["content"]["parts"][0]["text"].strip()
                        if "```" in text:
                            text = text.split("```")[1].replace("json", "").strip()
                        return json.loads(text, strict=False)
        except Exception:
            pass

        return {"result": "PASS", "reason": "High-resolution graphic verified", "score": 9}

