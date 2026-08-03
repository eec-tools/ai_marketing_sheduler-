import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, DateTime, Integer, Text,
    ForeignKey, JSON, Float, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import enum
from app.core.database import Base


def gen_uuid():
    return str(uuid.uuid4())


# ─── Enums ────────────────────────────────────────────────────────────────────

class ProviderEnum(str, enum.Enum):
    groq = "groq"
    gemini = "gemini"
    claude = "claude"


class PlatformEnum(str, enum.Enum):
    linkedin = "linkedin"
    instagram = "instagram"


class PostStatusEnum(str, enum.Enum):
    draft = "draft"
    research_pending = "research_pending"
    research_approved = "research_approved"
    script_review_pending = "script_review_pending"   # Reels only: AI script awaiting human review
    script_approved = "script_approved"               # Reels only: script approved, generating caption
    content_review_pending = "content_review_pending"
    content_approved = "content_approved"
    prompt_review_pending = "prompt_review_pending"
    prompt_approved = "prompt_approved"
    creative_review_pending = "creative_review_pending"
    creative_approved = "creative_approved"
    video_generation_pending = "video_generation_pending"
    video_review_pending = "video_review_pending"
    video_approved = "video_approved"
    scheduled = "scheduled"
    published = "published"
    failed = "failed"


class FrequencyEnum(str, enum.Enum):
    daily = "daily"
    weekly = "weekly"
    custom = "custom"


class TopicSourceEnum(str, enum.Enum):
    manual = "manual"
    ai = "ai"
    csv = "csv"


class ReviewResultEnum(str, enum.Enum):
    pass_ = "PASS"
    fail = "FAIL"
    pending = "PENDING"
    pending_extension = "PENDING_EXTENSION"


# ─── Models ───────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=gen_uuid)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=True)  # nullable for OAuth users
    full_name = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    theme = Column(String, default="light")
    max_retries = Column(Integer, default=3)
    automation_enabled = Column(Boolean, default=False)
    notifications_enabled = Column(Boolean, default=True)
    preferred_ai_provider = Column(String, default="groq")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    api_keys = relationship("ApiKey", back_populates="user", cascade="all, delete-orphan")
    brand_profile = relationship("BrandProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    connected_accounts = relationship("ConnectedAccount", back_populates="user", cascade="all, delete-orphan")
    schedules = relationship("Schedule", back_populates="user", cascade="all, delete-orphan")
    topics = relationship("Topic", back_populates="user", cascade="all, delete-orphan")
    generated_posts = relationship("GeneratedPost", back_populates="user", cascade="all, delete-orphan")
    publishing_history = relationship("PublishingHistory", back_populates="user", cascade="all, delete-orphan")
    logs = relationship("Log", back_populates="user", cascade="all, delete-orphan")
    monthly_strategies = relationship("MonthlyStrategy", back_populates="user", cascade="all, delete-orphan")


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(SAEnum(ProviderEnum, native_enum=False), nullable=False)
    encrypted_key = Column(Text, nullable=False)
    label = Column(String, default="My Key")
    priority = Column(Integer, default=1)  # Lower = higher priority
    usage_count = Column(Integer, default=0)
    fail_count = Column(Integer, default=0)
    last_used_at = Column(DateTime, nullable=True)
    last_failed_at = Column(DateTime, nullable=True)
    is_valid = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="api_keys")


class BrandProfile(Base):
    __tablename__ = "brand_profiles"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    company_name = Column(String, nullable=True)
    brand_name = Column(String, nullable=True)
    target_audience = Column(Text, nullable=True)
    industry = Column(String, nullable=True)
    writing_tone = Column(String, default="professional")
    preferred_language = Column(String, default="English")
    cta = Column(Text, nullable=True)
    hashtags = Column(JSON, default=list)
    logo_url = Column(String, nullable=True)
    primary_color = Column(String, default="#2563EB")
    secondary_color = Column(String, default="#64748B")
    image_style = Column(String, default="professional")
    image_size = Column(String, default="square")
    posting_style = Column(String, default="informative")
    avoid_words = Column(JSON, default=list)
    keywords = Column(JSON, default=list)
    image_instructions = Column(Text, nullable=True)
    caption_template = Column(Text, nullable=True)
    # ── Company Intelligence ─────────────────────────────────────────────────
    company_description = Column(Text, nullable=True)         # What the company does
    products_services = Column(Text, nullable=True)           # Key products/services
    unique_value_proposition = Column(Text, nullable=True)    # What makes them unique
    customer_pain_points = Column(Text, nullable=True)        # Problems they solve
    competitors_differentiators = Column(Text, nullable=True) # vs competitors
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="brand_profile")


