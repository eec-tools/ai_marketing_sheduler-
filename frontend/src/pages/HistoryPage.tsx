import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import { CheckCircle, XCircle, Clock, Filter, History as HistoryIcon } from 'lucide-react';
import api from '@/lib/axios';
import type { HistoryItem } from '@/types';

function StatusBadge({ status }: { status: string }) {
  if (status === 'published') return <span className="badge badge-green"><CheckCircle size={10} /> Published</span>;
  if (status === 'failed') return <span className="badge badge-red"><XCircle size={10} /> Failed</span>;
  return <span className="badge badge-gray">{status}</span>;
}

export default function HistoryPage() {
  const [platform, setPlatform] = useState('');
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);

  const { data: history = [], isLoading } = useQuery<HistoryItem[]>({
    queryKey: ['history', platform, status, page],
    queryFn: () => api.get('/api/v1/history', {
      params: { platform: platform || undefined, status: status || undefined, page, limit: 20 }
    }).then(r => r.data),
  });

  return (
    <div className="animate-fade-up">
      <div className="page-header">
        <h1 className="page-title">Publishing History</h1>
        <p className="page-subtitle">Track all published and failed posts</p>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-6 flex-wrap items-center">
        <Filter size={15} className="text-slate-400" />
        <select className="input w-36 text-sm" value={platform} onChange={e => { setPlatform(e.target.value); setPage(1); }}>
          <option value="">All Platforms</option>
          <option value="linkedin">LinkedIn</option>
          <option value="instagram">Instagram</option>
        </select>
        <select className="input w-36 text-sm" value={status} onChange={e => { setStatus(e.target.value); setPage(1); }}>
          <option value="">All Status</option>
          <option value="published">Published</option>
          <option value="failed">Failed</option>
        </select>
      </div>

      {isLoading ? (
        <div className="space-y-3">{[...Array(8)].map((_, i) => <div key={i} className="skeleton h-20 rounded-xl" />)}</div>
      ) : history.length === 0 ? (
        <div className="card text-center py-16">
          <HistoryIcon size={36} className="mx-auto text-slate-300 mb-3" />
          <p className="font-medium text-slate-600">No history yet</p>
          <p className="text-sm text-slate-400 mt-1">Published posts will appear here</p>
        </div>
      ) : (
        <div className="space-y-3">
          {history.map((item, i) => (
            <motion.div key={item.id}
              initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.03 }}
              className={`p-4 rounded-xl border flex items-start gap-4 ${
                item.status === 'failed' ? 'bg-red-50 border-red-200' : 'bg-white border-slate-200'}`}>
              <span className="text-xl mt-0.5">{item.platform === 'linkedin' ? '💼' : '📸'}</span>
              {item.image_url && (
                <img src={item.image_url} alt="" className="w-12 h-12 rounded-lg object-cover border border-slate-200 shrink-0" />
              )}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <StatusBadge status={item.status} />
                  <span className="text-xs text-slate-400 capitalize">{item.platform}</span>
                  {item.generation_time_ms && (
                    <span className="text-xs text-slate-400">· {(item.generation_time_ms / 1000).toFixed(1)}s</span>
                  )}
                </div>
                {item.caption_preview && (
                  <p className="text-sm text-slate-600 truncate">{item.caption_preview}</p>
                )}
                {item.error_message && (
                  <p className="text-xs text-red-600 mt-1">{item.error_message}</p>
                )}
              </div>
              <div className="text-right shrink-0">
                <p className="text-xs text-slate-500">
                  {item.published_at
                    ? new Date(item.published_at).toLocaleDateString()
                    : new Date(item.created_at).toLocaleDateString()}
                </p>
                <p className="text-xs text-slate-400">
                  {item.published_at
                    ? new Date(item.published_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                    : '—'}
                </p>
              </div>
            </motion.div>
          ))}

          <div className="flex justify-center gap-3 mt-6 items-center">
            <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
              className="btn btn-secondary btn-sm">← Previous</button>
            <span className="text-sm text-slate-500 flex items-center">Page {page}</span>
            {history.length < 20 ? (
              <span className="text-xs text-slate-400 italic px-3 py-1.5">End of results</span>
            ) : (
              <button onClick={() => setPage(p => p + 1)}
                className="btn btn-secondary btn-sm">Next →</button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
