import { Link, useLocation } from 'react-router-dom'
import { Home, FolderOpen, Activity, Menu, X, ScrollText, BookOpen, Settings, Orbit } from 'lucide-react'
import { useState } from 'react'
import styles from './Navbar.module.css'
import Logo from './Logo'

function Navbar() {
  const [isOpen, setIsOpen] = useState(false)
  const location = useLocation()

  const toggleMenu = () => setIsOpen(!isOpen)

  const isActive = (path) => location.pathname === path ? styles.active : ''

  return (
    <nav className={styles.navbar}>
      <div className={styles.navContainer}>
        <div className={styles.brand}>
          <Link to="/" onClick={() => setIsOpen(false)} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Logo size={24} />
            Archive Brain
          </Link>
        </div>
        
        <button className={styles.toggle} onClick={toggleMenu}>
          {isOpen ? <X /> : <Menu />}
        </button>

        <div className={`${styles.links} ${isOpen ? styles.open : ''}`}>
          <Link to="/" className={`${styles.link} ${isActive('/')}`} onClick={() => setIsOpen(false)}>
            <Home size={18} /> Search
          </Link>          
          <Link to="/dashboard" className={`${styles.link} ${isActive('/dashboard')}`} onClick={() => setIsOpen(false)}>
            <Activity size={18} /> Dashboard
          </Link>          
          <Link to="/embeddings" className={`${styles.link} ${isActive('/embeddings')}`} onClick={() => setIsOpen(false)}>
            <Orbit size={18} /> Embeddings
          </Link>
          <Link to="/browse" className={`${styles.link} ${location.pathname.startsWith('/browse') ? styles.active : ''}`} onClick={() => setIsOpen(false)}>
            <FolderOpen size={18} /> Browse
          </Link>
          <Link to="/how-it-works" className={`${styles.link} ${isActive('/how-it-works')}`} onClick={() => setIsOpen(false)}>
            <BookOpen size={18} /> How It Works
          </Link>
          <Link to="/settings" className={`${styles.link} ${isActive('/settings')}`} onClick={() => setIsOpen(false)}>
            <Settings size={18} /> Settings
          </Link>
          <Link to="/logs" className={`${styles.link} ${isActive('/logs')}`} onClick={() => setIsOpen(false)}>
            <ScrollText size={18} /> Logs
          </Link>
        </div>
      </div>
    </nav>
  )
}

export default Navbar
