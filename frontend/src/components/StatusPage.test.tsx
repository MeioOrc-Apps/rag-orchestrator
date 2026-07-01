import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import { StatusPage } from './StatusPage'
import * as api from '../api'

vi.mock('../api')

const mockStats: api.AdminStats = {
  files: { total: 11, by_parse_status: { done: 11 } },
  chunks: {
    total: 100,
    by_index_status: { done: 50, pending: 50 },
    by_translation_status: { done: 75, pending: 25 },
  },
}

describe('StatusPage', () => {
  beforeEach(() => {
    vi.mocked(api.getSyncStatus).mockResolvedValue({ last_run: '2026-06-14T12:00:00Z' })
    vi.mocked(api.getAdminStats).mockResolvedValue(mockStats)
    vi.mocked(api.triggerSync).mockResolvedValue({
      processed: 3, skipped: 1, failed: 0, scan_triggered: true,
    })
  })

  it('renders Sync Now button', () => {
    render(<StatusPage />)
    expect(screen.getByRole('button', { name: /sync now/i })).toBeInTheDocument()
  })

  it('shows pipeline status title', () => {
    render(<StatusPage />)
    expect(screen.getByText(/pipeline status/i)).toBeInTheDocument()
  })

  it('shows chunk totals after loading', async () => {
    render(<StatusPage />)
    await waitFor(() => {
      expect(screen.getByText('100')).toBeInTheDocument()
    })
  })

  it('shows last sync timestamp', async () => {
    render(<StatusPage />)
    await waitFor(() => {
      expect(screen.getByText(/14\/06\/2026/)).toBeInTheDocument()
    })
  })

  it('shows loading state while sync is running', async () => {
    let resolve: (v: api.SyncResult) => void
    vi.mocked(api.triggerSync).mockReturnValue(new Promise(r => { resolve = r }))
    const user = userEvent.setup()
    render(<StatusPage />)

    await user.click(screen.getByRole('button', { name: /sync now/i }))
    expect(screen.getByRole('button', { name: /syncing/i })).toBeDisabled()

    resolve!({ processed: 1, skipped: 0, failed: 0, scan_triggered: false })
  })
})
