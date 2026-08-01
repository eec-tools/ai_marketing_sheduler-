from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.models import User
from app.schemas.schemas import UserOut, UserSettingsUpdate, MessageResponse
from app.api.v1.deps import get_current_user

router = APIRouter(prefix="/users", tags=["Users & Settings"])


@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/me", response_model=UserOut)
async def update_settings(
    data: UserSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(current_user, k, v)
    await db.flush()
    return current_user


@router.delete("/me", response_model=MessageResponse)
async def delete_account(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await db.delete(current_user)
    return MessageResponse(message="Account deleted successfully")


@router.get("/me/export")
async def export_data(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from app.models.models import GeneratedPost, PublishingHistory, Topic
    posts_result = await db.execute(select(GeneratedPost).where(GeneratedPost.user_id == current_user.id))
    history_result = await db.execute(select(PublishingHistory).where(PublishingHistory.user_id == current_user.id))
    topics_result = await db.execute(select(Topic).where(Topic.user_id == current_user.id))

    return {
        "user": {"email": current_user.email, "created_at": current_user.created_at.isoformat()},
        "posts_count": len(posts_result.scalars().all()),
        "history_count": len(history_result.scalars().all()),
        "topics_count": len(topics_result.scalars().all()),
        "message": "Full export available — contact support for complete data export."
    }
