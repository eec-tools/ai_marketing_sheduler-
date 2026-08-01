import React, { useState, useMemo, useEffect, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/axios';
import toast from 'react-hot-toast';
import {
  ShieldCheck, FileSearch, FileText, Video, Image,
  CheckCircle2, XCircle, Loader2, ChevronDown, ChevronRight,
  Sparkles, Calendar, Trash2, BarChart3, Tv, Layout, Briefcase,
  AlertTriangle, Pencil, Save, X, Mic
} from 'lucide-react';

type FormatTab = 'instagram_reels' | 'instagram_posts' | 'linkedin';

const TABS: { key: FormatTab; label: string; icon: React.ElementType }[] = [
  { key: 'instagram_reels', label: 'Instagram Reels', icon: Tv },
  { key: 'instagram_posts', label: 'Instagram Post & Carousels', icon: Layout },
  { key: 'linkedin', label: 'LinkedIn Posts', icon: Briefcase },
];

const STAGE_LABELS: Record<string, string> = {
  draft: 'Strategy Maker (Drafts)',
  research_pending: 'Research Content',
  script_review_pending: 'Reel Script Review',
  content_review_pending: 'Content Review',
  prompt_review_pending: 'Prompt & Creative Review',
  video_review_pending: 'Prompt & Creative Review', // Grouped together
  failed: '\u26a0 Failed',
};

interface PendingPost {
  id: string;
  headline: string;
  platform: string;
  format: string;
  status: string;
  error_message?: string;
  linkedin_caption: string;
  instagram_caption: string;
  hook?: string;
  hashtags: string[];
  cta: string;
  created_at: string;
  // Reel script fields
  hook_1?: { text: string; style: string };
  hook_2?: { text: string; style: string };
  reel_script?: { hook: string; problem: string; insight: string; solution: string; cta: string };
  spoken_script?: string;
  text_overlays?: string[];
  estimated_duration?: number;
  brief?: {
    research_data?: string;
    statistics?: any[];
    references?: any[];
    market_trends?: string;
    key_takeaways?: string;
  };
}

interface PostEditValues {
  linkedin_caption?: string;
  instagram_caption?: string;
  hook?: string;
  key_takeaways?: string;
  market_trends?: string;
}

interface PipelineStatus {
  counts: Record<string, number>;
  latest_strategy: {
    id: string;
    month: string;
    status: string;
    total_ideas: number;
    created_at: string;
    audit_data?: any;
  } | null;
}

export default function ApprovalHubPage() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<FormatTab>('instagram_reels');
  const [activeStage, setActiveStage] = useState('draft');
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [generatingMonth, setGeneratingMonth] = useState('');
  const [editingPostId, setEditingPostId] = useState<string | null>(null);
  const [editValues, setEditValues] = useState<PostEditValues>({});
  const [isGeneratingStrategy, setIsGeneratingStrategy] = useState(false);
  const prevDraftsCount = useRef(0);



  const startEdit = (item: PendingPost) => {
    setEditingPostId(item.id);
    setEditValues({
      linkedin_caption: item.linkedin_caption || '',
      instagram_caption: item.instagram_caption || '',
      hook: item.hook || '',
      key_takeaways: item.brief?.key_takeaways || '',
      market_trends: item.brief?.market_trends || '',
    });
  };

  const cancelEdit = () => {
    setEditingPostId(null);
    setEditValues({});
  };

  const monthOptions = useMemo(() => {
    const options = [];
    const date = new Date();
    for (let i = 0; i < 12; i++) {
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const label = date.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
      options.push({ value: `${year}-${month}`, label });
      date.setMonth(date.getMonth() + 1);
    }
    return options;
  }, []);
  const [showAnalytics, setShowAnalytics] = useState(false);

  // ─── Queries ───────────────────────────────────────────────────────────
  const { data: pending, isLoading: loadingPending } = useQuery<PendingPost[]>({
    queryKey: ['pipeline-pending'],
    queryFn: () => api.get('/api/v1/pipeline/pending').then(r => r.data),
    refetchInterval: 5000,
  });

  const { data: status } = useQuery<PipelineStatus>({
    queryKey: ['pipeline-status'],
    queryFn: () => api.get('/api/v1/pipeline/status').then(r => r.data),
    refetchInterval: 5000,
  });

  // Monitor drafts count to stop loading
  useEffect(() => {
    if (pending) {
      const draftCount = pending.filter(p => p.status === 'draft').length;
      if (isGeneratingStrategy && draftCount > prevDraftsCount.current) {
        setIsGeneratingStrategy(false);
      }
      prevDraftsCount.current = draftCount;
    }
  }, [pending, isGeneratingStrategy]);

  // ─── Mutations ─────────────────────────────────────────────────────────
  const generateStrategy = useMutation({
    mutationFn: ({ month, format }: { month: string; format: string }) => 
      api.post('/api/v1/pipeline/generate-strategy', { month, target_format: format }),
    onSuccess: () => {
      setIsGeneratingStrategy(true);
      queryClient.invalidateQueries({ queryKey: ['pipeline-status'] });
    },
    onError: (e: any) => {
      setIsGeneratingStrategy(false);
      toast.error(e.response?.data?.detail || 'Strategy generation failed');
    },
  });

  const startAllResearch = useMutation({
    mutationFn: () => api.post('/api/v1/pipeline/research/start-all'),
    onSuccess: (res) => {
      toast.success(res.data.message || `Research started`);
      queryClient.invalidateQueries({ queryKey: ['pipeline-pending'] });
    },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Failed to start research'),
  });

  const startAllContent = useMutation({
    mutationFn: () => api.post('/api/v1/pipeline/content/start-all'),
    onSuccess: (res) => {
      toast.success(res.data.message || `Content generation started`);
      queryClient.invalidateQueries({ queryKey: ['pipeline-pending'] });
    },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Failed to start content generation'),
  });

  const startAllPrompts = useMutation({
    mutationFn: () => api.post('/api/v1/pipeline/prompts/start-all'),
    onSuccess: (res) => {
      toast.success(res.data.message || `Video prompt generation started`);
      queryClient.invalidateQueries({ queryKey: ['pipeline-pending'] });
    },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Failed to start prompt generation'),
  });

  const getEndpointStage = (type: string) => {
    switch (type) {
      case 'research_review': return 'research';
      case 'script_review': return 'script';
      case 'content_review': return 'content';
      case 'prompt_review': return 'prompts';
      case 'video_review': return 'video';
      case 'draft': return 'drafts';
      default: return type;
    }
  };

  const approveItem = useMutation({
    mutationFn: ({ type, id }: { type: keyof typeof activeTabPosts; id: string }) => {
      const stage = getEndpointStage(type);
      return api.post(`/api/v1/pipeline/${stage}/${id}/approve`);
    },
    onSuccess: () => {
      toast.success('Approved! Next step triggered automatically.');
      queryClient.invalidateQueries({ queryKey: ['pipeline-pending'] });
      queryClient.invalidateQueries({ queryKey: ['pipeline-status'] });
    },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Approval failed'),
  });

  const rejectItem = useMutation({
    mutationFn: ({ type, id }: { type: keyof typeof activeTabPosts; id: string }) => {
      const stage = getEndpointStage(type);
      return api.post(`/api/v1/pipeline/${stage}/${id}/reject`, { feedback: 'Rejected by reviewer' });
    },
    onSuccess: () => {
      toast.success('Rejected. Regeneration triggered.');
      queryClient.invalidateQueries({ queryKey: ['pipeline-pending'] });
    },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Rejection failed'),
  });

  const deleteDraft = useMutation({
    mutationFn: (id: string) => api.delete(`/api/v1/pipeline/drafts/${id}`),
    onSuccess: () => {
      toast.success('Draft removed.');
      queryClient.invalidateQueries({ queryKey: ['pipeline-pending'] });
      queryClient.invalidateQueries({ queryKey: ['pipeline-status'] });
    }
  });

  const clearStage = useMutation({
    mutationFn: (stage: string) => api.delete('/api/v1/pipeline/clear', { params: { stage } }),
    onSuccess: (res: any) => {
      toast.success(res.data?.message || 'Items removed.');
      queryClient.invalidateQueries({ queryKey: ['pipeline-pending'] });
      queryClient.invalidateQueries({ queryKey: ['pipeline-status'] });
    }
  });

  const saveEdit = useMutation({
    mutationFn: ({ id, values }: { id: string; values: PostEditValues }) =>
      api.put(`/api/v1/pipeline/posts/${id}`, {
        linkedin_caption: values.linkedin_caption,
        instagram_caption: values.instagram_caption,
        hook: values.hook,
        key_takeaways: values.key_takeaways,
        market_trends: values.market_trends,
      }),
    onSuccess: () => {
      toast.success('Changes saved!');
      queryClient.invalidateQueries({ queryKey: ['pipeline-pending'] });
      setEditingPostId(null);
      setEditValues({});
    },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Failed to save changes'),
  });

  // ─── Helpers ───────────────────────────────────────────────────────────
  const getAllPostsForFormat = (format: FormatTab) => {
    if (!pending || !Array.isArray(pending)) return [];
    return pending.filter(p => p.format === format);
  };

  const groupedPosts = (format: FormatTab) => {
    const posts = getAllPostsForFormat(format);
    const groups: Record<string, PendingPost[]> = {
      draft: [],
      research_pending: [],
      script_review_pending: [],
      content_review_pending: [],
      prompt_review_pending: [],
      failed: [],
    };

    posts.forEach(p => {
      if (p.status === 'failed') groups.failed.push(p);
      else if (p.status === 'draft') groups.draft.push(p);
      else if (p.status === 'research_pending') groups.research_pending.push(p);
      else if (p.status === 'script_review_pending') groups.script_review_pending.push(p);
      else if (p.status === 'research_approved' || p.status === 'script_approved' || p.status === 'content_review_pending') groups.content_review_pending.push(p);
      else if (p.status === 'content_approved' || p.status === 'prompt_review_pending' || p.status === 'video_review_pending' || p.status === 'prompt_approved') {
        groups.prompt_review_pending.push(p);
      }
    });

    return groups;
  };

  const getApproveType = (status: string) => {
    if (status === 'research_pending' || status === 'research_approved') return 'research_review';
    if (status === 'script_review_pending') return 'script_review';
    if (status === 'content_review_pending' || status === 'content_approved') return 'content_review';
    if (status === 'prompt_review_pending' || status === 'prompt_approved') return 'prompt_review';
    if (status === 'video_review_pending') return 'video_review';
    return status;
  };

  const getTargetTab = (status: string) => {
    if (status === 'draft') return 'drafts';
    if (status === 'research_pending') return 'research';
    if (status === 'script_review_pending') return 'script';
    if (status === 'research_approved' || status === 'script_approved' || status === 'content_review_pending') return 'content';
    if (status === 'content_approved' || status === 'prompt_review_pending' || status === 'video_review_pending' || status === 'prompt_approved') return 'prompts';
    return 'none';
  };

  const activeTabPosts = groupedPosts(activeTab);

  const renderPost = (item: PendingPost) => {
    const isApprovingThis = approveItem.isPending && approveItem.variables?.id === item.id;
    const isRejectingThis = rejectItem.isPending && rejectItem.variables?.id === item.id;
    const isDeletingThis = deleteDraft.isPending && deleteDraft.variables === item.id;
    const isSavingThis = saveEdit.isPending && (saveEdit.variables as any)?.id === item.id;
    const isEditing = editingPostId === item.id;

    return (
    <div key={item.id} className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden mb-3">
      {/* Header row */}
      <div
        className="flex items-center gap-3 px-5 py-4 cursor-pointer hover:bg-slate-50 transition-colors"
        onClick={() => setExpandedId(expandedId === item.id ? null : item.id)}
      >
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-slate-900 truncate">{item.headline || 'Untitled'}</p>
          <p className="text-xs text-slate-500 mt-0.5">
            {item.platform} · {new Date(item.created_at).toLocaleDateString()}
          </p>
        </div>
        <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded-lg bg-amber-50 text-amber-700">
          {item.status === 'draft' ? 'Draft Phase' :
           (item.status === 'research_pending' && !item.brief?.research_data) ? 'Processing...' :
           item.status === 'research_pending' ? 'Research Review' :
           item.status === 'content_review_pending' ? 'Content Review' :
           item.status === 'prompt_review_pending' ? 'Prompt Review' :
           item.status === 'video_review_pending' ? 'Video Review' :
           item.status?.endsWith('_approved') ? 'Processing...' :
           item.status?.replace(/_/g, ' ')}
        </span>
        {expandedId === item.id ? (
          <ChevronDown className="h-4 w-4 text-slate-400" />
        ) : (
          <ChevronRight className="h-4 w-4 text-slate-400" />
        )}
      </div>

      {/* Expanded content */}
      {expandedId === item.id && (
        <div className="border-t border-slate-100 px-5 py-4 space-y-4">
          {(item.linkedin_caption || isEditing) && (
            <div>
              <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">LinkedIn Caption</p>
              {isEditing ? (
                <textarea
                  value={editValues.linkedin_caption || ''}
                  onChange={e => setEditValues(v => ({ ...v, linkedin_caption: e.target.value }))}
                  rows={5}
                  className="w-full text-sm text-slate-700 bg-white border border-blue-300 rounded-xl p-3 focus:ring-2 focus:ring-blue-400 outline-none resize-y"
                />
              ) : (
                <p className="text-sm text-slate-700 whitespace-pre-wrap bg-slate-50 rounded-xl p-3 max-h-48 overflow-y-auto">
                  {item.linkedin_caption}
                </p>
              )}
            </div>
          )}
          {(item.instagram_caption || isEditing) && (
            <div>
              <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">Instagram Caption</p>
              {isEditing ? (
                <textarea
                  value={editValues.instagram_caption || ''}
                  onChange={e => setEditValues(v => ({ ...v, instagram_caption: e.target.value }))}
                  rows={5}
                  className="w-full text-sm text-slate-700 bg-white border border-blue-300 rounded-xl p-3 focus:ring-2 focus:ring-blue-400 outline-none resize-y"
                />
              ) : (
                <p className="text-sm text-slate-700 whitespace-pre-wrap bg-slate-50 rounded-xl p-3 max-h-48 overflow-y-auto">
                  {item.instagram_caption}
                </p>
              )}
            </div>
          )}
          {(item.hook || isEditing) && (
            <div>
              <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">Hook / Opening Line</p>
              {isEditing ? (
                <textarea
                  value={editValues.hook || ''}
                  onChange={e => setEditValues(v => ({ ...v, hook: e.target.value }))}
                  rows={2}
                  className="w-full text-sm text-slate-700 bg-white border border-blue-300 rounded-xl p-3 focus:ring-2 focus:ring-blue-400 outline-none resize-y"
                />
              ) : (
                <p className="text-sm text-slate-700 whitespace-pre-wrap bg-slate-50 rounded-xl p-3">
                  {item.hook}
                </p>
              )}
            </div>
          )}
          {item.hashtags?.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {item.hashtags.map((h, i) => (
                <span key={i} className="text-xs px-2 py-1 bg-blue-50 text-blue-700 rounded-lg font-medium">
                  #{h}
                </span>
              ))}
            </div>
          )}

          {item.status.startsWith('research_') && item.brief && (
            <div className="space-y-4">
              {item.brief.research_data && (
                <div>
                  <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">Key Insights (Research)</p>
                  <p className="text-sm text-slate-700 whitespace-pre-wrap bg-blue-50/50 rounded-xl p-3 border border-blue-100 max-h-48 overflow-y-auto">
                    {item.brief.research_data}
                  </p>
                </div>
              )}
              {(item.brief.market_trends || isEditing) && (
                <div>
                  <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">Market Trends</p>
                  {isEditing ? (
                    <textarea
                      value={editValues.market_trends || ''}
                      onChange={e => setEditValues(v => ({ ...v, market_trends: e.target.value }))}
                      rows={3}
                      className="w-full text-sm text-slate-700 bg-white border border-blue-300 rounded-xl p-3 focus:ring-2 focus:ring-blue-400 outline-none resize-y"
                    />
                  ) : (
                    <p className="text-sm text-slate-700 whitespace-pre-wrap bg-blue-50/50 rounded-xl p-3 border border-blue-100">
                      {item.brief.market_trends}
                    </p>
                  )}
                </div>
              )}
              {(item.brief.key_takeaways || isEditing) && (
                <div>
                  <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">Key Takeaways</p>
                  {isEditing ? (
                    <textarea
                      value={editValues.key_takeaways || ''}
                      onChange={e => setEditValues(v => ({ ...v, key_takeaways: e.target.value }))}
                      rows={3}
                      className="w-full text-sm text-slate-700 bg-white border border-blue-300 rounded-xl p-3 focus:ring-2 focus:ring-blue-400 outline-none resize-y"
                    />
                  ) : (
                    <p className="text-sm text-slate-700 whitespace-pre-wrap bg-blue-50/50 rounded-xl p-3 border border-blue-100">
                      {item.brief.key_takeaways}
                    </p>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Reel Script Display (script_review_pending) */}
          {item.status === 'script_review_pending' && (
            <div className="space-y-4">
              <div className="flex items-center gap-2 mb-2">
                <Mic className="h-4 w-4 text-purple-500" />
                <p className="text-xs font-bold text-purple-600 uppercase tracking-wider">Reel Script Ready for Review</p>
              </div>

              {/* Two Hooks */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {item.hook_1 && (
                  <div className="bg-purple-50 border border-purple-200 rounded-xl p-3">
                    <p className="text-[10px] font-bold text-purple-500 uppercase tracking-wider mb-1">Hook Option 1 — {item.hook_1.style}</p>
                    <p className="text-sm font-semibold text-purple-900">"{item.hook_1.text}"</p>
                  </div>
                )}
                {item.hook_2 && (
                  <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-3">
                    <p className="text-[10px] font-bold text-indigo-500 uppercase tracking-wider mb-1">Hook Option 2 — {item.hook_2.style}</p>
                    <p className="text-sm font-semibold text-indigo-900">"{item.hook_2.text}"</p>
                  </div>
                )}
              </div>

              {/* Full Script Breakdown */}
              {item.reel_script && (
                <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 space-y-2">
                  <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2">Scene-by-Scene Script</p>
                  {(['hook', 'problem', 'insight', 'solution', 'cta'] as const).map(section => (
                    item.reel_script![section] && (
                      <div key={section} className="flex gap-3">
                        <span className="text-[10px] font-bold text-slate-400 uppercase w-16 shrink-0 mt-0.5">{section}</span>
                        <p className="text-sm text-slate-700">{item.reel_script![section]}</p>
                      </div>
                    )
                  ))}
                </div>
              )}

              {/* Full Spoken Script */}
              {item.spoken_script && (
                <div>
                  <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">Full Spoken Script</p>
                  <p className="text-sm text-slate-700 whitespace-pre-wrap bg-emerald-50/50 rounded-xl p-3 border border-emerald-100 max-h-48 overflow-y-auto leading-relaxed">
                    {item.spoken_script}
                  </p>
                </div>
              )}

              {/* Text Overlays */}
              {item.text_overlays && item.text_overlays.length > 0 && (
                <div>
                  <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Text Overlays</p>
                  <div className="flex flex-wrap gap-2">
                    {item.text_overlays.map((overlay, i) => (
                      <span key={i} className="text-xs px-2.5 py-1 bg-slate-800 text-white rounded-lg font-medium">{overlay}</span>
                    ))}
                  </div>
                </div>
              )}

              {item.estimated_duration && (
                <p className="text-xs text-slate-500">⏱ Estimated duration: ~{item.estimated_duration}s</p>
              )}
            </div>
          )}

          {/* Error badge for failed posts */}
          {item.status === 'failed' && (
            <div className="flex items-start gap-2.5 p-3 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700">
              <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5 text-red-500" />
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-red-800 mb-0.5">Generation Failed</p>
                <p className="text-xs text-red-600 break-words">{item.error_message || 'An unexpected error occurred in the background task.'}</p>
              </div>
            </div>
          )}
          
          {/* Processing State */}
          {((item.status === 'research_pending' && !item.brief?.research_data) || item.status === 'research_approved' || item.status === 'script_approved') && (
            <div className="flex flex-col items-center justify-center p-8 bg-slate-50 border border-slate-100 rounded-xl text-center">
              <Loader2 className="h-8 w-8 animate-spin text-emerald-500 mb-3" />
              <p className="text-sm font-semibold text-slate-700 mb-1">AI is working in the background...</p>
              <p className="text-xs text-slate-500 max-w-xs mx-auto">
                Because we process items sequentially to prevent API limits, this item is in the queue and will populate shortly.
              </p>
            </div>
          )}

          {/* Action buttons */}
          {isEditing ? (
            <div className="flex items-center gap-3 pt-2 border-t border-slate-100 mt-2">
              <button
                onClick={() => saveEdit.mutate({ id: item.id, values: editValues })}
                disabled={isSavingThis}
                className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-semibold disabled:opacity-50 transition-colors"
              >
                {isSavingThis ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                Save Changes
              </button>
              <button
                onClick={cancelEdit}
                disabled={isSavingThis}
                className="flex items-center gap-2 px-5 py-2.5 bg-white border border-slate-200 text-slate-600 hover:bg-slate-50 rounded-xl text-sm font-semibold disabled:opacity-50 transition-colors"
              >
                <X className="h-4 w-4" />
                Cancel
              </button>
            </div>
          ) : item.status === 'failed' ? (
            <div className="flex items-center gap-3 pt-2">
              <button
                onClick={() => rejectItem.mutate({ type: getApproveType(item.status), id: item.id })}
                disabled={isRejectingThis}
                className="flex items-center gap-2 px-5 py-2.5 bg-white border border-red-200 text-red-600 hover:bg-red-50 rounded-xl text-sm font-semibold disabled:opacity-50 transition-colors"
              >
                {isRejectingThis ? <Loader2 className="h-4 w-4 animate-spin" /> : <XCircle className="h-4 w-4" />}
                Regenerate
              </button>
            </div>
          ) : item.status !== 'draft' ? (
            <div className="flex items-center gap-3 pt-2 flex-wrap">
              {(item.status.endsWith('_approved') || (item.status === 'research_pending' && approveItem.isPending)) ? (
                <button disabled className="flex items-center gap-2 px-5 py-2.5 bg-emerald-600/50 text-white rounded-xl text-sm font-semibold transition-colors">
                  <Loader2 className="h-4 w-4 animate-spin" /> Generating Next Stage...
                </button>
              ) : (
                <>
                  <button
                    onClick={() => approveItem.mutate({ type: getApproveType(item.status), id: item.id })}
                    disabled={isApprovingThis}
                    className="flex items-center gap-2 px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-sm font-semibold disabled:opacity-50 transition-colors"
                  >
                    {isApprovingThis ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                    {item.status === 'research_pending' ? 'Approve (Generate Content)' :
                     item.status === 'content_review_pending' ? 'Approve (Generate Prompt)' :
                     item.status === 'prompt_review_pending' ? 'Approve (Generate Video)' :
                     item.status === 'video_review_pending' ? 'Approve (Schedule)' : 'Approve'}
                  </button>
                  <button
                    onClick={() => startEdit(item)}
                    className="flex items-center gap-2 px-4 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-sm font-semibold transition-colors"
                  >
                    <Pencil className="h-4 w-4" />
                    Edit
                  </button>
                  <button
                    onClick={() => rejectItem.mutate({ type: getApproveType(item.status), id: item.id })}
                    disabled={isRejectingThis}
                    className="flex items-center gap-2 px-5 py-2.5 bg-white border border-red-200 text-red-600 hover:bg-red-50 rounded-xl text-sm font-semibold disabled:opacity-50 transition-colors"
                  >
                    {isRejectingThis ? <Loader2 className="h-4 w-4 animate-spin" /> : <XCircle className="h-4 w-4" />}
                    Reject (Regenerate)
                  </button>
                </>
              )}
            </div>
          ) : (
            <div className="flex items-center gap-3 pt-2 flex-wrap">
              <button
                onClick={() => approveItem.mutate({ type: 'drafts', id: item.id })}
                disabled={isApprovingThis}
                className="flex items-center gap-2 px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-sm font-semibold disabled:opacity-50 transition-colors"
              >
                {isApprovingThis ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                Approve (Start Research)
              </button>
              <button
                onClick={() => startEdit(item)}
                className="flex items-center gap-2 px-4 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-sm font-semibold transition-colors"
              >
                <Pencil className="h-4 w-4" />
                Edit
              </button>
              <button
                onClick={() => deleteDraft.mutate(item.id)}
                disabled={isDeletingThis}
                className="flex items-center gap-2 px-5 py-2.5 bg-red-50 hover:bg-red-100 text-red-700 rounded-xl text-sm font-semibold border border-red-200 disabled:opacity-50 transition-colors"
              >
                {isDeletingThis ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                Remove
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

  return (
    <div className="p-4 md:p-6 max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-900 flex items-center gap-2">
            <ShieldCheck className="h-7 w-7 text-blue-600" />
            Approval Hub
          </h1>
          <p className="text-slate-500 text-sm mt-0.5">
            Review your AI-generated pipelines independently per platform.
          </p>
        </div>
      </div>

      {/* Format Tabs */}
      <div className="flex gap-1 bg-slate-100 rounded-2xl p-1 mb-6">
        {TABS.map((tab) => {
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`flex-1 flex items-center justify-center gap-2 py-3 px-3 rounded-xl text-sm font-semibold transition-all ${
                activeTab === tab.key
                  ? 'bg-white shadow-sm text-slate-900 ring-1 ring-slate-200'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              <tab.icon className="h-4 w-4" />
              <span className="hidden sm:inline">{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* Active Tab Content */}
      <div className="space-y-8">
        
        {/* Strategy Generator for this format */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5 border-l-4 border-l-blue-500">
          <h2 className="text-sm font-bold text-slate-700 uppercase tracking-wider mb-3 flex items-center gap-2">
            <Calendar className="h-4 w-4" />
            Generate 1-Month {TABS.find(t => t.key === activeTab)?.label} Strategy
          </h2>
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
            <div className="relative">
              <select
                value={generatingMonth}
                onChange={(e) => setGeneratingMonth(e.target.value)}
                className="appearance-none border border-slate-300 rounded-xl pl-4 pr-10 py-2.5 text-sm font-medium text-slate-700 bg-white hover:bg-slate-50 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-colors cursor-pointer min-w-[220px]"
              >
                <option value="" disabled>Select Month</option>
                {monthOptions.map(opt => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400 pointer-events-none" />
            </div>
            <button
              onClick={() => generatingMonth && generateStrategy.mutate({ month: generatingMonth, format: activeTab })}
              disabled={!generatingMonth || generateStrategy.isPending || isGeneratingStrategy}
              className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-semibold disabled:opacity-50 flex items-center gap-2 transition-colors"
            >
              {(generateStrategy.isPending || isGeneratingStrategy) ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
              {(generateStrategy.isPending || isGeneratingStrategy) ? 'Generating...' : `Run Audit + Strategy`}
            </button>
            {activeTabPosts[activeStage as keyof typeof activeTabPosts]?.length > 0 && activeStage !== 'failed' && (
              <>
                <button
                  onClick={() => {
                    if (activeStage === 'draft') startAllResearch.mutate();
                    else if (activeStage === 'research_pending') startAllContent.mutate();
                    else if (activeStage === 'content_review_pending') startAllPrompts.mutate();
                  }}
                  disabled={startAllResearch.isPending || startAllContent.isPending || startAllPrompts.isPending}
                  className="px-5 py-2.5 bg-violet-600 hover:bg-violet-700 text-white rounded-xl text-sm font-semibold disabled:opacity-50 flex items-center gap-2 transition-colors ml-auto"
                >
                  {(startAllResearch.isPending || startAllContent.isPending || startAllPrompts.isPending) ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <CheckCircle2 className="h-4 w-4" />
                  )}
                  {activeStage === 'draft' ? 'Approve All Drafts' : 
                   activeStage === 'research_pending' ? 'Approve All Research' : 
                   activeStage === 'content_review_pending' ? 'Approve All Content' : 'Approve All'}
                </button>
                <button
                  onClick={() => {
                    if(confirm('Are you sure you want to remove all items in this stage?')) clearStage.mutate(activeStage);
                  }}
                  disabled={clearStage.isPending}
                  className="px-5 py-2.5 bg-red-50 hover:bg-red-100 text-red-600 rounded-xl text-sm font-semibold border border-red-200 disabled:opacity-50 flex items-center gap-2 transition-colors"
                >
                  {clearStage.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <XCircle className="h-4 w-4" />}
                  Remove All
                </button>
              </>
            )}
          </div>
        </div>

        {/* Audit Results */}
        {status?.latest_strategy?.audit_data && (
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5 border-l-4 border-l-purple-500">
            <h2 className="text-sm font-bold text-slate-700 uppercase tracking-wider mb-4 flex items-center gap-2">
              <BarChart3 className="h-4 w-4" />
              Latest Brand Audit Insights
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-4 bg-slate-50 rounded-xl">
                <h3 className="font-semibold text-slate-800 text-sm mb-2">Competitor Insights</h3>
                <p className="text-slate-600 text-sm">{status.latest_strategy.audit_data.competitor_insights || 'No data available'}</p>
              </div>
              <div className="p-4 bg-slate-50 rounded-xl">
                <h3 className="font-semibold text-slate-800 text-sm mb-2">Industry Trends</h3>
                <p className="text-slate-600 text-sm">{status.latest_strategy.audit_data.industry_trends || 'No data available'}</p>
              </div>
              <div className="p-4 bg-slate-50 rounded-xl">
                <h3 className="font-semibold text-slate-800 text-sm mb-2">Content Gaps</h3>
                <p className="text-slate-600 text-sm">{status.latest_strategy.audit_data.content_gaps || 'No data available'}</p>
              </div>
              <div className="p-4 bg-slate-50 rounded-xl">
                <h3 className="font-semibold text-slate-800 text-sm mb-2">Top Formats</h3>
                <div className="flex flex-wrap gap-2">
                  {status.latest_strategy.audit_data.top_performing_formats?.length > 0 ? (
                    status.latest_strategy.audit_data.top_performing_formats.map((fmt: string, i: number) => (
                      <span key={i} className="px-2 py-1 bg-purple-100 text-purple-700 rounded-md text-xs font-semibold">
                        {fmt}
                      </span>
                    ))
                  ) : (
                    <span className="text-slate-500 text-sm">No formats identified</span>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Stage Tabs (Nested) */}
        <div className="flex flex-wrap gap-2 border-b border-slate-200 pb-4">
        {Object.entries(STAGE_LABELS).map(([stageKey, label]) => {
            const count = activeTabPosts[stageKey as keyof typeof activeTabPosts]?.length || 0;
            const isFailed = stageKey === 'failed';
            return (
              <button
                key={stageKey}
                onClick={() => setActiveStage(stageKey)}
                className={`flex items-center gap-2 px-4 py-2 rounded-full text-sm font-semibold transition-colors ${
                  activeStage === stageKey
                    ? isFailed ? 'bg-red-600 text-white' : 'bg-slate-800 text-white'
                    : isFailed && count > 0
                      ? 'bg-red-100 text-red-700 hover:bg-red-200'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                {label}
                {count > 0 && (
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                    activeStage === stageKey
                      ? isFailed ? 'bg-red-800 text-white' : 'bg-slate-600 text-white'
                      : isFailed ? 'bg-red-200 text-red-700' : 'bg-slate-200 text-slate-700'
                  }`}>
                    {count}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* Pipeline Sections */}
        {loadingPending ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
          </div>
        ) : (
          <div className="space-y-3">
            {activeTabPosts[activeStage as keyof typeof activeTabPosts]?.length > 0 ? (
              activeTabPosts[activeStage as keyof typeof activeTabPosts].map(renderPost)
            ) : (
              <div className="bg-white rounded-2xl border border-dashed border-slate-300 py-16 text-center">
                <ShieldCheck className="h-12 w-12 text-slate-300 mx-auto mb-3" />
                <p className="text-slate-500 font-semibold">No items pending in this stage.</p>
                <p className="text-slate-400 text-sm mt-1">Check other tabs or generate a new strategy.</p>
              </div>
            )}
          </div>
        )}

        {!loadingPending && Object.values(activeTabPosts).every(arr => arr.length === 0) && (
           <div className="bg-white rounded-2xl border border-dashed border-slate-300 py-16 text-center">
             <ShieldCheck className="h-12 w-12 text-slate-300 mx-auto mb-3" />
             <p className="text-slate-500 font-semibold">No items pending review for this format.</p>
             <p className="text-slate-400 text-sm mt-1">Generate a strategy to begin your {TABS.find(t => t.key === activeTab)?.label} pipeline!</p>
           </div>
        )}
      </div>
    </div>
  );
}
