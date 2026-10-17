import { useCallback, useEffect, useState } from 'react'

export type ThemePref = 'light' | 'dark' | 'system'
const KEY = 'screeniq.theme'

function read(): ThemePref {
  try {
    const v = localStorage.getItem(KEY)
    return v === 'light' || v === 'dark' ? v : 'system'
  } catch {
    return 'system'
  }
}

export function applyTheme(pref: ThemePref) {
  const root = document.documentElement
  if (pref === 'system') root.removeAttribute('data-theme')
  else root.setAttribute('data-theme', pref)
}

export function useTheme() {
  const [pref, setPref] = useState<ThemePref>(read)

  useEffect(() => {
    applyTheme(pref)
  }, [pref])

  const set = useCallback((next: ThemePref) => {
    setPref(next)
    try {
      if (next === 'system') localStorage.removeItem(KEY)
      else localStorage.setItem(KEY, next)
    } catch {
      /* storage unavailable (private mode) — theme still applies for this session */
    }
  }, [])

  return { theme: pref, setTheme: set }
}

// Apply before first paint to avoid a flash of the wrong theme
applyTheme(read())
