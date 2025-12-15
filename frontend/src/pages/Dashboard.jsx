import { useState, useEffect } from 'react'
import { Database, FileText, Layers, Cpu, HardDrive, Clock, AlertCircle, Play, Pause, Power, RefreshCw, CheckCircle, FilePlus, FileEdit, FileX } from 'lucide-react'
import { Link } from 'react-router-dom'
import styles from './Dashboard.module.css'

function Dashboard() {
  const [metrics, setMetrics] = useState(null)
  const [workerState, setWorkerState] = useState(null)
  const [pipelineProgress, setPipelineProgress] = useState(null)
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

  const fetchWorkerState = async () => {
    try {
      const res = await fetch('/api/worker/state')
      const data = await res.json()
      setWorkerState(data)
    } catch (err) {
      console.error(err)
    }
  }

  const fetchPipelineProgress = async () => {
    try {
      const res = await fetch('/api/worker/progress')
      const data = await res.json()
      setPipelineProgress(data)
    } catch (err) {
      console.error(err)
    }
  }

  const updateWorkerState = async (updates) => {
    try {
      const res = await fetch('/api/worker/state', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates)
      })
      const data = await res.json()
      setWorkerState(data)
    } catch (err) {
      console.error(err)
    }
  }

  const toggleProcess = (process) => {
    if (workerState) {
      updateWorkerState({ [process]: !workerState[process] })
    }
  }

  const toggleAllProcesses = () => {
    if (workerState) {
      updateWorkerState({ running: !workerState.running })
    }
  }

  useEffect(() => {
    fetchMetrics()
    fetchWorkerState()
    fetchPipelineProgress()
    const metricsInterval = setInterval(fetchMetrics, 2000)
    const stateInterval = setInterval(fetchWorkerState, 5000)
    const progressInterval = setInterval(fetchPipelineProgress, 1000)
    return () => {
      clearInterval(metricsInterval)
      clearInterval(stateInterval)
      clearInterval(progressInterval)
    }
  }, [])

  const formatBytes = (bytes) => {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
    return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB'
  }

  if (loading) return <div className={styles.loading}>Loading metrics...</div>

  const enrichedPct = ((metrics.entries.enriched / (metrics.entries.total || 1)) * 100).toFixed(1)
  const embeddedPct = ((metrics.entries.embedded / (metrics.entries.total || 1)) * 100).toFixed(1)

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1>System Dashboard</h1>
        {lastUpdate && (
          <span className={styles.lastUpdate}>
            <Clock size={14} /> Updated {lastUpdate.toLocaleTimeString()}
          </span>
        )}
      </div>

      {/* Worker Controls */}
      {workerState && (
        <div className={`${styles.section} ${styles.controlsSection}`}>
          <div className={styles.controlsHeader}>
            <h2>Pipeline Controls</h2>
            <button 
              className={`${styles.masterToggle} ${workerState.running ? styles.running : styles.paused}`}
              onClick={toggleAllProcesses}
            >
              {workerState.running ? <Pause size={18} /> : <Play size={18} />}
              {workerState.running ? 'Pause All' : 'Resume All'}
            </button>
          </div>
          <div className={styles.controlsGrid}>
            <button 
              className={`${styles.controlBtn} ${workerState.ingest ? styles.active : ''}`}
              onClick={() => toggleProcess('ingest')}
              disabled={!workerState.running}
            >
              <Power size={16} />
              <span>Ingest</span>
              <span className={styles.controlStatus}>{workerState.ingest ? 'ON' : 'OFF'}</span>
            </button>
            <button 
              className={`${styles.controlBtn} ${workerState.segment ? styles.active : ''}`}
              onClick={() => toggleProcess('segment')}
              disabled={!workerState.running}
            >
              <Power size={16} />
              <span>Segment</span>
              <span className={styles.controlStatus}>{workerState.segment ? 'ON' : 'OFF'}</span>
            </button>
            <button 
              className={`${styles.controlBtn} ${workerState.enrich ? styles.active : ''}`}
              onClick={() => toggleProcess('enrich')}
              disabled={!workerState.running}
            >
              <Power size={16} />
              <span>Enrich</span>
              <span className={styles.controlStatus}>{workerState.enrich ? 'ON' : 'OFF'}</span>
            </button>
            <button 
              className={`${styles.controlBtn} ${workerState.embed ? styles.active : ''}`}
              onClick={() => toggleProcess('embed')}
              disabled={!workerState.running}
            >
              <Power size={16} />
              <span>Embed</span>
              <span className={styles.controlStatus}>{workerState.embed ? 'ON' : 'OFF'}</span>
            </button>
          </div>
        </div>
      )}

      {/* Pipeline Progress */}
      {pipelineProgress && (
        <div className={`${styles.section} ${styles.progressSection}`}>
          <h2 className={styles.sectionTitle}>Pipeline Progress</h2>
          
          {/* Ingest Progress */}
          {pipelineProgress.ingest && pipelineProgress.ingest.phase !== 'idle' && (
            <div className={styles.phaseProgress}>
              <div className={styles.progressHeader}>
                <h3>
                  <RefreshCw size={16} className={pipelineProgress.ingest.phase !== 'complete' ? styles.spin : ''} />
                  Ingest: {pipelineProgress.ingest.phase}
                </h3>
                <span className={styles.progressPct}>{pipelineProgress.ingest.percent}%</span>
              </div>
              {pipelineProgress.ingest.total > 0 && (
                <div className={`${styles.progressBar} ${styles.large}`}>
                  <div 
                    className={styles.progressFill}
                    style={{ 
                      width: `${pipelineProgress.ingest.percent}%`, 
                      backgroundColor: pipelineProgress.ingest.phase === 'complete' ? '#42b883' : '#646cff' 
                    }}
                  ></div>
                </div>
              )}
              {pipelineProgress.ingest.current_file && (
                <div className={styles.progressDetails}>
                  <span className={styles.progressCurrent}>{pipelineProgress.ingest.current_file}</span>
                </div>
              )}
            </div>
          )}
          
          {/* Enrich Progress */}
          {pipelineProgress.enrich && pipelineProgress.enrich.total > 0 && (
            <div className={styles.phaseProgress}>
              <div className={styles.progressHeader}>
                <h3>
                  <Layers size={16} className={styles.spin} />
                  Enriching
                </h3>
                <span className={styles.progressPct}>{pipelineProgress.enrich.percent}%</span>
              </div>
              <div className={`${styles.progressBar} ${styles.large}`}>
                <div 
                  className={styles.progressFill}
                  style={{ width: `${pipelineProgress.enrich.percent}%`, backgroundColor: '#ffc517' }}
                ></div>
              </div>
              <div className={styles.progressDetails}>
                <span className={styles.progressCount}>
                  {pipelineProgress.enrich.current} / {pipelineProgress.enrich.total} entries
                </span>
                {pipelineProgress.enrich.current_entry && (
                  <span className={styles.progressCurrent}>{pipelineProgress.enrich.current_entry}</span>
                )}
              </div>
            </div>
          )}
          
          {/* Embed Progress */}
          {pipelineProgress.embed && pipelineProgress.embed.total > 0 && (
            <div className={styles.phaseProgress}>
              <div className={styles.progressHeader}>
                <h3>
                  <Cpu size={16} className={styles.spin} />
                  Embedding
                </h3>
                <span className={styles.progressPct}>{pipelineProgress.embed.percent}%</span>
              </div>
              <div className={`${styles.progressBar} ${styles.large}`}>
                <div 
                  className={styles.progressFill}
                  style={{ width: `${pipelineProgress.embed.percent}%`, backgroundColor: '#42b883' }}
                ></div>
              </div>
              <div className={styles.progressDetails}>
                <span className={styles.progressCount}>
                  {pipelineProgress.embed.current} / {pipelineProgress.embed.total} entries
                </span>
                {pipelineProgress.embed.current_entry && (
                  <span className={styles.progressCurrent}>{pipelineProgress.embed.current_entry}</span>
                )}
              </div>
            </div>
          )}
        </div>
      )}
      
      <div className={styles.metricsGrid}>
        <div className={styles.metricCard}>
          <div className={styles.metricIcon}><FileText color="#646cff" /></div>
          <div className={styles.metricContent}>
            <h3>Total Files</h3>
            <p className={styles.metricValue}>{metrics.files.total.toLocaleString()}</p>
            <p className={styles.metricSub}>Processed: {metrics.files.processed.toLocaleString()}</p>
          </div>
        </div>

        <div className={styles.metricCard}>
          <div className={styles.metricIcon}><HardDrive color="#888" /></div>
          <div className={styles.metricContent}>
            <h3>Storage</h3>
            <p className={styles.metricValue}>{formatBytes(metrics.storage.total_bytes)}</p>
          </div>
        </div>

        <div className={styles.metricCard}>
          <div className={styles.metricIcon}><Database color="#42b883" /></div>
          <div className={styles.metricContent}>
            <h3>Total Entries</h3>
            <p className={styles.metricValue}>{metrics.entries.total.toLocaleString()}</p>
            <p className={styles.metricSub}>Pending: {metrics.entries.pending.toLocaleString()}</p>
          </div>
        </div>

        {metrics.files.failed > 0 && (
          <div className={`${styles.metricCard} ${styles.error}`}>
            <div className={styles.metricIcon}><AlertCircle color="#ff6464" /></div>
            <div className={styles.metricContent}>
              <h3>Failed Files</h3>
              <p className={styles.metricValue}>{metrics.files.failed}</p>
            </div>
          </div>
        )}

        <div className={styles.metricCard}>
          <div className={styles.metricIcon}><Layers color="#ffc517" /></div>
          <div className={styles.metricContent}>
            <h3>Enriched</h3>
            <div className={styles.metricRow}>
              <p className={styles.metricValue}>{metrics.entries.enriched.toLocaleString()}</p>
              <span className={styles.metricPct}>{enrichedPct}%</span>
            </div>
            <div className={styles.progressBar}>
              <div 
                className={styles.progressFill}
                style={{ width: `${enrichedPct}%`, backgroundColor: '#ffc517' }}
              ></div>
            </div>
            <p className={styles.metricSub}>AI Analysis</p>
          </div>
        </div>

        <div className={styles.metricCard}>
          <div className={styles.metricIcon}><Cpu color="#ff6464" /></div>
          <div className={styles.metricContent}>
            <h3>Embedded</h3>
            <div className={styles.metricRow}>
              <p className={styles.metricValue}>{metrics.entries.embedded.toLocaleString()}</p>
              <span className={styles.metricPct}>{embeddedPct}%</span>
            </div>
            <div className={styles.progressBar}>
              <div 
                className={styles.progressFill}
                style={{ width: `${embeddedPct}%`, backgroundColor: '#ff6464' }}
              ></div>
            </div>
            <p className={styles.metricSub}>Vector Index</p>
          </div>
        </div>
      </div>

      {metrics.extensions && metrics.extensions.length > 0 && (
        <div className={styles.section}>
          <h2>File Types</h2>
          <div className={styles.extGrid}>
            {metrics.extensions.map(ext => (
              <div key={ext.ext} className={styles.extChip}>
                <span className={styles.extName}>{ext.ext}</span>
                <span className={styles.extCount}>{ext.count.toLocaleString()}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {metrics.recent_files && metrics.recent_files.length > 0 && (
        <div className={styles.section}>
          <h2>Recently Ingested</h2>
          <div className={styles.recentList}>
            {metrics.recent_files.map(file => (
              <Link to={`/document/${file.id}`} key={file.id} className={styles.recentItem}>
                <FileText size={16} />
                <span className={styles.recentFilename}>{file.filename}</span>
                <span className={`${styles.recentStatus} ${file.status === 'ok' ? styles.ok : styles.extractFailed}`}>{file.status}</span>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default Dashboard
