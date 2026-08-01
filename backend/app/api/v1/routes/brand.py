from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
from app.core.database import get_db
from app.models.models import User, BrandProfile
from app.schemas.schemas import BrandProfileCreate, BrandProfileOut, MessageResponse
from app.api.v1.deps import get_current_user

router = APIRouter(prefix="/brand", tags=["Brand Profile"])


@router.get("", response_model=BrandProfileOut)
async def get_brand(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(BrandProfile).where(BrandProfile.user_id == current_user.id))
    brand = result.scalar_one_or_none()
    if not brand:
        raise HTTPException(404, "Brand profile not found. Please create one.")
    return brand


@router.put("", response_model=BrandProfileOut)
async def upsert_brand(
    data: BrandProfileCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(BrandProfile).where(BrandProfile.user_id == current_user.id))
    brand = result.scalar_one_or_none()

    if brand:
        for key, value in data.model_dump().items():
            setattr(brand, key, value)
    else:
        brand = BrandProfile(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            **data.model_dump()
        )
        db.add(brand)

    await db.flush()
    return brand


@router.post("/logo-data", response_model=MessageResponse)
async def save_logo_data(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Save a base64 logo data URI directly to the brand profile. Pass empty string to remove."""
    logo_url = data.get("logo_url", "")

    result = await db.execute(select(BrandProfile).where(BrandProfile.user_id == current_user.id))
    brand = result.scalar_one_or_none()

    if brand:
        brand.logo_url = logo_url or None
        await db.flush()
        action = "removed" if not logo_url else "saved"
        return MessageResponse(message=f"Brand logo {action} successfully!")
    else:
        raise HTTPException(404, "Brand profile not found. Please create a brand profile first.")
