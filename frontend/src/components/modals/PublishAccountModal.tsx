import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { motion } from 'framer-motion';
import { Send, Sparkles, CheckCircle2 } from 'lucide-react';

const LinkedinIcon = ({ size = 20 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor">
    <path d="M19 3a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h14m-.5 15.5v-5.3a3.26 3.26 0 0 0-3.26-3.26c-.85 0-1.84.52-2.28 1.3v-1.11h-2.79v8.37h2.79v-4.93c0-.77.62-1.4 1.39-1.4a1.4 1.4 0 0 1 1.4 1.4v4.93h2.75M6.88 8.56a1.68 1.68 0 0 0 1.68-1.68c0-.93-.75-1.69-1.68-1.69a1.69 1.69 0 0 0-1.69 1.69c0 .93.76 1.68 1.69 1.68m1.39 9.94v-8.37H5.5v8.37h2.77z"/>
  </svg>
);

const InstagramIcon = ({ size = 20 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect width="20" height="20" x="2" y="2" rx="5" ry="5"/>
    <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"/>
    <line x1="17.5" x2="17.51" y1="6.5" y2="6.5"/>
  </svg>
);

interface PublishAccountModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (platform: string) => void;
  isPublishing?: boolean;
  initialPlatform?: string;
}

export const PublishAccountModal: React.FC<PublishAccountModalProps> = ({
  isOpen,
  onClose,
  onConfirm,
  isPublishing = false,
  initialPlatform = 'linkedin',
}) => {
  const [selectedPlatform, setSelectedPlatform] = useState<'linkedin' | 'instagram' | 'both'>('linkedin');

  useEffect(() => {
    if (initialPlatform === 'instagram') {
      setSelectedPlatform('instagram');
    } else if (initialPlatform === 'both') {
      setSelectedPlatform('both');
    } else {
      setSelectedPlatform('linkedin');
    }
  }, [initialPlatform, isOpen]);

  if (!isOpen) return null;

  return createPortal(
    <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fade-in">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="bg-white rounded-2xl shadow-2xl border border-slate-200 p-6 max-w-md w-full space-y-5 text-left"
      >
        <div className="text-center space-y-1.5">
          <div className="w-12 h-12 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center mx-auto shadow-inner mb-2">
            <Send size={24} className="ml-0.5" />
          </div>
          <h3 className="text-xl font-extrabold text-slate-900">Select Publishing Account</h3>
          <p className="text-xs text-slate-500 max-w-xs mx-auto leading-relaxed">
            Choose which social platform or connected account you want to publish this post to right now:
          </p>
        </div>

        <div className="space-y-2.5">
          {/* LinkedIn Option */}
          <div
            onClick={() => !isPublishing && setSelectedPlatform('linkedin')}
            className={`border-2 rounded-xl p-3.5 flex items-center gap-3.5 cursor-pointer transition-all ${
              selectedPlatform === 'linkedin'
                ? 'border-blue-600 bg-blue-50/70 text-blue-950 shadow-sm'
                : 'border-slate-200 hover:border-slate-300 text-slate-700'
            }`}
          >
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${
              selectedPlatform === 'linkedin' ? 'bg-blue-600 text-white shadow-md' : 'bg-slate-100 text-blue-600'
            }`}>
              <LinkedinIcon size={20} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between">
                <p className="font-bold text-sm">LinkedIn Account</p>
                {selectedPlatform === 'linkedin' && <CheckCircle2 size={16} className="text-blue-600 shrink-0" />}
              </div>
              <p className="text-xs text-slate-500 mt-0.5 line-clamp-1">
                Publish professional update to your LinkedIn network
              </p>
            </div>
          </div>

          {/* Instagram Option */}
          <div
            onClick={() => !isPublishing && setSelectedPlatform('instagram')}
            className={`border-2 rounded-xl p-3.5 flex items-center gap-3.5 cursor-pointer transition-all ${
              selectedPlatform === 'instagram'
                ? 'border-pink-600 bg-pink-50/70 text-pink-950 shadow-sm'
                : 'border-slate-200 hover:border-slate-300 text-slate-700'
            }`}
          >
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${
              selectedPlatform === 'instagram' ? 'bg-gradient-to-tr from-amber-500 via-pink-600 to-purple-600 text-white shadow-md' : 'bg-slate-100 text-pink-600'
            }`}>
              <InstagramIcon size={20} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between">
                <p className="font-bold text-sm">Instagram Account</p>
                {selectedPlatform === 'instagram' && <CheckCircle2 size={16} className="text-pink-600 shrink-0" />}
              </div>
              <p className="text-xs text-slate-500 mt-0.5 line-clamp-1">
                Publish visual graphic and caption directly to Instagram
              </p>
            </div>
          </div>

          {/* Both Option */}
          <div
            onClick={() => !isPublishing && setSelectedPlatform('both')}
            className={`border-2 rounded-xl p-3.5 flex items-center gap-3.5 cursor-pointer transition-all ${
              selectedPlatform === 'both'
                ? 'border-indigo-600 bg-indigo-50/70 text-indigo-950 shadow-sm'
                : 'border-slate-200 hover:border-slate-300 text-slate-700'
            }`}
          >
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${
              selectedPlatform === 'both' ? 'bg-indigo-600 text-white shadow-md' : 'bg-slate-100 text-indigo-600'
            }`}>
              <Sparkles size={20} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between">
                <p className="font-bold text-sm">Both LinkedIn & Instagram</p>
                {selectedPlatform === 'both' && <CheckCircle2 size={16} className="text-indigo-600 shrink-0" />}
              </div>
              <p className="text-xs text-slate-500 mt-0.5 line-clamp-1">
                Simultaneously broadcast across both connected platforms
              </p>
            </div>
          </div>
        </div>

        <div className="flex gap-3 pt-2">
          <button
            type="button"
            onClick={onClose}
            disabled={isPublishing}
            className="btn btn-secondary flex-1 py-2.5 font-bold text-xs"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => onConfirm(selectedPlatform)}
            disabled={isPublishing}
            className="btn bg-blue-600 hover:bg-blue-700 text-white flex-1 py-2.5 font-bold text-xs flex items-center justify-center gap-2 shadow-lg shadow-blue-500/20 rounded-xl transition-all"
          >
            <Send size={15} />
            {isPublishing
              ? 'Publishing...'
              : selectedPlatform === 'both'
              ? 'Publish to Both'
              : selectedPlatform === 'linkedin'
              ? 'Publish to LinkedIn'
              : 'Publish to Instagram'}
          </button>
        </div>
      </motion.div>
    </div>,
    document.body
  );
};
