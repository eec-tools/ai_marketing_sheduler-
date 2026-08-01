import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import { Plus, Trash2, Sparkles, Upload, Check, Clock, Bot, FileText, Send, XCircle } from 'lucide-react';
import api from '@/lib/axios';
import type { Topic, Schedule, GeneratedPost } from '@/types';
import toast from 'react-hot-toast';
import { formatScheduledDate } from '@/lib/date';
import { PublishAccountModal } from '@/components/modals/PublishAccountModal';
import { useMemoryState } from '@/hooks/useMemoryState';

const TIMEZONES = ['UTC', 'Asia/Kolkata', 'America/New_York', 'America/Los_Angeles', 'Europe/London', 'Europe/Paris', 'Asia/Dubai', 'Asia/Singapore'];

export default function ContentPlannerPage() {
  const qc = useQueryClient();
  const [showPublishModal, setShowPublishModal] = useState<GeneratedPost | null>(null);
  const [publishingId, setPublishingId] = useState<string | null>(null);
  const [newTopic, setNewTopic] = useMemoryState('planner_newTopic', '');
  const [newCategory, setNewCategory] = useMemoryState('planner_newCategory', '');
  const [generating, setGenerating] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [tab, setTab] = useMemoryState<'topics' | 'schedule'>('planner_tab', 'topics');
  const [schedule, setSchedule] = useMemoryState<Partial<Schedule>>('planner_schedule', {
    frequency: 'daily', posting_times: ['09:00', '18:00'], timezone: 'UTC',
    max_posts_day: 2, categories: [], platforms: ['linkedin'],
  });

  const { data: topics = [], isLoading: topicsLoading } = useQuery<Topic[]>({
    queryKey: ['topics'],
    queryFn: () => api.get('/api/v1/topics').then(r => r.data),
  });

  const { data: savedSchedule } = useQuery<Schedule>({
    queryKey: ['schedule'],
    queryFn: () => api.get('/api/v1/schedule').then(r => r.data).catch(() => null),
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

  const addTopicMutation = useMutation({
    mutationFn: (data: any) => api.post('/api/v1/topics', data).then(r => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['topics'] }); setNewTopic(''); toast.success('Topic added!'); },
  });

  const deleteTopicMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/api/v1/topics/${id}`).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['topics'] }),
  });

  const deleteAllTopicsMutation = useMutation({
    mutationFn: () => api.delete('/api/v1/topics/bulk-delete').then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['topics'] });
      setShowDeleteConfirm(false);
      toast.success('All topics deleted!');
    },
    onError: () => toast.error('Failed to delete all topics'),
  });

  const schedMutation = useMutation({
    mutationFn: (data: any) => api.put('/api/v1/schedule', data).then(r => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['schedule'] }); toast.success('Schedule saved!'); },
  });

  const generateTopics = async () => {
    setGenerating(true);
    try {
      const result = await api.post('/api/v1/topics/generate', { count: 5, category: newCategory || null }).then(r => r.data);
      qc.invalidateQueries({ queryKey: ['topics'] });
      toast.success(`Generated ${result.length} new topics!`);
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Generation failed. Check your Groq API key.');
    } finally { setGenerating(false); }
  };

  const handleCSVUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const formData = new FormData();
    formData.append('file', file);
    try {
      const result = await api.post('/api/v1/topics/import', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      }).then(r => r.data);
      qc.invalidateQueries({ queryKey: ['topics'] });
      toast.success(`Imported ${result.length} topics from CSV!`);
    } catch { toast.error('CSV import failed'); }
  };

  const addTime = () => {
    const times = schedule.posting_times || [];
    if (times.length < 6) setSchedule(s => ({ ...s, posting_times: [...times, '12:00'] }));
  };

  const updateTime = (i: number, v: string) => {
    const times = [...(schedule.posting_times || [])];
    times[i] = v;
    setSchedule(s => ({ ...s, posting_times: times }));
  };

  const removeTime = (i: number) => {
    setSchedule(s => ({ ...s, posting_times: s.posting_times?.filter((_, idx) => idx !== i) }));
  };

  const unused = topics.filter(t => !t.is_used).length;

  return (
    <div className="animate-fade-up max-w-3xl">
      <div className="page-header">
        <h1 className="page-title">Content Planner</h1>
        <p className="page-subtitle">Manage your topics and posting schedule</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 p-1 bg-slate-100 rounded-xl mb-6 w-fit">
        {[
          { id: 'topics', label: 'Topics', icon: FileText },
          { id: 'schedule', label: 'Schedule', icon: Clock },
        ].map(({ id, label, icon: Icon }) => (
          <button key={id} onClick={() => setTab(id as any)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all
              ${tab === id ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}>
            <Icon size={14} /> {label}
          </button>
        ))}
      </div>

      {tab === 'topics' && (
        <div>
          {/* Add topic */}
          <div className="card mb-4">
            <h3 className="font-semibold text-slate-900 mb-3">Add Topics</h3>
            <div className="flex gap-2 mb-3">
              <input className="input flex-1" value={newTopic}
                onChange={e => setNewTopic(e.target.value)}
                placeholder="Enter a topic idea..."
                onKeyDown={e => { if (e.key === 'Enter' && newTopic.trim()) addTopicMutation.mutate({ topic: newTopic.trim(), category: newCategory || null }); }} />
              <input className="input w-32" value={newCategory}
                onChange={e => setNewCategory(e.target.value)} placeholder="Category" />
              <button onClick={() => addTopicMutation.mutate({ topic: newTopic.trim(), category: newCategory || null })}
                disabled={!newTopic.trim() || addTopicMutation.isPending}
                className="btn btn-primary btn-sm"><Plus size={15} /></button>
            </div>
            <div className="flex gap-2">
              <button onClick={generateTopics} disabled={generating} className="btn btn-secondary btn-sm flex-1">
                {generating
                  ? <><div className="w-3 h-3 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" /> Generating...</>
                  : <><Sparkles size={14} /> AI Generate (5 topics)</>}
              </button>
              <label className="btn btn-secondary btn-sm flex-1 cursor-pointer text-center">
                <Upload size={14} /> Import CSV
                <input type="file" accept=".csv" className="hidden" onChange={handleCSVUpload} />
              </label>
            </div>
          </div>

          {/* Topic stats + delete all */}
          <div className="flex items-center justify-between mb-4">
            <div className="flex gap-3">
              <div className="badge badge-blue">{topics.length} Total</div>
              <div className="badge badge-green">{unused} Unused</div>
              <div className="badge badge-gray">{topics.length - unused} Used</div>
            </div>
            {topics.length > 0 && !showDeleteConfirm && (
              <button
                onClick={() => setShowDeleteConfirm(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-red-600 border border-red-200 rounded-lg hover:bg-red-50 hover:border-red-300 transition-all"
              >
                <Trash2 size={13} /> Delete All
              </button>
            )}
          </div>

          {/* Inline delete confirmation — replaces window.confirm */}
          {showDeleteConfirm && (
            <div className="mb-4 flex items-center justify-between gap-3 px-4 py-3 bg-red-50 border border-red-200 rounded-xl">
              <p className="text-sm text-red-700 font-medium">
                ⚠️ Delete all <strong>{topics.length}</strong> topics? This cannot be undone.
              </p>
              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={() => setShowDeleteConfirm(false)}
                  disabled={deleteAllTopicsMutation.isPending}
                  className="px-3 py-1.5 text-xs font-medium text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-100 transition-all"
                >
                  Cancel
                </button>
                <button
                  onClick={() => deleteAllTopicsMutation.mutate()}
                  disabled={deleteAllTopicsMutation.isPending}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-white bg-red-500 rounded-lg hover:bg-red-600 transition-all disabled:opacity-60"
                >
                  {deleteAllTopicsMutation.isPending
                    ? <><div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" /> Deleting...</>
                    : <><Trash2 size={13} /> Yes, Delete All</>}
                </button>
              </div>
            </div>
          )}

          {/* Topic list */}
          {topicsLoading ? (
            <div className="space-y-2">{[...Array(5)].map((_, i) => <div key={i} className="skeleton h-14 rounded-xl" />)}</div>
          ) : topics.length === 0 ? (
            <div className="card text-center py-12">
              <Bot size={32} className="mx-auto text-slate-300 mb-3" />
              <p className="font-medium text-slate-600 mb-1">No topics yet</p>
              <p className="text-sm text-slate-400">Add topics manually or let AI generate them</p>
            </div>
          ) : (
            <div className="space-y-2">
              {topics.map((topic, i) => (
                <motion.div key={topic.id}
                  initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.03 }}
                  className={`flex items-center gap-3 p-3 rounded-xl border transition-all
                    ${topic.is_used ? 'border-slate-100 bg-slate-50 opacity-60' : 'border-slate-200 bg-white hover:border-blue-200'}`}>
                  {topic.is_used
                    ? <Check size={14} className="text-green-500 shrink-0" />
                    : <div className="w-3.5 h-3.5 rounded-full border-2 border-slate-300 shrink-0" />}
                  <p className={`flex-1 text-sm ${topic.is_used ? 'line-through text-slate-400' : 'text-slate-700'}`}>
                    {topic.topic}
                  </p>
                  {topic.category && <span className="badge badge-gray text-xs">{topic.category}</span>}
                  <span className={`badge text-xs ${topic.source === 'ai' ? 'badge-purple' : topic.source === 'csv' ? 'badge-blue' : 'badge-gray'}`}>
                    {topic.source}
                  </span>
                  <button onClick={() => deleteTopicMutation.mutate(topic.id)}
                    className="text-slate-300 hover:text-red-400 transition-colors p-1">
                    <Trash2 size={13} />
                  </button>
                </motion.div>
              ))}
            </div>
          )}
        </div>
      )}

      {tab === 'schedule' && (
        <div className="space-y-6">
          {/* Scheduled Posts Queue */}
          <div className="card mb-6 border-2 border-purple-200 dark:border-purple-900/40 bg-purple-50/10 dark:bg-purple-900/10">
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
              <div className="text-center py-6 bg-slate-50/60 rounded-xl border border-purple-100 dark:bg-slate-800/40 dark:border-purple-900/30">
                <Clock size={24} className="mx-auto text-purple-400 mb-1.5" />
                <p className="font-medium text-slate-700 text-sm">No posts currently scheduled</p>
                <p className="text-xs text-slate-500 mt-0.5">Generate or upload a post in AI Generator and hit "⏰ Schedule"</p>
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

          <div className="card">
            <h3 className="font-semibold text-slate-900 mb-4">Posting Schedule</h3>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">Frequency</label>
                <select className="input" value={schedule.frequency}
                  onChange={e => setSchedule(s => ({ ...s, frequency: e.target.value as any }))}>
                  <option value="daily">Daily</option>
                  <option value="weekly">Weekly</option>
                  <option value="custom">Custom</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">Max posts/day</label>
                <input type="number" min={1} max={20} className="input" value={schedule.max_posts_day}
                  onChange={e => setSchedule(s => ({ ...s, max_posts_day: parseInt(e.target.value) }))} />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Timezone</label>
              <select className="input" value={schedule.timezone}
                onChange={e => setSchedule(s => ({ ...s, timezone: e.target.value }))}>
                {TIMEZONES.map(tz => <option key={tz}>{tz}</option>)}
              </select>
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-sm font-medium text-slate-700">Posting Times</label>
                <button onClick={addTime} className="btn btn-ghost btn-sm text-blue-600">
                  <Plus size={13} /> Add time
                </button>
              </div>
              <div className="space-y-2">
                {(schedule.posting_times || []).map((time, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <input type="time" className="input flex-1" value={time}
                      onChange={e => updateTime(i, e.target.value)} />
                    <button onClick={() => removeTime(i)} className="text-slate-400 hover:text-red-400 p-1">
                      <Trash2 size={13} />
                    </button>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">Platforms</label>
              <div className="flex gap-2">
                {['linkedin', 'instagram'].map(p => (
                  <button key={p} onClick={() => {
                    const plats = schedule.platforms || [];
                    setSchedule(s => ({
                      ...s,
                      platforms: plats.includes(p) ? plats.filter(x => x !== p) : [...plats, p]
                    }));
                  }}
                    className={`px-4 py-2 rounded-xl text-sm font-medium border transition-all capitalize ${
                      (schedule.platforms || []).includes(p)
                        ? 'border-blue-500 bg-blue-50 text-blue-700'
                        : 'border-slate-200 text-slate-500 hover:border-slate-300'}`}>
                    {p}
                  </button>
                ))}
              </div>
            </div>

            <button onClick={() => schedMutation.mutate(schedule)} disabled={schedMutation.isPending}
              className="btn btn-primary w-full">
              {schedMutation.isPending ? 'Saving...' : 'Save Schedule'}
            </button>
          </div>
          </div>
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
