import type { FC } from 'react'

interface FilterControlsProps {
  searchQuery: string
  onSearchChange: (q: string) => void
  statusFilter: string
  onStatusFilterChange: (status: string) => void
  sourceFilter: string
  onSourceFilterChange: (source: string) => void
}

export const FilterControls: FC<FilterControlsProps> = ({
  searchQuery,
  onSearchChange,
  statusFilter,
  onStatusFilterChange,
  sourceFilter,
  onSourceFilterChange,
}) => {
  return (
    <div className="filter-controls-container">
      <div className="filter-search-box">
        <span className="search-icon">🔍</span>
        <input
          type="text"
          className="search-input"
          placeholder="Filter by Motor ID (e.g. MTR-001) or Device..."
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
        />
        {searchQuery && (
          <button className="clear-search-btn" onClick={() => onSearchChange('')}>
            ✕
          </button>
        )}
      </div>

      <div className="filter-pills-row">
        <div className="filter-group">
          <span className="filter-label">Health:</span>
          <div className="pill-group">
            {['all', 'healthy', 'warning', 'critical'].map((st) => (
              <button
                key={st}
                className={`filter-pill ${statusFilter === st ? 'active' : ''}`}
                onClick={() => onStatusFilterChange(st)}
              >
                {st.toUpperCase()}
              </button>
            ))}
          </div>
        </div>

        <div className="filter-group">
          <span className="filter-label">Source:</span>
          <div className="pill-group">
            {['all', 'hardware', 'simulator'].map((src) => (
              <button
                key={src}
                className={`filter-pill ${sourceFilter === src ? 'active' : ''}`}
                onClick={() => onSourceFilterChange(src)}
              >
                {src.toUpperCase()}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
