import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import { FilesPage } from './FilesPage'
import * as api from '../api'

vi.mock('../api')

const mockFiles: api.ProcessedFile[] = [
  {
    id: '1', owner_id: 'o1', folder_id: 'f1',
    source_path: '/data/docs/note.md', dest_path: '/input/docs/note.md',
    content_hash: 'abc123', file_type: 'md', route: 'direct',
    status: 'done', error_message: null,
    processed_at: '2026-06-14T10:00:00Z', created_at: '2026-06-14T10:00:00Z',
  },
  {
    id: '2', owner_id: 'o1', folder_id: 'f1',
    source_path: '/data/docs/report.pdf', dest_path: null,
    content_hash: 'def456', file_type: 'pdf', route: 'docling',
    status: 'failed', error_message: 'Docling server unreachable',
    processed_at: null, created_at: '2026-06-14T10:01:00Z',
  },
]

const mockPage: api.PaginatedFiles = { items: mockFiles, total: 2, limit: 50, offset: 0 }
const emptyPage: api.PaginatedFiles = { items: [], total: 0, limit: 50, offset: 0 }

describe('FilesPage', () => {
  beforeEach(() => {
    vi.mocked(api.listFiles).mockResolvedValue(mockPage)
    vi.mocked(api.listFolders).mockResolvedValue([])
  })

  it('renders list of files from API', async () => {
    render(<FilesPage />)
    await waitFor(() => {
      expect(screen.getAllByTestId('file-item')).toHaveLength(2)
    })
    expect(screen.getByText('/data/docs/note.md')).toBeInTheDocument()
    expect(screen.getByText('/data/docs/report.pdf')).toBeInTheDocument()
  })

  it('shows status badge for each file', async () => {
    render(<FilesPage />)
    await waitFor(() => {
      expect(screen.getByText('done')).toBeInTheDocument()
      expect(screen.getByText('failed')).toBeInTheDocument()
    })
  })

  it('shows error message for failed files', async () => {
    render(<FilesPage />)
    await waitFor(() => {
      expect(screen.getByText('Docling server unreachable')).toBeInTheDocument()
    })
  })

  it('shows empty message when no files', async () => {
    vi.mocked(api.listFiles).mockResolvedValue(emptyPage)
    render(<FilesPage />)
    await waitFor(() => {
      expect(screen.getByText(/no files/i)).toBeInTheDocument()
    })
  })

  it('filter buttons call API with correct status', async () => {
    const user = userEvent.setup()
    render(<FilesPage />)
    await waitFor(() => screen.getAllByTestId('file-item'))

    vi.mocked(api.listFiles).mockResolvedValue({ items: [mockFiles[1]], total: 1, limit: 50, offset: 0 })
    await user.click(screen.getByRole('button', { name: /failed/i }))

    await waitFor(() => {
      expect(api.listFiles).toHaveBeenCalledWith(
        expect.objectContaining({ status: 'failed' })
      )
    })
  })

  it('all filter shows files without status filter', async () => {
    const user = userEvent.setup()
    render(<FilesPage />)
    await waitFor(() => screen.getAllByTestId('file-item'))

    await user.click(screen.getByRole('button', { name: /^all$/i }))
    await waitFor(() => {
      const calls = vi.mocked(api.listFiles).mock.calls
      const lastCall = calls[calls.length - 1][0] as api.FilesQuery
      expect(lastCall.status).toBeUndefined()
    })
  })

  it('shows folder selector when folders exist', async () => {
    vi.mocked(api.listFolders).mockResolvedValue([
      { id: 'f1', owner_id: 'o1', host_path: '/docs', dest_subdir: 'docs', recursive: true, enabled: true, created_at: '' },
    ])
    render(<FilesPage />)
    await waitFor(() => {
      expect(screen.getByRole('combobox')).toBeInTheDocument()
    })
  })

  it('folder filter calls API with folder_id', async () => {
    vi.mocked(api.listFolders).mockResolvedValue([
      { id: 'f1', owner_id: 'o1', host_path: '/docs', dest_subdir: 'docs', recursive: true, enabled: true, created_at: '' },
    ])
    const user = userEvent.setup()
    render(<FilesPage />)
    await waitFor(() => screen.getByRole('combobox'))

    await user.selectOptions(screen.getByRole('combobox'), 'f1')
    await waitFor(() => {
      expect(api.listFiles).toHaveBeenCalledWith(
        expect.objectContaining({ folder_id: 'f1' })
      )
    })
  })

  it('sort buttons toggle order when clicked twice on same field', async () => {
    const user = userEvent.setup()
    render(<FilesPage />)
    await waitFor(() => screen.getAllByTestId('file-item'))

    await user.click(screen.getByRole('button', { name: /path/i }))
    await waitFor(() => {
      expect(api.listFiles).toHaveBeenCalledWith(
        expect.objectContaining({ sort_by: 'source_path', order: 'desc' })
      )
    })

    await user.click(screen.getByRole('button', { name: /path/i }))
    await waitFor(() => {
      expect(api.listFiles).toHaveBeenCalledWith(
        expect.objectContaining({ sort_by: 'source_path', order: 'asc' })
      )
    })
  })
})
