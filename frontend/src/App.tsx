import { Component, lazy, Suspense, type ReactNode } from 'react'
import { BrowserRouter, Route, Routes, useLocation } from 'react-router-dom'
import { MutationCache, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { FileQuestion, TriangleAlert } from 'lucide-react'
import { ApiError } from '@/lib/api'
import { AuthProvider } from '@/hooks/useAuth'
import { ToastProvider } from '@/components/ui/toast'
import { ButtonLink, Button } from '@/components/ui/button'
import { EmptyState, PageLoader } from '@/components/ui/misc'
import { RequireAuth } from '@/components/layout/AppShell'
import {
  AcceptInvitePage,
  ForgotPasswordPage,
  LoginPage,
  RegisterPage,
  ResetPasswordPage,
} from '@/features/auth/AuthPages'
import { LandingPage } from '@/features/public/LandingPage'

// Route-level code splitting keeps the candidate interview page and landing page light
const DashboardPage = lazy(() => import('@/features/dashboard/DashboardPage').then((m) => ({ default: m.DashboardPage })))
const JobsPage = lazy(() => import('@/features/jobs/JobsPage').then((m) => ({ default: m.JobsPage })))
const NewJobPage = lazy(() => import('@/features/jobs/NewJobPage').then((m) => ({ default: m.NewJobPage })))
const JobDetailPage = lazy(() => import('@/features/jobs/JobDetailPage').then((m) => ({ default: m.JobDetailPage })))
const ApplicationPage = lazy(() => import('@/features/applications/ApplicationPage').then((m) => ({ default: m.ApplicationPage })))
const CandidatesPage = lazy(() => import('@/features/candidates/CandidatesPage').then((m) => ({ default: m.CandidatesPage })))
const CandidatePage = lazy(() => import('@/features/candidates/CandidatePage').then((m) => ({ default: m.CandidatePage })))
const InterviewsPage = lazy(() => import('@/features/interviews/InterviewsPage').then((m) => ({ default: m.InterviewsPage })))
const FairnessPage = lazy(() => import('@/features/fairness/FairnessPage').then((m) => ({ default: m.FairnessPage })))
const SettingsPage = lazy(() => import('@/features/settings/SettingsPage').then((m) => ({ default: m.SettingsPage })))
const CareersPage = lazy(() => import('@/features/careers/CareersPage').then((m) => ({ default: m.CareersPage })))
const CareerJobPage = lazy(() => import('@/features/careers/CareersPage').then((m) => ({ default: m.CareerJobPage })))
const CandidateInterviewPage = lazy(() =>
  import('@/features/public/CandidateInterviewPage').then((m) => ({ default: m.CandidateInterviewPage })),
)

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      refetchOnWindowFocus: true,
      retry: (count, err) => !(err instanceof ApiError && err.status >= 400 && err.status < 500) && count < 2,
    },
  },
  mutationCache: new MutationCache({
    onError: (err) => {
      // Session expired mid-use → drop to the login screen
      if (err instanceof ApiError && err.status === 401) queryClient.setQueryData(['me'], null)
    },
  }),
})

class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null }
  static getDerivedStateFromError(error: Error) {
    return { error }
  }
  render() {
    if (this.state.error) {
      return (
        <EmptyState
          className="min-h-screen"
          icon={<TriangleAlert />}
          title="Something went wrong"
          description="An unexpected error occurred in this page. Reloading usually fixes it."
          action={<Button onClick={() => window.location.reload()}>Reload</Button>}
        />
      )
    }
    return this.props.children
  }
}

/** Remount on a new top-bar search so the page picks up the new ?q= */
function CandidatesRoute() {
  const { search } = useLocation()
  return <CandidatesPage key={search} />
}

function NotFound() {
  return (
    <EmptyState
      className="min-h-[70vh]"
      icon={<FileQuestion />}
      title="Page not found"
      description="The page you’re looking for doesn’t exist or was moved."
      action={<ButtonLink to="/">Go home</ButtonLink>}
    />
  )
}

export default function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <BrowserRouter>
            <AuthProvider>
              <Suspense fallback={<PageLoader />}>
                <Routes>
                  <Route path="/" element={<LandingPage />} />
                  <Route path="/login" element={<LoginPage />} />
                  <Route path="/register" element={<RegisterPage />} />
                  <Route path="/forgot-password" element={<ForgotPasswordPage />} />
                  <Route path="/reset-password" element={<ResetPasswordPage />} />
                  <Route path="/accept-invite" element={<AcceptInvitePage />} />
                  <Route path="/interview/:token" element={<CandidateInterviewPage />} />
                  <Route path="/careers/:slug" element={<CareersPage />} />
                  <Route path="/careers/:slug/jobs/:jobId" element={<CareerJobPage />} />
                  <Route path="/app" element={<RequireAuth />}>
                    <Route index element={<DashboardPage />} />
                    <Route path="jobs" element={<JobsPage />} />
                    <Route path="jobs/new" element={<NewJobPage />} />
                    <Route path="jobs/:jobId" element={<JobDetailPage />} />
                    <Route path="applications/:applicationId" element={<ApplicationPage />} />
                    <Route path="candidates" element={<CandidatesRoute />} />
                    <Route path="candidates/:candidateId" element={<CandidatePage />} />
                    <Route path="interviews" element={<InterviewsPage />} />
                    <Route path="fairness" element={<FairnessPage />} />
                    <Route path="settings" element={<SettingsPage />} />
                    <Route path="*" element={<NotFound />} />
                  </Route>
                  <Route path="*" element={<NotFound />} />
                </Routes>
              </Suspense>
            </AuthProvider>
          </BrowserRouter>
        </ToastProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  )
}
