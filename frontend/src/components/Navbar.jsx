import { Link, useLocation } from 'react-router-dom'
import { Home, FileText, Activity, Menu, X } from 'lucide-react'
import { useState } from 'react'

function Navbar() {
  const [isOpen, setIsOpen] = useState(false)
  const location = useLocation()

  const toggleMenu = () => setIsOpen(!isOpen)

  const isActive = (path) => location.pathname === path ? 'active' : ''

  return (
    <nav className="navbar">
      <div className="nav-brand">
        <Link to="/" onClick={() => setIsOpen(false)}>Archive Brain</Link>
      </div>
      
      <button className="nav-toggle" onClick={toggleMenu}>
        {isOpen ? <X /> : <Menu />}
      </button>

      <div className={`nav-links ${isOpen ? 'open' : ''}`}>
        <Link to="/" className={isActive('/')} onClick={() => setIsOpen(false)}>
          <Home size={18} /> Search
        </Link>
        <Link to="/files" className={isActive('/files')} onClick={() => setIsOpen(false)}>
          <FileText size={18} /> Files
        </Link>
        <Link to="/dashboard" className={isActive('/dashboard')} onClick={() => setIsOpen(false)}>
          <Activity size={18} /> Dashboard
        </Link>
      </div>
    </nav>
  )
}

export default Navbar
