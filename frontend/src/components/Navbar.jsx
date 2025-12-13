import { Link, useLocation } from 'react-router-dom'
import { Home, FileText, Activity, Menu, X, ScrollText } from 'lucide-react'
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
          <Link to="/dashboard" className={`${styles.link} ${isActive('/dashboard')}`} onClick={() => setIsOpen(false)}>
            <Activity size={18} /> Dashboard
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
