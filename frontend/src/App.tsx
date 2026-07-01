import { type ReactElement, useState } from 'react'
import { FolderList } from './components/FolderList'
import { StatusPage } from './components/StatusPage'
import { FilesPage } from './components/FilesPage'
import { SearchPage } from './components/SearchPage'
import { AdminPage } from './components/AdminPage'
import './App.css'

type Page = 'status' | 'folders' | 'files' | 'search' | 'admin'

function IconPipeline() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="5" r="3"/><circle cx="19" cy="12" r="3"/><circle cx="12" cy="19" r="3"/>
      <path d="M12 8v8M12 8l7-1M12 16l7-3"/>
    </svg>
  )
}

function IconStatus() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
    </svg>
  )
}

function IconFolders() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/>
    </svg>
  )
}

function IconFiles() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
      <polyline points="14 2 14 8 20 8"/>
      <line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>
      <line x1="10" y1="9" x2="8" y2="9"/>
    </svg>
  )
}

function IconSearch() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
    </svg>
  )
}

function IconAdmin() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3"/>
      <path d="M19.07 4.93a10 10 0 010 14.14M4.93 4.93a10 10 0 000 14.14"/>
    </svg>
  )
}

const PAGES: { id: Page; label: string; Icon: () => ReactElement }[] = [
  { id: 'status',  label: 'Status',  Icon: IconStatus },
  { id: 'folders', label: 'Folders', Icon: IconFolders },
  { id: 'files',   label: 'Files',   Icon: IconFiles },
  { id: 'search',  label: 'Search',  Icon: IconSearch },
  { id: 'admin',   label: 'Admin',   Icon: IconAdmin },
]

const LS_KEY = 'rag-page'

export default function App() {
  const [page, setPage] = useState<Page>(() => {
    const saved = localStorage.getItem(LS_KEY)
    return (saved as Page | null) ?? 'status'
  })

  function navigate(p: Page) {
    setPage(p)
    localStorage.setItem(LS_KEY, p)
  }

  return (
    <>
      <aside className="sidebar">
        <div className="sidebar-logo">
          <div className="sidebar-logo-icon">
            <IconPipeline />
          </div>
          <div className="sidebar-logo-name">
            RAG Orchestrator
            <span className="sidebar-logo-sub">v{__APP_VERSION__}</span>
          </div>
        </div>

        <nav className="sidebar-nav">
          {PAGES.map(({ id, label, Icon }) => (
            <button
              key={id}
              className="nav-item"
              onClick={() => navigate(id)}
              aria-current={page === id ? 'page' : undefined}
            >
              <Icon />
              {label}
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          Document pipeline
        </div>
      </aside>

      <main className="content">
        {page === 'status'  && <StatusPage />}
        {page === 'folders' && <FolderList />}
        {page === 'files'   && <FilesPage />}
        {page === 'search'  && <SearchPage />}
        {page === 'admin'   && <AdminPage />}
      </main>
    </>
  )
}
