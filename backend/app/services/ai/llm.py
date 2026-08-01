import httpx
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

async def call_llm(provider: str, api_key: str, system_prompt: str, user_prompt: str, temperature: float = 0.7, max_tokens: int = 4000) -> str:
    """
    Unified helper to call either Groq or Anthropic Claude API.
    Returns the raw text response.
    """
    async with httpx.AsyncClient(timeout=120) as client:
        if provider == "claude":
            payload = {
                "model": "claude-3-5-sonnet-20241022",
                "max_tokens": max_tokens,
                "temperature": temperature,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}]
            }
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json=payload
            )
            resp.raise_for_status()
            return resp.json()["content"][0]["text"]
        
        else: # default to groq
            payload = {
                "model": "openai/gpt-oss-120b",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
                "response_format": {"type": "json_object"}
            }
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
