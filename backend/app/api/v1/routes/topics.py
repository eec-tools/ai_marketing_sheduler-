from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List
import uuid, csv, io

from app.core.database import get_db
from app.models.models import User, Topic, BrandProfile, ApiKey
from app.schemas.schemas import TopicCreate, TopicOut, TopicGenerateRequest, MessageResponse
from app.api.v1.deps import get_current_user
from app.services.key_rotation import KeyRotator
from app.services.ai.groq import GroqService

router = APIRouter(prefix="/topics", tags=["Topics"])
rotator = KeyRotator()


@router.get("", response_model=List[TopicOut])
async def list_topics(
    unused_only: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = select(Topic).where(Topic.user_id == current_user.id).order_by(Topic.created_at.desc())
    if unused_only:
        query = query.where(Topic.is_used == False)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("", response_model=TopicOut, status_code=201)
async def add_topic(
    data: TopicCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    topic = Topic(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        topic=data.topic,
        category=data.category,
        source="manual"
    )
    db.add(topic)
    await db.flush()
    return topic


@router.post("/generate", response_model=List[TopicOut])
async def generate_topics(
    data: TopicGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Get brand profile for context
    brand_result = await db.execute(select(BrandProfile).where(BrandProfile.user_id == current_user.id))
    brand = brand_result.scalar_one_or_none()

    api_key = await rotator.get_next_key(current_user.id, "groq", db)
    groq = GroqService(api_key)

    brand_context = ""
    if brand:
        brand_context = f"Company: {brand.company_name}, Industry: {brand.industry}, Audience: {brand.target_audience}"

    prompt = f"""Generate {data.count} unique social media post topics for:
{brand_context}
Category: {data.category or 'general business'}

Return ONLY a JSON array of strings, no other text.
Example: ["Topic 1", "Topic 2", "Topic 3"]"""

    import json
    topics_text = await groq.generate_text(prompt)
    try:
        topic_list = json.loads(topics_text.strip())
    except Exception:
        topic_list = [line.strip("- ").strip() for line in topics_text.split("\n") if line.strip()]

    created = []
    existing_result = await db.execute(select(Topic.topic).where(Topic.user_id == current_user.id))
    existing_topics = {r for r in existing_result.scalars()}

    for t in topic_list[:data.count]:
        if t and t not in existing_topics:
            topic = Topic(
                id=str(uuid.uuid4()),
                user_id=current_user.id,
                topic=t,
                category=data.category,
                source="ai"
            )
            db.add(topic)
            created.append(topic)
            existing_topics.add(t)

    await db.flush()
    await rotator.mark_success(api_key.id, db)
    return created


@router.post("/import", response_model=List[TopicOut])
async def import_topics_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    content = await file.read()
    reader = csv.reader(io.StringIO(content.decode()))
    topics = []

    existing_result = await db.execute(select(Topic.topic).where(Topic.user_id == current_user.id))
    existing = {r for r in existing_result.scalars()}

    for row in reader:
        if row and row[0].strip() and row[0].strip() not in existing:
            topic = Topic(
                id=str(uuid.uuid4()),
                user_id=current_user.id,
                topic=row[0].strip(),
                category=row[1].strip() if len(row) > 1 else None,
                source="csv"
            )
            db.add(topic)
            topics.append(topic)
            existing.add(row[0].strip())

    await db.flush()
    return topics


@router.delete("/bulk-delete", response_model=MessageResponse)
async def delete_all_topics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete ALL topics belonging to the current user."""
    result = await db.execute(
        delete(Topic).where(Topic.user_id == current_user.id)
    )
    deleted_count = result.rowcount
    await db.commit()
    return MessageResponse(message=f"Deleted {deleted_count} topics")


@router.delete("/{topic_id}", response_model=MessageResponse)
async def delete_topic(
    topic_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(Topic).where(Topic.id == topic_id, Topic.user_id == current_user.id))
    topic = result.scalar_one_or_none()
    if not topic:
        raise HTTPException(404, "Topic not found")
    await db.delete(topic)
    return MessageResponse(message="Topic deleted")
