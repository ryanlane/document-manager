import { useState, useEffect, useCallback } from 'react'
import { 
  Database, FileText, Layers, Cpu, HardDrive, Clock, AlertCircle, 
  Play, Pause, Power, RefreshCw, FilePlus, Binary, Sparkles, Search,
  ArrowRight, FileCheck, Loader2
} from 'lucide-react'
import { Link } from 'react-router-dom'
import styles from './Dashboard.module.css'

// Skeleton loader component
const Skeleton = ({ width = '100%', height = '1rem', style = {} }) => (
  <div 
    className={styles.skeleton} 
    style={{ width, height, ...style }}
  />
)

// Stat card with lazy loading
const StatCard = ({ icon: Icon, color, title, value, sub, loading }) => (
  <div className={styles.statCard}>
    <div className={styles.statIcon}><Icon color={color} size={24} /></div>
    <div className={styles.statContent}>
      <span className={styles.statTitle}>{title}</span>
      {loading ? (
        <Skeleton height="2rem" width="80%" />
      ) : (
        <span className={styles.statValue}>{value?.toLocaleString() ?? '-'}</span>
      )}
      {sub && <span className={styles.statSub}>{sub}</span>}
    </div>
  </div>
)

// Progress bar component
const ProgressBar = ({ percent, color, label, sublabel, loading, active }) => (
  <div className={styles.progressItem}>
    <div className={styles.progressLabel}>
      <span className={styles.progressTitle}>
        {active && <Loader2 size={14} className={styles.spin} />}
        {label}
      </span>
      {loading ? (
        <Skeleton width="3rem" height="1rem" />
      ) : (
        <span className={styles.progressPct}>{percent?.toFixed(1) ?? 0}%</span>
      )}
    </div>
    <div className={styles.progressTrack}>
      <div 
        className={styles.progressFill}
        style={{ width: `${percent ?? 0}%`, backgroundColor: color }}
      />
    </div>
    {sublabel && <span className={styles.progressSub}>{sublabel}</span>}
  </div>
)

