import { useState, useEffect, useCallback, useRef } from 'react'
import { listFiles, softDeleteFile, reindexFile, type File, type FilesQuery } from '../api'

const STATUS_FILTERS = ['all', 'pending', 'processing', 'done', 'failed'] as const

const STATUS_CLASS: Record<string, string> = {
  done:       'badge badge-done',
  failed:     'badge badge-failed',
  pending:    'badge badge-pending',
  processing: 'badge badge-pending',
}

const PAGE_SIZE = 50
const POLL_INTERVAL_MS = 8000

function ChunkProgress({ chunks }: { chunks: File['chunks'] }) {
  if (!chunks || chunks.total === 0) return <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>—</span>
  const { total, done, failed } = chunks
  const pct = Math.round((done / total) * 100)
  return (
    <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
      {done}/{total} indexed
      {failed > 0 && <span style={{ color: 'var(--red)', marginLeft: 4 }}>{failed} failed</span>}
      {pct < 100 && <span style={{ marginLeft: 4 }}>({pct}%)</span>}
    </span>
  )
}

export function FilesPage() {
  const [files, setFiles]       = useState<File[]>([])
  const [total, setTotal]       = useState(0)
  const [parseStatus, setParseStatus] = useState<string | undefined>(undefined)
  const [domain, setDomain]     = useState('')
  const [page, setPage]         = useState(0)
  const [loading, setLoading]   = useState(false)
  const [acting, setActing]     = useState<string | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  const load = useCallback((silent = false) => {
    if (!silent) setLoading(true)
    const q: FilesQuery = { limit: PAGE_SIZE, offset: page * PAGE_SIZE }
    if (parseStatus)    q.parse_status = parseStatus
    if (domain.trim())  q.domain = domain.trim()
    listFiles(q)
      .then(data => { setFiles(data.items); setTotal(data.total) })
      .catch(console.error)
      .finally(() => { if (!silent) setLoading(false) })
  }, [parseStatus, domain, page, refreshKey])

  useEffect(() => { load() }, [load])

  // Auto-poll while any file is in-progress
  useEffect(() => {
    const hasInProgress = files.some(f =>
      f.parse_status === 'pending' || f.parse_status === 'processing'
    )
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
    if (hasInProgress) {
      pollRef.current = setInterval(() => load(true), POLL_INTERVAL_MS)
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [files, load])

  function handleStatusFilter(f: string) {
    setParseStatus(f === 'all' ? undefined : f)
    setPage(0)
  }

  async function handleReindex(id: string) {
    setActing(id + ':reindex')
    try { await reindexFile(id); setRefreshKey(k => k + 1) } catch { /* ignore */ }
    finally { setActing(null) }
  }

  async function handleDelete(id: string) {
    setActing(id + ':delete')
    try { await softDeleteFile(id); setRefreshKey(k => k + 1) } catch { /* ignore */ }
    finally { setActing(null) }
  }

  const hasInProgress = files.some(f =>
    f.parse_status === 'pending' || f.parse_status === 'processing'
  )

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">
          Files
          {total > 0 && (
            <span style={{ marginLeft: 10, fontSize: 13, fontWeight: 400, color: 'var(--text-muted)' }}>
              {total} total
            </span>
          )}
          {hasInProgress && (
            <span style={{ marginLeft: 10, fontSize: 12, color: 'var(--accent)', fontWeight: 400 }}>
              ● processing…
            </span>
          )}
        </h1>
      </div>

      <div className="files-toolbar">
        <div className="files-toolbar-row">
          <div role="group" aria-label="Status filters" className="filter-tabs">
            {STATUS_FILTERS.map(f => (
              <button
                key={f}
                className="filter-tab"
                onClick={() => handleStatusFilter(f)}
                aria-pressed={f === 'all' ? parseStatus === undefined : parseStatus === f}
              >
                {f}
              </button>
            ))}
          </div>

          <input
            type="text"
            className="form-input domain-filter"
            placeholder="Filter by domain…"
            value={domain}
            onChange={e => { setDomain(e.target.value); setPage(0) }}
          />
        </div>
      </div>

      {files.length === 0 && !loading ? (
        <div className="empty-state">No files found</div>
      ) : (
        <div className="files-table" style={{ opacity: loading ? 0.6 : 1, transition: 'opacity 0.15s' }}>
          <div className="files-table-head files-cols-5">
            <span>Path</span>
            <span>Status</span>
            <span>Progress</span>
            <span>Domain</span>
            <span></span>
          </div>
          {files.map(file => (
            <div key={file.id} data-testid="file-item">
              <div className="file-row files-cols-5">
                <span className="file-path" title={file.path}>{file.path}</span>
                <span className={STATUS_CLASS[file.parse_status] ?? 'badge badge-skipped'}>
                  {file.parse_status}
                </span>
                <ChunkProgress chunks={file.chunks} />
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{file.domain}</span>
                <span style={{ display: 'flex', gap: 4 }}>
                  <button
                    className="btn btn-secondary"
                    style={{ padding: '3px 8px', fontSize: 11 }}
                    onClick={() => handleReindex(file.id)}
                    disabled={acting === file.id + ':reindex'}
                    aria-label="Reindex"
                    title="Reindex"
                  >
                    Reindex
                  </button>
                  <button
                    className="btn"
                    style={{ padding: '3px 8px', fontSize: 11, background: 'var(--red-bg)', color: 'var(--red)', borderColor: 'rgba(220,38,38,0.2)' }}
                    onClick={() => handleDelete(file.id)}
                    disabled={acting === file.id + ':delete'}
                    aria-label="Delete"
                    title="Delete"
                  >
                    Delete
                  </button>
                </span>
              </div>
              {file.parse_error && (
                <div className="file-error" style={{ padding: '0 16px 10px' }}>
                  {file.parse_error}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {totalPages > 1 && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 16, fontSize: 13, color: 'var(--text-muted)' }}>
          <span>{page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, total)} of {total}</span>
          <div style={{ display: 'flex', gap: 4 }}>
            <button className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: 12 }} onClick={() => setPage(p => p - 1)} disabled={page === 0}>← Prev</button>
            {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
              const p = totalPages <= 7 ? i : Math.max(0, Math.min(page - 3, totalPages - 7)) + i
              return (
                <button key={p} className="btn" style={{ padding: '4px 10px', fontSize: 12, background: p === page ? 'var(--accent)' : 'var(--surface)', color: p === page ? '#fff' : 'var(--text)', border: '1px solid var(--border)' }} onClick={() => setPage(p)}>
                  {p + 1}
                </button>
              )
            })}
            <button className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: 12 }} onClick={() => setPage(p => p + 1)} disabled={page >= totalPages - 1}>Next →</button>
          </div>
        </div>
      )}
    </div>
  )
}
