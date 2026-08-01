import React, { useState, useEffect } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import { User, Bell, Moon, Sun, Shield, Download, Trash2, Save, AlertTriangle } from 'lucide-react';
import { useAuth } from '@/providers/AuthProvider';
import api from '@/lib/axios';
import toast from 'react-hot-toast';
import { useNavigate } from 'react-router-dom';
import { useMemoryState } from '@/hooks/useMemoryState';

export default function SettingsPage() {
  const { user, refreshUser, logout } = useAuth();
  const qc = useQueryClient();
  const navigate = useNavigate();

  const [form, setForm] = useMemoryState('settings_form', {
    full_name: user?.full_name || '',
    theme: user?.theme || 'light',
    notifications_enabled: user?.notifications_enabled ?? true,
    max_retries: 3,
    automation_enabled: user?.automation_enabled ?? false,
    preferred_ai_provider: user?.preferred_ai_provider || 'groq',
  });
  const [showDelete, setShowDelete] = useState(false);

  // Preview theme instantly when user clicks it in settings
  useEffect(() => {
    if (form.theme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [form.theme]);

  const updateMutation = useMutation({
    mutationFn: (data: any) => api.put('/api/v1/users/me', data).then(r => r.data),
    onSuccess: () => { refreshUser(); toast.success('Settings saved!'); },
    onError: () => toast.error('Failed to save settings'),
  });

  const exportMutation = useMutation({
    mutationFn: () => api.get('/api/v1/users/me/export').then(r => r.data),
    onSuccess: (data) => {
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = 'my-data.json'; a.click();
      URL.revokeObjectURL(url);
      toast.success('Data exported!');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.delete('/api/v1/users/me').then(r => r.data),
    onSuccess: () => { logout(); navigate('/login'); toast.success('Account deleted'); },
  });

  return (
    <div className="animate-fade-up max-w-2xl">
      <div className="page-header">
        <h1 className="page-title">Settings</h1>
        <p className="page-subtitle">Manage your account preferences</p>
      </div>

      <div className="space-y-5">
        {/* Profile */}
        <div className="card">
          <h3 className="font-semibold text-slate-900 mb-4 flex items-center gap-2">
            <User size={16} /> Profile
          </h3>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Full Name</label>
              <input className="input" value={form.full_name}
                onChange={e => setForm(f => ({ ...f, full_name: e.target.value }))}
                placeholder="Your full name" />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Email</label>
              <input className="input opacity-60" value={user?.email || ''} disabled />
              <p className="text-xs text-slate-400 mt-1">Email cannot be changed</p>
            </div>
          </div>
        </div>

        {/* Appearance */}
        <div className="card">
          <h3 className="font-semibold text-slate-900 mb-4 flex items-center gap-2">
            <Sun size={16} /> Appearance
          </h3>
          <div className="flex items-center gap-3">
            {[
              { value: 'light', icon: Sun, label: 'Light' },
              { value: 'dark', icon: Moon, label: 'Dark' },
            ].map(({ value, icon: Icon, label }) => (
              <button key={value} onClick={() => setForm(f => ({ ...f, theme: value }))}
                className={`flex items-center gap-2 px-4 py-2.5 rounded-xl border text-sm font-medium transition-all
                  ${form.theme === value ? 'border-blue-500 bg-blue-50 text-blue-700' : 'border-slate-200 text-slate-500'}`}>
                <Icon size={14} /> {label}
              </button>
            ))}
          </div>
        </div>

        {/* Notifications */}
        <div className="card">
          <h3 className="font-semibold text-slate-900 mb-4 flex items-center gap-2">
            <Bell size={16} /> Notifications
          </h3>
          <div className="flex items-center justify-between p-3 bg-slate-50 rounded-xl">
            <div>
              <p className="text-sm font-medium text-slate-700">Email Notifications</p>
              <p className="text-xs text-slate-400">Get notified about publish results</p>
            </div>
            <button onClick={() => setForm(f => ({ ...f, notifications_enabled: !f.notifications_enabled }))}
              className={`relative w-12 h-6 rounded-full transition-colors ${form.notifications_enabled ? 'bg-blue-500' : 'bg-slate-300'}`}>
              <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform
                ${form.notifications_enabled ? 'translate-x-6' : 'translate-x-0'}`} />
            </button>
          </div>
        </div>

        {/* AI Settings */}
        <div className="card">
          <h3 className="font-semibold text-slate-900 mb-4 flex items-center gap-2">
            <Shield size={16} /> AI Settings
          </h3>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">
                Preferred Text Generator
              </label>
              <select className="input" value={form.preferred_ai_provider}
                onChange={e => setForm(f => ({ ...f, preferred_ai_provider: e.target.value }))}>
                <option value="groq">Groq (Llama Models)</option>
                <option value="claude">Claude (Anthropic Sonnet)</option>
              </select>
              <p className="text-xs text-slate-400 mt-1">
                Choose which API to use for generating text, scripts, and strategies.
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">
                Max Image Retries (1-10)
              </label>
              <input type="number" min={1} max={10} className="input w-32"
                value={form.max_retries}
                onChange={e => setForm(f => ({ ...f, max_retries: parseInt(e.target.value) }))} />
              <p className="text-xs text-slate-400 mt-1">
                How many times to regenerate an image if review fails
              </p>
            </div>
          </div>
        </div>

        {/* Brand & Custom AI Instructions Shortcut */}
        <div className="card bg-gradient-to-br from-primary-50/40 to-slate-50 border-primary-200/50 flex items-center justify-between p-4">
          <div>
            <h4 className="font-semibold text-slate-800 text-sm">🎨 Company Style & Custom AI Rules</h4>
            <p className="text-xs text-slate-500 mt-0.5">Configure your custom image instructions, caption rules, and brand templates.</p>
          </div>
          <button
            onClick={() => navigate('/brand')}
            className="btn btn-primary btn-sm whitespace-nowrap"
          >
            Configure Rules →
          </button>
        </div>

        <button onClick={() => updateMutation.mutate(form)}
          disabled={updateMutation.isPending}
          className="btn btn-primary w-full">
          {updateMutation.isPending ? 'Saving...' : <><Save size={15} /> Save Settings</>}
        </button>

        {/* Data & Account */}
        <div className="card border-slate-200">
          <h3 className="font-semibold text-slate-900 mb-4 flex items-center gap-2">
            <Download size={16} /> Data & Account
          </h3>
          <div className="space-y-3">
            <button onClick={() => exportMutation.mutate()} disabled={exportMutation.isPending}
              className="btn btn-secondary w-full">
              <Download size={15} />
              {exportMutation.isPending ? 'Exporting...' : 'Export My Data'}
            </button>

            {!showDelete ? (
              <button onClick={() => setShowDelete(true)} className="btn btn-ghost w-full text-red-500 hover:bg-red-50">
                <Trash2 size={15} /> Delete Account
              </button>
            ) : (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                className="p-4 bg-red-50 border border-red-200 rounded-xl">
                <div className="flex items-start gap-2 mb-3">
                  <AlertTriangle size={16} className="text-red-600 mt-0.5 shrink-0" />
                  <p className="text-sm text-red-700">
                    This will permanently delete your account and all data. This cannot be undone.
                  </p>
                </div>
                <div className="flex gap-2">
                  <button onClick={() => deleteMutation.mutate()} disabled={deleteMutation.isPending}
                    className="btn btn-danger btn-sm flex-1">
                    {deleteMutation.isPending ? 'Deleting...' : 'Yes, Delete Everything'}
                  </button>
                  <button onClick={() => setShowDelete(false)} className="btn btn-secondary btn-sm">Cancel</button>
                </div>
              </motion.div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
