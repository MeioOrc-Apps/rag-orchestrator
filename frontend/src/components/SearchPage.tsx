import { useState } from 'react'
import { search, type SearchHit, type SearchResponse } from '../api'

export function SearchPage() {
  const [query, setQuery]       = useState('')
  const [domain, setDomain]     = useState('')
  const [enrich, setEnrich]     = useState(true)
  const [loading, setLoading]   = useState(false)
  const [response, setResponse] = useState<SearchResponse | null>(null)
  const [searched, setSearched] = useState(false)

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    if (!query.trim()) return
    setLoading(true)
    try {
      const res = await search({
        query: query.trim(),
        domain: domain.trim() || undefined,
        enrich,
        limit: 20,
      })
      setResponse(res)
      setSearched(true)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Search</h1>
      </div>

      <form onSubmit={handleSearch} style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 28 }}>
        <div style={{ display: 'flex', gap: 8 }}>
          <label htmlFor="search-query" style={{ display: 'none' }}>Query</label>
          <input
            id="search-query"
            type="text"
            className="form-input"
            placeholder="Search documents…"
            value={query}
            onChange={e => setQuery(e.target.value)}
            aria-label="Query"
            style={{ flex: 1 }}
          />
          <input
            type="text"
            className="form-input"
            placeholder="Domain (optional)"
            value={domain}
            onChange={e => setDomain(e.target.value)}
            style={{ width: 180 }}
          />
          <button type="submit" className="btn btn-primary" disabled={loading || !query.trim()}>
            {loading ? 'Searching…' : 'Search'}
          </button>
        </div>

        <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--text-muted)', cursor: 'pointer' }}>
          <input type="checkbox" checked={enrich} onChange={e => setEnrich(e.target.checked)} />
          LLM query enrichment
        </label>
      </form>

      {response?.query_enriched && (
        <div style={{ marginBottom: 12, padding: '8px 12px', background: 'var(--accent-dim)', borderRadius: 'var(--radius-sm)', fontSize: 13 }}>
          <span style={{ color: 'var(--text-muted)' }}>Enriched query: </span>
          <span style={{ color: 'var(--accent)', fontStyle: 'italic' }}>{response.query_enriched}</span>
        </div>
      )}

      {response?.fallback_used && (
        <div className="scan-notice" style={{ marginBottom: 16, background: 'var(--amber-bg)', color: 'var(--amber)', border: '1px solid rgba(217,119,6,0.2)' }}>
          Fallback used — LLM enrichment returned no results; search ran without enrichment
        </div>
      )}

      {searched && response && (
        response.results.length === 0 ? (
          <div className="empty-state">No results for "{query}"</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <p style={{ margin: '0 0 8px', fontSize: 13, color: 'var(--text-muted)' }}>
              {response.total} result{response.total !== 1 ? 's' : ''}
            </p>
            {response.results.map((hit: SearchHit) => (
              <div key={hit.chunk_id} className="card" style={{ padding: '16px 20px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8, gap: 12 }}>
                  <span className="pill" style={{ fontFamily: 'ui-monospace, monospace', fontSize: 11 }}>{hit.domain}</span>
                  <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                    score {hit.score.toFixed(2)} · chunk {hit.chunk_index} · {hit.source_language}
                  </span>
                </div>
                <p style={{ margin: 0, fontSize: 13, lineHeight: 1.6, color: 'var(--text)' }}>
                  {hit.content_en || hit.content_pt}
                </p>
              </div>
            ))}
          </div>
        )
      )}
    </div>
  )
}
