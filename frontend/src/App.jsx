import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import Home from './pages/Home'
import DocumentView from './pages/DocumentView'

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/document/:id" element={<DocumentView />} />
      </Routes>
    </Router>
  )
}

export default App