class ConnectedAccount(Base):
    __tablename__ = "connected_accounts"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    platform = Column(SAEnum(PlatformEnum, native_enum=False), nullable=False)
    access_token = Column(Text, nullable=False)  # encrypted
    refresh_token = Column(Text, nullable=True)  # encrypted
    platform_user_id = Column(String, nullable=True)
    platform_username = Column(String, nullable=True)
    platform_page_id = Column(String, nullable=True)  # For Instagram (Facebook Page)
    expires_at = Column(DateTime, nullable=True)
    status = Column(String, default="connected")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="connected_accounts")


class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    frequency = Column(SAEnum(FrequencyEnum, native_enum=False), default=FrequencyEnum.daily)
    posting_times = Column(JSON, default=list)  # ["09:00", "18:00"]
    timezone = Column(String, default="UTC")
    max_posts_day = Column(Integer, default=2)
    categories = Column(JSON, default=list)
    platforms = Column(JSON, default=list)  # ["linkedin", "instagram"]
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="schedules")


class Topic(Base):
    __tablename__ = "topics"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    topic = Column(Text, nullable=False)
    source = Column(SAEnum(TopicSourceEnum, native_enum=False), default=TopicSourceEnum.manual)
    category = Column(String, nullable=True)
    is_used = Column(Boolean, default=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="topics")


class GeneratedPost(Base):
    __tablename__ = "generated_posts"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    topic_id = Column(String, ForeignKey("topics.id", ondelete="SET NULL"), nullable=True)
    platform = Column(SAEnum(PlatformEnum, native_enum=False), nullable=False)
    headline = Column(Text, nullable=True)
    linkedin_caption = Column(Text, nullable=True)
    instagram_caption = Column(Text, nullable=True)
    hashtags = Column(JSON, default=list)
    cta = Column(Text, nullable=True)
    image_requirements = Column(Text, nullable=True)
    image_url = Column(String, nullable=True)
    media_url = Column(String, nullable=True)
    image_review_result = Column(String, default="PENDING")
    image_review_notes = Column(Text, nullable=True)
    image_retry_count = Column(Integer, default=0)
    status = Column(SAEnum(PostStatusEnum, native_enum=False), default=PostStatusEnum.draft)
    error_message = Column(Text, nullable=True)  # Populated when status = 'failed'
    scheduled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="generated_posts")
    topic = relationship("Topic")
    history = relationship("PublishingHistory", back_populates="post", cascade="all, delete-orphan")
    brief = relationship("ContentBrief", back_populates="post", cascade="all, delete-orphan")
    video_prompt = relationship("VideoPrompt", back_populates="post", cascade="all, delete-orphan")


class PublishingHistory(Base):
    __tablename__ = "publishing_history"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    post_id = Column(String, ForeignKey("generated_posts.id", ondelete="SET NULL"), nullable=True)
    platform = Column(SAEnum(PlatformEnum, native_enum=False), nullable=False)
    platform_post_id = Column(String, nullable=True)
    published_at = Column(DateTime, nullable=True)
    status = Column(String, nullable=False)  # published, failed
    error_message = Column(Text, nullable=True)
    generation_time_ms = Column(Integer, nullable=True)
    caption_preview = Column(Text, nullable=True)
    image_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="publishing_history")
    post = relationship("GeneratedPost", back_populates="history")


class Log(Base):
    __tablename__ = "logs"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    event = Column(String, nullable=False)
    level = Column(String, default="info")  # info, warning, error
    details = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="logs")


class MonthlyStrategy(Base):
    __tablename__ = "monthly_strategies"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    month = Column(String, nullable=False) # e.g. "2024-08"
    audit_data = Column(JSON, default=dict) # Windsor AI results
    strategy_content = Column(Text, nullable=True) # Text from Groq
    calendar = Column(JSON, default=list) # List of generated topics/ideas
    status = Column(String, default="draft") # draft, active, archived
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="monthly_strategies")


class ContentBrief(Base):
    __tablename__ = "content_briefs"

    id = Column(String, primary_key=True, default=gen_uuid)
    post_id = Column(String, ForeignKey("generated_posts.id", ondelete="CASCADE"), nullable=False, unique=True)
    research_data = Column(Text, nullable=True)
    statistics = Column(JSON, default=list)
    references = Column(JSON, default=list)
    market_trends = Column(Text, nullable=True)
    key_takeaways = Column(Text, nullable=True)
    ai_review_notes = Column(Text, nullable=True)
    human_feedback = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    post = relationship("GeneratedPost", back_populates="brief")


class VideoPrompt(Base):
    __tablename__ = "video_prompts"

    id = Column(String, primary_key=True, default=gen_uuid)
    post_id = Column(String, ForeignKey("generated_posts.id", ondelete="CASCADE"), nullable=False, unique=True)
    scenes = Column(JSON, default=list) # [{"scene_num": 1, "prompt": "...", "audio": "..."}]
    flow_ai_job_ids = Column(JSON, default=list)
    video_urls = Column(JSON, default=list)
    final_video_url = Column(String, nullable=True)
    ai_review_notes = Column(Text, nullable=True)
    human_feedback = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    post = relationship("GeneratedPost", back_populates="video_prompt")

