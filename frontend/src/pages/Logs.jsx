import { useState, useEffect, useRef } from 'react'
import { ArrowLeft, RefreshCw } from 'lucide-react'
import { Link } from 'react-router-dom'
import styles from './Logs.module.css'

function Logs() {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const logsEndRef = useRef(null)

  const fetchLogs = async () => {
    try {
      const res = await fetch('/api/worker/logs?lines=200')
      const data = await res.json()
      setLogs(data.lines || [])
      setLoading(false)
    } catch (err) {
      console.error(err)
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchLogs()
    let interval
    if (autoRefresh) {
      interval = setInterval(fetchLogs, 3000)
    }
    return () => interval && clearInterval(interval)
  }, [autoRefresh])

  useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logs])

  const getLogClass = (line) => {
    if (line.includes('ERROR')) return styles.logError
    if (line.includes('WARNING')) return styles.logWarning
    if (line.includes('Starting')) return styles.logInfo
    return ''
  }

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div className={styles.title}>
          <Link to="/dashboard" className={styles.backBtn}>
            <ArrowLeft size={20} />
          </Link>
          <h1>Worker Logs</h1>
        </div>
        <div className={styles.controls}>
          <label className={styles.autoRefresh}>
            <input 
              type="checkbox" 
              checked={autoRefresh} 
              onChange={(e) => setAutoRefresh(e.target.checked)} 
            />
            Auto-refresh
          </label>
          <button onClick={fetchLogs} className={styles.refreshBtn}>
            <RefreshCw size={16} /> Refresh
          </button>
        </div>
      </div>

      {loading ? (
        <div className={styles.loading}>Loading logs...</div>
      ) : logs.length === 0 ? (
        <div className={styles.noLogs}>
          No logs available. The worker may need to be restarted to enable logging.
        </div>
      ) : (
        <div className={styles.container}>
          <pre className={styles.content}>
            {logs.map((line, i) => (
              <div key={i} className={`${styles.logLine} ${getLogClass(line)}`}>
                {line}
              </div>
            ))}
            <div ref={logsEndRef} />
          </pre>
        </div>
      )}
    </div>
  )
}

export default Logs
