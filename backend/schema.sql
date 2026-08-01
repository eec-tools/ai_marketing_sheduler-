-- ============================================================
-- AI Social Media Manager — Supabase Schema
-- Paste this entire file into Supabase SQL Editor and click Run
-- ============================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─── Users ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    email TEXT UNIQUE NOT NULL,
    hashed_password TEXT,
    full_name TEXT,
    avatar_url TEXT,
    is_active BOOLEAN DEFAULT true,
    is_verified BOOLEAN DEFAULT false,
    theme TEXT DEFAULT 'light',
    max_retries INTEGER DEFAULT 3,
    automation_enabled BOOLEAN DEFAULT false,
    notifications_enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- ─── API Keys ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS api_keys (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider TEXT NOT NULL CHECK (provider IN ('groq', 'gemini')),
    encrypted_key TEXT NOT NULL,
    label TEXT DEFAULT 'My Key',
    priority INTEGER DEFAULT 1,
    usage_count INTEGER DEFAULT 0,
    fail_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMPTZ,
    last_failed_at TIMESTAMPTZ,
    is_valid BOOLEAN DEFAULT true,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys(user_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_provider ON api_keys(provider);

-- ─── Brand Profiles ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS brand_profiles (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    user_id TEXT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    company_name TEXT,
    brand_name TEXT,
    target_audience TEXT,
    industry TEXT,
    writing_tone TEXT DEFAULT 'professional',
    preferred_language TEXT DEFAULT 'English',
    cta TEXT,
    hashtags JSONB DEFAULT '[]',
    logo_url TEXT,
    primary_color TEXT DEFAULT '#2563EB',
    secondary_color TEXT DEFAULT '#64748B',
    image_style TEXT DEFAULT 'professional',
    image_size TEXT DEFAULT 'square',
    posting_style TEXT DEFAULT 'informative',
    image_instructions TEXT,
    caption_template TEXT,
    -- Company Intelligence
    company_description TEXT,
    products_services TEXT,
    unique_value_proposition TEXT,
    customer_pain_points TEXT,
    competitors_differentiators TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Migration: run this if the table already exists
ALTER TABLE brand_profiles ADD COLUMN IF NOT EXISTS image_instructions TEXT;
ALTER TABLE brand_profiles ADD COLUMN IF NOT EXISTS caption_template TEXT;
ALTER TABLE brand_profiles ADD COLUMN IF NOT EXISTS company_description TEXT;
ALTER TABLE brand_profiles ADD COLUMN IF NOT EXISTS products_services TEXT;
ALTER TABLE brand_profiles ADD COLUMN IF NOT EXISTS unique_value_proposition TEXT;
ALTER TABLE brand_profiles ADD COLUMN IF NOT EXISTS customer_pain_points TEXT;
ALTER TABLE brand_profiles ADD COLUMN IF NOT EXISTS competitors_differentiators TEXT;

-- ─── Connected Accounts ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS connected_accounts (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    platform TEXT NOT NULL CHECK (platform IN ('linkedin', 'instagram')),
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    platform_user_id TEXT,
    platform_username TEXT,
    platform_page_id TEXT,
    expires_at TIMESTAMPTZ,
    status TEXT DEFAULT 'connected',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_connected_accounts_user_id ON connected_accounts(user_id);

-- ─── Schedules ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS schedules (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    user_id TEXT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    frequency TEXT DEFAULT 'daily' CHECK (frequency IN ('daily', 'weekly', 'custom')),
    posting_times JSONB DEFAULT '["09:00"]',
    timezone TEXT DEFAULT 'UTC',
    max_posts_day INTEGER DEFAULT 2,
    categories JSONB DEFAULT '[]',
    platforms JSONB DEFAULT '["linkedin"]',
    is_active BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- ─── Topics ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS topics (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    topic TEXT NOT NULL,
    source TEXT DEFAULT 'manual' CHECK (source IN ('manual', 'ai', 'csv')),
    category TEXT,
    is_used BOOLEAN DEFAULT false,
    used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_topics_user_id ON topics(user_id);
CREATE INDEX IF NOT EXISTS idx_topics_is_used ON topics(is_used);

-- ─── Generated Posts ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS generated_posts (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    topic_id TEXT REFERENCES topics(id) ON DELETE SET NULL,
    platform TEXT NOT NULL CHECK (platform IN ('linkedin', 'instagram')),
    headline TEXT,
    linkedin_caption TEXT,
    instagram_caption TEXT,
    hashtags JSONB DEFAULT '[]',
    cta TEXT,
    image_requirements TEXT,
    image_url TEXT,
    image_review_result TEXT DEFAULT 'PENDING' CHECK (image_review_result IN ('PASS', 'FAIL', 'PENDING')),
    image_review_notes TEXT,
    image_retry_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'approved', 'scheduled', 'published', 'failed')),
    scheduled_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_generated_posts_user_id ON generated_posts(user_id);
CREATE INDEX IF NOT EXISTS idx_generated_posts_status ON generated_posts(status);

-- ─── Publishing History ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS publishing_history (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    post_id TEXT REFERENCES generated_posts(id) ON DELETE SET NULL,
    platform TEXT NOT NULL CHECK (platform IN ('linkedin', 'instagram')),
    platform_post_id TEXT,
    published_at TIMESTAMPTZ,
    status TEXT NOT NULL,
    error_message TEXT,
    generation_time_ms INTEGER,
    caption_preview TEXT,
    image_url TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_publishing_history_user_id ON publishing_history(user_id);
CREATE INDEX IF NOT EXISTS idx_publishing_history_status ON publishing_history(status);
CREATE INDEX IF NOT EXISTS idx_publishing_history_created_at ON publishing_history(created_at);

-- ─── Logs ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS logs (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    event TEXT NOT NULL,
    level TEXT DEFAULT 'info',
    details JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_logs_user_id ON logs(user_id);

-- ─── Row Level Security ────────────────────────────────────────
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE brand_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE connected_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE schedules ENABLE ROW LEVEL SECURITY;
ALTER TABLE topics ENABLE ROW LEVEL SECURITY;
ALTER TABLE generated_posts ENABLE ROW LEVEL SECURITY;
ALTER TABLE publishing_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE logs ENABLE ROW LEVEL SECURITY;

-- Service role bypasses RLS (backend uses service key)
-- Frontend never touches the DB directly

-- ─── Storage bucket ───────────────────────────────────────────
-- Run in Supabase Dashboard > Storage > Create Bucket
-- Bucket name: ai-social-media (set to private)

SELECT 'Schema created successfully! ✅' as result;
