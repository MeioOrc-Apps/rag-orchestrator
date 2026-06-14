export interface Folder {
  id: string
  owner_id: string
  host_path: string
  dest_subdir: string
  recursive: boolean
  enabled: boolean
  created_at: string
}

export interface FolderCreate {
  host_path: string
  dest_subdir: string
  recursive?: boolean
  enabled?: boolean
}

export interface SyncStatus {
  last_run: string | null
  processed?: number
  skipped?: number
  failed?: number
  scan_triggered?: boolean
}

export interface SyncResult {
  processed: number
  skipped: number
  failed: number
  scan_triggered: boolean
}

export interface ProcessedFile {
  id: string
  owner_id: string
  folder_id: string
  source_path: string
  dest_path: string | null
  content_hash: string
  file_type: string
  route: string
  status: string
  error_message: string | null
  processed_at: string | null
  created_at: string
}

const BASE = '/api'

export async function listFolders(): Promise<Folder[]> {
  const res = await fetch(`${BASE}/folders`)
  if (!res.ok) throw new Error('Failed to fetch folders')
  return res.json()
}

export async function createFolder(data: FolderCreate): Promise<Folder> {
  const res = await fetch(`${BASE}/folders`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error('Failed to create folder')
  return res.json()
}

export async function deleteFolder(id: string): Promise<void> {
  const res = await fetch(`${BASE}/folders/${id}`, { method: 'DELETE' })
  if (!res.ok) throw new Error('Failed to delete folder')
}

export async function getSyncStatus(): Promise<SyncStatus> {
  const res = await fetch(`${BASE}/sync/status`)
  if (!res.ok) throw new Error('Failed to fetch sync status')
  return res.json()
}

export async function triggerSync(): Promise<SyncResult> {
  const res = await fetch(`${BASE}/sync`, { method: 'POST' })
  if (!res.ok) throw new Error('Sync failed')
  return res.json()
}

export async function listFiles(status?: string): Promise<ProcessedFile[]> {
  const url = status ? `${BASE}/files?status=${encodeURIComponent(status)}` : `${BASE}/files`
  const res = await fetch(url)
  if (!res.ok) throw new Error('Failed to fetch files')
  return res.json()
}
