import { Link, useLocation } from 'react-router-dom'
import { Home, FileText, Activity, Menu, X, ScrollText, BookOpen, Image, Settings } from 'lucide-react'
import { useState } from 'react'
import styles from './Navbar.module.css'

function Navbar() {
  const [isOpen, setIsOpen] = useState(false)
  const location = useLocation()

  const toggleMenu = () => setIsOpen(!isOpen)

  const isActive = (path) => location.pathname === path ? styles.active : ''

  return (
    <nav className={styles.navbar}>
      <div className={styles.navContainer}>
        <div className={styles.brand}>
          <Link to="/" onClick={() => setIsOpen(false)}>Archive Brain</Link>
        </div>
        
        <button className={styles.toggle} onClick={toggleMenu}>
          {isOpen ? <X /> : <Menu />}
        </button>

        <div className={`${styles.links} ${isOpen ? styles.open : ''}`}>
          <Link to="/" className={`${styles.link} ${isActive('/')}`} onClick={() => setIsOpen(false)}>
            <Home size={18} /> Search
          </Link>
          <Link to="/files" className={`${styles.link} ${isActive('/files')}`} onClick={() => setIsOpen(false)}>
            <FileText size={18} /> Files
          </Link>
          <Link to="/gallery" className={`${styles.link} ${isActive('/gallery')}`} onClick={() => setIsOpen(false)}>
            <Image size={18} /> Gallery
          </Link>
          <Link to="/dashboard" className={`${styles.link} ${isActive('/dashboard')}`} onClick={() => setIsOpen(false)}>
            <Activity size={18} /> Dashboard
          </Link>
          <Link to="/logs" className={`${styles.link} ${isActive('/logs')}`} onClick={() => setIsOpen(false)}>
            <ScrollText size={18} /> Logs
          </Link>
          <Link to="/how-it-works" className={`${styles.link} ${isActive('/how-it-works')}`} onClick={() => setIsOpen(false)}>
            <BookOpen size={18} /> How It Works
          </Link>
          <Link to="/settings" className={`${styles.link} ${isActive('/settings')}`} onClick={() => setIsOpen(false)}>
            <Settings size={18} /> Settings
          </Link>
        </div>
      </div>
    </nav>
  )
}

export default Navbar
