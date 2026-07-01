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

      <form className="search-form" onSubmit={handleSearch}>
        <div className="search-row">
          <input
            id="search-query"
            type="text"
            className="form-input search-query"
            placeholder="Search documents…"
            value={query}
            onChange={e => setQuery(e.target.value)}
            aria-label="Query"
          />
          <input
            type="text"
            className="form-input search-domain"
            placeholder="Domain (optional)"
            value={domain}
            onChange={e => setDomain(e.target.value)}
          />
          <button type="submit" className="btn btn-primary" disabled={loading || !query.trim()}>
            {loading ? 'Searching…' : 'Search'}
          </button>
        </div>

        <label className="search-enrich">
          <input type="checkbox" checked={enrich} onChange={e => setEnrich(e.target.checked)} />
          LLM query enrichment
        </label>
      </form>

      {response?.query_enriched && (
        <div className="enriched-notice">
          <span style={{ color: 'var(--text-muted)' }}>Enriched query: </span>
          <span style={{ color: 'var(--accent)', fontStyle: 'italic' }}>{response.query_enriched}</span>
        </div>
      )}

      {response?.fallback_used && (
        <div className="fallback-notice">
          Fallback used — LLM enrichment returned no results; search ran without enrichment
        </div>
      )}

      {searched && response && (
        response.results.length === 0 ? (
          <div className="empty-state">No results for "{query}"</div>
        ) : (
          <div className="search-results">
            <p className="search-results-count">
              {response.total} result{response.total !== 1 ? 's' : ''}
            </p>
            {response.results.map((hit: SearchHit) => (
              <div key={hit.chunk_id} className="result-card">
                <div className="result-card-meta">
                  <span className="pill" style={{ fontFamily: 'ui-monospace, monospace', fontSize: 11 }}>{hit.domain}</span>
                  <span className="result-card-score">
                    score {hit.score.toFixed(2)} · chunk {hit.chunk_index} · {hit.source_language}
                  </span>
                </div>
                <p className="result-card-content">{hit.content_en || hit.content_pt}</p>
              </div>
            ))}
          </div>
        )
      )}
    </div>
  )
}
