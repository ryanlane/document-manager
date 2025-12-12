import { useState, useEffect } from 'react'
import { Activity, Database, FileText, Layers, Cpu } from 'lucide-react'

function Dashboard() {
  const [metrics, setMetrics] = useState(null)
  const [loading, setLoading] = useState(true)

  const fetchMetrics = async () => {
    try {
      const res = await fetch('/api/system/metrics')
      const data = await res.json()
      setMetrics(data)
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

  if (loading) return <div className="container">Loading metrics...</div>

  return (
    <div className="container dashboard">
      <h1>System Dashboard</h1>
      
      <div className="metrics-grid">
        <div className="metric-card">
          <div className="metric-icon"><FileText color="#646cff" /></div>
          <div className="metric-content">
            <h3>Total Files</h3>
            <p className="metric-value">{metrics.files.total}</p>
            <p className="metric-sub">Processed: {metrics.files.processed}</p>
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-icon"><Database color="#42b883" /></div>
          <div className="metric-content">
            <h3>Total Entries</h3>
            <p className="metric-value">{metrics.entries.total}</p>
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-icon"><Layers color="#ffc517" /></div>
          <div className="metric-content">
            <h3>Enriched</h3>
            <p className="metric-value">{metrics.entries.enriched}</p>
            <div className="progress-bar">
              <div 
                className="progress-fill" 
                style={{ width: `${(metrics.entries.enriched / (metrics.entries.total || 1)) * 100}%`, backgroundColor: '#ffc517' }}
              ></div>
            </div>
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-icon"><Cpu color="#ff6464" /></div>
          <div className="metric-content">
            <h3>Embedded</h3>
            <p className="metric-value">{metrics.entries.embedded}</p>
            <div className="progress-bar">
              <div 
                className="progress-fill" 
                style={{ width: `${(metrics.entries.embedded / (metrics.entries.total || 1)) * 100}%`, backgroundColor: '#ff6464' }}
              ></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Dashboard
