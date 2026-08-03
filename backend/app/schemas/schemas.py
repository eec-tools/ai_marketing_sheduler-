from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Any
from datetime import datetime
from enum import Enum


# ─── Auth Schemas ─────────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8)


class UserOut(BaseModel):
    id: str
    email: str
    full_name: Optional[str]
    avatar_url: Optional[str]
    is_active: bool
    theme: str
    automation_enabled: bool
    notifications_enabled: bool
    preferred_ai_provider: str = "groq"
    created_at: datetime

    class Config:
        from_attributes = True


# ─── API Key Schemas ──────────────────────────────────────────────────────────

class ApiKeyCreate(BaseModel):
    provider: str
    api_key: str
    label: str = "My Key"
    priority: int = 1


class ApiKeyUpdate(BaseModel):
    label: Optional[str] = None
    priority: Optional[int] = None


class ApiKeyOut(BaseModel):
    id: str
    provider: str
    label: str
    priority: int
    usage_count: int
    fail_count: int
    last_used_at: Optional[datetime]
    last_failed_at: Optional[datetime]
    is_valid: bool
    is_active: bool
    masked_key: str
    created_at: datetime

    class Config:
        from_attributes = True


class ApiKeyTestResult(BaseModel):
    key_id: str
    provider: str
    label: str
    success: bool
    message: str
    latency_ms: Optional[int] = None


# ─── Brand Profile Schemas ────────────────────────────────────────────────────

class BrandProfileCreate(BaseModel):
    company_name: Optional[str] = None
    brand_name: Optional[str] = None
    target_audience: Optional[str] = None
    industry: Optional[str] = None
    writing_tone: str = "professional"
    preferred_language: str = "English"
    cta: Optional[str] = None
    hashtags: List[str] = []
    primary_color: str = "#2563EB"
    secondary_color: str = "#64748B"
    image_style: str = "professional"
    image_size: str = "square"
    posting_style: str = "informative"
    avoid_words: List[str] = []
    keywords: List[str] = []
    image_instructions: Optional[str] = None
    caption_template: Optional[str] = None
    # ── Company Intelligence ──────────────────────────────────────────────────
    company_description: Optional[str] = None
    products_services: Optional[str] = None
    unique_value_proposition: Optional[str] = None
    customer_pain_points: Optional[str] = None
    competitors_differentiators: Optional[str] = None


class BrandProfileOut(BrandProfileCreate):
    id: str
    logo_url: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ─── Connected Account Schemas ────────────────────────────────────────────────

class ConnectedAccountOut(BaseModel):
    id: str
    platform: str
    platform_username: Optional[str]
    platform_user_id: Optional[str]
    platform_page_id: Optional[str] = None
    status: str
    expires_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class OAuthUrlResponse(BaseModel):
    auth_url: str
    state: str


# ─── Schedule Schemas ─────────────────────────────────────────────────────────

class ScheduleCreate(BaseModel):
    frequency: str = "daily"
    posting_times: List[str] = ["09:00"]
    timezone: str = "UTC"
    max_posts_day: int = Field(default=2, ge=1, le=20)
    categories: List[str] = []
    platforms: List[str] = ["linkedin"]


class ScheduleOut(ScheduleCreate):
    id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ─── Topic Schemas ────────────────────────────────────────────────────────────

class TopicCreate(BaseModel):
    topic: str
    category: Optional[str] = None


class TopicOut(BaseModel):
    id: str
    topic: str
    source: str
    category: Optional[str]
    is_used: bool
    used_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class TopicGenerateRequest(BaseModel):
    count: int = Field(default=5, ge=1, le=20)
    category: Optional[str] = None


# ─── Post Generation Schemas ──────────────────────────────────────────────────

class GeneratePostRequest(BaseModel):
    topic_id: Optional[str] = None
    topic: Optional[str] = None
    platforms: List[str] = ["linkedin"]
    generate_image: bool = True
    image_source: Optional[str] = "pillow"  # "pillow", "gemini", or "chatgpt_extension"


class GenerateFromImageRequest(BaseModel):
    image_data: str  # Base64 string of the uploaded image
    topic: Optional[str] = None
    platforms: List[str] = ["linkedin"]
    scheduled_at: Optional[datetime] = None


class SchedulePostRequest(BaseModel):
    scheduled_at: Optional[datetime] = None


class PostUpdateRequest(BaseModel):
    headline: Optional[str] = None
    linkedin_caption: Optional[str] = None
    instagram_caption: Optional[str] = None
    image_url: Optional[str] = None
    hashtags: Optional[List[str]] = None
    cta: Optional[str] = None


class GeneratedPostOut(BaseModel):
    id: str
    platform: str
    headline: Optional[str]
    linkedin_caption: Optional[str]
    instagram_caption: Optional[str]
    hashtags: List[str]
    cta: Optional[str]
    image_requirements: Optional[str]
    image_url: Optional[str]
    media_url: Optional[str]
    image_review_result: Optional[str]
    image_review_notes: Optional[str]
    image_retry_count: int
    status: str
    scheduled_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Publishing History Schemas ────────────────────────────────────────────────

class HistoryOut(BaseModel):
    id: str
    platform: str
    platform_post_id: Optional[str]
    published_at: Optional[datetime]
    status: str
    error_message: Optional[str]
    generation_time_ms: Optional[int]
    caption_preview: Optional[str]
    image_url: Optional[str]
    media_url: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Analytics Schemas ────────────────────────────────────────────────────────

class AnalyticsSummary(BaseModel):
    total_published: int
    total_failed: int
    success_rate: float
    avg_generation_time_ms: Optional[float]
    posts_today: int
    posts_this_week: int
    automation_status: bool
    connected_platforms: List[str]
    top_hashtags: List[dict]


# ─── Settings Schemas ─────────────────────────────────────────────────────────

class UserSettingsUpdate(BaseModel):
    full_name: Optional[str] = None
    theme: Optional[str] = None
    notifications_enabled: Optional[bool] = None
    max_retries: Optional[int] = Field(default=None, ge=1, le=10)
    automation_enabled: Optional[bool] = None
    preferred_ai_provider: Optional[str] = None


# ─── Generic Response ─────────────────────────────────────────────────────────

class MessageResponse(BaseModel):
    message: str
    success: bool = True
