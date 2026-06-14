import { useState, useEffect } from 'react'
import { getSyncStatus, triggerSync, type SyncStatus, type SyncResult } from '../api'

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

  const displayStatus = lastResult
    ? { ...status, ...lastResult }
    : status

  return (
    <div>
      <h2>Sync Status</h2>

      {displayStatus?.last_run == null ? (
        <p>Never synced</p>
      ) : (
        <div>
          <p>Last run: {displayStatus.last_run}</p>
          {displayStatus.processed != null && (
            <p>Processed: {displayStatus.processed}</p>
          )}
          {displayStatus.skipped != null && (
            <p>Skipped: {displayStatus.skipped}</p>
          )}
          {displayStatus.failed != null && (
            <p>Failed: {displayStatus.failed}</p>
          )}
          {displayStatus.scan_triggered && <p>Scan triggered</p>}
        </div>
      )}

      <button onClick={handleSync} disabled={syncing}>
        {syncing ? 'Syncing…' : 'Sync Now'}
      </button>
    </div>
  )
}
