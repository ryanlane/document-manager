import { useState, useEffect, useRef } from 'react'
import { ArrowLeft, RefreshCw } from 'lucide-react'
import { Link } from 'react-router-dom'

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
    if (line.includes('ERROR')) return 'log-error'
    if (line.includes('WARNING')) return 'log-warning'
    if (line.includes('Starting')) return 'log-info'
    return ''
  }

  return (
    <div className="container logs-page">
      <div className="logs-header">
        <div className="logs-title">
          <Link to="/dashboard" className="back-btn">
            <ArrowLeft size={20} />
          </Link>
          <h1>Worker Logs</h1>
        </div>
        <div className="logs-controls">
          <label className="auto-refresh-toggle">
            <input 
              type="checkbox" 
              checked={autoRefresh} 
              onChange={(e) => setAutoRefresh(e.target.checked)} 
            />
            Auto-refresh
          </label>
          <button onClick={fetchLogs} className="refresh-btn">
            <RefreshCw size={16} /> Refresh
          </button>
        </div>
      </div>

      {loading ? (
        <div>Loading logs...</div>
      ) : logs.length === 0 ? (
        <div className="no-logs">
          No logs available. The worker may need to be restarted to enable logging.
        </div>
      ) : (
        <div className="logs-container">
          <pre className="logs-content">
            {logs.map((line, i) => (
              <div key={i} className={`log-line ${getLogClass(line)}`}>
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
