import { useLayoutEffect, type ReactNode } from 'react'
import { useLocation } from 'react-router-dom'
import { useAnimate, useReducedMotion } from 'motion/react'

/**
 * Fades and lifts the routed page in on every navigation.
 *
 * Animates in place instead of remounting on a new key, so page state (e.g. the
 * selected tab while paging through candidates) survives the transition. Inside
 * a Suspense boundary the layout effect also re-runs when a lazy page is revealed.
 */
export function PageTransition({ children }: { children: ReactNode }) {
  const { pathname } = useLocation()
  const [scope, animate] = useAnimate<HTMLDivElement>()
  const reduceMotion = useReducedMotion()

  useLayoutEffect(() => {
    const el = scope.current
    if (!el || reduceMotion) return
    el.style.opacity = '0' // hide before paint; the animation starts a frame later
    const controls = animate(el, { opacity: [0, 1], y: [10, 0] }, { duration: 0.32, ease: [0.22, 1, 0.36, 1] })
    // A leftover transform would make this wrapper the containing block for fixed/sticky descendants
    controls.then(() => { el.style.transform = '' })
    return () => {
      controls.stop()
      el.style.opacity = ''
      el.style.transform = ''
    }
  }, [pathname, reduceMotion, animate, scope])

  return <div ref={scope}>{children}</div>
}
