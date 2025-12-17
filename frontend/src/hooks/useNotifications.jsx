import { useState, useEffect, useCallback, createContext, useContext } from 'react'

// Notification context for app-wide access
const NotificationContext = createContext(null)

export function useNotifications() {
  const context = useContext(NotificationContext)
  if (!context) {
    throw new Error('useNotifications must be used within NotificationProvider')
  }
  return context
}

export function NotificationProvider({ children }) {
  const [notifications, setNotifications] = useState([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [toasts, setToasts] = useState([])
  const [lastProgress, setLastProgress] = useState(null)
  const [isPolling, setIsPolling] = useState(true)

  // Add a notification
  const addNotification = useCallback((notification) => {
    const newNotification = {
      id: Date.now(),
      timestamp: new Date().toISOString(),
      read: false,
      ...notification
    }
    
    setNotifications(prev => [newNotification, ...prev].slice(0, 50)) // Keep last 50
    setUnreadCount(prev => prev + 1)
    
    // Show toast for important notifications
    if (notification.showToast !== false) {
      const toast = {
        id: newNotification.id,
        ...notification
      }
      setToasts(prev => [...prev, toast])
      
      // Auto-dismiss toast after 5 seconds
      setTimeout(() => {
        setToasts(prev => prev.filter(t => t.id !== toast.id))
      }, 5000)
    }
    
    return newNotification.id
  }, [])

  // Dismiss a toast
  const dismissToast = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  // Mark notification as read
  const markAsRead = useCallback((id) => {
    setNotifications(prev => 
      prev.map(n => n.id === id ? { ...n, read: true } : n)
    )
    setUnreadCount(prev => Math.max(0, prev - 1))
  }, [])

  // Mark all as read
  const markAllAsRead = useCallback(() => {
    setNotifications(prev => prev.map(n => ({ ...n, read: true })))
    setUnreadCount(0)
  }, [])

  // Clear all notifications
  const clearAll = useCallback(() => {
    setNotifications([])
    setUnreadCount(0)
  }, [])

  // Poll for processing milestones
  useEffect(() => {
    if (!isPolling) return

    const checkMilestones = async () => {
      try {
        const res = await fetch('/api/worker/progress')
        if (!res.ok) return
        
        const progress = await res.json()
        
        // Skip if no previous data to compare
        if (!lastProgress) {
          setLastProgress(progress)
          return
        }

        // Check for processing started
        if (!lastProgress.any_active && progress.any_active) {
          addNotification({
            type: 'info',
            title: 'Processing Started',
            message: 'Document processing has begun.',
            icon: 'play'
          })
        }

        // Check for processing completed
        if (lastProgress.any_active && !progress.any_active && progress.overall_progress === 100) {
          addNotification({
            type: 'success',
            title: 'Processing Complete',
            message: 'All documents have been processed.',
            icon: 'check-circle'
          })
        }

        // Check for milestone progress (25%, 50%, 75%)
        const milestones = [25, 50, 75]
        for (const milestone of milestones) {
          const wasBelow = (lastProgress.overall_progress || 0) < milestone
          const isAtOrAbove = (progress.overall_progress || 0) >= milestone
          if (wasBelow && isAtOrAbove && progress.any_active) {
            addNotification({
              type: 'info',
              title: `${milestone}% Complete`,
              message: `Processing is ${milestone}% complete.`,
              icon: 'trending-up',
              showToast: milestone === 50 // Only show toast at 50%
            })
          }
        }

        // Check for high error rate
        const totalErrors = Object.values(progress.phases || {}).reduce(
          (sum, p) => sum + (p.errors || 0), 0
        )
        const prevErrors = Object.values(lastProgress.phases || {}).reduce(
          (sum, p) => sum + (p.errors || 0), 0
        )
        
        if (totalErrors > prevErrors + 10) {
          addNotification({
            type: 'error',
            title: 'Errors Detected',
            message: `${totalErrors - prevErrors} new errors during processing.`,
            icon: 'alert-circle'
          })
        }

        setLastProgress(progress)
      } catch (err) {
        // Silently fail - don't spam notifications about polling errors
      }
    }

    // Poll every 10 seconds
    const interval = setInterval(checkMilestones, 10000)
    checkMilestones() // Initial check

    return () => clearInterval(interval)
  }, [isPolling, lastProgress, addNotification])

  const value = {
    notifications,
    unreadCount,
    toasts,
    addNotification,
    dismissToast,
    markAsRead,
    markAllAsRead,
    clearAll,
    setIsPolling
  }

  return (
    <NotificationContext.Provider value={value}>
      {children}
    </NotificationContext.Provider>
  )
}
