import React from 'react';
import { Outlet, Navigate } from 'react-router-dom';
import Sidebar from './Sidebar';
import { useAuth } from '@/providers/AuthProvider';

export default function AppLayout() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="flex flex-col items-center justify-center h-screen space-y-4 animate-fade-in">
          <img src="/logo.png" alt="AI Marketing Scheduler" className="w-14 h-14 object-contain animate-bounce" />
          <p className="text-sm text-slate-900 font-bold tracking-wide">Loading AI MARKETING SCHEDULER...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="page-content flex-1">
        <Outlet />
      </main>
    </div>
  );
}
