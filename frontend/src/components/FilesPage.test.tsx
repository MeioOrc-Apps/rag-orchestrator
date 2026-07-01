import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import { FilesPage } from './FilesPage'
import * as api from '../api'

vi.mock('../api')

const mockFiles: api.File[] = [
  {
    id: '1', path: '/data/docs/note.md', filename: 'note.md',
    domain: 'docs', file_hash: 'abc123', file_size_bytes: 1024,
    parse_status: 'done', parse_error: null,
    chunks: { total: 10, done: 10, pending: 0, failed: 0, deleted: 0 },
    created_at: '2026-06-14T10:00:00Z', updated_at: '2026-06-14T10:00:00Z',
  },
  {
    id: '2', path: '/data/docs/report.pdf', filename: 'report.pdf',
    domain: 'docs', file_hash: 'def456', file_size_bytes: 204800,
    parse_status: 'failed', parse_error: 'Parser timeout',
    chunks: null,
    created_at: '2026-06-14T10:01:00Z', updated_at: '2026-06-14T10:01:00Z',
  },
]

const mockPage: api.PaginatedFiles = { items: mockFiles, total: 2, limit: 50, offset: 0 }
const emptyPage: api.PaginatedFiles = { items: [], total: 0, limit: 50, offset: 0 }

describe('FilesPage', () => {
  beforeEach(() => {
    vi.mocked(api.listFiles).mockResolvedValue(mockPage)
    vi.mocked(api.reindexFile).mockResolvedValue(undefined)
    vi.mocked(api.softDeleteFile).mockResolvedValue(undefined)
  })

  it('renders list of files from API', async () => {
    render(<FilesPage />)
    await waitFor(() => {
      expect(screen.getAllByTestId('file-item')).toHaveLength(2)
    })
    expect(screen.getByText('/data/docs/note.md')).toBeInTheDocument()
    expect(screen.getByText('/data/docs/report.pdf')).toBeInTheDocument()
  })

  it('shows parse_status badge for each file', async () => {
    render(<FilesPage />)
    await waitFor(() => {
      expect(screen.getByText('done')).toBeInTheDocument()
      expect(screen.getByText('failed')).toBeInTheDocument()
    })
  })

  it('shows parse_error for failed files', async () => {
    render(<FilesPage />)
    await waitFor(() => {
      expect(screen.getByText('Parser timeout')).toBeInTheDocument()
    })
  })

  it('shows domain for each file', async () => {
    render(<FilesPage />)
    await waitFor(() => {
      expect(screen.getAllByText('docs').length).toBeGreaterThan(0)
    })
  })

  it('shows empty message when no files', async () => {
    vi.mocked(api.listFiles).mockResolvedValue(emptyPage)
    render(<FilesPage />)
    await waitFor(() => {
      expect(screen.getByText(/no files/i)).toBeInTheDocument()
    })
  })

  it('status filter tabs call API with correct parse_status', async () => {
    const user = userEvent.setup()
    render(<FilesPage />)
    await waitFor(() => screen.getAllByTestId('file-item'))

    vi.mocked(api.listFiles).mockResolvedValue({ items: [mockFiles[1]], total: 1, limit: 50, offset: 0 })
    await user.click(screen.getByRole('button', { name: /failed/i }))

    await waitFor(() => {
      expect(api.listFiles).toHaveBeenCalledWith(
        expect.objectContaining({ parse_status: 'failed' })
      )
    })
  })

  it('all filter removes parse_status filter', async () => {
    const user = userEvent.setup()
    render(<FilesPage />)
    await waitFor(() => screen.getAllByTestId('file-item'))

    await user.click(screen.getByRole('button', { name: /^all$/i }))
    await waitFor(() => {
      const calls = vi.mocked(api.listFiles).mock.calls
      const last = calls[calls.length - 1][0] as api.FilesQuery
      expect(last.parse_status).toBeUndefined()
    })
  })

  it('reindex button calls reindexFile and refreshes', async () => {
    const user = userEvent.setup()
    render(<FilesPage />)
    await waitFor(() => screen.getAllByTestId('file-item'))

    const reindexBtns = screen.getAllByRole('button', { name: /reindex/i })
    await user.click(reindexBtns[0])

    await waitFor(() => {
      expect(api.reindexFile).toHaveBeenCalledWith('1')
      expect(api.listFiles).toHaveBeenCalledTimes(2)
    })
  })

  it('delete button calls softDeleteFile and refreshes', async () => {
    const user = userEvent.setup()
    render(<FilesPage />)
    await waitFor(() => screen.getAllByTestId('file-item'))

    const deleteBtns = screen.getAllByRole('button', { name: /delete/i })
    await user.click(deleteBtns[0])

    await waitFor(() => {
      expect(api.softDeleteFile).toHaveBeenCalledWith('1')
      expect(api.listFiles).toHaveBeenCalledTimes(2)
    })
  })
})
