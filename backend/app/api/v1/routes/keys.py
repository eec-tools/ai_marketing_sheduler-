from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from typing import List
from datetime import datetime
import time, httpx, uuid

from app.core.database import get_db
from app.core.security import encrypt_value, decrypt_value
from app.models.models import User, ApiKey

from app.schemas.schemas import ApiKeyCreate, ApiKeyUpdate, ApiKeyOut, ApiKeyTestResult, MessageResponse
from app.api.v1.deps import get_current_user

router = APIRouter(prefix="/keys", tags=["API Keys"])


def mask_key(key: str) -> str:
    if len(key) <= 8:
        return "••••••••"
    return key[:4] + "••••••••" + key[-4:]


@router.get("", response_model=List[ApiKeyOut])
async def list_keys(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.user_id == current_user.id)
        .order_by(ApiKey.provider, ApiKey.priority)
    )
    keys = result.scalars().all()
    return [
        ApiKeyOut(
            **{k: v for k, v in key.__dict__.items() if k != "encrypted_key"},
            masked_key=mask_key("placeholder")  # Never return actual key
        )
        for key in keys
    ]


@router.post("", response_model=ApiKeyOut, status_code=201)
async def add_key(
    data: ApiKeyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if data.provider not in ("groq", "gemini"):
        raise HTTPException(400, "Provider must be 'groq' or 'gemini'")

    # Get current max priority for this user+provider
    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.user_id == current_user.id, ApiKey.provider == data.provider)
        .order_by(ApiKey.priority.desc())
    )
    existing = result.scalars().all()
    next_priority = (max(k.priority for k in existing) + 1) if existing else 1

    key = ApiKey(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        provider=data.provider,
        encrypted_key=encrypt_value(data.api_key),
        label=data.label,
        priority=data.priority if data.priority else next_priority,
    )
    db.add(key)
    await db.flush()

    return ApiKeyOut(
        id=key.id,
        provider=key.provider.value if hasattr(key.provider, 'value') else str(key.provider),
        label=key.label,
        priority=key.priority,
        usage_count=key.usage_count or 0,
        fail_count=key.fail_count or 0,
        last_used_at=key.last_used_at,
        last_failed_at=key.last_failed_at,
        is_valid=key.is_valid if key.is_valid is not None else True,
        is_active=key.is_active if key.is_active is not None else True,
        masked_key=mask_key(data.api_key),
        created_at=key.created_at or datetime.utcnow(),
    )


@router.put("/{key_id}", response_model=ApiKeyOut)
async def update_key(
    key_id: str,
    data: ApiKeyUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == current_user.id))
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(404, "Key not found")

    if data.label is not None:
        key.label = data.label
    if data.priority is not None:
        key.priority = data.priority

    await db.flush()
    return ApiKeyOut(**{k: v for k, v in key.__dict__.items() if k != "encrypted_key"}, masked_key="••••••••")


@router.delete("/{key_id}", response_model=MessageResponse)
async def delete_key(
    key_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == current_user.id))
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(404, "Key not found")
    await db.delete(key)
    return MessageResponse(message="Key deleted successfully")


@router.patch("/{key_id}/toggle", response_model=ApiKeyOut)
async def toggle_key(
    key_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == current_user.id))
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(404, "Key not found")
    key.is_active = not key.is_active
    await db.flush()
    return ApiKeyOut(**{k: v for k, v in key.__dict__.items() if k != "encrypted_key"}, masked_key="••••••••")


@router.patch("/{key_id}/priority", response_model=ApiKeyOut)
async def update_priority(
    key_id: str,
    priority: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == current_user.id))
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(404, "Key not found")
    key.priority = priority
    await db.flush()
    return ApiKeyOut(**{k: v for k, v in key.__dict__.items() if k != "encrypted_key"}, masked_key="••••••••")


async def _test_groq_key(api_key: str) -> tuple[bool, str, int]:
    start = time.time()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": "llama3-8b-8192", "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 5}
            )
            latency = int((time.time() - start) * 1000)
            if resp.status_code == 200:
                return True, "Connected successfully", latency
            return False, f"API error: {resp.status_code}", latency
    except Exception as e:
        return False, str(e), int((time.time() - start) * 1000)


async def _test_gemini_key(api_key: str) -> tuple[bool, str, int]:
    start = time.time()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
            )
            latency = int((time.time() - start) * 1000)
            if resp.status_code == 200:
                return True, "Connected successfully", latency
            return False, f"API error: {resp.status_code}", latency
    except Exception as e:
        return False, str(e), int((time.time() - start) * 1000)


@router.post("/{key_id}/test", response_model=ApiKeyTestResult)
async def test_key(
    key_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == current_user.id))
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(404, "Key not found")

    decrypted = decrypt_value(key.encrypted_key)

    if key.provider == "groq":
        success, message, latency = await _test_groq_key(decrypted)
    else:
        success, message, latency = await _test_gemini_key(decrypted)

    key.is_valid = success
    if not success:
        key.fail_count += 1
        key.last_failed_at = datetime.utcnow()
    await db.flush()

    return ApiKeyTestResult(key_id=key_id, provider=key.provider, label=key.label,
                            success=success, message=message, latency_ms=latency)


@router.post("/test-all", response_model=List[ApiKeyTestResult])
async def test_all_keys(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(ApiKey).where(ApiKey.user_id == current_user.id))
    keys = result.scalars().all()
    results = []

    for key in keys:
        decrypted = decrypt_value(key.encrypted_key)
        if key.provider == "groq":
            success, message, latency = await _test_groq_key(decrypted)
        else:
            success, message, latency = await _test_gemini_key(decrypted)

        key.is_valid = success
        if not success:
            key.fail_count += 1
            key.last_failed_at = datetime.utcnow()

        results.append(ApiKeyTestResult(key_id=key.id, provider=key.provider, label=key.label,
                                         success=success, message=message, latency_ms=latency))

    await db.flush()
    return results



