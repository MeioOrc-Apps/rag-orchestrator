import { useState, useEffect, useCallback } from 'react'
import { listFiles, listFolders, type ProcessedFile, type Folder, type FilesQuery } from '../api'

const STATUS_FILTERS = ['all', 'done', 'failed', 'processing', 'skipped'] as const

const SORT_OPTIONS: { value: FilesQuery['sort_by']; label: string }[] = [
  { value: 'created_at', label: 'Date' },
  { value: 'source_path', label: 'Path' },
  { value: 'status', label: 'Status' },
]

const STATUS_CLASS: Record<string, string> = {
  done:       'badge badge-done',
  failed:     'badge badge-failed',
  processing: 'badge badge-processing',
  skipped:    'badge badge-skipped',
  pending:    'badge badge-pending',
}

const PAGE_SIZE = 50

export function FilesPage() {
  const [files, setFiles]         = useState<ProcessedFile[]>([])
  const [total, setTotal]         = useState(0)
  const [folders, setFolders]     = useState<Folder[]>([])
  const [status, setStatus]       = useState<string | undefined>(undefined)
  const [folderId, setFolderId]   = useState<string | undefined>(undefined)
  const [sortBy, setSortBy]       = useState<FilesQuery['sort_by']>('created_at')
  const [order, setOrder]         = useState<'asc' | 'desc'>('desc')
  const [page, setPage]           = useState(0)
  const [loading, setLoading]     = useState(false)

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  const load = useCallback(() => {
    setLoading(true)
    listFiles({
      status,
      folder_id: folderId,
      sort_by: sortBy,
      order,
      limit: PAGE_SIZE,
      offset: page * PAGE_SIZE,
    })
      .then(data => { setFiles(data.items); setTotal(data.total) })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [status, folderId, sortBy, order, page])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    listFolders().then(setFolders).catch(console.error)
  }, [])

  function handleStatusFilter(f: string) {
    setStatus(f === 'all' ? undefined : f)
    setPage(0)
  }

  function handleSortBy(val: FilesQuery['sort_by']) {
    if (val === sortBy) {
      setOrder(o => o === 'asc' ? 'desc' : 'asc')
    } else {
      setSortBy(val)
      setOrder('desc')
    }
    setPage(0)
  }

  function handleFolderChange(e: React.ChangeEvent<HTMLSelectElement>) {
    setFolderId(e.target.value || undefined)
    setPage(0)
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">
          Processed Files
          {total > 0 && (
            <span style={{
              marginLeft: 10, fontSize: 13, fontWeight: 400,
              color: 'var(--text-muted)',
            }}>
              {total} total
            </span>
          )}
        </h1>
      </div>

      {/* ── Filters bar ───────────────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 16, alignItems: 'center' }}>

        {/* Status tabs */}
        <div role="group" aria-label="Status filters" className="filter-tabs">
          {STATUS_FILTERS.map(f => (
            <button
              key={f}
              className="filter-tab"
              onClick={() => handleStatusFilter(f)}
              aria-pressed={f === 'all' ? status === undefined : status === f}
            >
              {f}
            </button>
          ))}
        </div>

        {/* Folder selector */}
        {folders.length > 0 && (
          <select
            value={folderId ?? ''}
            onChange={handleFolderChange}
            style={{
              padding: '5px 10px',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border)',
              fontSize: 12,
              color: folderId ? 'var(--text-strong)' : 'var(--text-muted)',
              background: 'var(--surface)',
              cursor: 'pointer',
            }}
          >
            <option value="">All folders</option>
            {folders.map(f => (
              <option key={f.id} value={f.id}>
                {f.host_path} → {f.dest_subdir}
              </option>
            ))}
          </select>
        )}

        {/* Sort controls */}
        <div style={{ display: 'flex', gap: 4, marginLeft: 'auto', alignItems: 'center' }}>
          <span style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600, letterSpacing: '0.05em', textTransform: 'uppercase' }}>
            Sort
          </span>
          {SORT_OPTIONS.map(opt => (
            <button
              key={opt.value}
              onClick={() => handleSortBy(opt.value)}
              style={{
                padding: '4px 10px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border)',
                fontSize: 12,
                cursor: 'pointer',
                background: sortBy === opt.value ? 'var(--accent-dim)' : 'var(--surface)',
                color: sortBy === opt.value ? 'var(--accent)' : 'var(--text-muted)',
                fontWeight: sortBy === opt.value ? 600 : 400,
              }}
            >
              {opt.label}
              {sortBy === opt.value && (
                <span style={{ marginLeft: 3, fontSize: 10 }}>
                  {order === 'asc' ? '↑' : '↓'}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* ── Table ─────────────────────────────────────────────────────── */}
      {files.length === 0 && !loading ? (
        <div className="empty-state">No files found</div>
      ) : (
        <div className="files-table" style={{ opacity: loading ? 0.6 : 1, transition: 'opacity 0.15s' }}>
          <div className="files-table-head">
            <span>Path</span>
            <span>Status</span>
            <span>Route</span>
          </div>
          {files.map(file => (
            <div key={file.id} data-testid="file-item">
              <div className="file-row">
                <span className="file-path">{file.source_path}</span>
                <span className={STATUS_CLASS[file.status] ?? 'badge badge-skipped'}>
                  {file.status}
                </span>
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{file.route}</span>
              </div>
              {file.error_message && (
                <div className="file-error" style={{ padding: '0 16px 10px' }}>
                  {file.error_message}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* ── Pagination ────────────────────────────────────────────────── */}
      {totalPages > 1 && (
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          marginTop: 16, fontSize: 13, color: 'var(--text-muted)',
        }}>
          <span>
            {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, total)} of {total}
          </span>
          <div style={{ display: 'flex', gap: 4 }}>
            <button
              className="btn btn-secondary"
              style={{ padding: '4px 10px', fontSize: 12 }}
              onClick={() => setPage(p => p - 1)}
              disabled={page === 0}
            >
              ← Prev
            </button>
            {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
              const p = totalPages <= 7 ? i : Math.max(0, Math.min(page - 3, totalPages - 7)) + i
              return (
                <button
                  key={p}
                  className="btn"
                  style={{
                    padding: '4px 10px', fontSize: 12,
                    background: p === page ? 'var(--accent)' : 'var(--surface)',
                    color: p === page ? '#fff' : 'var(--text)',
                    border: '1px solid var(--border)',
                  }}
                  onClick={() => setPage(p)}
                >
                  {p + 1}
                </button>
              )
            })}
            <button
              className="btn btn-secondary"
              style={{ padding: '4px 10px', fontSize: 12 }}
              onClick={() => setPage(p => p + 1)}
              disabled={page >= totalPages - 1}
            >
              Next →
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
