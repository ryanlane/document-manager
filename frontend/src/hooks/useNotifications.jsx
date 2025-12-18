import { useState, useEffect, useCallback, createContext, useContext, useRef } from 'react'

// Notification context for app-wide access
const NotificationContext = createContext(null)

// Counter for unique IDs
let notificationIdCounter = 0

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
  const [isPolling, setIsPolling] = useState(true)
  const [isVisible, setIsVisible] = useState(!document.hidden)
  
  // Use refs for values that shouldn't trigger effect re-runs
  const lastProgressRef = useRef(null)
  const shownNotificationsRef = useRef(new Set())
  const toastTimeoutsRef = useRef(new Map())
  
  // Track page visibility to pause polling when tab is hidden
  useEffect(() => {
    const handleVisibility = () => setIsVisible(!document.hidden)
    document.addEventListener('visibilitychange', handleVisibility)
    return () => document.removeEventListener('visibilitychange', handleVisibility)
  }, [])

  // Add a notification
  const addNotification = useCallback((notification) => {
    // Generate unique ID using timestamp + counter
    const uniqueId = `${Date.now()}-${++notificationIdCounter}`
    
    const newNotification = {
      id: uniqueId,
      timestamp: new Date().toISOString(),
      read: false,
      ...notification
    }
    
    setNotifications(prev => [newNotification, ...prev].slice(0, 50)) // Keep last 50
    setUnreadCount(prev => prev + 1)
    
    // Show toast for important notifications
    if (notification.showToast !== false) {
      const toast = {
        id: uniqueId,
        ...notification
      }
      setToasts(prev => [...prev, toast])
      
      // Auto-dismiss toast after 5 seconds - track timeout for cleanup
      const timeoutId = setTimeout(() => {
        setToasts(prev => prev.filter(t => t.id !== toast.id))
        toastTimeoutsRef.current.delete(uniqueId)
      }, 5000)
      toastTimeoutsRef.current.set(uniqueId, timeoutId)
    }
    
    return uniqueId
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
    if (!isPolling || !isVisible) return
    
    const shownNotifications = shownNotificationsRef.current

    const checkMilestones = async () => {
      try {
        const res = await fetch('/api/worker/progress')
        if (!res.ok) return
        
        const progress = await res.json()
        const lastProgress = lastProgressRef.current
        
        // Skip if no previous data to compare
        if (!lastProgress) {
          lastProgressRef.current = progress
          return
        }

        // Check for processing started (only once per session)
        if (!lastProgress.any_active && progress.any_active) {
          const key = `started-${Date.now()}`
          if (!shownNotifications.has('processing-started')) {
            shownNotifications.add('processing-started')
            addNotification({
              type: 'info',
              title: 'Processing Started',
              message: 'Document processing has begun.',
              icon: 'play'
            })
          }
        }

        // Reset the "started" flag when processing stops, so next start can show again
        if (lastProgress.any_active && !progress.any_active) {
          shownNotifications.delete('processing-started')
        }

        // Check for processing completed (only once per completion)
        if (lastProgress.any_active && !progress.any_active && progress.overall_progress === 100) {
          const completionKey = 'completed'
          if (!shownNotifications.has(completionKey)) {
            shownNotifications.add(completionKey)
            addNotification({
              type: 'success',
              title: 'Processing Complete',
              message: 'All documents have been processed.',
              icon: 'check-circle'
            })
            // Reset completion flag after some time so it can trigger again on new processing
            setTimeout(() => shownNotifications.delete(completionKey), 60000)
          }
        }

        // Check for milestone progress (25%, 50%, 75%) - only once per milestone
        const milestones = [25, 50, 75]
        for (const milestone of milestones) {
          const milestoneKey = `milestone-${milestone}`
          const wasBelow = (lastProgress.overall_progress || 0) < milestone
          const isAtOrAbove = (progress.overall_progress || 0) >= milestone
          
          if (wasBelow && isAtOrAbove && progress.any_active && !shownNotifications.has(milestoneKey)) {
            shownNotifications.add(milestoneKey)
            addNotification({
              type: 'info',
              title: `${milestone}% Complete`,
              message: `Processing is ${milestone}% complete.`,
              icon: 'trending-up',
              showToast: milestone === 50 // Only show toast at 50%
            })
          }
        }
        
        // Reset milestone flags when progress goes back to 0 (new processing run)
        if (progress.overall_progress < 10 && (lastProgress.overall_progress || 0) >= 10) {
          milestones.forEach(m => shownNotifications.delete(`milestone-${m}`))
          shownNotifications.delete('completed')
        }

        // Check for high error rate (throttled - only once per 10 errors)
        const totalErrors = Object.values(progress.phases || {}).reduce(
          (sum, p) => sum + (p.errors || 0), 0
        )
        const prevErrors = Object.values(lastProgress.phases || {}).reduce(
          (sum, p) => sum + (p.errors || 0), 0
        )
        
        const errorThreshold = Math.floor(totalErrors / 10) * 10
        const errorKey = `errors-${errorThreshold}`
        if (totalErrors > prevErrors + 10 && !shownNotifications.has(errorKey)) {
          shownNotifications.add(errorKey)
          addNotification({
            type: 'error',
            title: 'Errors Detected',
            message: `${totalErrors - prevErrors} new errors during processing.`,
            icon: 'alert-circle'
          })
        }

        lastProgressRef.current = progress
      } catch (err) {
        // Silently fail - don't spam notifications about polling errors
      }
    }

    // Poll every 10 seconds
    const interval = setInterval(checkMilestones, 10000)
    checkMilestones() // Initial check

    return () => {
      clearInterval(interval)
      // Clean up any pending toast timeouts
      toastTimeoutsRef.current.forEach(timeoutId => clearTimeout(timeoutId))
      toastTimeoutsRef.current.clear()
    }
  }, [isPolling, isVisible, addNotification])

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
