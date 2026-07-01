import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import { SearchPage } from './SearchPage'
import * as api from '../api'

vi.mock('../api')

const mockHit: api.SearchHit = {
  chunk_id: 'c1', file_id: 'f1', domain: 'docs',
  chunk_index: 0, source_language: 'pt',
  content_en: 'This is the English content of the chunk.',
  content_pt: 'Este é o conteúdo em português.',
  score: 1.42,
  highlights: {},
}

const mockResponse: api.SearchResponse = {
  results: [mockHit],
  total: 1,
  fallback_used: false,
  query_enriched: null,
}

describe('SearchPage', () => {
  beforeEach(() => {
    vi.mocked(api.search).mockResolvedValue(mockResponse)
  })

  it('renders search input', () => {
    render(<SearchPage />)
    expect(screen.getByRole('textbox', { name: /query/i })).toBeInTheDocument()
  })

  it('renders search button', () => {
    render(<SearchPage />)
    expect(screen.getByRole('button', { name: /search/i })).toBeInTheDocument()
  })

  it('calls search API on submit', async () => {
    const user = userEvent.setup()
    render(<SearchPage />)

    await user.type(screen.getByRole('textbox', { name: /query/i }), 'test query')
    await user.click(screen.getByRole('button', { name: /search/i }))

    await waitFor(() => {
      expect(api.search).toHaveBeenCalledWith(
        expect.objectContaining({ query: 'test query' })
      )
    })
  })

  it('shows results after search', async () => {
    const user = userEvent.setup()
    render(<SearchPage />)

    await user.type(screen.getByRole('textbox', { name: /query/i }), 'test')
    await user.click(screen.getByRole('button', { name: /search/i }))

    await waitFor(() => {
      expect(screen.getByText(/English content of the chunk/i)).toBeInTheDocument()
    })
  })

  it('shows domain and score for each result', async () => {
    const user = userEvent.setup()
    render(<SearchPage />)

    await user.type(screen.getByRole('textbox', { name: /query/i }), 'test')
    await user.click(screen.getByRole('button', { name: /search/i }))

    await waitFor(() => {
      expect(screen.getByText('docs')).toBeInTheDocument()
      expect(screen.getByText(/1\.42/)).toBeInTheDocument()
    })
  })

  it('shows fallback notice when fallback_used is true', async () => {
    vi.mocked(api.search).mockResolvedValue({ ...mockResponse, fallback_used: true })
    const user = userEvent.setup()
    render(<SearchPage />)

    await user.type(screen.getByRole('textbox', { name: /query/i }), 'test')
    await user.click(screen.getByRole('button', { name: /search/i }))

    await waitFor(() => {
      expect(screen.getByText(/fallback/i)).toBeInTheDocument()
    })
  })

  it('shows enriched query when returned', async () => {
    vi.mocked(api.search).mockResolvedValue({ ...mockResponse, query_enriched: 'enriched test query' })
    const user = userEvent.setup()
    render(<SearchPage />)

    await user.type(screen.getByRole('textbox', { name: /query/i }), 'test')
    await user.click(screen.getByRole('button', { name: /search/i }))

    await waitFor(() => {
      expect(screen.getByText(/enriched test query/i)).toBeInTheDocument()
    })
  })

  it('shows no results message when empty', async () => {
    vi.mocked(api.search).mockResolvedValue({ results: [], total: 0, fallback_used: false, query_enriched: null })
    const user = userEvent.setup()
    render(<SearchPage />)

    await user.type(screen.getByRole('textbox', { name: /query/i }), 'noresults')
    await user.click(screen.getByRole('button', { name: /search/i }))

    await waitFor(() => {
      expect(screen.getByText(/no results/i)).toBeInTheDocument()
    })
  })
})
