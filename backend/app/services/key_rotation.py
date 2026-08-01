from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.models import ApiKey
from app.core.security import decrypt_value, encrypt_value
from app.core.config import settings


class NoAvailableKeyError(Exception):
    pass


class KeyRotator:
    """
    Manages API key rotation across multiple keys per provider.
    Tries keys in priority order (lower number = higher priority).
    Skips keys that are cooling down after a failure.
    """

    def _is_cooling_down(self, key: ApiKey) -> bool:
        if not key.last_failed_at:
            return False
        last_failed = key.last_failed_at
        # DB may return timezone-aware or naive depending on driver settings
        # Normalize both to naive UTC for comparison
        if hasattr(last_failed, 'tzinfo') and last_failed.tzinfo is not None:
            from datetime import timezone
            last_failed = last_failed.astimezone(timezone.utc).replace(tzinfo=None)
        elapsed = (datetime.utcnow() - last_failed).total_seconds()
        return elapsed < settings.KEY_COOLDOWN_SECONDS



    async def get_next_key(
        self,
        user_id: str,
        provider: str,
        db: AsyncSession
    ) -> ApiKey:
        """Returns the next available, non-cooling key for the provider."""
        result = await db.execute(
            select(ApiKey).where(
                ApiKey.user_id == user_id,
                ApiKey.provider == provider,
                ApiKey.is_active == True,
                ApiKey.is_valid == True,
            ).order_by(ApiKey.priority.asc())
        )
        keys = result.scalars().all()

        if not keys:
            raise NoAvailableKeyError(f"No active {provider} keys found.")

        for key in keys:
            if not self._is_cooling_down(key):
                return key

        # All keys are cooling down — return the one with oldest failure (soonest to recover)
        def _naive(dt):
            if dt is None:
                return datetime.min
            if hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
                from datetime import timezone
                return dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt

        keys_sorted = sorted(keys, key=lambda k: _naive(k.last_failed_at))
        raise NoAvailableKeyError(
            f"All {provider} keys are cooling down. "
            f"Next available in {settings.KEY_COOLDOWN_SECONDS}s."
        )

    def get_decrypted_key(self, key: ApiKey) -> str:
        return decrypt_value(key.encrypted_key)

    async def mark_success(self, key_id: str, db: AsyncSession):
        result = await db.execute(select(ApiKey).where(ApiKey.id == key_id))
        key = result.scalar_one_or_none()
        if key:
            key.usage_count += 1
            key.last_used_at = datetime.utcnow()

    async def mark_failure(self, key_id: str, db: AsyncSession):
        result = await db.execute(select(ApiKey).where(ApiKey.id == key_id))
        key = result.scalar_one_or_none()
        if key:
            key.fail_count += 1
            key.last_failed_at = datetime.utcnow()
