import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import { FolderList } from './FolderList'
import * as api from '../api'

vi.mock('../api')

const mockFolders = [
  {
    id: 'f1',
    owner_id: 'o1',
    host_path: '/data/docs',
    dest_subdir: 'docs',
    recursive: true,
    enabled: true,
    created_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 'f2',
    owner_id: 'o1',
    host_path: '/data/books',
    dest_subdir: 'books',
    recursive: true,
    enabled: true,
    created_at: '2026-01-01T00:00:00Z',
  },
]

describe('FolderList', () => {
  beforeEach(() => {
    vi.mocked(api.listFolders).mockResolvedValue(mockFolders)
    vi.mocked(api.createFolder).mockResolvedValue({
      id: 'f3',
      owner_id: 'o1',
      host_path: '/data/pdfs',
      dest_subdir: 'pdfs',
      recursive: true,
      enabled: true,
      created_at: '2026-01-01T00:00:00Z',
    })
  })

  it('renders the folders list from the API', async () => {
    render(<FolderList />)
    await waitFor(() => {
      const items = screen.getAllByTestId('folder-item')
      expect(items).toHaveLength(2)
    })
    expect(screen.getByText('/data/docs → docs')).toBeInTheDocument()
    expect(screen.getByText('/data/books → books')).toBeInTheDocument()
  })

  it('shows an empty list when API returns no folders', async () => {
    vi.mocked(api.listFolders).mockResolvedValue([])
    render(<FolderList />)
    await waitFor(() => {
      expect(screen.queryByTestId('folder-item')).not.toBeInTheDocument()
    })
  })

  it('renders the add folder form', async () => {
    render(<FolderList />)
    expect(screen.getByRole('button', { name: /add folder/i })).toBeInTheDocument()
    expect(screen.getByLabelText('Host path')).toBeInTheDocument()
    expect(screen.getByLabelText('Destination subdirectory')).toBeInTheDocument()
  })

  it('submitting the form calls createFolder and updates the list', async () => {
    const user = userEvent.setup()
    render(<FolderList />)

    await user.type(screen.getByLabelText('Host path'), '/data/pdfs')
    await user.type(screen.getByLabelText('Destination subdirectory'), 'pdfs')
    await user.click(screen.getByRole('button', { name: /add folder/i }))

    await waitFor(() => {
      expect(api.createFolder).toHaveBeenCalledWith({
        host_path: '/data/pdfs',
        dest_subdir: 'pdfs',
      })
    })

    await waitFor(() => {
      const items = screen.getAllByTestId('folder-item')
      expect(items).toHaveLength(3)
    })
  })

  it('clears form fields after successful submission', async () => {
    const user = userEvent.setup()
    render(<FolderList />)

    await user.type(screen.getByLabelText('Host path'), '/data/pdfs')
    await user.type(screen.getByLabelText('Destination subdirectory'), 'pdfs')
    await user.click(screen.getByRole('button', { name: /add folder/i }))

    await waitFor(() => {
      expect(screen.getByLabelText('Host path')).toHaveValue('')
      expect(screen.getByLabelText('Destination subdirectory')).toHaveValue('')
    })
  })

  it('shows error message when API call fails', async () => {
    vi.mocked(api.createFolder).mockRejectedValue(new Error('network'))
    const user = userEvent.setup()
    render(<FolderList />)

    await user.type(screen.getByLabelText('Host path'), '/bad')
    await user.type(screen.getByLabelText('Destination subdirectory'), 'bad')
    await user.click(screen.getByRole('button', { name: /add folder/i }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument()
    })
  })
})
