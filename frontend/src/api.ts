const BASE = '/api'

async function _json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

// ── Folders ────────────────────────────────────────────────────────────────

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

export async function listFolders(): Promise<Folder[]> {
  return _json(await fetch(`${BASE}/folders`))
}

export async function createFolder(data: FolderCreate): Promise<Folder> {
  return _json(await fetch(`${BASE}/folders`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  }))
}

export async function deleteFolder(id: string): Promise<void> {
  const res = await fetch(`${BASE}/folders/${id}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
}

// ── Sync ───────────────────────────────────────────────────────────────────

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

export async function getSyncStatus(): Promise<SyncStatus> {
  return _json(await fetch(`${BASE}/sync/status`))
}

export async function triggerSync(): Promise<SyncResult> {
  return _json(await fetch(`${BASE}/sync`, { method: 'POST' }))
}

// ── Files (v2.0) ───────────────────────────────────────────────────────────

export interface File {
  id: string
  path: string
  filename: string
  domain: string
  file_hash: string
  file_size_bytes: number
  parse_status: string
  parse_error: string | null
  chunks: ChunksSummary | null
  created_at: string
  updated_at: string
}

export interface ChunksSummary {
  total: number
  translated: number
  done: number
  pending: number
  failed: number
  deleted: number
}

export interface FileDetail extends File {
  chunks: ChunksSummary
}

export interface FilesQuery {
  domain?: string
  parse_status?: string
  limit?: number
  offset?: number
}

export interface PaginatedFiles {
  items: File[]
  total: number
  limit: number
  offset: number
}

export async function listFiles(query: FilesQuery = {}): Promise<PaginatedFiles> {
  const params = new URLSearchParams()
  if (query.domain)       params.set('domain', query.domain)
  if (query.parse_status) params.set('parse_status', query.parse_status)
  if (query.limit  != null) params.set('limit',  String(query.limit))
  if (query.offset != null) params.set('offset', String(query.offset))
  const qs = params.toString()
  return _json(await fetch(qs ? `${BASE}/files?${qs}` : `${BASE}/files`))
}

export async function getFile(id: string): Promise<FileDetail> {
  return _json(await fetch(`${BASE}/files/${id}`))
}

export async function softDeleteFile(id: string): Promise<void> {
  const res = await fetch(`${BASE}/files/${id}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
}

export async function reindexFile(id: string): Promise<void> {
  await _json(await fetch(`${BASE}/files/${id}/reindex`, { method: 'POST' }))
}

export async function retranslateFile(id: string): Promise<void> {
  await _json(await fetch(`${BASE}/files/${id}/retranslate`, { method: 'POST' }))
}

// ── Search ─────────────────────────────────────────────────────────────────

export interface SearchRequest {
  query: string
  domain?: string
  enrich?: boolean
  limit?: number
  offset?: number
}

export interface SearchHit {
  chunk_id: string
  file_id: string
  domain: string
  chunk_index: number
  source_language: string
  content_en: string
  content_pt: string
  highlight: string
  score: number
}

export interface SearchResponse {
  results: SearchHit[]
  total: number
  fallback_used: boolean
  query_enriched: string | null
}

export async function search(req: SearchRequest): Promise<SearchResponse> {
  return _json(await fetch(`${BASE}/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  }))
}

// ── Admin ──────────────────────────────────────────────────────────────────

export interface AdminStats {
  files: {
    total: number
    by_parse_status: Record<string, number>
  }
  chunks: {
    total: number
    by_index_status: Record<string, number>
    by_translation_status: Record<string, number>
    translated_pending_reindex: number
  }
}

export interface FailedFile {
  id: string
  path: string
  parse_error: string | null
}

export interface FailedChunk {
  id: string
  file_id: string
  translation_status: string
  index_status: string
  translation_error: string | null
  index_error: string | null
}

export interface AdminFailed {
  failed_files: FailedFile[]
  failed_chunks: FailedChunk[]
}

export async function getAdminStats(): Promise<AdminStats> {
  return _json(await fetch(`${BASE}/admin/stats`))
}

export async function getAdminFailed(): Promise<AdminFailed> {
  return _json(await fetch(`${BASE}/admin/failed`))
}

export async function retryFailed(): Promise<{ message: string }> {
  return _json(await fetch(`${BASE}/admin/retry-failed`, { method: 'POST' }))
}

export async function reindexAll(): Promise<{ message: string }> {
  return _json(await fetch(`${BASE}/admin/reindex-all`, { method: 'POST' }))
}

export async function forcemerge(): Promise<{ message: string }> {
  return _json(await fetch(`${BASE}/admin/forcemerge`, { method: 'POST' }))
}

// ── Admin Settings ─────────────────────────────────────────────────────────

export interface LLMSettings {
  translation_model: string
  enrichment_model: string
  translation_enabled: boolean
  translation_batch_size: number
  translate_workers: number
  prompt_template_en: string
  prompt_template_pt: string
  prompt_enrichment: string
}

export interface PipelineSettings {
  chunk_size: number
  chunk_overlap: number
  parse_batch_size: number
  max_translation_retries: number
}

export interface AppSettings {
  llm: LLMSettings
  pipeline: PipelineSettings
}

export interface LLMSettingsUpdate {
  translation_model?: string
  enrichment_model?: string
  translation_enabled?: boolean
  translation_batch_size?: number
  translate_workers?: number
  prompt_template_en?: string
  prompt_template_pt?: string
  prompt_enrichment?: string
}

export interface PipelineSettingsUpdate {
  chunk_size?: number
  chunk_overlap?: number
  parse_batch_size?: number
  max_translation_retries?: number
}

export interface SettingsUpdate {
  llm?: LLMSettingsUpdate
  pipeline?: PipelineSettingsUpdate
}

export async function getSettings(): Promise<AppSettings> {
  return _json(await fetch(`${BASE}/admin/settings`))
}

export async function updateSettings(body: SettingsUpdate): Promise<AppSettings> {
  return _json(await fetch(`${BASE}/admin/settings`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }))
}
