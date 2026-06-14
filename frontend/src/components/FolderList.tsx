import { useState, useEffect } from 'react'
import { listFolders, createFolder, type Folder } from '../api'

export function FolderList() {
  const [folders, setFolders] = useState<Folder[]>([])
  const [hostPath, setHostPath] = useState('')
  const [destSubdir, setDestSubdir] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    listFolders().then(setFolders).catch(() => setError('Failed to load folders'))
  }, [])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      const created = await createFolder({ host_path: hostPath, dest_subdir: destSubdir })
      setFolders(prev => [...prev, created])
      setHostPath('')
      setDestSubdir('')
    } catch {
      setError('Failed to create folder')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div>
      <h2>Watched Folders</h2>
      {error && <p role="alert">{error}</p>}
      <ul>
        {folders.map(f => (
          <li key={f.id} data-testid="folder-item">
            {f.host_path} → {f.dest_subdir}
          </li>
        ))}
      </ul>
      <form onSubmit={handleSubmit} aria-label="Add folder">
        <label>
          Host path
          <input
            value={hostPath}
            onChange={e => setHostPath(e.target.value)}
            placeholder="/data/docs"
            aria-label="Host path"
          />
        </label>
        <label>
          Destination subdirectory
          <input
            value={destSubdir}
            onChange={e => setDestSubdir(e.target.value)}
            placeholder="docs"
            aria-label="Destination subdirectory"
          />
        </label>
        <button type="submit" disabled={submitting}>
          {submitting ? 'Adding…' : 'Add folder'}
        </button>
      </form>
    </div>
  )
}
