import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import Navbar from './components/Navbar'
import Home from './pages/Home'
import DocumentView from './pages/DocumentView'
import Files from './pages/Files'
import Dashboard from './pages/Dashboard'
import Logs from './pages/Logs'
import ResolveLink from './pages/ResolveLink'
import HowItWorks from './pages/HowItWorks'
import Gallery from './pages/Gallery'
import Settings from './pages/Settings'
import EntryInspector from './pages/EntryInspector'
import EmbeddingViz from './pages/EmbeddingViz'

function App() {
  return (
    <Router future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Navbar />
      <div style={{ paddingTop: '60px' }}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/files" element={<Files />} />
          <Route path="/gallery" element={<Gallery />} />
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
    </Router>
  )
}

export default App
