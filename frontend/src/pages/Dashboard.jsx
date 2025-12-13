import { useState, useEffect } from 'react'
import { Database, FileText, Layers, Cpu, HardDrive, Clock, AlertCircle } from 'lucide-react'
import { Link } from 'react-router-dom'

function Dashboard() {
  const [metrics, setMetrics] = useState(null)
  const [loading, setLoading] = useState(true)
  const [lastUpdate, setLastUpdate] = useState(null)

  const fetchMetrics = async () => {
    try {
      const res = await fetch('/api/system/metrics')
      const data = await res.json()
      setMetrics(data)
      setLastUpdate(new Date())
      setLoading(false)
    } catch (err) {
      console.error(err)
    }
  }

  useEffect(() => {
    fetchMetrics()
    const interval = setInterval(fetchMetrics, 2000) // Poll every 2 seconds
    return () => clearInterval(interval)
  }, [])

  const formatBytes = (bytes) => {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
    return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB'
  }

  if (loading) return <div className="container">Loading metrics...</div>

  const enrichedPct = ((metrics.entries.enriched / (metrics.entries.total || 1)) * 100).toFixed(1)
  const embeddedPct = ((metrics.entries.embedded / (metrics.entries.total || 1)) * 100).toFixed(1)

  return (
    <div className="container dashboard">
      <div className="dashboard-header">
        <h1>System Dashboard</h1>
        {lastUpdate && (
          <span className="last-update">
            <Clock size={14} /> Updated {lastUpdate.toLocaleTimeString()}
          </span>
        )}
      </div>
      
      <div className="metrics-grid">
        <div className="metric-card">
          <div className="metric-icon"><FileText color="#646cff" /></div>
          <div className="metric-content">
            <h3>Total Files</h3>
            <p className="metric-value">{metrics.files.total.toLocaleString()}</p>
            <p className="metric-sub">Processed: {metrics.files.processed.toLocaleString()}</p>
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-icon"><HardDrive color="#888" /></div>
          <div className="metric-content">
            <h3>Storage</h3>
            <p className="metric-value">{formatBytes(metrics.storage.total_bytes)}</p>
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-icon"><Database color="#42b883" /></div>
          <div className="metric-content">
            <h3>Total Entries</h3>
            <p className="metric-value">{metrics.entries.total.toLocaleString()}</p>
            <p className="metric-sub">Pending: {metrics.entries.pending.toLocaleString()}</p>
          </div>
        </div>

        {metrics.files.failed > 0 && (
          <div className="metric-card error-card">
            <div className="metric-icon"><AlertCircle color="#ff6464" /></div>
            <div className="metric-content">
              <h3>Failed Files</h3>
              <p className="metric-value">{metrics.files.failed}</p>
            </div>
          </div>
        )}

        <div className="metric-card wide-card">
          <div className="metric-icon"><Layers color="#ffc517" /></div>
          <div className="metric-content">
            <h3>Enriched</h3>
            <div className="metric-row">
              <p className="metric-value">{metrics.entries.enriched.toLocaleString()}</p>
              <span className="metric-pct">{enrichedPct}%</span>
            </div>
            <div className="progress-bar">
              <div 
                className="progress-fill" 
                style={{ width: `${enrichedPct}%`, backgroundColor: '#ffc517' }}
              ></div>
            </div>
          </div>
        </div>

        <div className="metric-card wide-card">
          <div className="metric-icon"><Cpu color="#ff6464" /></div>
          <div className="metric-content">
            <h3>Embedded</h3>
            <div className="metric-row">
              <p className="metric-value">{metrics.entries.embedded.toLocaleString()}</p>
              <span className="metric-pct">{embeddedPct}%</span>
            </div>
            <div className="progress-bar">
              <div 
                className="progress-fill" 
                style={{ width: `${embeddedPct}%`, backgroundColor: '#ff6464' }}
              ></div>
            </div>
          </div>
        </div>
      </div>

      {metrics.extensions && metrics.extensions.length > 0 && (
        <div className="dashboard-section">
          <h2>File Types</h2>
          <div className="ext-grid">
            {metrics.extensions.map(ext => (
              <div key={ext.ext} className="ext-chip">
                <span className="ext-name">{ext.ext}</span>
                <span className="ext-count">{ext.count.toLocaleString()}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {metrics.recent_files && metrics.recent_files.length > 0 && (
        <div className="dashboard-section">
          <h2>Recently Ingested</h2>
          <div className="recent-list">
            {metrics.recent_files.map(file => (
              <Link to={`/document/${file.id}`} key={file.id} className="recent-item">
                <FileText size={16} />
                <span className="recent-filename">{file.filename}</span>
                <span className={`recent-status ${file.status}`}>{file.status}</span>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default Dashboard
