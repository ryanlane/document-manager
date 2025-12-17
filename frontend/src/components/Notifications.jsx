import { useState, useRef, useEffect } from 'react'
import { 
  Bell, 
  X, 
  Check, 
  CheckCircle, 
  AlertCircle, 
  Info, 
  TrendingUp,
  Play,
  Trash2
} from 'lucide-react'
import { useNotifications } from '../hooks/useNotifications'
import styles from './Notifications.module.css'

// Icon mapping
const iconMap = {
  'check-circle': CheckCircle,
  'alert-circle': AlertCircle,
  'info': Info,
  'trending-up': TrendingUp,
  'play': Play,
  'check': Check
}

function NotificationItem({ notification, onMarkRead }) {
  const Icon = iconMap[notification.icon] || Info
  const timeAgo = getTimeAgo(notification.timestamp)
  
  return (
    <div 
      className={`${styles.notificationItem} ${notification.read ? styles.read : ''} ${styles[notification.type] || ''}`}
      onClick={() => !notification.read && onMarkRead(notification.id)}
    >
      <div className={styles.notificationIcon}>
        <Icon size={16} />
      </div>
      <div className={styles.notificationContent}>
        <div className={styles.notificationTitle}>{notification.title}</div>
        <div className={styles.notificationMessage}>{notification.message}</div>
        <div className={styles.notificationTime}>{timeAgo}</div>
      </div>
      {!notification.read && <div className={styles.unreadDot} />}
    </div>
  )
}

function Toast({ toast, onDismiss }) {
  const Icon = iconMap[toast.icon] || Info
  
  return (
    <div className={`${styles.toast} ${styles[toast.type] || ''}`}>
      <div className={styles.toastIcon}>
        <Icon size={18} />
      </div>
      <div className={styles.toastContent}>
        <div className={styles.toastTitle}>{toast.title}</div>
        {toast.message && <div className={styles.toastMessage}>{toast.message}</div>}
      </div>
      <button className={styles.toastDismiss} onClick={() => onDismiss(toast.id)}>
        <X size={16} />
      </button>
    </div>
  )
}

export function NotificationBell() {
  const { notifications, unreadCount, markAsRead, markAllAsRead, clearAll } = useNotifications()
  const [isOpen, setIsOpen] = useState(false)
  const panelRef = useRef(null)
  
  // Close on click outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (panelRef.current && !panelRef.current.contains(e.target)) {
        setIsOpen(false)
      }
    }
    
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isOpen])
  
  return (
    <div className={styles.bellContainer} ref={panelRef}>
      <button 
        className={styles.bellButton}
        onClick={() => setIsOpen(!isOpen)}
        aria-label="Notifications"
      >
        <Bell size={20} />
        {unreadCount > 0 && (
          <span className={styles.badge}>
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>
      
      {isOpen && (
        <div className={styles.panel}>
          <div className={styles.panelHeader}>
            <h3>Notifications</h3>
            <div className={styles.panelActions}>
              {unreadCount > 0 && (
                <button onClick={markAllAsRead} title="Mark all as read">
                  <Check size={14} />
                </button>
              )}
              {notifications.length > 0 && (
                <button onClick={clearAll} title="Clear all">
                  <Trash2 size={14} />
                </button>
              )}
            </div>
          </div>
          
          <div className={styles.panelContent}>
            {notifications.length === 0 ? (
              <div className={styles.emptyState}>
                <Bell size={32} />
                <p>No notifications yet</p>
              </div>
            ) : (
              notifications.map(notification => (
                <NotificationItem 
                  key={notification.id}
                  notification={notification}
                  onMarkRead={markAsRead}
                />
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export function ToastContainer() {
  const { toasts, dismissToast } = useNotifications()
  
  if (toasts.length === 0) return null
  
  return (
    <div className={styles.toastContainer}>
      {toasts.map(toast => (
        <Toast key={toast.id} toast={toast} onDismiss={dismissToast} />
      ))}
    </div>
  )
}

// Helper function
function getTimeAgo(timestamp) {
  const now = new Date()
  const then = new Date(timestamp)
  const seconds = Math.floor((now - then) / 1000)
  
  if (seconds < 60) return 'Just now'
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
  return `${Math.floor(seconds / 86400)}d ago`
}

export default NotificationBell
