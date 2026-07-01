import { useState, useEffect, useCallback } from 'react'
import {
  getAdminStats, getAdminFailed, retryFailed, reindexAll, forcemerge,
  getSettings, updateSettings,
  type AdminStats, type AdminFailed, type AppSettings,
} from '../api'

export function AdminPage() {
  const [stats, setStats]       = useState<AdminStats | null>(null)
  const [failed, setFailed]     = useState<AdminFailed | null>(null)
  const [settings, setSettings] = useState<AppSettings | null>(null)
  const [loading, setLoading]   = useState(false)
  const [acting, setActing]     = useState<string | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)
  const [settingsSaved, setSettingsSaved] = useState(false)

  // Local editable state for settings form
  const [llmForm, setLlmForm] = useState({
    translation_model: '',
    enrichment_model: '',
    translation_enabled: false,
    translation_batch_size: 5,
    prompt_template_en: '',
    prompt_template_pt: '',
    prompt_enrichment: '',
  })
  const [pipeForm, setPipeForm] = useState({
    chunk_size: 1000,
    chunk_overlap: 100,
    parse_batch_size: 20,
    max_translation_retries: 3,
  })

  const load = useCallback(() => {
    setLoading(true)
    Promise.all([getAdminStats(), getAdminFailed(), getSettings()])
      .then(([s, f, cfg]) => {
        setStats(s)
        setFailed(f)
        setSettings(cfg)
        setLlmForm({
          translation_model: cfg.llm.translation_model,
          enrichment_model: cfg.llm.enrichment_model,
          translation_enabled: cfg.llm.translation_enabled,
          translation_batch_size: cfg.llm.translation_batch_size,
          prompt_template_en: cfg.llm.prompt_template_en,
          prompt_template_pt: cfg.llm.prompt_template_pt,
          prompt_enrichment: cfg.llm.prompt_enrichment,
        })
        setPipeForm({
          chunk_size: cfg.pipeline.chunk_size,
          chunk_overlap: cfg.pipeline.chunk_overlap,
          parse_batch_size: cfg.pipeline.parse_batch_size,
          max_translation_retries: cfg.pipeline.max_translation_retries,
        })
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [refreshKey])

  useEffect(() => { load() }, [load])

  async function handleAction(key: string, fn: () => Promise<unknown>) {
    setActing(key)
    try { await fn(); setRefreshKey(k => k + 1) } catch { /* ignore */ }
    finally { setActing(null) }
  }

  async function handleSaveSettings() {
    setActing('settings')
    try {
      const updated = await updateSettings({ llm: llmForm, pipeline: pipeForm })
      setSettings(updated)
      setSettingsSaved(true)
      setTimeout(() => setSettingsSaved(false), 2500)
    } catch { /* ignore */ }
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
          >
            Retry Failed
          </button>
          <button
            className="btn btn-secondary"
            onClick={() => handleAction('reindex', reindexAll)}
            disabled={!!acting}
          >
            Reindex All
          </button>
          <button
            className="btn btn-secondary"
            onClick={() => handleAction('forcemerge', forcemerge)}
            disabled={!!acting}
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
            <div className="stat-value" style={{ fontSize: 20 }}>{String(count)}</div>
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

      {/* ── Settings ───────────────────────────────────────────────────────── */}
      {settings !== null && (
        <section style={{ marginTop: 32 }}>
          <h2 className="section-title">Settings</h2>

          <div className="settings-section">
            <h3 className="settings-group-title">LLM / Translation</h3>

            <div className="settings-field">
              <label className="settings-label">
                Translation Model
                <span className="settings-hint">Leave empty to disable translation</span>
              </label>
              <input
                className="settings-input"
                value={llmForm.translation_model}
                onChange={e => setLlmForm(f => ({ ...f, translation_model: e.target.value }))}
                placeholder="e.g. local:qwen2.5:7b  or  openrouter:google/gemini-2.0-flash-lite"
              />
              <div className="settings-examples">
                <span className="settings-example-label">Examples:</span>
                <code className="settings-example">local:qwen2.5:7b</code> — Ollama (set OLLAMA_HOST to your server)
                <code className="settings-example">openrouter:google/gemini-2.0-flash-lite</code> — OpenRouter (set OPENROUTER_API_KEY)
                <code className="settings-example">openrouter:anthropic/claude-haiku-4-5-20251001</code> — Claude Haiku via OpenRouter
              </div>
            </div>

            <div className="settings-field">
              <label className="settings-label">
                <span className="settings-toggle">
                  <input
                    type="checkbox"
                    checked={llmForm.translation_enabled}
                    onChange={e => setLlmForm(f => ({ ...f, translation_enabled: e.target.checked }))}
                  />
                  Translation Enabled
                </span>
              </label>
            </div>

            <div className="settings-field">
              <label className="settings-label">
                Enrichment Model
                <span className="settings-hint">Used to expand search queries. Leave empty to disable enrichment</span>
              </label>
              <input
                className="settings-input"
                value={llmForm.enrichment_model}
                onChange={e => setLlmForm(f => ({ ...f, enrichment_model: e.target.value }))}
                placeholder="e.g. local:qwen2.5:7b  or  openrouter:google/gemini-2.0-flash-lite"
              />
              <div className="settings-examples">
                <span className="settings-example-label">Same format as translation model above</span>
              </div>
            </div>

            <div className="settings-row-2">
              <div className="settings-field">
                <label className="settings-label">Translation Batch Size</label>
                <input
                  className="settings-input settings-input-sm"
                  type="number"
                  min={1}
                  value={llmForm.translation_batch_size}
                  onChange={e => setLlmForm(f => ({ ...f, translation_batch_size: Number(e.target.value) }))}
                />
              </div>
            </div>

            <div className="settings-field">
              <label className="settings-label">
                Prompt PT→EN
                <span className="settings-hint">Translates Portuguese text to English. Use {'{text}'} as placeholder.</span>
              </label>
              <textarea
                className="settings-input settings-textarea"
                value={llmForm.prompt_template_en}
                onChange={e => setLlmForm(f => ({ ...f, prompt_template_en: e.target.value }))}
                rows={3}
              />
            </div>

            <div className="settings-field">
              <label className="settings-label">
                Prompt EN→PT
                <span className="settings-hint">Translates English text to Portuguese (Brazil). Use {'{text}'} as placeholder.</span>
              </label>
              <textarea
                className="settings-input settings-textarea"
                value={llmForm.prompt_template_pt}
                onChange={e => setLlmForm(f => ({ ...f, prompt_template_pt: e.target.value }))}
                rows={3}
              />
            </div>

            <div className="settings-field">
              <label className="settings-label">
                Prompt de Enriquecimento de Query
                <span className="settings-hint">Expande a query de busca. Use {'{text}'} como placeholder.</span>
              </label>
              <textarea
                className="settings-input settings-textarea"
                value={llmForm.prompt_enrichment}
                onChange={e => setLlmForm(f => ({ ...f, prompt_enrichment: e.target.value }))}
                rows={3}
              />
            </div>
          </div>

          <div className="settings-section">
            <h3 className="settings-group-title">Pipeline</h3>

            <div className="settings-row-2">
              <div className="settings-field">
                <label className="settings-label">
                  Chunk Size (chars)
                  <span className="settings-hint">Chars per chunk</span>
                </label>
                <input
                  className="settings-input settings-input-sm"
                  type="number"
                  min={100}
                  value={pipeForm.chunk_size}
                  onChange={e => setPipeForm(f => ({ ...f, chunk_size: Number(e.target.value) }))}
                />
              </div>
              <div className="settings-field">
                <label className="settings-label">
                  Chunk Overlap (chars)
                  <span className="settings-hint">Overlap between consecutive chunks</span>
                </label>
                <input
                  className="settings-input settings-input-sm"
                  type="number"
                  min={0}
                  value={pipeForm.chunk_overlap}
                  onChange={e => setPipeForm(f => ({ ...f, chunk_overlap: Number(e.target.value) }))}
                />
              </div>
            </div>

            <div className="settings-row-2">
              <div className="settings-field">
                <label className="settings-label">
                  Parse Batch Size
                  <span className="settings-hint">Files processed per scheduler run</span>
                </label>
                <input
                  className="settings-input settings-input-sm"
                  type="number"
                  min={1}
                  value={pipeForm.parse_batch_size}
                  onChange={e => setPipeForm(f => ({ ...f, parse_batch_size: Number(e.target.value) }))}
                />
              </div>
              <div className="settings-field">
                <label className="settings-label">
                  Max Translation Retries
                </label>
                <input
                  className="settings-input settings-input-sm"
                  type="number"
                  min={1}
                  value={pipeForm.max_translation_retries}
                  onChange={e => setPipeForm(f => ({ ...f, max_translation_retries: Number(e.target.value) }))}
                />
              </div>
            </div>
          </div>

          <div className="settings-footer">
            <button
              className="btn btn-primary"
              onClick={handleSaveSettings}
              disabled={!!acting}
            >
              {acting === 'settings' ? 'Saving…' : settingsSaved ? 'Saved ✓' : 'Save Settings'}
            </button>
          </div>
        </section>
      )}
    </div>
  )
}
