import React, { useState } from 'react';
import { createPortal } from 'react-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import {
  CheckCircle, Clock, Send, XCircle, Trash2, Calendar
} from 'lucide-react';
import api from '@/lib/axios';
import type { GeneratedPost, HistoryItem } from '@/types';
import toast from 'react-hot-toast';
import { formatScheduledDate } from '@/lib/date';
import { PublishAccountModal } from '@/components/modals/PublishAccountModal';

export default function PublishedPage() {
  const qc = useQueryClient();
  const [activeTab, setActiveTab] = useState<'all' | 'scheduled' | 'published'>('all');
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [publishingId, setPublishingId] = useState<string | null>(null);
  const [showDeleteModal, setShowDeleteModal] = useState<string | null>(null);
  const [showPublishModal, setShowPublishModal] = useState<GeneratedPost | null>(null);

  // Fetch all posts to extract scheduled and published posts from GeneratedPost
  const { data: allPosts = [], isLoading: postsLoading } = useQuery<GeneratedPost[]>({
    queryKey: ['posts'],
    queryFn: () => api.get('/api/v1/posts').then(r => r.data),
    refetchInterval: 5000,
  });

  // Also fetch publishing history for records that completed
  const { data: historyItems = [], isLoading: historyLoading } = useQuery<HistoryItem[]>({
    queryKey: ['history'],
    queryFn: () => api.get('/api/v1/history', { params: { limit: 50 } }).then(r => r.data),
  });

  const scheduledPosts = allPosts.filter(p => p.status === 'scheduled');
  const publishedPosts = allPosts.filter(p => p.status === 'published');

  // Mutations
  const publishNowMutation = useMutation({
    mutationFn: ({ id, platform }: { id: string; platform?: string }) => {
      const url = platform ? `/api/v1/posts/${id}/publish?platform=${platform}` : `/api/v1/posts/${id}/publish`;
      return api.post(url).then(r => r.data);
    },
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ['posts'] });
      qc.invalidateQueries({ queryKey: ['history'] });
      toast.success(res.message || 'Published successfully!');
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Publishing failed'),
    onSettled: () => setPublishingId(null),
  });

  const cancelScheduleMutation = useMutation({
    mutationFn: (id: string) => api.put(`/api/v1/posts/${id}/schedule`, { scheduled_at: null }).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['posts'] });
      toast.success('Schedule cancelled');
    },
    onError: () => toast.error('Failed to cancel schedule'),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/api/v1/posts/${id}`).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['posts'] });
      toast.success('Post deleted');
    },
    onError: () => toast.error('Failed to delete post'),
    onSettled: () => setDeletingId(null),
  });

  const confirmDelete = (id: string) => {
    setDeletingId(id);
    deleteMutation.mutate(id);
    setShowDeleteModal(null);
  };

  const isLoading = postsLoading || historyLoading;

  return (
    <div className="animate-fade-up space-y-6">
      <div className="page-header">
        <h1 className="page-title">Published & Scheduled Studio</h1>
        <p className="page-subtitle">Manage all your upcoming scheduled posts and track published content across platforms</p>
      </div>

      {/* Tabs / Filters */}
      <div className="flex gap-2 p-1.5 bg-slate-100 rounded-2xl w-fit">
        <button
          onClick={() => setActiveTab('all')}
          className={`px-5 py-2 rounded-xl font-semibold text-sm transition-all ${
            activeTab === 'all'
              ? 'bg-white text-blue-600 shadow-sm'
              : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          All ({scheduledPosts.length + publishedPosts.length + historyItems.length})
        </button>
        <button
          onClick={() => setActiveTab('scheduled')}
          className={`flex items-center gap-2 px-5 py-2 rounded-xl font-semibold text-sm transition-all ${
            activeTab === 'scheduled'
              ? 'bg-white text-purple-600 shadow-sm'
              : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          <Clock size={15} /> Scheduled ({scheduledPosts.length})
        </button>
        <button
          onClick={() => setActiveTab('published')}
          className={`flex items-center gap-2 px-5 py-2 rounded-xl font-semibold text-sm transition-all ${
            activeTab === 'published'
              ? 'bg-white text-green-600 shadow-sm'
              : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          <CheckCircle size={15} /> Published ({publishedPosts.length + historyItems.length})
        </button>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="skeleton h-64 rounded-2xl" />
          ))}
        </div>
      ) : (
        <div className="space-y-8">
          {/* Scheduled Section */}
          {(activeTab === 'all' || activeTab === 'scheduled') && (
            <div>
              <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2 mb-4">
                <Clock size={18} className="text-purple-600" />
                Upcoming Scheduled Posts ({scheduledPosts.length})
              </h2>

              {scheduledPosts.length === 0 ? (
                <div className="card text-center py-10 border-dashed">
                  <Calendar size={32} className="mx-auto text-slate-300 mb-2" />
                  <p className="font-medium text-slate-600 text-sm">No upcoming scheduled posts</p>
                  <p className="text-xs text-slate-400 mt-0.5">Schedule posts from the AI Generator tab</p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {scheduledPosts.map(post => {
                    const caption = post.platform === 'linkedin' ? post.linkedin_caption : post.instagram_caption;
                    return (
                      <motion.div
                        key={post.id}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="card border-2 border-purple-100 flex flex-col justify-between"
                      >
                        <div>
                          <div className="flex items-center justify-between mb-3">
                            <div className="flex items-center gap-2">
                              <span className="text-lg">{post.platform === 'linkedin' ? '💼' : '📸'}</span>
                              <span className="font-semibold text-slate-900 capitalize">{post.platform}</span>
                            </div>
                            <span className="badge badge-purple flex items-center gap-1">
                              <Clock size={11} /> Scheduled
                            </span>
                          </div>

                          <div className="p-2.5 mb-3 bg-purple-50 border border-purple-200 rounded-xl text-xs font-semibold text-purple-900 flex items-center justify-between">
                            <span className="flex items-center gap-1.5">
                              <Calendar size={13} className="text-purple-600" />
                              Going live:
                            </span>
                            <span>{formatScheduledDate(post.scheduled_at)}</span>
                          </div>

                          {post.headline && (
                            <h4 className="font-bold text-slate-900 mb-1.5 text-sm">{post.headline}</h4>
                          )}
                          <p className="text-xs text-slate-600 line-clamp-3 mb-3 bg-slate-50 p-2.5 rounded-xl border border-slate-100 font-mono">
                            {caption || 'No caption provided'}
                          </p>

                          {post.image_url && (
                            <div className="rounded-xl overflow-hidden mb-3 border border-slate-100 max-h-48 bg-slate-50">
                              <img src={post.image_url} alt="Scheduled post" className="w-full h-auto object-cover" />
                            </div>
                          )}
                        </div>

                        <div className="flex items-center gap-2 pt-2 border-t border-slate-100">
                          <button
                            onClick={() => setShowPublishModal(post)}
                            disabled={publishingId === post.id}
                            className="btn btn-primary btn-sm flex-1 flex items-center justify-center gap-1.5 text-xs"
                          >
                            <Send size={13} />
                            {publishingId === post.id ? 'Publishing...' : 'Publish Now'}
                          </button>
                          <button
                            onClick={() => cancelScheduleMutation.mutate(post.id)}
                            disabled={cancelScheduleMutation.isPending}
                            className="btn btn-secondary btn-sm flex items-center gap-1.5 text-xs text-slate-700"
                            title="Revert to draft"
                          >
                            <XCircle size={13} /> Cancel
                          </button>
                          <button
                            onClick={() => setShowDeleteModal(post.id)}
                            className="p-2 rounded-xl text-slate-400 hover:text-red-600 hover:bg-red-50 transition-colors"
                            title="Delete post"
                          >
                            <Trash2 size={15} />
                          </button>
                        </div>
                      </motion.div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* Published Section */}
          {(activeTab === 'all' || activeTab === 'published') && (
            <div>
              <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2 mb-4">
                <CheckCircle size={18} className="text-green-600" />
                Published Posts ({publishedPosts.length + historyItems.length})
              </h2>

              {publishedPosts.length === 0 && historyItems.length === 0 ? (
                <div className="card text-center py-10 border-dashed">
                  <CheckCircle size={32} className="mx-auto text-slate-300 mb-2" />
                  <p className="font-medium text-slate-600 text-sm">No published posts yet</p>
                  <p className="text-xs text-slate-400 mt-0.5">Posts that you publish will show up here permanently</p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {publishedPosts.map(post => {
                    const caption = post.platform === 'linkedin' ? post.linkedin_caption : post.instagram_caption;
                    return (
                      <motion.div
                        key={post.id}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="card border-2 border-green-100 flex flex-col justify-between"
                      >
                        <div>
                          <div className="flex items-center justify-between mb-3">
                            <div className="flex items-center gap-2">
                              <span className="text-lg">{post.platform === 'linkedin' ? '💼' : '📸'}</span>
                              <span className="font-semibold text-slate-900 capitalize">{post.platform}</span>
                            </div>
                            <span className="badge badge-green flex items-center gap-1">
                              <CheckCircle size={11} /> Published
                            </span>
                          </div>

                          {post.headline && (
                            <h4 className="font-bold text-slate-900 mb-1.5 text-sm">{post.headline}</h4>
                          )}
                          <p className="text-xs text-slate-600 line-clamp-3 mb-3 bg-slate-50 p-2.5 rounded-xl border border-slate-100 font-mono">
                            {caption || 'No caption provided'}
                          </p>

                          {post.image_url && (
                            <div className="rounded-xl overflow-hidden mb-3 border border-slate-100 max-h-48 bg-slate-50">
                              <img src={post.image_url} alt="Published post" className="w-full h-auto object-cover" />
                            </div>
                          )}
                        </div>

                        <div className="flex items-center justify-between pt-2 border-t border-slate-100 text-xs text-slate-400">
                          <span>Published from AI Generator</span>
                          <button
                            onClick={() => setShowDeleteModal(post.id)}
                            className="p-1.5 rounded-lg hover:text-red-600 hover:bg-red-50 transition-colors"
                            title="Delete post record"
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </motion.div>
                    );
                  })}

                  {historyItems.map(item => (
                    <motion.div
                      key={item.id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className={`card border-2 ${
                        item.status === 'published' ? 'border-green-100' : 'border-red-100'
                      } flex flex-col justify-between`}
                    >
                      <div>
                        <div className="flex items-center justify-between mb-3">
                          <div className="flex items-center gap-2">
                            <span className="text-lg">{item.platform === 'linkedin' ? '💼' : '📸'}</span>
                            <span className="font-semibold text-slate-900 capitalize">{item.platform}</span>
                          </div>
                          <span className={`badge ${item.status === 'published' ? 'badge-green' : 'badge-red'} flex items-center gap-1`}>
                            {item.status === 'published' ? <CheckCircle size={11} /> : <XCircle size={11} />}
                            {item.status}
                          </span>
                        </div>

                        <div className="text-xs text-slate-400 mb-2">
                          {new Date(item.published_at).toLocaleString()}
                        </div>

                        {item.caption_preview && (
                          <p className="text-xs text-slate-600 line-clamp-3 mb-3 bg-slate-50 p-2.5 rounded-xl border border-slate-100 font-mono">
                            {item.caption_preview}
                          </p>
                        )}

                        {item.image_url && (
                          <div className="rounded-xl overflow-hidden mb-3 border border-slate-100 max-h-48 bg-slate-50">
                            <img src={item.image_url} alt="History image" className="w-full h-auto object-cover" />
                          </div>
                        )}
                      </div>

                      <div className="pt-2 border-t border-slate-100 text-xs text-slate-400 flex justify-between items-center">
                        <span>History Record</span>
                      </div>
                    </motion.div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Confirmation Modal */}
      {showDeleteModal && createPortal(
        <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fade-in">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="bg-white rounded-2xl shadow-2xl border border-slate-200 p-6 max-w-sm w-full text-center space-y-4"
          >
            <div className="w-14 h-14 bg-red-100 text-red-600 rounded-full flex items-center justify-center mx-auto shadow-inner">
              <Trash2 size={28} />
            </div>
            <div>
              <h3 className="text-xl font-extrabold text-slate-900">Delete Post?</h3>
              <p className="text-sm text-slate-500 mt-1.5 leading-relaxed">
                Are you sure you want to delete this post record? This action cannot be undone.
              </p>
            </div>
            <div className="flex gap-3 pt-3">
              <button
                onClick={() => setShowDeleteModal(null)}
                disabled={!!deletingId}
                className="btn btn-secondary flex-1 py-2.5 font-bold"
              >
                Cancel
              </button>
              <button
                onClick={() => confirmDelete(showDeleteModal)}
                disabled={!!deletingId}
                className="btn btn-danger flex-1 py-2.5 font-bold flex items-center justify-center gap-2 shadow-lg shadow-red-500/20"
              >
                <Trash2 size={16} />
                {deletingId ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </motion.div>
        </div>,
        document.body
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
