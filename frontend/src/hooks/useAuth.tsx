import { createContext, useCallback, useContext, useMemo, type ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api, ApiError } from '@/lib/api'
import type { Me, Role } from '@/lib/types'

interface AuthState {
  me: Me | null
  loading: boolean
  setSession: (me: Me) => void
  logout: () => Promise<void>
  can: (action: 'write' | 'admin') => boolean
}

const AuthContext = createContext<AuthState | null>(null)

const WRITE_ROLES: Role[] = ['owner', 'admin', 'recruiter']
const ADMIN_ROLES: Role[] = ['owner', 'admin']

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({
    queryKey: ['me'],
    queryFn: async () => {
      try {
        return await api.me()
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) return null
        throw e
      }
    },
    staleTime: 5 * 60_000,
    retry: false,
  })

  const setSession = useCallback((me: Me) => qc.setQueryData(['me'], { user: me.user, organization: me.organization }), [qc])

  const logout = useCallback(async () => {
    try {
      await api.logout()
    } finally {
      qc.clear()
      qc.setQueryData(['me'], null)
    }
  }, [qc])

  const value = useMemo<AuthState>(() => {
    const me = data ?? null
    return {
      me,
      loading: isLoading,
      setSession,
      logout,
      can: (action) => !!me && (action === 'admin' ? ADMIN_ROLES : WRITE_ROLES).includes(me.user.role),
    }
  }, [data, isLoading, setSession, logout])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}

/** Convenience accessor for authenticated pages (rendered under <RequireAuth>). */
export function useSession(): Me {
  const { me } = useAuth()
  if (!me) throw new Error('useSession used outside an authenticated route')
  return me
}
