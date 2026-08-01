import React, { useState, useEffect, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import { Save, Plus, X, Palette, Upload, ImageIcon, Brain } from 'lucide-react';
import api from '@/lib/axios';
import type { BrandProfile } from '@/types';
import toast from 'react-hot-toast';
import { useMemoryState } from '@/hooks/useMemoryState';

const TONES = ['professional', 'friendly', 'witty', 'authoritative', 'inspirational', 'casual'];
const STYLES = ['professional', 'minimal', 'corporate', 'creative', 'bold'];
const SIZES = ['square', 'portrait', 'landscape'];
const LANGUAGES = ['English', 'Hindi', 'Spanish', 'French', 'German', 'Arabic', 'Portuguese'];
const INDUSTRIES = ['Technology', 'Healthcare', 'Finance', 'Retail', 'Education', 'Marketing', 'Manufacturing', 'Real Estate', 'Food & Beverage', 'Sourcing & Procurement', 'Other'];

export default function BrandProfilePage() {
  const qc = useQueryClient();
  const { data: brand, isLoading } = useQuery<BrandProfile>({
    queryKey: ['brand'],
    queryFn: () => api.get('/api/v1/brand').then(r => r.data).catch(() => null),
  });

  const [form, setForm] = useMemoryState('brand_form', {
    company_name: '', brand_name: '', target_audience: '', industry: '',
    writing_tone: 'professional', preferred_language: 'English',
    cta: '', hashtags: [] as string[], primary_color: '#2563EB',
    secondary_color: '#64748B', image_style: 'professional',
    image_size: 'square', posting_style: 'informative',
    avoid_words: [] as string[], keywords: [] as string[],
    image_instructions: '', caption_template: '',
    // Company Intelligence
    company_description: '',
    products_services: '',
    unique_value_proposition: '',
    customer_pain_points: '',
    competitors_differentiators: '',
  });
  const [logoPreview, setLogoPreview] = useState<string | null>(null);
  const [logoUploading, setLogoUploading] = useState(false);
  const logoInputRef = useRef<HTMLInputElement>(null);
  const [hashtagInput, setHashtagInput] = useState('');
  const [keywordInput, setKeywordInput] = useState('');
  const [avoidInput, setAvoidInput] = useState('');

  const [formInitialized, setFormInitialized] = useMemoryState('brand_form_init', false);

  useEffect(() => {
    if (brand && !formInitialized) {
      setForm(prev => ({ ...prev, ...brand }));
      setLogoPreview(brand.logo_url || null);
      setFormInitialized(true);
    }
  }, [brand, formInitialized]);

  const mutation = useMutation({
    mutationFn: (data: any) => api.put('/api/v1/brand', data).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['brand'] });
      toast.success('Brand profile saved!');
    },
    onError: () => toast.error('Failed to save brand profile'),
  });

  const logoMutation = useMutation({
    mutationFn: (logoDataUri: string) =>
      api.post('/api/v1/brand/logo-data', { logo_url: logoDataUri }).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['brand'] });
      toast.success('Logo saved! It will appear on all generated images.');
    },
    onError: () => toast.error('Failed to save logo'),
  });

  const handleLogoUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      toast.error('Only image files are allowed');
      return;
    }
    if (file.size > 2 * 1024 * 1024) {
      toast.error('Logo must be under 2MB');
      return;
    }
    setLogoUploading(true);
    const reader = new FileReader();
    reader.onload = (ev) => {
      const dataUri = ev.target?.result as string;
      setLogoPreview(dataUri);
      logoMutation.mutate(dataUri);
      setLogoUploading(false);
    };
    reader.onerror = () => {
      toast.error('Failed to read logo file');
      setLogoUploading(false);
    };
    reader.readAsDataURL(file);
    // Reset input so same file can be re-uploaded
    e.target.value = '';
  };

  const handleRemoveLogo = () => {
    setLogoPreview(null);
    logoMutation.mutate('');
  };
  const addTag = (field: 'hashtags' | 'keywords' | 'avoid_words', value: string, setter: (v: string) => void) => {
    const cleaned = value.replace(/^#/, '').trim();
    if (cleaned && !form[field].includes(cleaned)) {
      setForm(f => ({ ...f, [field]: [...f[field], cleaned] }));
    }
    setter('');
  };

  const removeTag = (field: 'hashtags' | 'keywords' | 'avoid_words', tag: string) =>
    setForm(f => ({ ...f, [field]: f[field].filter(t => t !== tag) }));

  const TagInput = ({ field, value, setValue, placeholder, prefix }: any) => (
    <div>
      <div className="flex gap-2 flex-wrap mb-2">
        {form[field].map((tag: string) => (
          <span key={tag} className="badge badge-blue flex items-center gap-1">
            {prefix}{tag}
            <button onClick={() => removeTag(field, tag)} className="hover:text-red-500">
              <X size={11} />
            </button>
          </span>
        ))}
      </div>
      <div className="flex gap-2">
        <input className="input flex-1" value={value} onChange={e => setValue(e.target.value)}
          placeholder={placeholder}
          onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addTag(field, value, setValue); } }} />
        <button onClick={() => addTag(field, value, setValue)} className="btn btn-secondary btn-sm">
          <Plus size={15} />
        </button>
      </div>
    </div>
  );

  if (isLoading) return (
    <div className="space-y-4">
      {[...Array(6)].map((_, i) => <div key={i} className="skeleton h-16 rounded-xl" />)}
    </div>
  );

  return (
    <div className="animate-fade-up max-w-3xl">
      <div className="page-header">
        <h1 className="page-title">Brand Profile</h1>
        <p className="page-subtitle">Define your brand identity — AI uses this for all generated content</p>
      </div>

      <div className="space-y-6">
        {/* Brand Logo */}
        <div className="card border-2 border-blue-100">
          <h3 className="font-semibold text-slate-900 mb-1 flex items-center gap-2">
            <ImageIcon size={17} className="text-blue-500" /> Brand Logo
          </h3>
          <p className="text-xs text-slate-500 mb-4">
            Your logo will appear on every generated image card. PNG or SVG with transparent background works best.
          </p>
          <div className="flex items-start gap-5">
            {/* Logo Preview */}
            <div className="shrink-0">
              {logoPreview ? (
                <div className="relative w-28 h-28 rounded-2xl border-2 border-blue-200 bg-white flex items-center justify-center overflow-hidden shadow-sm">
                  <img src={logoPreview} alt="Brand logo" className="max-w-full max-h-full object-contain p-2" />
                  <button
                    onClick={handleRemoveLogo}
                    className="absolute top-1 right-1 w-6 h-6 bg-red-500 text-white rounded-full flex items-center justify-center shadow hover:bg-red-600 transition-colors"
                    title="Remove logo"
                  >
                    <X size={13} />
                  </button>
                </div>
              ) : (
                <div className="w-28 h-28 rounded-2xl border-2 border-dashed border-slate-300 bg-slate-50 flex flex-col items-center justify-center text-slate-400 gap-1">
                  <ImageIcon size={26} />
                  <span className="text-xs">No logo</span>
                </div>
              )}
            </div>

            {/* Upload Controls */}
            <div className="flex-1">
              <input
                ref={logoInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={handleLogoUpload}
              />
              <button
                onClick={() => logoInputRef.current?.click()}
                disabled={logoUploading || logoMutation.isPending}
                className="btn btn-primary btn-sm flex items-center gap-2 mb-3"
              >
                {logoUploading || logoMutation.isPending ? (
                  <><div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" /> Uploading...</>
                ) : (
                  <><Upload size={15} /> {logoPreview ? 'Change Logo' : 'Upload Logo'}</>
                )}
              </button>
              <ul className="text-xs text-slate-400 space-y-0.5">
                <li>✓ PNG, JPG, SVG, or WebP accepted</li>
                <li>✓ Max 2 MB file size</li>
                <li>✓ Transparent background recommended</li>
                <li>✓ Displayed in top corner of every generated card</li>
              </ul>
            </div>
          </div>
        </div>

        {/* Company info */}
        <div className="card">
          <h3 className="font-semibold text-slate-900 mb-4">Company Information</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[
              { label: 'Company Name', key: 'company_name', placeholder: 'Acme Corp' },
              { label: 'Brand Name', key: 'brand_name', placeholder: 'Acme' },
            ].map(({ label, key, placeholder }) => (
              <div key={key}>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">{label}</label>
                <input className="input" value={form[key as keyof typeof form] as string}
                  onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
                  placeholder={placeholder} />
              </div>
            ))}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Industry</label>
              <select className="input" value={form.industry}
                onChange={e => setForm(f => ({ ...f, industry: e.target.value }))}>
                <option value="">Select industry</option>
                {INDUSTRIES.map(i => <option key={i} value={i}>{i}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Language</label>
              <select className="input" value={form.preferred_language}
                onChange={e => setForm(f => ({ ...f, preferred_language: e.target.value }))}>
                {LANGUAGES.map(l => <option key={l}>{l}</option>)}
              </select>
            </div>
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Target Audience</label>
              <textarea className="input resize-none" rows={2} value={form.target_audience}
                onChange={e => setForm(f => ({ ...f, target_audience: e.target.value }))}
                placeholder="e.g., Small business owners aged 30-50 in manufacturing..." />
            </div>
          </div>
        </div>

        {/* Voice & Style */}
        <div className="card">
          <h3 className="font-semibold text-slate-900 mb-4">Voice & Style</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Writing Tone</label>
              <select className="input" value={form.writing_tone}
                onChange={e => setForm(f => ({ ...f, writing_tone: e.target.value }))}>
                {TONES.map(t => <option key={t} className="capitalize">{t}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Image Style</label>
              <select className="input" value={form.image_style}
                onChange={e => setForm(f => ({ ...f, image_style: e.target.value }))}>
                {STYLES.map(s => <option key={s} className="capitalize">{s}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Image Size</label>
              <select className="input" value={form.image_size}
                onChange={e => setForm(f => ({ ...f, image_size: e.target.value }))}>
                {SIZES.map(s => <option key={s} className="capitalize">{s}</option>)}
              </select>
            </div>
          </div>
          <div className="mt-4">
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Default Call to Action</label>
            <input className="input" value={form.cta}
              onChange={e => setForm(f => ({ ...f, cta: e.target.value }))}
              placeholder="e.g., Visit our website to learn more" />
          </div>
        </div>

        {/* Colors */}
        <div className="card">
          <h3 className="font-semibold text-slate-900 mb-4 flex items-center gap-2">
            <Palette size={17} /> Brand Colors
          </h3>
          <div className="grid grid-cols-2 gap-4">
            {[
              { label: 'Primary Color', key: 'primary_color' },
              { label: 'Secondary Color', key: 'secondary_color' },
            ].map(({ label, key }) => (
              <div key={key} className="flex items-center gap-3 p-3 border border-slate-200 rounded-xl">
                <input type="color" value={form[key as keyof typeof form] as string}
                  onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
                  className="w-10 h-10 rounded-lg border-0 cursor-pointer" />
                <div>
                  <p className="text-sm font-medium text-slate-700">{label}</p>
                  <p className="text-xs text-slate-400 font-mono">{form[key as keyof typeof form] as string}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Keywords & Hashtags */}
        <div className="card">
          <h3 className="font-semibold text-slate-900 mb-4">Content Preferences</h3>
          <div className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Default Hashtags</label>
              <TagInput field="hashtags" value={hashtagInput} setValue={setHashtagInput}
                placeholder="Add hashtag (press Enter)" prefix="#" />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Brand Keywords</label>
              <TagInput field="keywords" value={keywordInput} setValue={setKeywordInput}
                placeholder="Add keyword (press Enter)" prefix="" />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Avoid Words</label>
              <TagInput field="avoid_words" value={avoidInput} setValue={setAvoidInput}
                placeholder="Words to avoid in generated content" prefix="" />
            </div>
          </div>
        </div>

        {/* Custom AI Instructions & Templates */}
        <div className="card border-2 border-primary-500/20 bg-gradient-to-br from-primary-50/30 to-slate-50">
          <h3 className="font-semibold text-slate-900 mb-2 flex items-center gap-2 text-base">
            ✨ Custom AI Generation Rules & Templates
          </h3>
          <p className="text-xs text-slate-500 mb-5">
            Set strict company-style guidelines. The AI will strictly follow these instructions for every post and image generated.
          </p>
          <div className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-slate-800 mb-1">
                Custom Caption Creation Template / Structure Rules
              </label>
              <p className="text-xs text-slate-500 mb-2">
                Specify exact bullet formats, formatting preferences, or brand storytelling formulas you want enforced in captions.
              </p>
              <textarea
                className="input min-h-[100px] font-sans text-sm"
                value={form.caption_template || ''}
                onChange={e => setForm(f => ({ ...f, caption_template: e.target.value }))}
                placeholder="e.g., Always start with a bold statistics hook. Use only 3 bullet points. End with a question asking for audience feedback."
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-800 mb-1">
                Custom Image & Card Creation Instructions
              </label>
              <p className="text-xs text-slate-500 mb-2">
                Specify visual guidelines, color schemes, typography placement, or photography styles for generated cards and images.
              </p>
              <textarea
                className="input min-h-[100px] font-sans text-sm"
                value={form.image_instructions || ''}
                onChange={e => setForm(f => ({ ...f, image_instructions: e.target.value }))}
                placeholder="e.g., Use dark navy backgrounds with high-contrast white text. Include subtle geometric patterns. Never show generic office desks."
              />
            </div>
          </div>
        </div>

        {/* Company Intelligence */}
        <div className="card border-2 border-violet-100 bg-gradient-to-br from-violet-50/40 to-slate-50">
          <h3 className="font-semibold text-slate-900 mb-1 flex items-center gap-2 text-base">
            <Brain size={17} className="text-violet-500" /> Company Intelligence
          </h3>
          <p className="text-xs text-slate-500 mb-5">
            Tell the AI exactly what your company does. The more detail you add here, the more specific, authentic, and compelling every generated post will be.
          </p>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-1">
                What does your company do? <span className="text-violet-500">*</span>
              </label>
              <p className="text-xs text-slate-400 mb-1.5">A clear 1-3 sentence description of your business and what you offer.</p>
              <textarea
                className="input min-h-[80px] font-sans text-sm"
                value={form.company_description || ''}
                onChange={e => setForm(f => ({ ...f, company_description: e.target.value }))}
                placeholder="e.g., EEC is a B2B SaaS platform that helps mid-size manufacturers reduce energy waste by 30% using real-time IoT monitoring and AI-powered insights."
              />
            </div>
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-1">Key Products / Services</label>
              <p className="text-xs text-slate-400 mb-1.5">List your main offerings, separated by commas.</p>
              <textarea
                className="input min-h-[70px] font-sans text-sm"
                value={form.products_services || ''}
                onChange={e => setForm(f => ({ ...f, products_services: e.target.value }))}
                placeholder="e.g., Energy Audit Tool, Real-Time Smart Dashboard, Compliance Report Generator, Mobile App"
              />
            </div>
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-1">Unique Value Proposition</label>
              <p className="text-xs text-slate-400 mb-1.5">What makes you different? What can customers only get from you?</p>
              <textarea
                className="input min-h-[70px] font-sans text-sm"
                value={form.unique_value_proposition || ''}
                onChange={e => setForm(f => ({ ...f, unique_value_proposition: e.target.value }))}
                placeholder="e.g., The only platform that guarantees ROI within 6 months or you get a full refund. Plug-and-play setup — no consultants or IT team needed."
              />
            </div>
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-1">Customer Pain Points You Solve</label>
              <p className="text-xs text-slate-400 mb-1.5">What problems do your customers have before they find you?</p>
              <textarea
                className="input min-h-[70px] font-sans text-sm"
                value={form.customer_pain_points || ''}
                onChange={e => setForm(f => ({ ...f, customer_pain_points: e.target.value }))}
                placeholder="e.g., Skyrocketing energy bills, manual Excel-based tracking, compliance fines, no visibility into real-time usage, wasted engineer time."
              />
            </div>
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-1">Competitors &amp; Differentiators</label>
              <p className="text-xs text-slate-400 mb-1.5">Who do you compete with and how are you better?</p>
              <textarea
                className="input min-h-[70px] font-sans text-sm"
                value={form.competitors_differentiators || ''}
                onChange={e => setForm(f => ({ ...f, competitors_differentiators: e.target.value }))}
                placeholder="e.g., Unlike Siemens or Schneider, we are plug-and-play with no hardware costs. Unlike spreadsheets, we provide real-time AI alerts before problems happen."
              />
            </div>
          </div>
        </div>

        <button
          onClick={() => mutation.mutate(form)}
          disabled={mutation.isPending}
          className="btn btn-primary w-full"
        >
          {mutation.isPending ? 'Saving...' : <><Save size={16} /> Save Brand Profile</>}
        </button>
      </div>
    </div>
  );
}
