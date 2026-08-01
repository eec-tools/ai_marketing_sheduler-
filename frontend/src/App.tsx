import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'react-hot-toast';
import { AuthProvider } from '@/providers/AuthProvider';
import AppLayout from '@/components/layout/AppLayout';

// Pages
import LoginPage from '@/pages/LoginPage';
import RegisterPage from '@/pages/RegisterPage';
import ForgotPasswordPage from '@/pages/ForgotPasswordPage';
import DashboardPage from '@/pages/DashboardPage';
import BrandProfilePage from '@/pages/BrandProfilePage';
import ApiKeysPage from '@/pages/ApiKeysPage';
import SocialAccountsPage from '@/pages/SocialAccountsPage';
import ContentPlannerPage from '@/pages/ContentPlannerPage';
import AIGeneratorPage from '@/pages/AIGeneratorPage';
import SchedulerPage from '@/pages/SchedulerPage';
import PublishedPage from '@/pages/PublishedPage';
import HistoryPage from '@/pages/HistoryPage';
import AnalyticsPage from '@/pages/AnalyticsPage';
import SettingsPage from '@/pages/SettingsPage';
import ApprovalHubPage from '@/pages/ApprovalHubPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            {/* Public */}
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />

            {/* Protected */}
            <Route element={<AppLayout />}>
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/brand" element={<BrandProfilePage />} />
              <Route path="/api-keys" element={<ApiKeysPage />} />
              <Route path="/social" element={<SocialAccountsPage />} />
              <Route path="/planner" element={<ContentPlannerPage />} />
              <Route path="/generate" element={<AIGeneratorPage />} />
              <Route path="/approval-hub" element={<ApprovalHubPage />} />
              <Route path="/scheduler" element={<SchedulerPage />} />
              <Route path="/published" element={<PublishedPage />} />
              <Route path="/history" element={<HistoryPage />} />
              <Route path="/analytics" element={<AnalyticsPage />} />
              <Route path="/settings" element={<SettingsPage />} />
            </Route>

            {/* Redirect root */}
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </BrowserRouter>

        <Toaster
          position="top-right"
          toastOptions={{
            duration: 4000,
            style: {
              background: '#fff',
              color: '#0F172A',
              border: '1px solid #E2E8F0',
              borderRadius: '12px',
              fontSize: '14px',
              fontFamily: 'Inter, sans-serif',
              boxShadow: '0 4px 16px rgba(0,0,0,0.08)',
            },
          }}
        />
      </AuthProvider>
    </QueryClientProvider>
  );
}
