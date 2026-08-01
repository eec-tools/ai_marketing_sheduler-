import React, { useState } from 'react';
import { createPortal } from 'react-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Wand2, Send, RefreshCw, CheckCircle, XCircle, Clock,
  Copy, Sparkles, Image as ImageIcon, Upload, Calendar, Trash2, MoreVertical
} from 'lucide-react';
import api from '@/lib/axios';
import type { Topic, GeneratedPost } from '@/types';
import toast from 'react-hot-toast';
import { toLocalDatetimeInput, formatScheduledDate } from '@/lib/date';
import { PublishAccountModal } from '@/components/modals/PublishAccountModal';
import { useMemoryState } from '@/hooks/useMemoryState';

function PostCard({
  post,
  onPublish,
  publishing,
  onSchedule,
  scheduling,
  onDelete,
  deleting
}: {
  post: GeneratedPost;
  onPublish: (id: string, platform?: string) => void;
  publishing: boolean;
  onSchedule: (id: string, dateStr: string | null) => void;
  scheduling: boolean;
  onDelete: (id: string) => void;
  deleting: boolean;
}) {
  const qc = useQueryClient();
  const [showMenu, setShowMenu] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [showPublishModal, setShowPublishModal] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);
  const [showScheduleModal, setShowScheduleModal] = useState(false);
  const [scheduleDateInput, setScheduleDateInput] = useState(
    toLocalDatetimeInput(post.scheduled_at)
  );
  const caption = post.platform === 'linkedin' ? post.linkedin_caption : post.instagram_caption;
  const [isEditing, setIsEditing] = useState(false);
  const [editedHeadline, setEditedHeadline] = useState(post.headline || '');
  const [editedCaption, setEditedCaption] = useState(caption || '');

  const updateMutation = useMutation({
    mutationFn: (data: any) => api.put(`/api/v1/posts/${post.id}`, data).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['posts'] });
      setIsEditing(false);
      toast.success('Caption updated successfully!');
    },
    onError: () => toast.error('Failed to update caption'),
  });

  const copy = (text: string, key: string) => {
    navigator.clipboard.writeText(text);
    setCopied(key);
    setTimeout(() => setCopied(null), 2000);
  };

  const isPendingExtension = post.image_review_result === 'PENDING_EXTENSION';

  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
      className="card border-2 border-blue-100 flex flex-col justify-between">
      <div>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <span className="text-lg">{post.platform === 'linkedin' ? '💼' : '📸'}</span>
            <span className="font-semibold text-slate-900 capitalize">{post.platform}</span>
          </div>
          <div className="flex items-center gap-2">
            {post.image_review_result === 'PASS' && <span className="badge badge-green"><CheckCircle size={10} /> Image OK</span>}
            {post.image_review_result === 'FAIL' && <span className="badge badge-red"><XCircle size={10} /> Review Failed</span>}
            {isPendingExtension && (
              <span className="badge badge-yellow flex items-center gap-1.5 animate-pulse">
                <Clock size={11} /> ChatGPT Drawing...
              </span>
            )}
            {!isPendingExtension && post.image_review_result === 'PENDING' && <span className="badge badge-yellow"><Clock size={10} /> Pending</span>}
            <span className={`badge ${
              post.status === 'published' ? 'badge-green'
              : post.status === 'approved' ? 'badge-blue'
              : post.status === 'scheduled' ? 'badge-purple'
              : post.status === 'failed' ? 'badge-red' : 'badge-gray'}`}>
              {post.status}
            </span>

            <div className="relative">
              <button
                onClick={() => setShowMenu(!showMenu)}
                className="p-1.5 rounded-xl text-slate-500 hover:text-red-600 hover:bg-red-50 border border-transparent hover:border-red-200 transition-all ml-1"
                title="Post Options"
              >
                <MoreVertical size={18} />
              </button>
              {showMenu && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setShowMenu(false)} />
                  <div className="absolute right-0 mt-1 w-48 bg-white rounded-xl shadow-xl border border-slate-200 py-1.5 z-50 animate-fade-in">
                    <label className="w-full px-3.5 py-2 text-left text-xs font-bold text-blue-600 hover:bg-blue-50 flex items-center gap-2 transition-colors cursor-pointer">
                      <ImageIcon size={14} />
                      Replace Image
                      <input 
                        type="file" 
                        accept="image/*" 
                        className="hidden" 
                        onChange={(e) => {
                          setShowMenu(false);
                          const file = e.target.files?.[0];
                          if (!file) return;
                          if (file.size > 5 * 1024 * 1024) {
                            toast.error('Image must be under 5MB');
                            return;
                          }
                          const reader = new FileReader();
                          reader.onload = (ev) => {
                            const dataUri = ev.target?.result as string;
                            const loadingToast = toast.loading('Uploading image...');
                            api.put(`/api/v1/posts/${post.id}`, { image_url: dataUri })
                              .then(() => {
                                toast.success('Image replaced successfully!', { id: loadingToast });
                                qc.invalidateQueries({ queryKey: ['posts'] });
                              })
                              .catch(() => toast.error('Failed to replace image', { id: loadingToast }));
                          };
                          reader.readAsDataURL(file);
                        }} 
                      />
                    </label>
                    <button
                      onClick={() => { setShowMenu(false); setShowDeleteModal(true); }}
                      disabled={deleting}
                      className="w-full px-3.5 py-2 text-left text-xs font-bold text-red-600 hover:bg-red-50 flex items-center gap-2 transition-colors"
                    >
                      <Trash2 size={14} />
                      {deleting ? 'Deleting...' : 'Delete Post'}
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>

        {post.scheduled_at && post.status !== 'published' && (
          <div className="flex items-center justify-between p-2.5 mb-3 bg-purple-50 border border-purple-200 rounded-xl text-xs font-medium text-purple-900">
            <span className="flex items-center gap-1.5">
              <Clock size={13} className="text-purple-600" />
              Scheduled: <b>{formatScheduledDate(post.scheduled_at)}</b>
            </span>
            <button
              onClick={() => onSchedule(post.id, null)}
              disabled={scheduling}
              className="text-red-600 hover:underline font-semibold"
            >
              Cancel
            </button>
          </div>
        )}

        {isEditing ? (
          <div className="space-y-3 mb-4 p-3 bg-blue-50/50 border border-blue-200 rounded-xl">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Headline</label>
              <input
                className="input text-sm font-semibold"
                value={editedHeadline}
                onChange={e => setEditedHeadline(e.target.value)}
                placeholder="Post headline"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Caption</label>
              <textarea
                className="input min-h-[140px] text-sm font-sans"
                value={editedCaption}
                onChange={e => setEditedCaption(e.target.value)}
                placeholder="Post caption text..."
              />
            </div>
            <div className="flex justify-end gap-2 pt-1">
              <button
                onClick={() => setIsEditing(false)}
                className="btn btn-secondary btn-sm text-xs"
              >
                Cancel
              </button>
              <button
                onClick={() => updateMutation.mutate({
                  headline: editedHeadline,
                  [post.platform === 'linkedin' ? 'linkedin_caption' : 'instagram_caption']: editedCaption,
                })}
                disabled={updateMutation.isPending}
                className="btn btn-primary btn-sm text-xs"
              >
                {updateMutation.isPending ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </div>
        ) : (
          <>
            <div className="flex items-center justify-between mb-2">
              {post.headline ? (
                <h4 className="font-bold text-slate-900 text-lg flex-1">{post.headline}</h4>
              ) : <div className="flex-1" />}
              <button
                onClick={() => {
                  setEditedHeadline(post.headline || '');
                  setEditedCaption(caption || '');
                  setIsEditing(true);
                }}
                className="btn btn-ghost btn-sm text-blue-600 hover:bg-blue-50 flex items-center gap-1 text-xs shrink-0"
              >
                ✏️ Edit Caption
              </button>
            </div>

            {caption && (
              <div className="relative mb-3">
                <p className="text-sm text-slate-600 leading-relaxed whitespace-pre-line p-3 bg-slate-50 rounded-xl border max-h-64 overflow-y-auto">
                  {caption}
                </p>
                <button onClick={() => copy(caption, 'caption')}
                  className="absolute top-2 right-2 btn btn-ghost btn-sm text-xs">
                  {copied === 'caption' ? <><CheckCircle size={11} /> Copied</> : <><Copy size={11} /> Copy</>}
                </button>
              </div>
            )}
          </>
        )}

        {post.hashtags?.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-3">
            {post.hashtags.map(tag => {
              const cleanTag = tag.replace(/^#+/, '');
              return <span key={tag} className="badge badge-blue text-xs">#{cleanTag}</span>;
            })}
          </div>
        )}

        {post.cta && (
          <p className="text-sm text-blue-600 font-medium mb-3 flex items-center gap-1.5">
            <span>→</span> {post.cta}
          </p>
        )}

        {isPendingExtension && (
          <div className="mb-4 rounded-xl border-2 border-dashed border-amber-300 bg-amber-50/60 p-6 text-center">
            <div className="w-8 h-8 border-3 border-amber-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
            <p className="text-sm font-semibold text-amber-800">Generating with ChatGPT / DALL-E...</p>
            <p className="text-xs text-amber-600 mt-1">
              Keep your logged-in <b>chatgpt.com</b> tab open. The Chrome Extension is currently drawing this graphic and will automatically update this card when ready!
            </p>
          </div>
        )}

        {post.image_url && (
          <div className="mb-4 rounded-xl overflow-hidden border border-slate-200 bg-slate-900 flex items-center justify-center max-h-80 shadow-sm">
            <img
              src={post.image_url}
              alt="Generated post graphic"
              className="w-full h-auto object-cover max-h-80"
            />
          </div>
        )}

        {post.image_review_notes && (
          <p className="text-xs text-slate-400 mb-3 italic">{post.image_review_notes}</p>
        )}
      </div>

      <div>
        {post.status !== 'published' && (
          <div>
            <div className="flex gap-2 mt-2">
              <button onClick={() => setShowPublishModal(true)} disabled={publishing || post.status === 'failed' || isPendingExtension}
                className="btn btn-primary flex-1">
                {publishing ? 'Publishing...' : <><Send size={15} /> Publish Now</>}
              </button>
              <button onClick={() => setShowScheduleModal(!showScheduleModal)} disabled={scheduling || post.status === 'failed'}
                className="btn btn-secondary px-3.5" title="Schedule Post">
                <Clock size={15} />
              </button>
            </div>

            {showScheduleModal && (
              <div className="mt-3 p-3 bg-slate-50 border rounded-xl space-y-2.5 animate-fade-down">
                <label className="block text-xs font-semibold text-slate-700">Pick Schedule Date & Time</label>
                <input
                  type="datetime-local"
                  className="input text-xs py-1.5"
                  value={scheduleDateInput}
                  onChange={e => setScheduleDateInput(e.target.value)}
                />
                <div className="flex gap-2">
                  <button
                    onClick={() => {
                      if (!scheduleDateInput) { toast.error('Pick a date & time'); return; }
                      onSchedule(post.id, new Date(scheduleDateInput).toISOString());
                      setShowScheduleModal(false);
                    }}
                    disabled={scheduling || !scheduleDateInput}
                    className="btn btn-primary btn-sm flex-1 text-xs"
                  >
                    Set Schedule
                  </button>
                  <button onClick={() => setShowScheduleModal(false)} className="btn btn-ghost btn-sm text-xs">
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {post.status === 'published' && (
          <div className="flex items-center justify-center gap-2 p-3 bg-green-50 rounded-xl text-sm text-green-700 font-medium mt-2">
            <CheckCircle size={15} /> Published successfully!
          </div>
        )}
      </div>

      {showDeleteModal && createPortal(
        <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fade-in">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="bg-white rounded-2xl shadow-2xl border border-slate-200 p-6 max-w-sm w-full text-center space-y-4"
          >
            <div className="w-14 h-14 bg-red-100 text-red-600 rounded-full flex items-center justify-center mx-auto shadow-inner">
              <Trash2 size={26} />
            </div>
            <div>
              <h3 className="text-xl font-extrabold text-slate-900">Delete Post?</h3>
              <p className="text-sm text-slate-500 mt-1.5 leading-relaxed">
                Are you sure you want to permanently delete this post? This action cannot be undone.
              </p>
            </div>
            <div className="flex gap-3 pt-3">
              <button
                onClick={() => setShowDeleteModal(false)}
                disabled={deleting}
                className="btn btn-secondary flex-1 py-2.5 font-bold"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  onDelete(post.id);
                  setShowDeleteModal(false);
                }}
                disabled={deleting}
                className="btn btn-danger flex-1 py-2.5 font-bold flex items-center justify-center gap-2 shadow-lg shadow-red-500/20"
              >
                <Trash2 size={16} />
                {deleting ? 'Deleting...' : 'Yes, Delete'}
              </button>
            </div>
          </motion.div>
        </div>,
        document.body
      )}

      <PublishAccountModal
        isOpen={showPublishModal}
        onClose={() => setShowPublishModal(false)}
        onConfirm={(platform) => {
          setShowPublishModal(false);
          onPublish(post.id, platform);
        }}
        isPublishing={publishing}
        initialPlatform={post.platform}
      />
    </motion.div>
  );
}

export default function AIGeneratorPage() {
  const qc = useQueryClient();
  const [generatorMode, setGeneratorMode] = useMemoryState<'topic' | 'image'>('aigen_mode', 'topic');
  
  // Topic mode state
  const [customTopic, setCustomTopic] = useMemoryState('aigen_customTopic', '');
  const [selectedTopicId, setSelectedTopicId] = useMemoryState('aigen_selectedTopicId', '');
  const [platforms, setPlatforms] = useMemoryState<string[]>('aigen_platforms', ['linkedin']);
  const [imageSource, setImageSource] = useMemoryState<'pillow' | 'chatgpt_extension' | 'nanobana'>('aigen_imageSource', 'pillow');
  
  // Image upload mode state
  const [uploadedImage, setUploadedImage] = useMemoryState<string | null>('aigen_uploadedImage', null);
  const [uploadTopic, setUploadTopic] = useMemoryState('aigen_uploadTopic', '');
  const [scheduledAt, setScheduledAt] = useMemoryState('aigen_scheduledAt', '');

  const [generating, setGenerating] = useState(false);
  const [publishingId, setPublishingId] = useState<string | null>(null);
  const [schedulingId, setSchedulingId] = useState<string | null>(null);

  const { data: topics = [] } = useQuery<Topic[]>({
    queryKey: ['topics'],
    queryFn: () => api.get('/api/v1/topics?unused_only=true').then(r => r.data),
  });

  const { data: allPosts = [], isLoading } = useQuery<GeneratedPost[]>({
    queryKey: ['posts'],
    queryFn: () => api.get('/api/v1/posts').then(r => r.data),
    refetchInterval: (query) => {
      const hasPending = query.state.data?.some(p => p.image_review_result === 'PENDING_EXTENSION');
      return hasPending ? 3000 : false;
    },
  });

  const posts = allPosts.filter(p => p.status !== 'published' && p.status !== 'scheduled');

  const togglePlatform = (p: string) => {
    setPlatforms(prev => prev.includes(p) ? prev.filter(x => x !== p) : [...prev, p]);
  };

  const handleImageFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === 'string') {
        setUploadedImage(reader.result);
      }
    };
    reader.readAsDataURL(file);
  };

  const generateFromTopic = async () => {
    if (!customTopic && !selectedTopicId) {
      toast.error('Select a topic or enter a custom one');
      return;
    }
    setGenerating(true);
    try {
      await api.post('/api/v1/posts/generate', {
        topic: customTopic || undefined,
        topic_id: selectedTopicId || undefined,
        platforms,
        generate_image: true,
        image_source: imageSource,
      });
      qc.invalidateQueries({ queryKey: ['posts'] });
      qc.invalidateQueries({ queryKey: ['topics'] });
      toast.success(imageSource === 'chatgpt_extension'
        ? 'Post created! Chrome Extension is drawing your DALL-E image...'
        : imageSource === 'nanobana'
        ? '🍌 Nano Banana (Imagen 3) is generating your image...'
        : 'Content and image generated successfully!');
      setCustomTopic('');
      setSelectedTopicId('');
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Generation failed. Check your API keys.');
    } finally { setGenerating(false); }
  };

  const generateFromImage = async () => {
    if (!uploadedImage) {
      toast.error('Please select or upload an image file first');
      return;
    }
    setGenerating(true);
    try {
      await api.post('/api/v1/posts/generate-from-image', {
        image_data: uploadedImage,
        topic: uploadTopic || undefined,
        platforms,
        scheduled_at: scheduledAt ? new Date(scheduledAt).toISOString() : null,
      });
      qc.invalidateQueries({ queryKey: ['posts'] });
      toast.success('Image uploaded & scannable caption generated!');
      setUploadedImage(null);
      setUploadTopic('');
      setScheduledAt('');
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Generation from image failed.');
    } finally { setGenerating(false); }
  };

  const publish = async (postId: string, platform?: string) => {
    setPublishingId(postId);
    try {
      const url = platform ? `/api/v1/posts/${postId}/publish?platform=${platform}` : `/api/v1/posts/${postId}/publish`;
      const res = await api.post(url).then(r => r.data);
      qc.invalidateQueries({ queryKey: ['posts'] });
      toast.success(res.message);
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Publishing failed');
    } finally { setPublishingId(null); }
  };

  const schedule = async (postId: string, dateStr: string | null) => {
    setSchedulingId(postId);
    try {
      const res = await api.put(`/api/v1/posts/${postId}/schedule`, { scheduled_at: dateStr }).then(r => r.data);
      qc.invalidateQueries({ queryKey: ['posts'] });
      toast.success(res.message);
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Scheduling failed');
    } finally { setSchedulingId(null); }
  };

  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [showClearCacheModal, setShowClearCacheModal] = useState(false);

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/api/v1/posts/${id}`).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['posts'] });
      toast.success('Post deleted');
    },
    onError: () => toast.error('Failed to delete post'),
    onSettled: () => setDeletingId(null),
  });

  const onDelete = (id: string) => {
    setDeletingId(id);
    deleteMutation.mutate(id);
  };

  const clearCacheMutation = useMutation({
    mutationFn: () => api.delete('/api/v1/posts/clear-cache').then(r => r.data),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['posts'] });
      toast.success(data.message || 'Cache cleared!');
      setShowClearCacheModal(false);
    },
    onError: () => toast.error('Failed to clear cache'),
  });

  return (
    <div className="animate-fade-up">
      <div className="page-header">
        <h1 className="page-title">AI Generator & Upload Studio</h1>
        <p className="page-subtitle">Generate posts from ideas OR upload your own images for AI scannable captions & scheduling</p>
      </div>

      {/* Generator Modes / Tabs */}
      <div className="flex gap-2 p-1.5 bg-slate-100 rounded-2xl mb-6 w-fit">
        <button
          onClick={() => setGeneratorMode('topic')}
          className={`flex items-center gap-2 px-5 py-2.5 rounded-xl font-semibold text-sm transition-all ${
            generatorMode === 'topic'
              ? 'bg-slate-50 text-blue-600 dark:text-blue-400 shadow-sm'
              : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          <Wand2 size={16} /> Generate from Topic
        </button>
        <button
          onClick={() => setGeneratorMode('image')}
          className={`flex items-center gap-2 px-5 py-2.5 rounded-xl font-semibold text-sm transition-all ${
            generatorMode === 'image'
              ? 'bg-slate-50 text-purple-600 dark:text-purple-400 shadow-sm'
              : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          <Upload size={16} /> Upload Image & AI Caption
        </button>
      </div>

      {/* Generator Card */}
      <div className="card mb-8">
        {generatorMode === 'topic' ? (
          <div>
            <h3 className="font-semibold text-slate-900 mb-4 flex items-center gap-2">
              <Wand2 size={17} className="text-blue-500" /> Create Post from Idea or Topic
            </h3>

            <div className="space-y-4">
              {topics.length > 0 && (
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1.5">Pick from Topics</label>
                  <select className="input" value={selectedTopicId}
                    onChange={e => { setSelectedTopicId(e.target.value); if (e.target.value) setCustomTopic(''); }}>
                    <option value="">-- Select a saved topic --</option>
                    {topics.map(t => <option key={t.id} value={t.id}>{t.topic}</option>)}
                  </select>
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">
                  {topics.length > 0 ? 'Or enter custom topic' : 'Topic'}
                </label>
                <input className="input" value={customTopic}
                  onChange={e => { setCustomTopic(e.target.value); if (e.target.value) setSelectedTopicId(''); }}
                  placeholder="e.g., 5 tips for improving team productivity in 2025" />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">Platforms</label>
                <div className="flex gap-2">
                  {['linkedin', 'instagram'].map(p => (
                    <button key={p} onClick={() => togglePlatform(p)}
                      className={`px-4 py-2 rounded-xl text-sm font-medium border capitalize transition-all ${
                        platforms.includes(p)
                          ? 'border-blue-500 bg-blue-50 text-blue-700'
                          : 'border-slate-200 text-slate-500'}`}>
                      {p === 'linkedin' ? '💼' : '📸'} {p}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">Image Generation Source</label>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => setImageSource('pillow')}
                    className={`p-3 rounded-xl border text-left flex flex-col transition-all ${
                      imageSource === 'pillow'
                        ? 'border-blue-500 bg-blue-50/80 dark:bg-blue-900/40 shadow-sm ring-1 ring-blue-500'
                        : 'border-slate-200 bg-slate-50 hover:bg-slate-100'
                    }`}
                  >
                    <div className="font-semibold text-sm text-slate-900 flex items-center gap-1.5">
                      🎨 Instant Branded Card
                    </div>
                    <div className="text-xs text-slate-500 mt-1">
                      High-res template with topic keywords & stock photo background (~1s)
                    </div>
                  </button>

                  <button
                    type="button"
                    onClick={() => setImageSource('chatgpt_extension')}
                    className={`p-3 rounded-xl border text-left flex flex-col transition-all ${
                      imageSource === 'chatgpt_extension'
                        ? 'border-amber-500 bg-amber-50/80 dark:bg-amber-900/40 shadow-sm ring-1 ring-amber-500'
                        : 'border-slate-200 bg-slate-50 hover:bg-slate-100'
                    }`}
                  >
                    <div className="font-semibold text-sm text-slate-900 flex items-center gap-1.5">
                      ✨ ChatGPT / DALL-E Companion
                    </div>
                    <div className="text-xs text-slate-500 mt-1">
                      Automates DALL-E drawing inside your active ChatGPT tab via Chrome Extension
                    </div>
                  </button>

                  <button
                    type="button"
                    onClick={() => setImageSource('nanobana')}
                    className={`p-3 rounded-xl border text-left flex flex-col transition-all ${
                      imageSource === 'nanobana'
                        ? 'border-violet-500 bg-violet-50/80 dark:bg-violet-900/40 shadow-sm ring-1 ring-violet-500'
                        : 'border-slate-200 bg-slate-50 hover:bg-slate-100'
                    }`}
                  >
                    <div className="font-semibold text-sm text-slate-900 flex items-center gap-1.5">
                      🍌 Nano Banana — Imagen 3
                    </div>
                    <div className="text-xs text-slate-500 mt-1">
                      Google's Imagen 3 model via Gemini API — highest quality AI images
                    </div>
                  </button>
                </div>
              </div>

              <button onClick={generateFromTopic} disabled={generating || (!customTopic && !selectedTopicId)}
                className="btn btn-primary w-full mt-2">
                {generating ? (
                  <span className="flex items-center gap-2">
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    Generating text & queueing graphic...
                  </span>
                ) : (
                  <><Sparkles size={16} /> Generate Post + Graphic</>
                )}
              </button>
            </div>
          </div>
        ) : (
          <div>
            <h3 className="font-semibold text-slate-900 mb-4 flex items-center gap-2">
              <ImageIcon size={17} className="text-purple-600" /> Upload Custom Image & Generate AI Caption
            </h3>

            <div className="space-y-5">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">Upload Your Graphic or Photo</label>
                {!uploadedImage ? (
                  <label className="border-2 border-dashed border-slate-300 hover:border-purple-500 bg-slate-50/60 hover:bg-purple-50/20 rounded-2xl p-8 flex flex-col items-center justify-center cursor-pointer transition-all">
                    <Upload size={36} className="text-purple-500 mb-3" />
                    <span className="font-semibold text-sm text-slate-800">Click to upload or drop image here</span>
                    <span className="text-xs text-slate-400 mt-1">Supports PNG, JPG, WEBP (max 10MB)</span>
                    <input type="file" accept="image/*" onChange={handleImageFileChange} className="hidden" />
                  </label>
                ) : (
                  <div className="relative rounded-2xl border border-slate-200 overflow-hidden bg-slate-900 max-h-72 flex items-center justify-center">
                    <img src={uploadedImage} alt="Preview" className="max-h-72 w-auto object-contain" />
                    <button
                      onClick={() => setUploadedImage(null)}
                      className="absolute top-3 right-3 btn btn-danger btn-sm flex items-center gap-1.5 shadow-md"
                    >
                      <Trash2 size={13} /> Remove Image
                    </button>
                  </div>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">
                  Context Notes / What is this image about? (Optional)
                </label>
                <input
                  className="input"
                  value={uploadTopic}
                  onChange={e => setUploadTopic(e.target.value)}
                  placeholder="e.g., We saved a client $10,000 in supply chain tariffs this week..."
                />
                <p className="text-xs text-slate-400 mt-1">
                  AI will analyze your image and apply our Personal Brand Scannable Template.
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">Target Platforms</label>
                <div className="flex gap-2">
                  {['linkedin', 'instagram'].map(p => (
                    <button key={p} onClick={() => togglePlatform(p)}
                      className={`px-4 py-2 rounded-xl text-sm font-medium border capitalize transition-all ${
                        platforms.includes(p)
                          ? 'border-purple-500 bg-purple-50 text-purple-700 font-semibold'
                          : 'border-slate-200 text-slate-500'}`}>
                      {p === 'linkedin' ? '💼' : '📸'} {p}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5 flex items-center gap-1.5">
                  <Calendar size={15} className="text-slate-500" /> Schedule Post for Specific Date & Time (Optional)
                </label>
                <input
                  type="datetime-local"
                  className="input"
                  value={scheduledAt}
                  onChange={e => setScheduledAt(e.target.value)}
                />
                <p className="text-xs text-slate-400 mt-1">
                  Leave blank if you want to publish manually right away or queue for automatic scheduler slots.
                </p>
              </div>

              <button onClick={generateFromImage} disabled={generating || !uploadedImage}
                className="btn btn-primary bg-purple-600 hover:bg-purple-700 w-full mt-2 py-3 text-base">
                {generating ? (
                  <span className="flex items-center gap-2">
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    Analyzing Image & Writing Scannable Caption...
                  </span>
                ) : (
                  <><Sparkles size={18} /> Generate Scannable Caption & Ready Post</>
                )}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Generated posts */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-slate-900 text-xl">Generated Posts ({posts.length})</h3>
          {posts.length > 0 && (
            <button
              onClick={() => setShowClearCacheModal(true)}
              disabled={clearCacheMutation.isPending}
              className="btn bg-blue-600 hover:bg-blue-700 text-white font-bold px-4 py-2 rounded-xl text-xs flex items-center gap-1.5 shadow-sm transition-all"
              title="Clear all generated or failed posts from cache"
            >
              <Trash2 size={15} />
              {clearCacheMutation.isPending ? 'Clearing...' : 'Clear Cache'}
            </button>
          )}
        </div>
        {isLoading ? (
          <div className="space-y-4">{[1, 2].map(i => <div key={i} className="skeleton h-64 rounded-xl" />)}</div>
        ) : posts.length === 0 ? (
          <div className="card text-center py-12">
            <Sparkles size={32} className="mx-auto text-slate-300 mb-3" />
            {allPosts.length > 0 ? (
              <>
                <p className="font-medium text-slate-600">All posts are scheduled or published! 🎉</p>
                <p className="text-sm text-slate-400 mt-1">
                  Check the <a href="/published" className="text-blue-500 hover:underline font-semibold">Published tab</a> to see your content
                </p>
              </>
            ) : (
              <>
                <p className="font-medium text-slate-600">No posts generated yet</p>
                <p className="text-sm text-slate-400 mt-1">Use the generator options above to create or upload your first post</p>
              </>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {posts.map(post => (
              <PostCard
                key={post.id}
                post={post}
                onPublish={publish}
                publishing={publishingId === post.id}
                onSchedule={schedule}
                scheduling={schedulingId === post.id}
                onDelete={onDelete}
                deleting={deletingId === post.id}
              />
            ))}
          </div>
        )}
      </div>

      {/* Clear Cache Confirmation Modal */}
      {showClearCacheModal && createPortal(
        <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fade-in">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="bg-white rounded-2xl shadow-2xl border border-slate-200 p-6 max-w-sm w-full text-center space-y-4"
          >
            <div className="w-14 h-14 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center mx-auto shadow-inner">
              <Trash2 size={28} />
            </div>
            <div>
              <h3 className="text-xl font-extrabold text-slate-900">Clear Generator Cache?</h3>
              <p className="text-sm text-slate-500 mt-1.5 leading-relaxed">
                Are you sure you want to clear all generated and failed posts from your generator? (Scheduled & Published posts in your Published tab remain safe!)
              </p>
            </div>
            <div className="flex gap-3 pt-3">
              <button
                onClick={() => setShowClearCacheModal(false)}
                disabled={clearCacheMutation.isPending}
                className="btn btn-secondary flex-1 py-2.5 font-bold"
              >
                Cancel
              </button>
              <button
                onClick={() => clearCacheMutation.mutate()}
                disabled={clearCacheMutation.isPending}
                className="btn bg-blue-600 hover:bg-blue-700 text-white flex-1 py-2.5 font-bold flex items-center justify-center gap-2 shadow-lg shadow-blue-500/20 rounded-xl"
              >
                <Trash2 size={16} />
                {clearCacheMutation.isPending ? 'Clearing...' : 'Yes, Clear All'}
              </button>
            </div>
          </motion.div>
        </div>,
        document.body
      )}
    </div>
  );
}
