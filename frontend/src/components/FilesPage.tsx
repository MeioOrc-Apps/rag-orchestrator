import { useState, useEffect } from 'react'
import { listFiles, type ProcessedFile } from '../api'

const STATUS_FILTERS = ['all', 'done', 'failed', 'processing', 'skipped'] as const

export function FilesPage() {
  const [files, setFiles] = useState<ProcessedFile[]>([])
  const [activeFilter, setActiveFilter] = useState<string | undefined>(undefined)

  useEffect(() => {
    listFiles(activeFilter).then(setFiles).catch(console.error)
  }, [activeFilter])

  function handleFilter(filter: string) {
    setActiveFilter(filter === 'all' ? undefined : filter)
  }

  return (
    <div>
      <h2>Processed Files</h2>

      <div role="group" aria-label="Status filters">
        {STATUS_FILTERS.map(f => (
          <button
            key={f}
            onClick={() => handleFilter(f)}
            aria-pressed={
              f === 'all' ? activeFilter === undefined : activeFilter === f
            }
          >
            {f}
          </button>
        ))}
      </div>

      {files.length === 0 ? (
        <p>No files found</p>
      ) : (
        <ul>
          {files.map(file => (
            <li key={file.id} data-testid="file-item">
              <span>{file.source_path}</span>
              <span>{file.status}</span>
              {file.error_message && (
                <span>{file.error_message}</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
