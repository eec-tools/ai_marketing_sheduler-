import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Plus, Trash2, Eye, EyeOff, TestTube, ToggleLeft, ToggleRight,
  CheckCircle, XCircle, Clock, GripVertical, Zap, Star, AlertTriangle
} from 'lucide-react';
import { DndContext, closestCenter, DragEndEvent } from '@dnd-kit/core';
import { SortableContext, verticalListSortingStrategy, useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import api from '@/lib/axios';
import type { ApiKey, ApiKeyTestResult } from '@/types';
import toast from 'react-hot-toast';

const PROVIDERS = [
  { id: 'groq', name: 'Groq', icon: '⚡', color: '#F97316', desc: 'LLaMA text generation' },
  { id: 'gemini', name: 'Gemini', icon: '✨', color: '#2563EB', desc: 'Image generation & vision' },
  { id: 'claude', name: 'Claude (Anthropic)', icon: '🧠', color: '#D97757', desc: 'Claude 3.5 Sonnet text generation' },
];

function KeyCard({ keyItem, onTest, onToggle, onDelete, testResult, testing }: any) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: keyItem.id });
  const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.5 : 1 };

  const isCooling = keyItem.last_failed_at &&
    (Date.now() - new Date(keyItem.last_failed_at).getTime()) < 60000;

  const statusBadge = isCooling
    ? <span className="badge badge-yellow">⏱ Cooling Down</span>
    : !keyItem.is_valid
    ? <span className="badge badge-red">✗ Invalid</span>
    : !keyItem.is_active
    ? <span className="badge badge-gray">Disabled</span>
    : <span className="badge badge-green">✓ Active</span>;

  return (
    <div ref={setNodeRef} style={style}
      className={`p-4 border rounded-xl transition-all ${keyItem.is_active ? 'border-slate-200 bg-white' : 'border-slate-100 bg-slate-50'}`}>
      <div className="flex items-start gap-3">
        <div {...attributes} {...listeners}
          className="mt-1 cursor-grab active:cursor-grabbing text-slate-300 hover:text-slate-400">
          <GripVertical size={16} />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className="font-semibold text-sm text-slate-900">{keyItem.label}</span>
            {keyItem.priority === 1 && <Star size={12} className="text-yellow-400 fill-yellow-400" />}
            {statusBadge}
          </div>
          <p className="text-xs font-mono text-slate-400 mb-2">{keyItem.masked_key}</p>

          {testResult && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
              className={`text-xs p-2 rounded-lg flex items-center gap-1.5 mb-2 ${
                testResult.success ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-600'}`}>
              {testResult.success
                ? <><CheckCircle size={12} /> Connected ({testResult.latency_ms}ms)</>
                : <><XCircle size={12} /> {testResult.message}</>}
            </motion.div>
          )}

          <div className="flex items-center gap-3 text-xs text-slate-400">
            <span>Used: {keyItem.usage_count}×</span>
            <span>Fails: {keyItem.fail_count}</span>
            {keyItem.last_used_at && (
              <span>Last: {new Date(keyItem.last_used_at).toLocaleDateString()}</span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <button onClick={() => onTest(keyItem.id)} disabled={testing}
            className="btn btn-ghost btn-sm" title="Test key">
            {testing ? <div className="w-3 h-3 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
              : <TestTube size={15} />}
          </button>
          <button onClick={() => onToggle(keyItem.id)}
            className="btn btn-ghost btn-sm" title={keyItem.is_active ? 'Disable' : 'Enable'}>
            {keyItem.is_active ? <ToggleRight size={15} className="text-blue-500" /> : <ToggleLeft size={15} />}
          </button>
          <button onClick={() => onDelete(keyItem.id)}
            className="btn btn-ghost btn-sm text-slate-400 hover:text-red-500" title="Delete">
            <Trash2 size={15} />
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ApiKeysPage() {
  const qc = useQueryClient();
  const [showAdd, setShowAdd] = useState<string | null>(null);
  const [newKey, setNewKey] = useState({ label: '', key: '', priority: 1 });
  const [showKey, setShowKey] = useState(false);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, ApiKeyTestResult>>({});
  const [testingAll, setTestingAll] = useState(false);

  const { data: keys = [], isLoading } = useQuery<ApiKey[]>({
    queryKey: ['api-keys'],
    queryFn: () => api.get('/api/v1/keys').then(r => r.data),
  });

  const addMutation = useMutation({
    mutationFn: (data: any) => api.post('/api/v1/keys', data).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['api-keys'] });
      setShowAdd(null);
      setNewKey({ label: '', key: '', priority: 1 });
      toast.success('API key added!');
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Failed to add key'),
  });

  const toggleMutation = useMutation({
    mutationFn: (id: string) => api.patch(`/api/v1/keys/${id}/toggle`).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['api-keys'] }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/api/v1/keys/${id}`).then(r => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['api-keys'] }); toast.success('Key deleted'); },
  });

  const testKey = async (id: string) => {
    setTestingId(id);
    try {
      const result = await api.post(`/api/v1/keys/${id}/test`).then(r => r.data);
      setTestResults(prev => ({ ...prev, [id]: result }));
      toast[result.success ? 'success' : 'error'](result.message);
      qc.invalidateQueries({ queryKey: ['api-keys'] });
    } catch { toast.error('Test failed'); }
    finally { setTestingId(null); }
  };

  const testAll = async () => {
    setTestingAll(true);
    try {
      const results: ApiKeyTestResult[] = await api.post('/api/v1/keys/test-all').then(r => r.data);
      const map: Record<string, ApiKeyTestResult> = {};
      results.forEach(r => { map[r.key_id] = r; });
      setTestResults(map);
      const passed = results.filter(r => r.success).length;
      toast.success(`${passed}/${results.length} keys connected`);
      qc.invalidateQueries({ queryKey: ['api-keys'] });
    } catch { toast.error('Test all failed'); }
  };

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIndex = keys.findIndex(k => k.id === active.id);
    const newIndex = keys.findIndex(k => k.id === over.id);
    if (oldIndex !== -1 && newIndex !== -1) {
      await api.patch(`/api/v1/keys/${active.id}/priority`, null, { params: { priority: newIndex + 1 } });
      qc.invalidateQueries({ queryKey: ['api-keys'] });
    }
  };

  return (
    <div className="animate-fade-up max-w-3xl">
      <div className="page-header flex items-center justify-between">
        <div>
          <h1 className="page-title">API Keys</h1>
          <p className="page-subtitle">Add multiple keys per provider — system rotates automatically</p>
        </div>
        <div className="flex items-center gap-2">
          {keys.length > 0 && (
            <button onClick={testAll} disabled={testingAll} className="btn btn-secondary btn-sm">
              {testingAll ? 'Testing...' : <><TestTube size={14} /> Test All</>}
            </button>
          )}
        </div>
      </div>

      <div className="p-4 bg-blue-50 border border-blue-200 rounded-xl mb-6 flex gap-3 items-start">
        <Zap size={16} className="text-blue-600 mt-0.5 shrink-0" />
        <p className="text-sm text-blue-700">
          <strong>Key Rotation:</strong> Add multiple keys per provider. If one hits rate limits,
          the system automatically switches to the next. Drag to reorder priority.
        </p>
      </div>

      {PROVIDERS.map(provider => {
        const providerKeys = keys.filter(k => k.provider === provider.id)
          .sort((a, b) => a.priority - b.priority);

        return (
          <div key={provider.id} className="card mb-5">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center text-xl"
                  style={{ background: `${provider.color}15` }}>
                  {provider.icon}
                </div>
                <div>
                  <h3 className="font-semibold text-slate-900">{provider.name}</h3>
                  <p className="text-xs text-slate-500">{provider.desc} · {providerKeys.length} key{providerKeys.length !== 1 ? 's' : ''}</p>
                </div>
              </div>
              <button onClick={() => setShowAdd(provider.id)} className="btn btn-primary btn-sm">
                <Plus size={14} /> Add Key
              </button>
            </div>

            {/* Add key form */}
            <AnimatePresence>
              {showAdd === provider.id && (
                <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }} className="mb-4 p-4 bg-slate-50 rounded-xl border border-slate-200">
                  <div className="space-y-3">
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs font-medium text-slate-600 mb-1">Label</label>
                        <input className="input text-sm" value={newKey.label}
                          onChange={e => setNewKey(k => ({ ...k, label: e.target.value }))}
                          placeholder="e.g., Main Key" />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-slate-600 mb-1">Priority</label>
                        <input type="number" min={1} className="input text-sm" value={newKey.priority}
                          onChange={e => setNewKey(k => ({ ...k, priority: parseInt(e.target.value) }))} />
                      </div>
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-slate-600 mb-1">API Key</label>
                      <div className="relative">
                        <input type={showKey ? 'text' : 'password'} className="input text-sm pr-10 font-mono"
                          value={newKey.key}
                          onChange={e => setNewKey(k => ({ ...k, key: e.target.value }))}
                          placeholder={provider.id === 'claude' ? 'sk-ant-api...' : provider.id === 'groq' ? 'gsk_...' : 'AIza...'} />
                        <button type="button" onClick={() => setShowKey(!showKey)}
                          className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400">
                          {showKey ? <EyeOff size={14} /> : <Eye size={14} />}
                        </button>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => addMutation.mutate({ provider: provider.id, api_key: newKey.key, label: newKey.label || `${provider.name} Key`, priority: newKey.priority })}
                        disabled={!newKey.key || addMutation.isPending}
                        className="btn btn-primary btn-sm">
                        {addMutation.isPending ? 'Adding...' : 'Add Key'}
                      </button>
                      <button onClick={() => setShowAdd(null)} className="btn btn-ghost btn-sm">Cancel</button>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Key list */}
            {isLoading ? (
              <div className="space-y-2">
                {[1, 2].map(i => <div key={i} className="skeleton h-20 rounded-xl" />)}
              </div>
            ) : providerKeys.length === 0 ? (
              <div className="text-center py-8 text-sm text-slate-400">
                <AlertTriangle size={24} className="mx-auto mb-2 text-slate-300" />
                No keys yet — add one to get started
              </div>
            ) : (
              <DndContext collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
                <SortableContext items={providerKeys.map(k => k.id)} strategy={verticalListSortingStrategy}>
                  <div className="space-y-2">
                    {providerKeys.map(key => (
                      <KeyCard key={key.id} keyItem={key}
                        onTest={testKey} onToggle={(id: string) => toggleMutation.mutate(id)}
                        onDelete={(id: string) => deleteMutation.mutate(id)}
                        testResult={testResults[key.id]}
                        testing={testingId === key.id} />
                    ))}
                  </div>
                </SortableContext>
              </DndContext>
            )}
          </div>
        );
      })}
    </div>
  );
}
