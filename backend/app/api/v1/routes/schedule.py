from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.core.database import get_db
from app.models.models import User, Schedule
from app.schemas.schemas import ScheduleCreate, ScheduleOut, MessageResponse
from app.api.v1.deps import get_current_user

router = APIRouter(prefix="/schedule", tags=["Scheduler"])


@router.get("", response_model=ScheduleOut)
async def get_schedule(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(Schedule).where(Schedule.user_id == current_user.id))
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(404, "No schedule configured yet")
    return schedule


@router.put("", response_model=ScheduleOut)
async def upsert_schedule(
    data: ScheduleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(Schedule).where(Schedule.user_id == current_user.id))
    schedule = result.scalar_one_or_none()

    if schedule:
        for k, v in data.model_dump().items():
            setattr(schedule, k, v)
    else:
        schedule = Schedule(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            **data.model_dump()
        )
        db.add(schedule)

    await db.flush()
    return schedule


@router.post("/toggle", response_model=MessageResponse)
async def toggle_automation(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(Schedule).where(Schedule.user_id == current_user.id))
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(404, "Configure a schedule first")

    schedule.is_active = not schedule.is_active
    current_user.automation_enabled = schedule.is_active
    await db.flush()

    status = "enabled" if schedule.is_active else "disabled"
    return MessageResponse(message=f"Automation {status}")
