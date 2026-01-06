import { Link, useLocation } from 'react-router-dom'
import { Search, FolderOpen, Activity, Menu, X, ScrollText, BookOpen, Settings, Orbit, AlertCircle, CheckCircle, AlertTriangle, ChevronDown, Image, Gauge } from 'lucide-react'
import { useState, useEffect, useCallback, useRef } from 'react'
import styles from './Navbar.module.css'
import Logo from './Logo'
import { NotificationBell } from './Notifications'
import HealthMetricsIcon from '../assets/monitor_heart.svg'

// Health metrics icon - changes color based on status
const HealthIcon = ({ size = 18, className }) => (
  <img 
    src={HealthMetricsIcon} 
    alt="System Health" 
    width={size} 
    height={size} 
    className={className}
  />
)

// Dropdown menu component
function NavDropdown({ label, icon: Icon, items, isOpen, onToggle, onClose, location }) {
  const dropdownRef = useRef(null)
  
  // Check if any child is active
  const hasActiveChild = items.some(item => 
    item.match ? location.pathname.startsWith(item.match) : location.pathname === item.path
  )

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        onClose()
      }
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
    }
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [isOpen, onClose])

  return (
    <div className={styles.dropdown} ref={dropdownRef}>
      <button 
        className={`${styles.dropdownTrigger} ${hasActiveChild ? styles.active : ''}`}
        onClick={onToggle}
      >
        <Icon size={18} />
        <span>{label}</span>
        <ChevronDown size={14} className={`${styles.chevron} ${isOpen ? styles.chevronOpen : ''}`} />
      </button>
      {isOpen && (
        <div className={styles.dropdownMenu}>
          {items.map(item => (
            <Link 
              key={item.path}
              to={item.path} 
              className={`${styles.dropdownItem} ${
                (item.match ? location.pathname.startsWith(item.match) : location.pathname === item.path) 
                  ? styles.active : ''
              }`}
              onClick={onClose}
            >
              <item.icon size={16} />
              <span>{item.label}</span>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}

function Navbar() {
  const [isOpen, setIsOpen] = useState(false)
  const [openDropdown, setOpenDropdown] = useState(null)
  const [healthStatus, setHealthStatus] = useState(null)
  const [showHealthPopup, setShowHealthPopup] = useState(false)
  const location = useLocation()

  const toggleMenu = () => setIsOpen(!isOpen)
  const closeMenu = () => setIsOpen(false)

  // Navigation structure
  const exploreItems = [
    { path: '/browse', match: '/browse', label: 'Browse', icon: FolderOpen },
    { path: '/browse?tab=images', match: '/browse', label: 'Gallery', icon: Image },
    { path: '/embeddings', label: 'Embeddings', icon: Orbit },
  ]

  const systemItems = [
    { path: '/dashboard', label: 'Dashboard', icon: Gauge },
    { path: '/settings', label: 'Settings', icon: Settings },
    { path: '/logs', label: 'Logs', icon: ScrollText },
  ]

  const fetchHealth = useCallback(async () => {
    try {
      const res = await fetch('/api/system/health-check')
      const data = await res.json()
      setHealthStatus(data)
    } catch (err) {
      setHealthStatus({ status: 'error', checks: {}, error: err.message })
    }
  }, [])

  useEffect(() => {
    fetchHealth()
    const interval = setInterval(fetchHealth, 60000)
    return () => clearInterval(interval)
  }, [fetchHealth])

  // Close dropdowns on route change
  useEffect(() => {
    setOpenDropdown(null)
    setShowHealthPopup(false)
  }, [location.pathname])

  const getHealthClass = () => {
    if (!healthStatus) return ''
    switch (healthStatus.status) {
      case 'ok': return styles.healthOk
      case 'warning': return styles.healthWarning
      case 'error': return styles.healthError
      default: return ''
    }
  }

  const getCheckIcon = (status) => {
    switch (status) {
      case 'ok':
        return <CheckCircle size={14} className={styles.healthOk} />
      case 'warning':
        return <AlertTriangle size={14} className={styles.healthWarning} />
      case 'error':
        return <AlertCircle size={14} className={styles.healthError} />
      default:
        return null
    }
  }

  const handleDropdownToggle = (name) => {
    setOpenDropdown(openDropdown === name ? null : name)
    setShowHealthPopup(false)
  }

  return (
    <nav className={styles.navbar}>
      <div className={styles.navContainer}>
        <div className={styles.brand}>
          <Link to="/" onClick={closeMenu} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Logo size={24} />
            <span className={styles.brandText}>Archive Brain</span>
          </Link>
        </div>
        
        {/* Mobile: Notifications + Health + Hamburger */}
        <div className={styles.mobileControls}>
          <NotificationBell />
          <div className={styles.healthIndicator}>
            <button 
              className={styles.healthButton}
              onClick={() => {
                setShowHealthPopup(!showHealthPopup)
                setOpenDropdown(null)
              }}
              title={`System Status: ${healthStatus?.status || 'checking...'}`}
            >
              <HealthIcon size={18} className={getHealthClass()} />
            </button>
            
            {showHealthPopup && healthStatus && (
              <div className={styles.healthPopup}>
                <div className={styles.healthPopupHeader}>
                  <span>System Health</span>
                  <button onClick={() => setShowHealthPopup(false)}><X size={14} /></button>
                </div>
                <div className={styles.healthChecks}>
                  {Object.entries(healthStatus.checks || {}).map(([key, check]) => (
                    <div key={key} className={styles.healthCheck}>
                      <div className={styles.healthCheckHeader}>
                        {getCheckIcon(check.status)}
                        <span className={styles.healthCheckName}>{key}</span>
                      </div>
                      <span className={styles.healthCheckMessage}>{check.message}</span>
                      {check.fix && (
                        <span className={styles.healthCheckFix}>{check.fix}</span>
                      )}
                    </div>
                  ))}
                </div>
                <button className={styles.healthRefresh} onClick={fetchHealth}>
                  Refresh
                </button>
              </div>
            )}
          </div>
          <button className={styles.toggle} onClick={toggleMenu} aria-label="Toggle menu">
            {isOpen ? <X /> : <Menu />}
          </button>
        </div>

        <div className={`${styles.links} ${isOpen ? styles.open : ''}`}>
          {/* Search - Primary action, always visible */}
          <Link to="/" className={`${styles.link} ${styles.primary} ${location.pathname === '/' ? styles.active : ''}`} onClick={closeMenu}>
            <Search size={18} /> Search
          </Link>
          
          {/* Explore dropdown */}
          <NavDropdown
            label="Explore"
            icon={FolderOpen}
            items={exploreItems}
            isOpen={openDropdown === 'explore'}
            onToggle={() => handleDropdownToggle('explore')}
            onClose={() => setOpenDropdown(null)}
            location={location}
          />

          {/* System dropdown */}
          <NavDropdown
            label="System"
            icon={Activity}
            items={systemItems}
            isOpen={openDropdown === 'system'}
            onToggle={() => handleDropdownToggle('system')}
            onClose={() => setOpenDropdown(null)}
            location={location}
          />

          {/* Help - standalone link */}
          <Link to="/how-it-works" className={`${styles.link} ${location.pathname === '/how-it-works' ? styles.active : ''}`} onClick={closeMenu}>
            <BookOpen size={18} /> <span className={styles.helpLabel}>Help</span>
          </Link>

          {/* Desktop Notifications */}
          <div className={styles.notificationsDesktop}>
            <NotificationBell />
          </div>

          {/* Desktop Health Indicator */}
          <div className={styles.healthIndicatorDesktop}>
            <button 
              className={styles.healthButton}
              onClick={() => {
                setShowHealthPopup(!showHealthPopup)
                setOpenDropdown(null)
              }}
              title={`System Status: ${healthStatus?.status || 'checking...'}`}
            >
              <HealthIcon size={18} className={getHealthClass()} />
            </button>
            
            {showHealthPopup && healthStatus && (
              <div className={styles.healthPopup}>
                <div className={styles.healthPopupHeader}>
                  <span>System Health</span>
                  <button onClick={() => setShowHealthPopup(false)}><X size={14} /></button>
                </div>
                <div className={styles.healthChecks}>
                  {Object.entries(healthStatus.checks || {}).map(([key, check]) => (
                    <div key={key} className={styles.healthCheck}>
                      <div className={styles.healthCheckHeader}>
                        {getCheckIcon(check.status)}
                        <span className={styles.healthCheckName}>{key}</span>
                      </div>
                      <span className={styles.healthCheckMessage}>{check.message}</span>
                      {check.fix && (
                        <span className={styles.healthCheckFix}>{check.fix}</span>
                      )}
                    </div>
                  ))}
                </div>
                <button className={styles.healthRefresh} onClick={fetchHealth}>
                  Refresh
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </nav>
  )
}

export default Navbar