function Dashboard() {
  // Core counts - loads first
  const [counts, setCounts] = useState(null)
  const [docCounts, setDocCounts] = useState(null)
  const [workerState, setWorkerState] = useState(null)
  
  // Secondary data - loads after
  const [storage, setStorage] = useState(null)
  const [extensions, setExtensions] = useState(null)
  const [recentFiles, setRecentFiles] = useState(null)
  
  const [lastUpdate, setLastUpdate] = useState(null)

  // Fast initial loads
  const fetchCounts = useCallback(async () => {
    try {
      const res = await fetch('/api/system/counts')
      const data = await res.json()
      setCounts(data)
      setLastUpdate(new Date())
    } catch (err) { console.error('counts:', err) }
  }, [])

  const fetchDocCounts = useCallback(async () => {
    try {
      const res = await fetch('/api/system/doc-counts')
      const data = await res.json()
      setDocCounts(data)
    } catch (err) { console.error('doc-counts:', err) }
  }, [])

  const fetchWorkerState = useCallback(async () => {
    try {
      const res = await fetch('/api/worker/state')
      const data = await res.json()
      setWorkerState(data)
    } catch (err) { console.error('worker state:', err) }
  }, [])

  // Lazy secondary loads
  const fetchStorage = useCallback(async () => {
    try {
      const res = await fetch('/api/system/storage')
      const data = await res.json()
      setStorage(data)
    } catch (err) { console.error('storage:', err) }
  }, [])

  const fetchExtensions = useCallback(async () => {
    try {
      const res = await fetch('/api/system/extensions')
      const data = await res.json()
      setExtensions(data)
    } catch (err) { console.error('extensions:', err) }
  }, [])

  const fetchRecent = useCallback(async () => {
    try {
      const res = await fetch('/api/system/recent?limit=5')
      const data = await res.json()
      setRecentFiles(data)
    } catch (err) { console.error('recent:', err) }
  }, [])

  const updateWorkerState = async (updates) => {
    try {
      const res = await fetch('/api/worker/state', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates)
      })
      const data = await res.json()
      setWorkerState(data)
    } catch (err) { console.error('update state:', err) }
  }

  const toggleProcess = (process) => {
    if (workerState) {
      updateWorkerState({ [process]: !workerState[process] })
    }
  }

  // Initial load - fast endpoints first
  useEffect(() => {
    // Load critical data immediately
    fetchCounts()
    fetchDocCounts()
    fetchWorkerState()
    
    // Load secondary data with slight delay
    const secondaryTimer = setTimeout(() => {
      fetchStorage()
      fetchExtensions()
      fetchRecent()
    }, 100)

    // Set up polling intervals
    const countsInterval = setInterval(fetchCounts, 3000)
    const docCountsInterval = setInterval(fetchDocCounts, 3000)
    const stateInterval = setInterval(fetchWorkerState, 5000)
    const storageInterval = setInterval(fetchStorage, 30000)
    
    return () => {
      clearTimeout(secondaryTimer)
      clearInterval(countsInterval)
      clearInterval(docCountsInterval)
      clearInterval(stateInterval)
      clearInterval(storageInterval)
    }
  }, [fetchCounts, fetchDocCounts, fetchWorkerState, fetchStorage, fetchExtensions, fetchRecent])

  const formatBytes = (bytes) => {
    if (!bytes) return '0 B'
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
    return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB'
  }

  // Calculate percentages
  const docEnrichPct = docCounts ? ((docCounts.enriched) / (docCounts.total || 1)) * 100 : 0
  const docEmbedPct = docCounts ? (docCounts.embedded / (docCounts.total || 1)) * 100 : 0
  const chunkEnrichPct = counts ? (counts.entries.enriched / (counts.entries.total || 1)) * 100 : 0
  const chunkEmbedPct = counts ? (counts.entries.embedded / (counts.entries.total || 1)) * 100 : 0

  return (
    <div className={styles.page}>
      {/* Header */}
      <div className={styles.header}>
        <h1>Dashboard</h1>
        {lastUpdate && (
          <span className={styles.lastUpdate}>
            <Clock size={14} /> {lastUpdate.toLocaleTimeString()}
          </span>
        )}
      </div>

      {/* Worker Controls - Compact */}
      <div className={styles.controlBar}>
        <button 
          className={`${styles.masterBtn} ${workerState?.running ? styles.running : styles.paused}`}
          onClick={() => updateWorkerState({ running: !workerState?.running })}
        >
          {workerState?.running ? <Pause size={16} /> : <Play size={16} />}
          {workerState?.running ? 'Running' : 'Paused'}
        </button>
        
        <div className={styles.toggleGroup}>
          <button 
            className={`${styles.toggleBtn} ${workerState?.ingest ? styles.on : ''}`}
            onClick={() => toggleProcess('ingest')}
            disabled={!workerState?.running}
            title="Ingest new files"
          >
            <FilePlus size={14} /> Ingest
          </button>
          <button 
            className={`${styles.toggleBtn} ${workerState?.enrich_docs ? styles.on : ''}`}
            onClick={() => toggleProcess('enrich_docs')}
            disabled={!workerState?.running}
            title="Enrich documents"
          >
            <Sparkles size={14} /> Docs
          </button>
          <button 
            className={`${styles.toggleBtn} ${workerState?.embed_docs ? styles.on : ''}`}
            onClick={() => toggleProcess('embed_docs')}
            disabled={!workerState?.running}
            title="Embed documents"
          >
            <Binary size={14} /> Doc Embed
          </button>
          <button 
            className={`${styles.toggleBtn} ${workerState?.enrich ? styles.on : ''}`}
            onClick={() => toggleProcess('enrich')}
            disabled={!workerState?.running}
            title="Enrich chunks"
          >
            <Layers size={14} /> Chunks
          </button>
          <button 
            className={`${styles.toggleBtn} ${workerState?.embed ? styles.on : ''}`}
            onClick={() => toggleProcess('embed')}
            disabled={!workerState?.running}
            title="Embed chunks"
          >
            <Cpu size={14} /> Chunk Embed
          </button>
        </div>
      </div>

      {/* Two-Stage Pipeline Progress */}
      <div className={styles.pipelineGrid}>
        {/* Doc-Level (Stage 1) */}
        <div className={styles.pipelineCard}>
          <div className={styles.pipelineHeader}>
            <h2><FileCheck size={18} /> Doc-Level</h2>
            <span className={styles.pipelineTag}>Stage 1: Coarse Search</span>
          </div>
          <div className={styles.statsRow}>
            <StatCard 
              icon={FileText} 
              color="#646cff" 
              title="Documents" 
              value={docCounts?.total}
              loading={!docCounts}
            />
            <StatCard 
              icon={Sparkles} 
              color="#a855f7" 
              title="Enriched" 
              value={docCounts?.enriched}
              loading={!docCounts}
            />
            <StatCard 
              icon={Search} 
              color="#06b6d4" 
              title="Searchable" 
              value={docCounts?.embedded}
              loading={!docCounts}
            />
          </div>
          <div className={styles.progressStack}>
            <ProgressBar 
              percent={docEnrichPct} 
              color="#a855f7" 
              label="Doc Enrichment" 
              sublabel={docCounts ? `${docCounts.enriched?.toLocaleString()} / ${docCounts.total?.toLocaleString()}` : null}
              loading={!docCounts}
              active={workerState?.enrich_docs}
            />
            <ProgressBar 
              percent={docEmbedPct} 
              color="#06b6d4" 
              label="Doc Embedding" 
              sublabel={docCounts ? `${docCounts.embedded?.toLocaleString()} / ${docCounts.total?.toLocaleString()}` : null}
              loading={!docCounts}
              active={workerState?.embed_docs}
            />
          </div>
          {docCounts?.error > 0 && (
            <div className={styles.errorBadge}>
              <AlertCircle size={14} /> {docCounts.error} errors
            </div>
          )}
        </div>

        {/* Chunk-Level (Stage 2) */}
        <div className={styles.pipelineCard}>
          <div className={styles.pipelineHeader}>
            <h2><Layers size={18} /> Chunk-Level</h2>
            <span className={styles.pipelineTag}>Stage 2: Fine Search</span>
          </div>
          <div className={styles.statsRow}>
            <StatCard 
              icon={Database} 
              color="#42b883" 
              title="Chunks" 
              value={counts?.entries.total}
              loading={!counts}
            />
            <StatCard 
              icon={Sparkles} 
              color="#ffc517" 
              title="Enriched" 
              value={counts?.entries.enriched}
              loading={!counts}
            />
            <StatCard 
              icon={Cpu} 
              color="#ff6464" 
              title="Embedded" 
              value={counts?.entries.embedded}
              loading={!counts}
            />
          </div>
          <div className={styles.progressStack}>
            <ProgressBar 
              percent={chunkEnrichPct} 
              color="#ffc517" 
              label="Chunk Enrichment" 
              sublabel={counts ? `${counts.entries.enriched?.toLocaleString()} / ${counts.entries.total?.toLocaleString()}` : null}
              loading={!counts}
              active={workerState?.enrich}
            />
            <ProgressBar 
              percent={chunkEmbedPct} 
              color="#ff6464" 
              label="Chunk Embedding" 
              sublabel={counts ? `${counts.entries.embedded?.toLocaleString()} / ${counts.entries.total?.toLocaleString()}` : null}
              loading={!counts}
              active={workerState?.embed}
            />
          </div>
        </div>
      </div>

      {/* Secondary Stats Row */}
      <div className={styles.secondaryRow}>
        <div className={styles.miniCard}>
          <HardDrive size={18} color="#888" />
          <div>
            <span className={styles.miniLabel}>Storage</span>
            {storage ? (
              <span className={styles.miniValue}>{formatBytes(storage.total_bytes)}</span>
            ) : (
              <Skeleton width="4rem" height="1.2rem" />
            )}
          </div>
        </div>
        
        <div className={styles.miniCard}>
          <FileText size={18} color="#646cff" />
          <div>
            <span className={styles.miniLabel}>Files</span>
            {counts ? (
              <span className={styles.miniValue}>
                {counts.files.processed?.toLocaleString()} / {counts.files.total?.toLocaleString()}
              </span>
            ) : (
              <Skeleton width="5rem" height="1.2rem" />
            )}
          </div>
        </div>

        {extensions && extensions.length > 0 && (
          <div className={styles.extPills}>
            {extensions.slice(0, 6).map(ext => (
              <span key={ext.ext} className={styles.extPill}>
                {ext.ext} <strong>{ext.count.toLocaleString()}</strong>
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Recent Files - Lazy loaded */}
      {recentFiles && recentFiles.length > 0 && (
        <div className={styles.recentSection}>
          <h3>Recent Files</h3>
          <div className={styles.recentList}>
            {recentFiles.map(file => (
              <Link to={`/document/${file.id}`} key={file.id} className={styles.recentItem}>
                <FileText size={14} />
                <span className={styles.recentName}>{file.filename}</span>
                <span className={`${styles.recentStatus} ${styles[file.status]}`}>
                  {file.status}
                </span>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default Dashboard
