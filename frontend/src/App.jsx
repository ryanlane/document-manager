import { BrowserRouter as Router, Routes, Route, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import Navbar from './components/Navbar'
import { ToastContainer } from './components/Notifications'
import { NotificationProvider } from './hooks/useNotifications'
import Home from './pages/Home'
import DocumentView from './pages/DocumentView'
import Browse from './pages/Browse'
import Dashboard from './pages/Dashboard'
import Logs from './pages/Logs'
import ResolveLink from './pages/ResolveLink'
import HowItWorks from './pages/HowItWorks'
import Settings from './pages/Settings'
import EntryInspector from './pages/EntryInspector'
import EmbeddingViz from './pages/EmbeddingViz'
import Setup from './pages/Setup'

// Component that handles first-run detection and redirect
function FirstRunRedirect({ children }) {
  const location = useLocation()
  const navigate = useNavigate()
  const [checking, setChecking] = useState(true)
  const [setupRequired, setSetupRequired] = useState(false)

  useEffect(() => {
    // Skip check if already on setup page
    if (location.pathname === '/setup') {
      setChecking(false)
      return
    }

    // Check first-run status
    const checkFirstRun = async () => {
      try {
        const res = await fetch('/api/system/first-run')
        if (res.ok) {
          const data = await res.json()
          if (data.setup_required) {
            setSetupRequired(true)
            navigate('/setup')
          }
        }
      } catch (err) {
        console.error('Failed to check first-run status:', err)
      }
      setChecking(false)
    }

    checkFirstRun()
  }, [location.pathname, navigate])

  // Show loading briefly while checking
  if (checking && location.pathname === '/') {
    return null
  }

  return children
}

function App() {
  return (
    <Router future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <NotificationProvider>
        <FirstRunRedirect>
          <Navbar />
          <div style={{ paddingTop: '60px' }}>
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/setup" element={<Setup />} />
              <Route path="/browse" element={<Browse />} />
              <Route path="/files" element={<Navigate to="/browse?tab=files" replace />} />
              <Route path="/gallery" element={<Navigate to="/browse?tab=images" replace />} />
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/logs" element={<Logs />} />
              <Route path="/how-it-works" element={<HowItWorks />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="/document/:id" element={<DocumentView />} />
              <Route path="/resolve" element={<ResolveLink />} />
              <Route path="/entry" element={<EntryInspector />} />
              <Route path="/entry/:entryId" element={<EntryInspector />} />
              <Route path="/embeddings" element={<EmbeddingViz />} />
            </Routes>
          </div>
        </FirstRunRedirect>
        <ToastContainer />
      </NotificationProvider>
    </Router>
  )
}

export default App
