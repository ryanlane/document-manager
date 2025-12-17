import { useState, useEffect, useCallback } from 'react'
import { 
  Database, FileText, Layers, Cpu, HardDrive, Clock, AlertCircle, 
  Play, Pause, Power, RefreshCw, FilePlus, Binary, Sparkles, Search,
  ArrowRight, FileCheck, Loader2, Zap, Box, Download, ArrowDown
} from 'lucide-react'
import { Link } from 'react-router-dom'
import styles from './Dashboard.module.css'

// Track which toggles are pending
const usePendingToggles = () => {
  const [pending, setPending] = useState({})
  
  const setPending_ = (key, value) => {
    setPending(prev => ({ ...prev, [key]: value }))
  }
  
  return [pending, setPending_]
}

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

// Progress bar component with optional ETA
const ProgressBar = ({ percent, color, label, sublabel, loading, active, eta }) => (
  <div className={styles.progressItem}>
    <div className={styles.progressLabel}>
      <span className={styles.progressTitle}>
        {active && <Loader2 size={14} className={styles.spin} />}
        {label}
      </span>
      <div className={styles.progressRight}>
        {eta && eta.eta_string && eta.eta_string !== 'Complete' && (
          <span className={styles.etaTag} title={`Rate: ${eta.rate_per_min || 0}/min`}>
            <Clock size={10} /> {eta.eta_string}
          </span>
        )}
        {loading ? (
          <Skeleton width="3rem" height="1rem" />
        ) : (
          <span className={styles.progressPct}>{percent?.toFixed(1) ?? 0}%</span>
        )}
      </div>
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
  const [pendingToggles, setPendingToggle] = usePendingToggles()
  const [systemStatus, setSystemStatus] = useState(null)
  const [workerStats, setWorkerStats] = useState(null)
  
  // Secondary data - loads after
  const [storage, setStorage] = useState(null)
  const [extensions, setExtensions] = useState(null)
  const [recentFiles, setRecentFiles] = useState(null)
  
  // Inheritance state
  const [inheritanceStats, setInheritanceStats] = useState(null)
  const [inheritanceRunning, setInheritanceRunning] = useState(false)
  const [inheritanceProgress, setInheritanceProgress] = useState({ total: 0, batches: 0 })
  
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

  const fetchSystemStatus = useCallback(async () => {
    try {
      const res = await fetch('/api/system/status')
      const data = await res.json()
      setSystemStatus(data)
    } catch (err) { console.error('system status:', err) }
  }, [])

  const fetchWorkerStats = useCallback(async () => {
    try {
      const res = await fetch('/api/worker/stats')
      const data = await res.json()
      setWorkerStats(data)
    } catch (err) { console.error('worker stats:', err) }
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

  const fetchInheritanceStats = useCallback(async () => {
    try {
      const res = await fetch('/api/config/inheritance-stats')
      const data = await res.json()
      setInheritanceStats(data)
    } catch (err) { console.error('inheritance stats:', err) }
  }, [])

  const runInheritance = async () => {
    if (inheritanceRunning) return
    
    setInheritanceRunning(true)
    setInheritanceProgress({ total: 0, batches: 0 })
    
    let totalInherited = 0
    let batches = 0
    
    while (true) {
      try {
        const res = await fetch('/api/config/inherit-metadata?batch_size=5000', { method: 'POST' })
        const data = await res.json()
        const count = data.inherited || 0
        
        if (count === 0) break
        
        totalInherited += count
        batches++
        setInheritanceProgress({ total: totalInherited, batches })
        
        // Refresh stats periodically
        if (batches % 5 === 0) {
          fetchInheritanceStats()
        }
      } catch (err) {
        console.error('inheritance error:', err)
        break
      }
    }
    
    setInheritanceRunning(false)
    fetchInheritanceStats()
    fetchCounts() // Refresh entry counts
  }

  const updateWorkerState = async (updates) => {
    // Mark the keys as pending
    Object.keys(updates).forEach(key => setPendingToggle(key, true))
    
    try {
      const res = await fetch('/api/worker/state', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates)
      })
      const data = await res.json()
      setWorkerState(data)
    } catch (err) { console.error('update state:', err) }
    
    // Clear pending state after a short delay to show the transition
    setTimeout(() => {
      Object.keys(updates).forEach(key => setPendingToggle(key, false))
    }, 300)
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
    fetchSystemStatus()
    fetchWorkerStats()
    
    // Load secondary data with slight delay
    const secondaryTimer = setTimeout(() => {
      fetchStorage()
      fetchExtensions()
      fetchRecent()
      fetchInheritanceStats()
    }, 100)

    // Set up polling intervals
    const countsInterval = setInterval(fetchCounts, 3000)
    const docCountsInterval = setInterval(fetchDocCounts, 3000)
    const stateInterval = setInterval(fetchWorkerState, 5000)
    const statsInterval = setInterval(fetchWorkerStats, 5000)
    const storageInterval = setInterval(fetchStorage, 30000)
    const inheritanceInterval = setInterval(fetchInheritanceStats, 10000)
    
    return () => {
      clearTimeout(secondaryTimer)
      clearInterval(countsInterval)
      clearInterval(docCountsInterval)
      clearInterval(stateInterval)
      clearInterval(statsInterval)
      clearInterval(storageInterval)
      clearInterval(inheritanceInterval)
    }
  }, [fetchCounts, fetchDocCounts, fetchWorkerState, fetchSystemStatus, fetchWorkerStats, fetchStorage, fetchExtensions, fetchRecent, fetchInheritanceStats])

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
          className={`${styles.masterBtn} ${workerState?.running ? styles.running : styles.paused} ${pendingToggles.running ? styles.pending : ''}`}
          onClick={() => updateWorkerState({ running: !workerState?.running })}
          disabled={pendingToggles.running}
        >
          {pendingToggles.running ? <Loader2 size={16} className={styles.spin} /> : (workerState?.running ? <Pause size={16} /> : <Play size={16} />)}
          {workerState?.running ? 'Running' : 'Paused'}
        </button>
        
        <div className={styles.toggleGroup}>
          <button 
            className={`${styles.toggleBtn} ${workerState?.ingest ? styles.on : ''} ${pendingToggles.ingest ? styles.pending : ''}`}
            onClick={() => toggleProcess('ingest')}
            disabled={!workerState?.running || pendingToggles.ingest}
            title="Ingest new files"
          >
            {pendingToggles.ingest ? <Loader2 size={14} className={styles.spin} /> : <FilePlus size={14} />} Ingest
          </button>
          <button 
            className={`${styles.toggleBtn} ${workerState?.enrich_docs ? styles.on : ''} ${pendingToggles.enrich_docs ? styles.pending : ''}`}
            onClick={() => toggleProcess('enrich_docs')}
            disabled={!workerState?.running || pendingToggles.enrich_docs}
            title="Enrich documents"
          >
            {pendingToggles.enrich_docs ? <Loader2 size={14} className={styles.spin} /> : <Sparkles size={14} />} Docs
          </button>
          <button 
            className={`${styles.toggleBtn} ${workerState?.embed_docs ? styles.on : ''} ${pendingToggles.embed_docs ? styles.pending : ''}`}
            onClick={() => toggleProcess('embed_docs')}
            disabled={!workerState?.running || pendingToggles.embed_docs}
            title="Embed documents"
          >
            {pendingToggles.embed_docs ? <Loader2 size={14} className={styles.spin} /> : <Binary size={14} />} Doc Embed
          </button>
          <button 
            className={`${styles.toggleBtn} ${workerState?.enrich ? styles.on : ''} ${pendingToggles.enrich ? styles.pending : ''}`}
            onClick={() => toggleProcess('enrich')}
            disabled={!workerState?.running || pendingToggles.enrich}
            title="Enrich chunks"
          >
            {pendingToggles.enrich ? <Loader2 size={14} className={styles.spin} /> : <Layers size={14} />} Chunks
          </button>
          <button 
            className={`${styles.toggleBtn} ${workerState?.embed ? styles.on : ''} ${pendingToggles.embed ? styles.pending : ''}`}
            onClick={() => toggleProcess('embed')}
            disabled={!workerState?.running || pendingToggles.embed}
            title="Embed chunks"
          >
            {pendingToggles.embed ? <Loader2 size={14} className={styles.spin} /> : <Cpu size={14} />} Chunk Embed
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
          
          {/* Model Info for Doc-Level */}
          {systemStatus?.ollama && (
            <div className={styles.modelInfo}>
              <div className={styles.modelBadge} title="LLM used for doc enrichment (summary generation)">
                <Sparkles size={12} />
                <span>{systemStatus.ollama.chat_model}</span>
              </div>
              <div className={styles.modelBadge} title="Embedding model for doc vectors">
                <Box size={12} />
                <span>{systemStatus.ollama.embedding_model}</span>
              </div>
              {workerStats?.rates?.enrich_per_minute > 0 && (
                <div className={styles.rateBadge} title="Current processing rate">
                  <Zap size={12} />
                  <span>{workerStats.rates.enrich_per_minute}/min</span>
                </div>
              )}
            </div>
          )}
          
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
              eta={workerStats?.docs?.eta}
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
          
          {/* Rate info for doc processing */}
          {workerStats?.docs?.rate_per_hour > 0 && (
            <div className={styles.etaInfo}>
              <Zap size={12} />
              <span>{workerStats.docs.rate_per_hour}/hr</span>
              <span className={styles.etaDivider}>•</span>
              <span>{workerStats.docs.pending?.toLocaleString()} remaining</span>
            </div>
          )}
        </div>

        {/* Chunk-Level (Stage 2) */}
        <div className={styles.pipelineCard}>
          <div className={styles.pipelineHeader}>
            <h2><Layers size={18} /> Chunk-Level</h2>
            <span className={styles.pipelineTag}>Stage 2: Fine Search</span>
          </div>
          
          {/* Model Info for Chunk-Level */}
          {systemStatus?.ollama && (
            <div className={styles.modelInfo}>
              <div className={styles.modelBadge} title="LLM used for chunk enrichment">
                <Sparkles size={12} />
                <span>{systemStatus.ollama.chat_model}</span>
              </div>
              <div className={styles.modelBadge} title="Embedding model for chunk vectors">
                <Box size={12} />
                <span>{systemStatus.ollama.embedding_model}</span>
              </div>
              {workerStats?.eta?.eta_string && workerStats.eta.eta_string !== 'Calculating...' && (
                <div className={styles.etaBadge} title="Estimated time remaining">
                  <Clock size={12} />
                  <span>ETA: {workerStats.eta.eta_string}</span>
                </div>
              )}
            </div>
          )}
          
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
              eta={workerStats?.eta}
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
          
          {/* Rate info for chunk processing */}
          {workerStats?.rates?.enrich_per_hour > 0 && (
            <div className={styles.etaInfo}>
              <Zap size={12} />
              <span>{workerStats.rates.enrich_per_hour}/hr</span>
              <span className={styles.etaDivider}>•</span>
              <span>{workerStats.eta?.pending_count?.toLocaleString()} remaining</span>
            </div>
          )}
          
          {/* Inheritance Quick Action */}
          {inheritanceStats && inheritanceStats.can_inherit_title > 0 && (
            <div className={styles.inheritanceCard}>
              <div className={styles.inheritanceHeader}>
                <ArrowDown size={16} />
                <span>Inherit from Docs</span>
                <span className={styles.inheritanceCount}>
                  {inheritanceStats.can_inherit_title.toLocaleString()} chunks
                </span>
              </div>
              <p className={styles.inheritanceDesc}>
                Copy titles & metadata from enriched documents to their chunks (no LLM needed)
              </p>
              <button 
                className={styles.inheritanceBtn}
                onClick={runInheritance}
                disabled={inheritanceRunning}
              >
                {inheritanceRunning ? (
                  <>
                    <Loader2 size={14} className={styles.spin} />
                    Running... {inheritanceProgress.total.toLocaleString()} inherited
                  </>
                ) : (
                  <>
                    <Download size={14} />
                    Run Inheritance
                  </>
                )}
              </button>
            </div>
          )}
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
