import { useState, useEffect, useCallback, createContext, useContext, useRef } from 'react'

const ConnectionContext = createContext(null)

export function useConnectionStatus() {
  const context = useContext(ConnectionContext)
  if (!context) {
    throw new Error('useConnectionStatus must be used within ConnectionProvider')
  }
  return context
}

export function ConnectionProvider({ children }) {
  const [isConnected, setIsConnected] = useState(true)
  const [lastCheck, setLastCheck] = useState(null)
  const [consecutiveFailures, setConsecutiveFailures] = useState(0)
  const retryTimeoutRef = useRef(null)

  const checkConnection = useCallback(async () => {
    try {
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 5000) // 5 second timeout
      
      const res = await fetch('/api/system/status', {
        signal: controller.signal
      })
      clearTimeout(timeoutId)
      
      if (res.ok) {
        setIsConnected(true)
        setConsecutiveFailures(0)
        setLastCheck(new Date())
        return true
      } else {
        throw new Error('Bad response')
      }
    } catch (err) {
      setIsConnected(false)
      setConsecutiveFailures(prev => prev + 1)
      setLastCheck(new Date())
      return false
    }
  }, [])

  const retry = useCallback(async () => {
    // Clear any pending retry
    if (retryTimeoutRef.current) {
      clearTimeout(retryTimeoutRef.current)
      retryTimeoutRef.current = null
    }
    return checkConnection()
  }, [checkConnection])

  // Initial check and periodic health check
  useEffect(() => {
    checkConnection()

    // Check connection every 30 seconds
    const interval = setInterval(checkConnection, 30000)

    return () => {
      clearInterval(interval)
      if (retryTimeoutRef.current) {
        clearTimeout(retryTimeoutRef.current)
      }
    }
  }, [checkConnection])

  // Auto-retry with exponential backoff when disconnected
  useEffect(() => {
    if (!isConnected && consecutiveFailures > 0) {
      // Exponential backoff: 2s, 4s, 8s, 16s, max 30s
      const delay = Math.min(2000 * Math.pow(2, consecutiveFailures - 1), 30000)
      
      retryTimeoutRef.current = setTimeout(() => {
        checkConnection()
      }, delay)

      return () => {
        if (retryTimeoutRef.current) {
          clearTimeout(retryTimeoutRef.current)
        }
      }
    }
  }, [isConnected, consecutiveFailures, checkConnection])

  const value = {
    isConnected,
    lastCheck,
    consecutiveFailures,
    retry,
    checkConnection
  }

  return (
    <ConnectionContext.Provider value={value}>
      {children}
    </ConnectionContext.Provider>
  )
}
