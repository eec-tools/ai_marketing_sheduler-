// Shared TypeScript types for the entire application

export interface User {
  id: string;
  email: string;
  full_name?: string;
  avatar_url?: string;
  is_active: boolean;
  theme: string;
  automation_enabled: boolean;
  notifications_enabled: boolean;
  preferred_ai_provider?: string;
  created_at: string;
}

export interface ApiKey {
  id: string;
  provider: 'groq' | 'gemini';
  label: string;
  priority: number;
  usage_count: number;
  fail_count: number;
  last_used_at?: string;
  last_failed_at?: string;
  is_valid: boolean;
  is_active: boolean;
  masked_key: string;
  created_at: string;
}

export interface ApiKeyTestResult {
  key_id: string;
  provider: string;
  label: string;
  success: boolean;
  message: string;
  latency_ms?: number;
}

export interface BrandProfile {
  id: string;
  company_name?: string;
  brand_name?: string;
  target_audience?: string;
  industry?: string;
  writing_tone: string;
  preferred_language: string;
  cta?: string;
  hashtags: string[];
  logo_url?: string;
  primary_color: string;
  secondary_color: string;
  image_style: string;
  image_size: string;
  posting_style: string;
  avoid_words: string[];
  keywords: string[];
  image_instructions?: string;
  caption_template?: string;
  created_at: string;
  updated_at: string;
}

export interface ConnectedAccount {
  id: string;
  platform: 'linkedin' | 'instagram';
  platform_username?: string;
  platform_user_id?: string;
  platform_page_id?: string;
  status: string;
  expires_at?: string;
  created_at: string;
}

export interface Schedule {
  id: string;
  frequency: 'daily' | 'weekly' | 'custom';
  posting_times: string[];
  timezone: string;
  max_posts_day: number;
  categories: string[];
  platforms: string[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Topic {
  id: string;
  topic: string;
  source: 'manual' | 'ai' | 'csv';
  category?: string;
  is_used: boolean;
  used_at?: string;
  created_at: string;
}

export interface GeneratedPost {
  id: string;
  platform: 'linkedin' | 'instagram';
  headline?: string;
  linkedin_caption?: string;
  instagram_caption?: string;
  hashtags: string[];
  cta?: string;
  image_requirements?: string;
  image_url?: string;
  image_review_result?: 'PASS' | 'FAIL' | 'PENDING' | 'PENDING_EXTENSION';
  image_review_notes?: string;
  image_retry_count: number;
  status: 'draft' | 'approved' | 'scheduled' | 'published' | 'failed';
  scheduled_at?: string;
  created_at: string;
}

export interface HistoryItem {
  id: string;
  platform: 'linkedin' | 'instagram';
  platform_post_id?: string;
  published_at?: string;
  status: string;
  error_message?: string;
  generation_time_ms?: number;
  caption_preview?: string;
  image_url?: string;
  created_at: string;
}

export interface AnalyticsSummary {
  total_published: number;
  total_failed: number;
  success_rate: number;
  avg_generation_time_ms?: number;
  posts_today: number;
  posts_this_week: number;
  automation_status: boolean;
  connected_platforms: string[];
  top_hashtags: { tag: string; count: number }[];
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface ApiError {
  detail: string;
}
