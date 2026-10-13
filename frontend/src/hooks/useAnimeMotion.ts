import { useEffect, useRef } from 'react'
import { animate } from 'animejs'

/**
 * Custom hook to apply subtle, restrained Anime.js page/panel transitions.
 * Respects prefers-reduced-motion and cleans up cleanly on unmount.
 */
export function useAnimePageTransition(triggerKey: string | number) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    // Check for reduced motion preference
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      return
    }

    if (containerRef.current) {
      try {
        animate(containerRef.current, {
          opacity: [0.85, 1],
          translateY: [4, 0],
          duration: 180,
          ease: 'outQuad',
        })
      } catch {
        // Fallback gracefully
      }
    }
  }, [triggerKey])

  return containerRef
}
