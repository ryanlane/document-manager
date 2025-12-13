import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import Navbar from './components/Navbar'
import Home from './pages/Home'
import DocumentView from './pages/DocumentView'
import Files from './pages/Files'
import Dashboard from './pages/Dashboard'
import Logs from './pages/Logs'

function App() {
  return (
    <Router>
      <Navbar />
      <div style={{ paddingTop: '60px' }}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/files" element={<Files />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/logs" element={<Logs />} />
          <Route path="/document/:id" element={<DocumentView />} />
        </Routes>
      </div>
    </Router>
  )
}

export default App
