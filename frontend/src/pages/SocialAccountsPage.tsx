import React, { useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import { Link2, Unlink, ExternalLink, CheckCircle, AlertCircle } from 'lucide-react';
import api from '@/lib/axios';
import type { ConnectedAccount } from '@/types';
import toast from 'react-hot-toast';

const PLATFORMS = [
  {
    id: 'linkedin', name: 'LinkedIn', icon: '💼', color: '#0A66C2',
    desc: 'Publish professional posts and articles to your LinkedIn network',
    requirements: ['LinkedIn Developer App', 'w_member_social permission'],
  },
  {
    id: 'instagram', name: 'Instagram', icon: '📸', color: '#E1306C',
    desc: 'Publish photo posts to your Instagram Business or Creator account',
    requirements: ['Instagram Business/Creator account', 'Connected Facebook Page'],
  },
];

export default function SocialAccountsPage() {
  const qc = useQueryClient();
  const { data: accounts = [], isLoading } = useQuery<ConnectedAccount[]>({
    queryKey: ['social-accounts'],
    queryFn: () => api.get('/api/v1/social').then(r => r.data),
  });

  useEffect(() => {
    const handleMessage = (e: MessageEvent) => {
      if (e.data && e.data.type === 'SOCIAL_CONNECTED') {
        qc.invalidateQueries({ queryKey: ['social-accounts'] });
        toast.success(`${e.data.platform.toUpperCase()} connected successfully!`);
      }
    };
    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [qc]);

  const connectLinkedIn = async () => {
    const res = await api.get('/api/v1/social/linkedin/auth-url').then(r => r.data);
    window.open(res.auth_url, '_blank', 'width=600,height=700');
    toast('Complete authorization in the popup window', { icon: '🔗' });
  };

  const connectInstagram = async () => {
    const res = await api.get('/api/v1/social/instagram/auth-url').then(r => r.data);
    window.open(res.auth_url, '_blank', 'width=600,height=700');
    toast('Complete authorization in the popup window', { icon: '🔗' });
  };

  const disconnectMutation = useMutation({
    mutationFn: (platform: string) => api.delete(`/api/v1/social/${platform}`).then(r => r.data),
    onSuccess: (_, platform) => {
      qc.invalidateQueries({ queryKey: ['social-accounts'] });
      toast.success(`${platform} disconnected`);
    },
  });

  const [pageIdInput, setPageIdInput] = React.useState<Record<string, string>>({});

  const updatePageIdMutation = useMutation({
    mutationFn: ({ platform, pageId }: { platform: string, pageId: string }) => 
      api.patch(`/api/v1/social/${platform}/page`, { page_id: pageId }).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['social-accounts'] });
      toast.success('Page ID saved!');
    },
    onError: () => toast.error('Failed to save Page ID')
  });

  const getAccount = (platform: string) => accounts.find(a => a.platform === platform);

  return (
    <div className="animate-fade-up max-w-2xl">
      <div className="page-header">
        <h1 className="page-title">Social Accounts</h1>
        <p className="page-subtitle">Connect your social media accounts to enable publishing</p>
      </div>

      <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl mb-6 flex gap-3 items-start">
        <AlertCircle size={16} className="text-amber-600 mt-0.5 shrink-0" />
        <p className="text-sm text-amber-700">
          <strong>Note:</strong> LinkedIn and Instagram require approved Developer Apps.
          See the setup guide for configuration instructions.
        </p>
      </div>

      <div className="space-y-4">
        {PLATFORMS.map((platform, i) => {
          const account = getAccount(platform.id);
          const isConnected = account?.status === 'connected';

          return (
            <motion.div key={platform.id}
              initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.1 }}
              className={`card border-2 transition-all ${isConnected ? 'border-green-200' : 'border-transparent'}`}>
              <div className="flex items-start gap-4">
                <div className="w-14 h-14 rounded-2xl flex items-center justify-center text-2xl"
                  style={{ background: `${platform.color}15` }}>
                  {platform.icon}
                </div>

                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="font-semibold text-slate-900">{platform.name}</h3>
                    {isConnected
                      ? <span className="badge badge-green"><CheckCircle size={10} /> Connected</span>
                      : <span className="badge badge-gray">Not Connected</span>}
                  </div>
                  <p className="text-sm text-slate-500 mb-2">{platform.desc}</p>

                  {isConnected && account ? (
                    <div className="flex flex-col gap-3">
                      <div className="p-3 bg-green-50 rounded-xl text-sm">
                        <p className="font-medium text-green-800">@{account.platform_username || account.platform_user_id}</p>
                        <p className="text-xs text-green-600 mt-0.5">
                          Connected on {new Date(account.created_at).toLocaleDateString()}
                        </p>
                      </div>
                      
                      {platform.id === 'linkedin' && (
                        <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl text-sm">
                          <label className="block font-semibold text-slate-700 mb-1">Company Page ID (Optional)</label>
                          <p className="text-xs text-slate-500 mb-2">
                            To publish to a company page instead of your personal profile, enter its ID here.
                          </p>
                          <div className="flex gap-2">
                            <input 
                              type="text" 
                              className="input flex-1 text-sm py-1.5"
                              placeholder={account.platform_page_id || "e.g. 12345678"}
                              value={pageIdInput[platform.id] !== undefined ? pageIdInput[platform.id] : (account.platform_page_id || '')}
                              onChange={(e) => setPageIdInput({ ...pageIdInput, [platform.id]: e.target.value })}
                            />
                            <button 
                              className="btn btn-primary btn-sm px-4"
                              disabled={updatePageIdMutation.isPending}
                              onClick={() => updatePageIdMutation.mutate({ platform: platform.id, pageId: pageIdInput[platform.id] || '' })}
                            >
                              Save
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div>
                      <p className="text-xs text-slate-400 mb-2">Requirements:</p>
                      <ul className="space-y-1">
                        {platform.requirements.map(r => (
                          <li key={r} className="text-xs text-slate-500 flex items-center gap-1.5">
                            <span className="w-1 h-1 bg-slate-400 rounded-full" />{r}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>

                <div className="flex flex-col gap-2">
                  {isConnected ? (
                    <button
                      onClick={() => disconnectMutation.mutate(platform.id)}
                      disabled={disconnectMutation.isPending}
                      className="btn btn-danger btn-sm">
                      <Unlink size={14} /> Disconnect
                    </button>
                  ) : (
                    <button
                      onClick={platform.id === 'linkedin' ? connectLinkedIn : connectInstagram}
                      className="btn btn-primary btn-sm">
                      <Link2 size={14} /> Connect
                    </button>
                  )}
                </div>
              </div>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
