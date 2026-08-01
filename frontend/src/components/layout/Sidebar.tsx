import React, { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  LayoutDashboard, Key, User, Link2, Calendar, Wand2,
  Clock, History, BarChart3, Settings, LogOut, Menu, X,
  Sparkles, ChevronRight, CheckCircle, ShieldCheck
} from 'lucide-react';
import { useAuth } from '@/providers/AuthProvider';

const NAV_ITEMS = [
  { icon: LayoutDashboard, label: 'Dashboard',      path: '/dashboard' },
  { icon: User,            label: 'Brand Profile',  path: '/brand' },
  { icon: Key,             label: 'API Keys',        path: '/api-keys' },
  { icon: Link2,           label: 'Social Accounts', path: '/social' },
  { icon: Calendar,        label: 'Content Planner', path: '/planner' },
  { icon: Wand2,           label: 'AI Generator',    path: '/generate' },
  { icon: ShieldCheck,     label: 'Approval Hub',    path: '/approval-hub' },
  { icon: Clock,           label: 'Scheduler',       path: '/scheduler' },
  { icon: CheckCircle,     label: 'Published',       path: '/published' },
  { icon: History,         label: 'History',         path: '/history' },
  { icon: BarChart3,       label: 'Analytics',       path: '/analytics' },
  { icon: Settings,        label: 'Settings',        path: '/settings' },
];

export default function Sidebar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const SidebarContent = () => (
    <div className="flex flex-col h-full">
      {/* Logo */}
      <div className="p-4 border-b border-slate-100">
        <div className="flex items-center gap-3">
          <img src="/logo.png" alt="AI Marketing Scheduler Logo" className="w-10 h-10 object-contain rounded-xl shadow-sm bg-white" />
          <div>
            <p className="font-extrabold text-[15px] tracking-wide text-slate-900 leading-tight">AI MARKETING<br/>SCHEDULER</p>
            <p className="text-[10px] text-slate-400 font-semibold tracking-wider uppercase mt-0.5">Smart Schedules</p>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 p-3 space-y-0.5 overflow-y-auto">
        {NAV_ITEMS.map(({ icon: Icon, label, path }) => (
          <NavLink
            key={path}
            to={path}
            onClick={() => setMobileOpen(false)}
            className={({ isActive }) =>
              `sidebar-item ${isActive ? 'active' : ''}`
            }
          >
            <Icon size={17} />
            <span className="flex-1">{label}</span>
            <ChevronRight size={13} className="opacity-0 group-hover:opacity-100 transition-opacity" />
          </NavLink>
        ))}
      </nav>

      {/* User footer */}
      <div className="p-3 border-t border-slate-100">
        <div className="flex items-center gap-3 p-2 rounded-xl hover:bg-slate-50 transition-colors">
          <div className="w-8 h-8 rounded-full gradient-primary flex items-center justify-center text-white text-xs font-bold shrink-0">
            {user?.full_name?.[0]?.toUpperCase() || user?.email?.[0]?.toUpperCase() || 'U'}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-slate-900 truncate">{user?.full_name || 'User'}</p>
            <p className="text-xs text-slate-400 truncate">{user?.email}</p>
          </div>
          <button onClick={handleLogout} className="p-1.5 rounded-lg text-slate-400 hover:text-red-500 hover:bg-red-50 transition-colors">
            <LogOut size={15} />
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop sidebar */}
      <aside className="sidebar hidden md:flex flex-col">
        <SidebarContent />
      </aside>

      {/* Mobile hamburger */}
      <button
        className="md:hidden fixed top-4 left-4 z-50 p-2 bg-white rounded-xl shadow-md border border-slate-200"
        onClick={() => setMobileOpen(!mobileOpen)}
      >
        {mobileOpen ? <X size={20} /> : <Menu size={20} />}
      </button>

      {/* Mobile drawer */}
      <AnimatePresence>
        {mobileOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/40 z-40 md:hidden"
              onClick={() => setMobileOpen(false)}
            />
            <motion.aside
              initial={{ x: -260 }} animate={{ x: 0 }} exit={{ x: -260 }}
              transition={{ type: 'spring', damping: 28, stiffness: 280 }}
              className="sidebar md:hidden flex flex-col z-50"
            >
              <SidebarContent />
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
