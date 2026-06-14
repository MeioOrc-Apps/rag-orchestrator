import { useState, useEffect } from 'react'
import { listFolders, createFolder, deleteFolder, type Folder } from '../api'

function IconPlus() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
    </svg>
  )
}

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

  async function handleDelete(id: string) {
    try {
      await deleteFolder(id)
      setFolders(prev => prev.filter(f => f.id !== id))
    } catch {
      setError('Failed to delete folder')
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Watched Folders</h1>
      </div>

      {error && (
        <div role="alert" className="alert">
          {error}
        </div>
      )}

      {folders.length === 0 ? (
        <div className="empty-state" style={{ marginBottom: 24 }}>
          No folders configured yet. Add one below.
        </div>
      ) : (
        <div className="folder-list">
          {folders.map(f => (
            <div key={f.id} data-testid="folder-item" className="folder-item">
              <div className="folder-path-row">
                {/* single span so getByText('/data/docs → docs') finds it as one text node */}
                <span style={{
                  fontFamily: 'ui-monospace, Consolas, monospace',
                  fontSize: 13,
                  color: 'var(--text-strong)',
                }}>
                  {f.host_path} → {f.dest_subdir}
                </span>
              </div>
              <div className="folder-meta">
                <span className={f.recursive ? 'pill pill-green' : 'pill'}>
                  {f.recursive ? 'recursive' : 'flat'}
                </span>
                <span className={f.enabled ? 'pill pill-green' : 'pill pill-gray'}>
                  {f.enabled ? 'enabled' : 'disabled'}
                </span>
                <button
                  className="btn-danger-sm"
                  onClick={() => handleDelete(f.id)}
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="form-section">
        <p className="form-title">
          <IconPlus />
          Add Folder
        </p>
        <form onSubmit={handleSubmit} aria-label="Add folder">
          <div className="form-row">
            <div className="form-group">
              <label className="form-label" htmlFor="host-path">Host path</label>
              <input
                id="host-path"
                className="form-input"
                value={hostPath}
                onChange={e => setHostPath(e.target.value)}
                placeholder="/data/documents"
                aria-label="Host path"
              />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="dest-subdir">Destination subdirectory</label>
              <input
                id="dest-subdir"
                className="form-input"
                value={destSubdir}
                onChange={e => setDestSubdir(e.target.value)}
                placeholder="docs"
                aria-label="Destination subdirectory"
              />
            </div>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={submitting}
              style={{ alignSelf: 'flex-end', flexShrink: 0 }}
            >
              {submitting ? 'Adding…' : 'Add folder'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
