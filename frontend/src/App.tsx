import { useState } from 'react'
import { FolderList } from './components/FolderList'
import { StatusPage } from './components/StatusPage'
import { FilesPage } from './components/FilesPage'

type Page = 'status' | 'folders' | 'files'

export default function App() {
  const [page, setPage] = useState<Page>('status')

  return (
    <div>
      <nav>
        <button onClick={() => setPage('status')} aria-current={page === 'status' ? 'page' : undefined}>Status</button>
        <button onClick={() => setPage('folders')} aria-current={page === 'folders' ? 'page' : undefined}>Folders</button>
        <button onClick={() => setPage('files')} aria-current={page === 'files' ? 'page' : undefined}>Files</button>
      </nav>
      <main>
        {page === 'status' && <StatusPage />}
        {page === 'folders' && <FolderList />}
        {page === 'files' && <FilesPage />}
      </main>
    </div>
  )
}
