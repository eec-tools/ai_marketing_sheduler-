import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import {
  BarChart3, CheckCircle, XCircle, Zap, Clock,
  Link2, TrendingUp, Calendar, Wand2, ArrowRight, Send
} from 'lucide-react';
import { Link } from 'react-router-dom';
import api from '@/lib/axios';
import type { AnalyticsSummary, GeneratedPost } from '@/types';
import { useAuth } from '@/providers/AuthProvider';
import toast from 'react-hot-toast';
import { formatScheduledDate } from '@/lib/date';
import { PublishAccountModal } from '@/components/modals/PublishAccountModal';

const Skeleton = ({ className }: { className?: string }) => (
  <div className={`skeleton ${className}`} />
);

function StatCard({ icon: Icon, label, value, sub, color, delay = 0 }: any) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.4 }}
      className="stat-card"
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-slate-500 font-medium">{label}</p>
          <p className="text-2xl font-bold text-slate-900 mt-1">{value}</p>
          {sub && <p className="text-xs text-slate-400 mt-1">{sub}</p>}
        </div>
        <div className="p-2.5 rounded-xl" style={{ background: `${color}15` }}>
          <Icon size={20} style={{ color }} />
        </div>
      </div>
    </motion.div>
  );
}

export default function DashboardPage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [showPublishModal, setShowPublishModal] = useState<GeneratedPost | null>(null);
  const [publishingId, setPublishingId] = useState<string | null>(null);
  const { data: analytics, isLoading } = useQuery<AnalyticsSummary>({
    queryKey: ['analytics'],
    queryFn: () => api.get('/api/v1/analytics/summary').then(r => r.data),
  });

  const { data: posts = [], isLoading: postsLoading } = useQuery<GeneratedPost[]>({
    queryKey: ['posts'],
    queryFn: () => api.get('/api/v1/posts').then(r => r.data),
    refetchInterval: 10000,
  });

  const scheduledPosts = posts.filter(p => p.status === 'scheduled' || (Boolean(p.scheduled_at) && p.status !== 'published'));

  const cancelScheduleMutation = useMutation({
    mutationFn: (postId: string) => api.put(`/api/v1/posts/${postId}/schedule`, { scheduled_at: null }).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['posts'] });
      toast.success('Scheduled post cancelled');
    },
    onError: () => toast.error('Failed to cancel scheduled post'),
  });

  const publishNowMutation = useMutation({
    mutationFn: ({ id, platform }: { id: string; platform?: string }) => {
      const url = platform ? `/api/v1/posts/${id}/publish?platform=${platform}` : `/api/v1/posts/${id}/publish`;
      return api.post(url).then(r => r.data);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['posts'] });
      qc.invalidateQueries({ queryKey: ['analytics'] });
      toast.success('Post published successfully!');
    },
    onError: (err: any) => toast.error(err?.response?.data?.detail || 'Failed to publish post right now'),
    onSettled: () => setPublishingId(null),
  });

  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';

  return (
    <div className="animate-fade-up">
      {/* Header */}
      <div className="page-header flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="page-title">
            {greeting}, {user?.full_name?.split(' ')[0] || 'there'} 👋
          </h1>
          <p className="page-subtitle">Here's what's happening with your social media</p>
        </div>
        <Link to="/generate" className="btn btn-primary">
          <Wand2 size={16} /> Quick Generate
        </Link>
      </div>

      {/* Stats grid */}
      {isLoading ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="stat-card">
              <Skeleton className="h-4 w-24 mb-2" />
              <Skeleton className="h-8 w-16" />
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <StatCard icon={CheckCircle} label="Published" value={analytics?.total_published ?? 0}
            sub="All time" color="#10B981" delay={0} />
          <StatCard icon={TrendingUp} label="Success Rate" value={`${analytics?.success_rate ?? 0}%`}
            sub="Of all posts" color="#2563EB" delay={0.05} />
          <StatCard icon={Calendar} label="Posts Today" value={analytics?.posts_today ?? 0}
            sub={`${analytics?.posts_this_week ?? 0} this week`} color="#6366F1" delay={0.1} />
          <StatCard icon={XCircle} label="Failed" value={analytics?.total_failed ?? 0}
            sub="With errors" color="#EF4444" delay={0.15} />
        </div>
      )}

      {/* Scheduled Posts Queue */}
      <div className="card mb-8 border-2 border-purple-200 dark:border-purple-900/40 bg-purple-50/10 dark:bg-purple-900/10">
        <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
          <h3 className="font-semibold text-slate-900 flex items-center gap-2 text-base">
            <Clock size={18} className="text-purple-600" />
            Scheduled Posts Queue ({scheduledPosts.length})
          </h3>
          <span className="badge badge-purple">Ready for Dispatch</span>
        </div>

        {postsLoading ? (
          <div className="space-y-3">
            {[1, 2].map(i => <div key={i} className="skeleton h-20 rounded-xl" />)}
          </div>
        ) : scheduledPosts.length === 0 ? (
          <div className="text-center py-6 bg-slate-50/60 rounded-xl border border-purple-100 dark:border-purple-900/30">
            <Clock size={24} className="mx-auto text-purple-400 mb-1.5" />
            <p className="font-medium text-slate-700 text-sm">No posts currently scheduled</p>
            <p className="text-xs text-slate-500 mt-0.5">Generate or upload a post in Quick Generate and hit "⏰ Schedule"</p>
          </div>
        ) : (
          <div className="space-y-3">
            {scheduledPosts.map(post => {
              const caption = post.platform === 'linkedin' ? post.linkedin_caption : (post.instagram_caption || post.linkedin_caption || post.headline);
              return (
                <div key={post.id} className="p-4 bg-slate-50 rounded-xl border border-purple-200 dark:border-purple-900/40 shadow-sm flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                  <div className="flex items-start gap-3.5 flex-1">
                    {post.image_url ? (
                      <img src={post.image_url} alt="Post preview" className="w-14 h-14 rounded-lg object-cover border border-slate-200 shrink-0" />
                    ) : (
                      <div className="w-14 h-14 rounded-lg bg-purple-100 flex items-center justify-center text-xl shrink-0">
                        {post.platform === 'linkedin' ? '💼' : '📸'}
                      </div>
                    )}
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="badge badge-purple flex items-center gap-1 text-xs">
                          <Clock size={11} />
                          Scheduled: {formatScheduledDate(post.scheduled_at)}
                        </span>
                        <span className="text-xs font-semibold uppercase px-2 py-0.5 rounded bg-slate-100 text-slate-700">
                          {post.platform}
                        </span>
                      </div>
                      <p className="text-xs text-slate-700 font-medium line-clamp-2">
                        {caption || post.headline || 'No caption text'}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 self-end md:self-center shrink-0">
                    <button
                      onClick={() => setShowPublishModal(post)}
                      disabled={publishingId === post.id}
                      className="btn btn-primary btn-sm flex items-center gap-1.5"
                    >
                      <Send size={13} /> {publishingId === post.id ? 'Publishing...' : 'Publish Now'}
                    </button>
                    <button
                      onClick={() => cancelScheduleMutation.mutate(post.id)}
                      disabled={cancelScheduleMutation.isPending}
                      className="btn btn-danger btn-sm flex items-center gap-1.5"
                    >
                      <XCircle size={13} /> Cancel
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Second row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Automation status */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }} className="card">
          <h3 className="font-semibold text-slate-900 mb-4 flex items-center gap-2">
            <Zap size={18} className="text-blue-500" /> Automation Status
          </h3>
          <div className="flex items-center gap-3 p-4 rounded-xl bg-slate-50">
            <div className={`status-dot ${analytics?.automation_status ? 'green' : 'gray'}`} />
            <div>
              <p className="font-semibold text-sm text-slate-900">
                {analytics?.automation_status ? 'Running' : 'Paused'}
              </p>
              <p className="text-xs text-slate-500">
                {analytics?.automation_status
                  ? 'Posts are being scheduled automatically'
                  : 'Enable automation in Scheduler settings'}
              </p>
            </div>
          </div>
          <Link to="/scheduler" className="btn btn-secondary w-full mt-4 btn-sm">
            Manage Scheduler <ArrowRight size={13} />
          </Link>
        </motion.div>

        {/* Connected platforms */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25 }} className="card">
          <h3 className="font-semibold text-slate-900 mb-4 flex items-center gap-2">
            <Link2 size={18} className="text-blue-500" /> Connected Accounts
          </h3>
          {isLoading ? (
            <div className="space-y-2"><Skeleton className="h-12 w-full" /><Skeleton className="h-12 w-full" /></div>
          ) : analytics?.connected_platforms?.length ? (
            <div className="space-y-2">
              {analytics.connected_platforms.map(p => (
                <div key={p} className="flex items-center gap-3 p-3 rounded-xl bg-slate-50">
                  <span className="status-dot green" />
                  <span className="text-sm font-medium capitalize text-slate-700">{p}</span>
                  <span className="badge badge-green ml-auto text-xs">Connected</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-6">
              <p className="text-sm text-slate-500 mb-3">No accounts connected yet</p>
              <Link to="/social" className="btn btn-primary btn-sm">Connect Now</Link>
            </div>
          )}
        </motion.div>

        {/* Top hashtags */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }} className="card">
          <h3 className="font-semibold text-slate-900 mb-4 flex items-center gap-2">
            <BarChart3 size={18} className="text-blue-500" /> Top Hashtags
          </h3>
          {isLoading ? (
            <div className="space-y-2">
              {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-8 w-full" />)}
            </div>
          ) : analytics?.top_hashtags?.length ? (
            <div className="space-y-2">
              {analytics.top_hashtags.slice(0, 5).map(({ tag, count }) => (
                <div key={tag} className="flex items-center gap-3">
                  <span className="text-sm text-slate-700 flex-1">#{tag}</span>
                  <span className="text-xs text-slate-400">{count}×</span>
                  <div className="h-1.5 w-16 bg-slate-100 rounded-full overflow-hidden">
                    <div className="h-full gradient-primary rounded-full"
                      style={{ width: `${Math.min(100, (count / (analytics.top_hashtags[0]?.count || 1)) * 100)}%` }} />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-500 text-center py-6">
              No hashtag data yet. Generate some posts first!
            </p>
          )}
        </motion.div>

      </div>

      {/* Quick actions row */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.35 }}
        className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Add Topics', icon: '🗂️', path: '/planner', desc: 'Manage your content ideas' },
          { label: 'Brand Setup', icon: '🎨', path: '/brand', desc: 'Configure brand identity' },
          { label: 'View History', icon: '📜', path: '/history', desc: 'See all published posts' },
          { label: 'Analytics', icon: '📊', path: '/analytics', desc: 'Track performance' },
        ].map(({ label, icon, path, desc }) => (
          <Link key={path} to={path} className="card hover:shadow-md transition-all hover:-translate-y-0.5 cursor-pointer block">
            <div className="text-2xl mb-2">{icon}</div>
            <p className="font-semibold text-sm text-slate-900">{label}</p>
            <p className="text-xs text-slate-500 mt-0.5">{desc}</p>
          </Link>
        ))}
      </motion.div>

      <PublishAccountModal
        isOpen={!!showPublishModal}
        onClose={() => setShowPublishModal(null)}
        onConfirm={(platform) => {
          if (showPublishModal) {
            setPublishingId(showPublishModal.id);
            publishNowMutation.mutate({ id: showPublishModal.id, platform });
            setShowPublishModal(null);
          }
        }}
        isPublishing={!!publishingId}
        initialPlatform={showPublishModal?.platform}
      />
    </div>
  );
}
