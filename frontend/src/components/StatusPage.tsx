import { useState, useEffect, useCallback } from 'react'
import { getSyncStatus, triggerSync, getAdminStats, type AdminStats } from '../api'

function IconSync({ spin }: { spin?: boolean }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
      strokeLinecap="round" strokeLinejoin="round"
      style={spin ? { animation: 'spin 1s linear infinite' } : undefined}>
      <polyline points="23 4 23 11 16 11"/>
      <polyline points="1 20 1 13 8 13"/>
      <path d="M3.51 9a9 9 0 0114.85-3.36L23 11M1 13l4.64 5.36A9 9 0 0020.49 15"/>
    </svg>
  )
}

function ProgressBar({ value, total, color }: { value: number; total: number; color: string }) {
  const pct = total > 0 ? Math.round((value / total) * 100) : 0
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
      <div style={{ flex: 1, height: 6, background: 'var(--border)', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 3, transition: 'width 0.4s ease' }} />
      </div>
      <span style={{ fontSize: 12, color: 'var(--text-muted)', minWidth: 60, textAlign: 'right' }}>
        {value.toLocaleString()} / {total.toLocaleString()}
      </span>
      <span style={{ fontSize: 12, fontWeight: 600, minWidth: 36, textAlign: 'right' }}>{pct}%</span>
    </div>
  )
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleString('pt-BR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}

function etaString(done: number, total: number, chunksPerMin: number): string {
  if (done >= total || chunksPerMin <= 0) return ''
  const remaining = total - done
  const mins = Math.ceil(remaining / chunksPerMin)
  if (mins < 60) return `~${mins}min restantes`
  const h = Math.floor(mins / 60)
  const m = mins % 60
  return `~${h}h${m > 0 ? `${m}min` : ''} restantes`
}

const POLL_MS = 5000

export function StatusPage() {
  const [stats, setStats]     = useState<AdminStats | null>(null)
  const [lastSync, setLastSync] = useState<string | null>(null)
  const [syncing, setSyncing] = useState(false)
  const [prevDone, setPrevDone] = useState<{ ts: number; done: number } | null>(null)
  const [chunksPerMin, setChunksPerMin] = useState(0)

  const load = useCallback(async (silent = false) => {
    try {
      const [s, sync] = await Promise.all([getAdminStats(), getSyncStatus()])
      setStats(prev => {
        if (prev) {
          const oldDone = prev.chunks.by_translation_status['done'] ?? 0
          const newDone = s.chunks.by_translation_status['done'] ?? 0
          const now = Date.now()
          if (prevDone && newDone > oldDone) {
            const elapsed = (now - prevDone.ts) / 60000
            if (elapsed > 0) setChunksPerMin((newDone - prevDone.done) / elapsed)
          }
          setPrevDone({ ts: now, done: newDone })
        } else {
          setPrevDone({ ts: Date.now(), done: s.chunks.by_translation_status['done'] ?? 0 })
        }
        return s
      })
      if (sync.last_run) setLastSync(sync.last_run)
    } catch { if (!silent) console.error('Failed to load stats') }
  }, [prevDone])

  useEffect(() => { load() }, [])
  useEffect(() => {
    const id = setInterval(() => load(true), POLL_MS)
    return () => clearInterval(id)
  }, [load])

  async function handleSync() {
    setSyncing(true)
    try { await triggerSync(); await load() } finally { setSyncing(false) }
  }

  const totalChunks            = stats?.chunks.total ?? 0
  const translatedDone         = stats?.chunks.by_translation_status['done'] ?? 0
  const indexedDone            = stats?.chunks.by_index_status['done'] ?? 0
  const parseTotal             = stats?.files.total ?? 0
  const parseDone              = stats?.files.by_parse_status['done'] ?? 0
  const translateFailed        = stats?.chunks.by_translation_status['failed'] ?? 0
  const indexFailed            = stats?.chunks.by_index_status['failed'] ?? 0
  const translatedPendingReindex = stats?.chunks.translated_pending_reindex ?? 0
  // Translated chunks already re-indexed with bilingual content
  const translatedReindexed    = Math.max(0, translatedDone - translatedPendingReindex)

  const isActive = translatedDone < totalChunks || indexedDone < totalChunks

  return (
    <div className="page">
      <style>{`@keyframes spin { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }`}</style>

      <div className="page-header">
        <h1 className="page-title">
          Pipeline Status
          {isActive && stats && (
            <span style={{ marginLeft: 10, fontSize: 12, color: 'var(--accent)', fontWeight: 400 }}>
              ● processando…
            </span>
          )}
        </h1>
        <button className="btn btn-primary" onClick={handleSync} disabled={syncing}>
          <IconSync spin={syncing} />
          {syncing ? 'Syncing…' : 'Sync Now'}
        </button>
      </div>

      {lastSync && (
        <p style={{ margin: '0 0 20px', fontSize: 12, color: 'var(--text-muted)' }}>
          Último scan: {formatDate(lastSync)}
        </p>
      )}

      {/* Files */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <span style={{ fontWeight: 600, fontSize: 14 }}>Arquivos</span>
          <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>{parseTotal} total</span>
        </div>
        <div style={{ marginBottom: 6, fontSize: 12, color: 'var(--text-muted)' }}>Parseados</div>
        <ProgressBar value={parseDone} total={parseTotal} color="var(--accent)" />
      </div>

      {/* Chunks */}
      {totalChunks > 0 && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <span style={{ fontWeight: 600, fontSize: 14 }}>Chunks</span>
            <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>{totalChunks.toLocaleString()} total</span>
          </div>

          <div style={{ marginBottom: 6, fontSize: 12, color: 'var(--text-muted)' }}>
            Tradução
            {translateFailed > 0 && (
              <span style={{ color: 'var(--red)', marginLeft: 8 }}>{translateFailed} falhou</span>
            )}
            {chunksPerMin > 0 && translatedDone < totalChunks && (
              <span style={{ color: 'var(--text-muted)', marginLeft: 8 }}>
                {etaString(translatedDone, totalChunks, chunksPerMin)}
              </span>
            )}
          </div>
          <ProgressBar value={translatedDone} total={totalChunks} color="#8b5cf6" />

          <div style={{ marginTop: 14, marginBottom: 6, fontSize: 12, color: 'var(--text-muted)' }}>
            Indexado no OpenSearch
            {indexFailed > 0 && (
              <span style={{ color: 'var(--red)', marginLeft: 8 }}>{indexFailed} falhou</span>
            )}
          </div>
          <ProgressBar value={indexedDone} total={totalChunks} color="var(--accent)" />

          {translatedDone > 0 && (
            <>
              <div style={{ marginTop: 14, marginBottom: 6, fontSize: 12, color: 'var(--text-muted)' }}>
                Tradução re-indexada (bilíngue)
                {translatedPendingReindex > 0 && (
                  <span style={{ color: '#f59e0b', marginLeft: 8 }}>{translatedPendingReindex} aguardando</span>
                )}
              </div>
              <ProgressBar value={translatedReindexed} total={translatedDone} color="#10b981" />
            </>
          )}
        </div>
      )}

      {/* Summary cards */}
      {stats && (
        <div className="stat-grid">
          <div className="stat-card">
            <div className="stat-label">Arquivos</div>
            <div className="stat-value">{parseTotal}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Chunks</div>
            <div className="stat-value">{totalChunks.toLocaleString()}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Traduzidos</div>
            <div className="stat-value" style={{ color: translatedDone === totalChunks && totalChunks > 0 ? 'var(--green)' : undefined }}>
              {translatedDone.toLocaleString()}
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Indexados</div>
            <div className="stat-value" style={{ color: indexedDone === totalChunks && totalChunks > 0 ? 'var(--green)' : undefined }}>
              {indexedDone.toLocaleString()}
            </div>
          </div>
        </div>
      )}

      {!stats && (
        <div className="card" style={{ textAlign: 'center', padding: '56px 24px', color: 'var(--text-muted)' }}>
          <p style={{ margin: 0, fontSize: 13 }}>Carregando…</p>
        </div>
      )}
    </div>
  )
}
