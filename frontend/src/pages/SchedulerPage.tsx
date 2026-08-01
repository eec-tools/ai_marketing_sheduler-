import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import { Zap, ZapOff, Clock, Calendar, Globe, Info, Send, XCircle, CheckCircle } from 'lucide-react';
import { Link } from 'react-router-dom';
import api from '@/lib/axios';
import type { Schedule, GeneratedPost } from '@/types';
import toast from 'react-hot-toast';
import { formatScheduledDate } from '@/lib/date';
import { PublishAccountModal } from '@/components/modals/PublishAccountModal';

export default function SchedulerPage() {
  const qc = useQueryClient();
  const [showPublishModal, setShowPublishModal] = useState<GeneratedPost | null>(null);
  const [publishingId, setPublishingId] = useState<string | null>(null);

  const { data: schedule, isLoading } = useQuery<Schedule>({
    queryKey: ['schedule'],
    queryFn: () => api.get('/api/v1/schedule').then(r => r.data).catch(() => null),
  });

  const { data: posts = [], isLoading: postsLoading } = useQuery<GeneratedPost[]>({
    queryKey: ['posts'],
    queryFn: () => api.get('/api/v1/posts').then(r => r.data),
    refetchInterval: 10000,
  });

  const scheduledPosts = posts.filter(p => p.status === 'scheduled' || (Boolean(p.scheduled_at) && p.status !== 'published'));

  const toggleMutation = useMutation({
    mutationFn: () => api.post('/api/v1/schedule/toggle').then(r => r.data),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['schedule'] });
      qc.invalidateQueries({ queryKey: ['analytics'] });
      toast.success(data.message);
    },
    onError: () => toast.error('Failed to toggle automation'),
  });

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

  const isActive = schedule?.is_active;

  if (isLoading) return (
    <div className="space-y-4">
      {[1, 2, 3].map(i => <div key={i} className="skeleton h-24 rounded-xl" />)}
    </div>
  );

  if (!schedule) return (
    <div className="animate-fade-up max-w-2xl">
      <div className="page-header">
        <h1 className="page-title">Scheduler</h1>
      </div>
      <div className="card text-center py-12">
        <Clock size={32} className="mx-auto text-slate-300 mb-3" />
        <p className="font-medium text-slate-600 mb-1">No schedule configured</p>
        <p className="text-sm text-slate-400 mb-4">Set up your posting schedule in Content Planner first</p>
        <Link to="/planner" className="btn btn-primary">Go to Content Planner</Link>
      </div>
    </div>
  );

  return (
    <div className="animate-fade-up max-w-2xl">
      <div className="page-header">
        <h1 className="page-title">Scheduler</h1>
        <p className="page-subtitle">Control your automated posting pipeline</p>
      </div>

      {/* Status card */}
      <motion.div
        initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
        className={`card mb-6 border-2 transition-all ${isActive ? 'border-green-200 bg-green-50/30' : 'border-slate-200'}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className={`w-14 h-14 rounded-2xl flex items-center justify-center
              ${isActive ? 'bg-green-100' : 'bg-slate-100'}`}>
              {isActive
                ? <Zap size={24} className="text-green-600" />
                : <ZapOff size={24} className="text-slate-400" />}
            </div>
            <div>
              <h3 className="font-bold text-lg text-slate-900">
                Automation {isActive ? 'Running' : 'Paused'}
              </h3>
              <p className="text-sm text-slate-500">
                {isActive
                  ? 'Posts will be generated and published automatically'
                  : 'Enable to start automatic posting'}
              </p>
            </div>
          </div>
          <button
            onClick={() => toggleMutation.mutate()}
            disabled={toggleMutation.isPending}
            className={`btn ${isActive ? 'btn-danger' : 'btn-primary'}`}>
            {toggleMutation.isPending ? 'Updating...' : isActive ? 'Pause' : 'Enable Automation'}
          </button>
        </div>
      </motion.div>

      {/* Pipeline visualization */}
      {isActive && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="card mb-6">
          <h3 className="font-semibold text-slate-900 mb-4">Active Pipeline</h3>
          <div className="flex items-center gap-2 flex-wrap">
            {[
              { step: '1', label: 'Check topics', icon: '📋', color: 'blue' },
              { step: '2', label: 'Generate text (Groq)', icon: '✍️', color: 'indigo' },
              { step: '3', label: 'Generate image (Gemini)', icon: '🎨', color: 'purple' },
              { step: '4', label: 'Review image', icon: '🔍', color: 'orange' },
              { step: '5', label: 'Publish', icon: '🚀', color: 'green' },
            ].map(({ step, label, icon }, i, arr) => (
              <React.Fragment key={step}>
                <div className="flex items-center gap-2 p-2.5 bg-slate-50 rounded-xl border border-slate-200">
                  <span className="text-lg">{icon}</span>
                  <span className="text-xs font-medium text-slate-600">{label}</span>
                </div>
                {i < arr.length - 1 && <span className="text-slate-300">→</span>}
              </React.Fragment>
            ))}
          </div>
        </motion.div>
      )}

      {/* Scheduled Posts Queue */}
      <div className="card border-2 border-purple-200 dark:border-purple-900/40 bg-purple-50/10 dark:bg-purple-900/10 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-slate-900 flex items-center gap-2">
            <Clock size={18} className="text-purple-600" />
            Scheduled Posts Queue ({scheduledPosts.length})
          </h3>
          <span className="badge badge-purple">Automatic Dispatch</span>
        </div>

        {postsLoading ? (
          <div className="space-y-3">
            {[1, 2].map(i => <div key={i} className="skeleton h-20 rounded-xl" />)}
          </div>
        ) : scheduledPosts.length === 0 ? (
          <div className="text-center py-8 bg-slate-50/60 rounded-xl border border-purple-100 dark:border-purple-900/30">
            <Clock size={24} className="mx-auto text-purple-400 mb-1.5" />
            <p className="font-medium text-slate-700 text-sm">No posts scheduled right now</p>
            <p className="text-xs text-slate-500 mt-1">Generate or upload a post in the AI Generator tab and click "⏰ Schedule"</p>
            <Link to="/generate" className="btn btn-primary btn-sm mt-3 inline-block">Go to AI Generator</Link>
          </div>
        ) : (
          <div className="space-y-3">
            {scheduledPosts.map(post => {
              const caption = post.platform === 'linkedin' ? post.linkedin_caption : (post.instagram_caption || post.linkedin_caption || post.headline);
              return (
                <div key={post.id} className="p-4 bg-white rounded-xl border border-purple-200 shadow-sm flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
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
                          Scheduled for: {formatScheduledDate(post.scheduled_at)}
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

      {/* Schedule details */}
      <div className="card">
        <h3 className="font-semibold text-slate-900 mb-4">Schedule Configuration</h3>
        <div className="space-y-3">
          {[
            { icon: Calendar, label: 'Frequency', value: schedule.frequency },
            {
              icon: Clock, label: 'Posting Times',
              value: schedule.posting_times?.join(', ') || 'None set'
            },
            { icon: Globe, label: 'Timezone', value: schedule.timezone },
            { icon: Info, label: 'Max posts/day', value: `${schedule.max_posts_day} posts` },
            {
              icon: Info, label: 'Platforms',
              value: schedule.platforms?.join(', ') || 'None selected'
            },
          ].map(({ icon: Icon, label, value }) => (
            <div key={label} className="flex items-center gap-3 py-3 border-b border-slate-100 last:border-0">
              <Icon size={16} className="text-slate-400 shrink-0" />
              <span className="text-sm text-slate-500 w-36">{label}</span>
              <span className="text-sm font-medium text-slate-900 capitalize">{value}</span>
            </div>
          ))}
        </div>
        <Link to="/planner" className="btn btn-secondary w-full mt-4 btn-sm">
          Edit Schedule in Content Planner
        </Link>
      </div>

      {isActive && (
        <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-xl flex gap-3 items-start">
          <Info size={16} className="text-blue-600 mt-0.5 shrink-0" />
          <p className="text-sm text-blue-700">
            The scheduler checks every 60 seconds for posts that are due. It runs completely unattended —
            just make sure you have unused topics and connected social accounts.
          </p>
        </div>
      )}

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
