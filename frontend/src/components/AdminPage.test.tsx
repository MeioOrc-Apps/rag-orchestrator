import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import { AdminPage } from './AdminPage'
import * as api from '../api'

vi.mock('../api')

const mockStats: api.AdminStats = {
  files: { total: 10, by_parse_status: { done: 8, failed: 1, pending: 1 } },
  chunks: {
    total: 50,
    by_index_status: { done: 45, failed: 3, pending: 2 },
    by_translation_status: { done: 40, not_needed: 5, failed: 5 },
  },
}

const mockFailed: api.AdminFailed = {
  failed_files: [{ id: 'f1', path: '/data/docs/bad.pdf', parse_error: 'Parser timeout' }],
  failed_chunks: [{ id: 'c1', file_id: 'f1', translation_status: 'failed', index_status: 'pending', translation_error: 'LLM unreachable', index_error: null }],
}

describe('AdminPage', () => {
  beforeEach(() => {
    vi.mocked(api.getAdminStats).mockResolvedValue(mockStats)
    vi.mocked(api.getAdminFailed).mockResolvedValue(mockFailed)
    vi.mocked(api.retryFailed).mockResolvedValue({ message: 'ok' })
    vi.mocked(api.reindexAll).mockResolvedValue({ message: 'ok' })
    vi.mocked(api.forcemerge).mockResolvedValue({ message: 'ok' })
  })

  it('shows total files and chunks stats', async () => {
    render(<AdminPage />)
    await waitFor(() => {
      expect(screen.getByText('10')).toBeInTheDocument()
      expect(screen.getByText('50')).toBeInTheDocument()
    })
  })

  it('shows files by parse_status breakdown', async () => {
    render(<AdminPage />)
    await waitFor(() => {
      expect(screen.getByText(/done.*8|8.*done/i)).toBeInTheDocument()
    })
  })

  it('shows failed files list', async () => {
    render(<AdminPage />)
    await waitFor(() => {
      expect(screen.getByText('/data/docs/bad.pdf')).toBeInTheDocument()
      expect(screen.getByText('Parser timeout')).toBeInTheDocument()
    })
  })

  it('retry-failed button calls retryFailed', async () => {
    const user = userEvent.setup()
    render(<AdminPage />)
    await waitFor(() => screen.getByText('10'))

    await user.click(screen.getByRole('button', { name: /retry failed/i }))

    await waitFor(() => {
      expect(api.retryFailed).toHaveBeenCalledOnce()
    })
  })

  it('reindex-all button calls reindexAll', async () => {
    const user = userEvent.setup()
    render(<AdminPage />)
    await waitFor(() => screen.getByText('10'))

    await user.click(screen.getByRole('button', { name: /reindex all/i }))

    await waitFor(() => {
      expect(api.reindexAll).toHaveBeenCalledOnce()
    })
  })

  it('forcemerge button calls forcemerge', async () => {
    const user = userEvent.setup()
    render(<AdminPage />)
    await waitFor(() => screen.getByText('10'))

    await user.click(screen.getByRole('button', { name: /forcemerge/i }))

    await waitFor(() => {
      expect(api.forcemerge).toHaveBeenCalledOnce()
    })
  })
})
