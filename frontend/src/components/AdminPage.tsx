import { useState, useEffect, useCallback } from 'react'
import { getAdminStats, getAdminFailed, retryFailed, reindexAll, forcemerge, type AdminStats, type AdminFailed } from '../api'

export function AdminPage() {
  const [stats, setStats]       = useState<AdminStats | null>(null)
  const [failed, setFailed]     = useState<AdminFailed | null>(null)
  const [loading, setLoading]   = useState(false)
  const [acting, setActing]     = useState<string | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)

  const load = useCallback(() => {
    setLoading(true)
    Promise.all([getAdminStats(), getAdminFailed()])
      .then(([s, f]) => { setStats(s); setFailed(f) })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [refreshKey])

  useEffect(() => { load() }, [load])

  async function handleAction(key: string, fn: () => Promise<unknown>) {
    setActing(key)
    try { await fn(); setRefreshKey(k => k + 1) } catch { /* ignore */ }
    finally { setActing(null) }
  }

  const fileStatuses = stats ? Object.entries(stats.files.by_parse_status) : []
  const indexStatuses = stats ? Object.entries(stats.chunks.by_index_status) : []

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Admin</h1>
        <div className="admin-actions">
          <button
            className="btn btn-secondary"
            onClick={() => handleAction('retry', retryFailed)}
            disabled={!!acting}
            aria-label="Retry Failed"
          >
            Retry Failed
          </button>
          <button
            className="btn btn-secondary"
            onClick={() => handleAction('reindex', reindexAll)}
            disabled={!!acting}
            aria-label="Reindex All"
          >
            Reindex All
          </button>
          <button
            className="btn btn-secondary"
            onClick={() => handleAction('forcemerge', forcemerge)}
            disabled={!!acting}
            aria-label="Forcemerge"
          >
            Forcemerge
          </button>
        </div>
      </div>

      <div className="stat-grid" style={{ opacity: loading ? 0.6 : 1, transition: 'opacity 0.15s' }}>
        <div className="stat-card">
          <div className="stat-label">Total Files</div>
          <div className="stat-value">{stats?.files.total ?? '—'}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Total Chunks</div>
          <div className="stat-value">{stats?.chunks.total ?? '—'}</div>
        </div>
        {fileStatuses.map(([status, count]) => (
          <div className="stat-card" key={status}>
            <div className="stat-label">Files {status}</div>
            <div className="stat-value" style={{ fontSize: 20 }}>{String(count)} {status}</div>
          </div>
        ))}
        {indexStatuses.map(([status, count]) => (
          <div className="stat-card" key={`idx-${status}`}>
            <div className="stat-label">Indexed {status}</div>
            <div className="stat-value" style={{ fontSize: 20 }}>{count}</div>
          </div>
        ))}
      </div>

      {failed && failed.failed_files.length > 0 && (
        <section style={{ marginTop: 28 }}>
          <h2 className="section-title">Failed Files ({failed.failed_files.length})</h2>
          <div className="files-table">
            {failed.failed_files.map(f => (
              <div key={f.id} data-testid="failed-file">
                <div className="file-row" style={{ gridTemplateColumns: '1fr' }}>
                  <span className="file-path">{f.path}</span>
                </div>
                {f.parse_error && (
                  <div className="file-error" style={{ padding: '0 16px 10px' }}>{f.parse_error}</div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {failed && failed.failed_chunks.length > 0 && (
        <section style={{ marginTop: 20 }}>
          <h2 className="section-title">Failed Chunks ({failed.failed_chunks.length})</h2>
          <div className="card" style={{ fontSize: 13, color: 'var(--text-muted)' }}>
            {failed.failed_chunks.length} chunk{failed.failed_chunks.length !== 1 ? 's' : ''} with
            failed translation or indexing. Use <strong>Retry Failed</strong> to reset them.
          </div>
        </section>
      )}
    </div>
  )
}
