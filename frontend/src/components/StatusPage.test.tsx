import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import { StatusPage } from './StatusPage'
import * as api from '../api'

vi.mock('../api')

describe('StatusPage', () => {
  beforeEach(() => {
    vi.mocked(api.getSyncStatus).mockResolvedValue({ last_run: null })
    vi.mocked(api.triggerSync).mockResolvedValue({
      processed: 3,
      skipped: 1,
      failed: 0,
      scan_triggered: true,
    })
  })

  it('shows "never synced" when last_run is null', async () => {
    render(<StatusPage />)
    await waitFor(() => {
      expect(screen.getByText(/never synced/i)).toBeInTheDocument()
    })
  })

  it('shows last run timestamp when available', async () => {
    vi.mocked(api.getSyncStatus).mockResolvedValue({
      last_run: '2026-06-14T12:00:00Z',
      processed: 5,
      skipped: 2,
      failed: 1,
      scan_triggered: true,
    })
    render(<StatusPage />)
    await waitFor(() => {
      expect(screen.getByText(/2026/)).toBeInTheDocument()
    })
  })

  it('renders "Sync Now" button', async () => {
    render(<StatusPage />)
    expect(screen.getByRole('button', { name: /sync now/i })).toBeInTheDocument()
  })

  it('shows loading state while sync is running', async () => {
    let resolve: (v: api.SyncResult) => void
    vi.mocked(api.triggerSync).mockReturnValue(
      new Promise(r => { resolve = r })
    )
    const user = userEvent.setup()
    render(<StatusPage />)

    await user.click(screen.getByRole('button', { name: /sync now/i }))
    expect(screen.getByRole('button', { name: /syncing/i })).toBeDisabled()

    resolve!({ processed: 1, skipped: 0, failed: 0, scan_triggered: false })
  })

  it('updates status after sync completes', async () => {
    const user = userEvent.setup()
    render(<StatusPage />)

    await user.click(screen.getByRole('button', { name: /sync now/i }))

    await waitFor(() => {
      expect(screen.getByText(/processed: 3/i)).toBeInTheDocument()
    })
  })

  it('shows scan_triggered indicator', async () => {
    vi.mocked(api.getSyncStatus).mockResolvedValue({
      last_run: '2026-06-14T10:00:00Z',
      processed: 1,
      skipped: 0,
      failed: 0,
      scan_triggered: true,
    })
    render(<StatusPage />)
    await waitFor(() => {
      expect(screen.getByText(/scan triggered/i)).toBeInTheDocument()
    })
  })
})
