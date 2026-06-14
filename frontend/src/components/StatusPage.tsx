import { useState, useEffect } from 'react'
import { getSyncStatus, triggerSync, type SyncStatus, type SyncResult } from '../api'

function IconSync({ spin }: { spin?: boolean }) {
  return (
    <svg
      viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
      style={spin ? { animation: 'spin 1s linear infinite' } : undefined}
    >
      <polyline points="23 4 23 11 16 11"/>
      <polyline points="1 20 1 13 8 13"/>
      <path d="M3.51 9a9 9 0 0114.85-3.36L23 11M1 13l4.64 5.36A9 9 0 0020.49 15"/>
    </svg>
  )
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleString('en-US', {
    year: 'numeric', month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

export function StatusPage() {
  const [status, setStatus] = useState<SyncStatus | null>(null)
  const [lastResult, setLastResult] = useState<SyncResult | null>(null)
  const [syncing, setSyncing] = useState(false)

  useEffect(() => {
    getSyncStatus().then(setStatus).catch(console.error)
  }, [])

  async function handleSync() {
    setSyncing(true)
    try {
      const result = await triggerSync()
      setLastResult(result)
      setStatus({
        last_run: new Date().toISOString(),
        processed: result.processed,
        skipped: result.skipped,
        failed: result.failed,
        scan_triggered: result.scan_triggered,
      })
    } finally {
      setSyncing(false)
    }
  }

  const display = lastResult ? { ...status, ...lastResult } : status
  const hasRun = display?.last_run != null

  return (
    <div className="page">
      <style>{`@keyframes spin { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }`}</style>

      <div className="page-header">
        <h1 className="page-title">Sync Status</h1>
        <button className="btn btn-primary" onClick={handleSync} disabled={syncing}>
          <IconSync spin={syncing} />
          {syncing ? 'Syncing…' : 'Sync Now'}
        </button>
      </div>

      {!hasRun ? (
        <div className="card" style={{ textAlign: 'center', padding: '56px 24px', color: 'var(--text-muted)' }}>
          <div style={{ fontSize: 40, marginBottom: 12, opacity: 0.3 }}>⟳</div>
          <p style={{ margin: '0 0 4px', fontWeight: 600, color: 'var(--text)', fontSize: 15 }}>Never synced</p>
          <p style={{ margin: 0, fontSize: 12 }}>Click "Sync Now" to run the pipeline for the first time.</p>
        </div>
      ) : (
        <>
          <div className="stat-grid">
            <div className="stat-card">
              <div className="stat-label">Last Run</div>
              <div className="stat-value-sm">
                {display!.last_run ? formatDate(display!.last_run) : '—'}
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Processed</div>
              <div className="stat-value">{display?.processed ?? '—'}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Skipped</div>
              <div className="stat-value">{display?.skipped ?? '—'}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Failed</div>
              <div
                className="stat-value"
                style={{ color: (display?.failed ?? 0) > 0 ? 'var(--red)' : undefined }}
              >
                {display?.failed ?? '—'}
              </div>
            </div>
          </div>

          {(display?.processed != null || display?.skipped != null || display?.failed != null) && (
            <p style={{ margin: '4px 0 0', fontSize: 12, color: 'var(--text-muted)' }}>
              {display?.processed != null && <>Processed: {display.processed}</>}
              {display?.skipped != null && <> · Skipped: {display.skipped}</>}
              {display?.failed != null && <> · Failed: {display.failed}</>}
            </p>
          )}

          {display?.scan_triggered && (
            <div className="scan-notice" style={{ marginTop: 20 }}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ width: 12, height: 12 }}>
                <polyline points="20 6 9 17 4 12"/>
              </svg>
              Scan triggered
            </div>
          )}
        </>
      )}
    </div>
  )
}
