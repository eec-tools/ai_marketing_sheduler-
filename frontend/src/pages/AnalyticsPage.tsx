import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend
} from 'recharts';
import { TrendingUp, CheckCircle, XCircle, Clock, Hash, BarChart3 } from 'lucide-react';
import api from '@/lib/axios';
import type { AnalyticsSummary } from '@/types';

const COLORS = ['#2563EB', '#6366F1', '#10B981', '#F59E0B', '#EF4444'];

function StatBox({ icon: Icon, label, value, sub, color }: any) {
  return (
    <div className="stat-card">
      <div className="flex items-center gap-3 mb-2">
        <div className="p-2 rounded-xl" style={{ background: `${color}15` }}>
          <Icon size={18} style={{ color }} />
        </div>
        <p className="text-sm text-slate-500">{label}</p>
      </div>
      <p className="text-2xl font-bold text-slate-900">{value}</p>
      {sub && <p className="text-xs text-slate-400 mt-1">{sub}</p>}
    </div>
  );
}

export default function AnalyticsPage() {
  const { data: analytics, isLoading } = useQuery<AnalyticsSummary>({
    queryKey: ['analytics'],
    queryFn: () => api.get('/api/v1/analytics/summary').then(r => r.data),
  });

  if (isLoading) return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 animate-fade-up">
      {[...Array(8)].map((_, i) => <div key={i} className="skeleton h-28 rounded-xl" />)}
    </div>
  );

  const pieData = [
    { name: 'Published', value: analytics?.total_published || 0 },
    { name: 'Failed', value: analytics?.total_failed || 0 },
  ].filter(d => d.value > 0);

  const hashtagData = (analytics?.top_hashtags || []).slice(0, 8);

  return (
    <div className="animate-fade-up">
      <div className="page-header">
        <h1 className="page-title">Analytics</h1>
        <p className="page-subtitle">Track your content performance over time</p>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <StatBox icon={CheckCircle} label="Total Published" value={analytics?.total_published ?? 0}
          sub="All time" color="#10B981" />
        <StatBox icon={XCircle} label="Failed Posts" value={analytics?.total_failed ?? 0}
          sub="With errors" color="#EF4444" />
        <StatBox icon={TrendingUp} label="Success Rate" value={`${analytics?.success_rate ?? 0}%`}
          sub="Published / Total" color="#2563EB" />
        <StatBox icon={Clock} label="Avg Gen Time"
          value={analytics?.avg_generation_time_ms
            ? `${(analytics.avg_generation_time_ms / 1000).toFixed(1)}s`
            : 'N/A'}
          sub="Per post" color="#6366F1" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Success/fail pie */}
        {pieData.length > 0 && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="card">
            <h3 className="font-semibold text-slate-900 mb-4">Post Results</h3>
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={pieData} cx="50%" cy="50%" innerRadius={55} outerRadius={85}
                  paddingAngle={4} dataKey="value">
                  {pieData.map((_, index) => (
                    <Cell key={index} fill={index === 0 ? '#10B981' : '#EF4444'} />
                  ))}
                </Pie>
                <Legend />
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </motion.div>
        )}

        {/* Weekly summary */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }} className="card">
          <h3 className="font-semibold text-slate-900 mb-4">Recent Activity</h3>
          <div className="space-y-4">
            {[
              { label: 'Posts today', value: analytics?.posts_today ?? 0, icon: '📅' },
              { label: 'Posts this week', value: analytics?.posts_this_week ?? 0, icon: '📊' },
              { label: 'Connected platforms', value: analytics?.connected_platforms?.length ?? 0, icon: '🔗' },
            ].map(({ label, value, icon }) => (
              <div key={label} className="flex items-center justify-between py-3 border-b border-slate-100 last:border-0">
                <div className="flex items-center gap-3">
                  <span className="text-xl">{icon}</span>
                  <span className="text-sm text-slate-600">{label}</span>
                </div>
                <span className="font-bold text-slate-900 text-lg">{value}</span>
              </div>
            ))}
          </div>
        </motion.div>
      </div>

      {/* Top hashtags chart */}
      {hashtagData.length > 0 && (
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }} className="card">
          <h3 className="font-semibold text-slate-900 mb-4 flex items-center gap-2">
            <Hash size={17} className="text-blue-500" /> Top Hashtags
          </h3>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={hashtagData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
              <XAxis dataKey="tag" tick={{ fontSize: 12 }} tickFormatter={v => `#${v}`} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip formatter={(v: any) => [`${v} uses`, 'Count']}
                labelFormatter={l => `#${l}`} />
              <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                {hashtagData.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </motion.div>
      )}

      {!analytics?.total_published && !analytics?.total_failed && (
        <div className="card text-center py-16">
          <BarChart3 size={36} className="mx-auto text-slate-300 mb-3" />
          <p className="font-medium text-slate-600">No data yet</p>
          <p className="text-sm text-slate-400 mt-1">Analytics will appear after you publish your first post</p>
        </div>
      )}
    </div>
  );
}
