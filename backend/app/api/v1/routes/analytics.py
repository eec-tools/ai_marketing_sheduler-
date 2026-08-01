from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from typing import List
from datetime import datetime, timedelta

from app.core.database import get_db
from app.models.models import User, PublishingHistory
from app.schemas.schemas import HistoryOut, AnalyticsSummary
from app.api.v1.deps import get_current_user

router = APIRouter(tags=["History & Analytics"])


@router.get("/history", response_model=List[HistoryOut])
async def get_history(
    page: int = 1,
    limit: int = 20,
    platform: str = None,
    status: str = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = (
        select(PublishingHistory)
        .where(PublishingHistory.user_id == current_user.id)
        .order_by(desc(PublishingHistory.created_at))
        .offset((page - 1) * limit)
        .limit(limit)
    )
    if platform:
        query = query.where(PublishingHistory.platform == platform)
    if status:
        query = query.where(PublishingHistory.status == status)

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/analytics/summary", response_model=AnalyticsSummary)
async def get_analytics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from app.models.models import ConnectedAccount, GeneratedPost
    from sqlalchemy import case

    # Total counts
    total_result = await db.execute(
        select(
            func.count(PublishingHistory.id).label("total"),
            func.sum(case((PublishingHistory.status == "published", 1), else_=0)).label("published"),
            func.sum(case((PublishingHistory.status == "failed", 1), else_=0)).label("failed"),
            func.avg(PublishingHistory.generation_time_ms).label("avg_time")
        ).where(PublishingHistory.user_id == current_user.id)
    )
    stats = total_result.one()

    total = stats.total or 0
    published = stats.published or 0
    failed = stats.failed or 0
    avg_time = stats.avg_time

    success_rate = (published / total * 100) if total > 0 else 0.0

    # Posts today
    today = datetime.utcnow().replace(hour=0, minute=0, second=0)
    today_result = await db.execute(
        select(func.count(PublishingHistory.id))
        .where(PublishingHistory.user_id == current_user.id, PublishingHistory.created_at >= today)
    )
    posts_today = today_result.scalar() or 0

    # Posts this week
    week_ago = datetime.utcnow() - timedelta(days=7)
    week_result = await db.execute(
        select(func.count(PublishingHistory.id))
        .where(PublishingHistory.user_id == current_user.id, PublishingHistory.created_at >= week_ago)
    )
    posts_week = week_result.scalar() or 0

    # Connected platforms
    platform_result = await db.execute(
        select(ConnectedAccount.platform)
        .where(ConnectedAccount.user_id == current_user.id, ConnectedAccount.status == "connected")
    )
    platforms = [r for r in platform_result.scalars()]

    # Top hashtags from generated posts
    posts_result = await db.execute(
        select(GeneratedPost.hashtags)
        .where(GeneratedPost.user_id == current_user.id, GeneratedPost.status == "published")
        .limit(100)
    )
    hashtag_counts = {}
    for row in posts_result.scalars():
        for tag in (row or []):
            hashtag_counts[tag] = hashtag_counts.get(tag, 0) + 1

    top_hashtags = [
        {"tag": k, "count": v}
        for k, v in sorted(hashtag_counts.items(), key=lambda x: -x[1])[:10]
    ]

    return AnalyticsSummary(
        total_published=published,
        total_failed=failed,
        success_rate=round(success_rate, 1),
        avg_generation_time_ms=avg_time,
        posts_today=posts_today,
        posts_this_week=posts_week,
        automation_status=current_user.automation_enabled,
        connected_platforms=platforms,
        top_hashtags=top_hashtags,
    )
