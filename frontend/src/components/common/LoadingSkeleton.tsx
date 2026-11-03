import type { FC } from 'react'

interface LoadingSkeletonProps {
  lines?: number
  height?: string | number
  width?: string | number
  className?: string
}

export const LoadingSkeleton: FC<LoadingSkeletonProps> = ({
  lines = 1,
  height = '20px',
  width = '100%',
  className = '',
}) => {
  return (
    <div className={`skeleton-container ${className}`} style={{ display: 'flex', flexDirection: 'column', gap: '8px', width: '100%' }}>
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          style={{
            height: typeof height === 'number' ? `${height}px` : height,
            width: i === lines - 1 && lines > 1 ? '70%' : typeof width === 'number' ? `${width}px` : width,
            borderRadius: 'var(--radius-xs, 4px)',
            background: 'linear-gradient(90deg, var(--bg-subtle) 25%, var(--bg-hover) 50%, var(--bg-subtle) 75%)',
            backgroundSize: '200% 100%',
            animation: 'skeleton-pulse 1.6s ease-in-out infinite',
          }}
        />
      ))}
    </div>
  )
}
