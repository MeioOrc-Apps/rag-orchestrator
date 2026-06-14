import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import { FilesPage } from './FilesPage'
import * as api from '../api'

vi.mock('../api')

const mockFiles: api.ProcessedFile[] = [
  {
    id: '1',
    owner_id: 'o1',
    folder_id: 'f1',
    source_path: '/data/docs/note.md',
    dest_path: '/input/docs/note.md',
    content_hash: 'abc123',
    file_type: 'md',
    route: 'direct',
    status: 'done',
    error_message: null,
    processed_at: '2026-06-14T10:00:00Z',
    created_at: '2026-06-14T10:00:00Z',
  },
  {
    id: '2',
    owner_id: 'o1',
    folder_id: 'f1',
    source_path: '/data/docs/report.pdf',
    dest_path: null,
    content_hash: 'def456',
    file_type: 'pdf',
    route: 'docling',
    status: 'failed',
    error_message: 'Docling server unreachable',
    processed_at: null,
    created_at: '2026-06-14T10:01:00Z',
  },
]

describe('FilesPage', () => {
  beforeEach(() => {
    vi.mocked(api.listFiles).mockResolvedValue(mockFiles)
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
    vi.mocked(api.listFiles).mockResolvedValue([])
    render(<FilesPage />)
    await waitFor(() => {
      expect(screen.getByText(/no files/i)).toBeInTheDocument()
    })
  })

  it('filter buttons call API with correct status', async () => {
    const user = userEvent.setup()
    render(<FilesPage />)
    await waitFor(() => screen.getAllByTestId('file-item'))

    vi.mocked(api.listFiles).mockResolvedValue([mockFiles[1]])
    await user.click(screen.getByRole('button', { name: /failed/i }))

    await waitFor(() => {
      expect(api.listFiles).toHaveBeenCalledWith('failed')
    })
  })

  it('all filter shows files without status filter', async () => {
    const user = userEvent.setup()
    render(<FilesPage />)
    await waitFor(() => screen.getAllByTestId('file-item'))

    await user.click(screen.getByRole('button', { name: /^all$/i }))
    expect(api.listFiles).toHaveBeenCalledWith(undefined)
  })
})
