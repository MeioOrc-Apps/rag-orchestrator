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
