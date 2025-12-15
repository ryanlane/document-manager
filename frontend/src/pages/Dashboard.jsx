import { useState, useEffect } from 'react'
import { 
  Database, FileText, Layers, Cpu, HardDrive, Clock, AlertCircle, 
  Play, Pause, Power, RefreshCw, CheckCircle, FilePlus, FileEdit, FileX,
  ArrowRight, Scissors, Sparkles, Binary, Search, ChevronDown, ChevronUp,
  Info, Zap, Box
} from 'lucide-react'
import { Link } from 'react-router-dom'
import styles from './Dashboard.module.css'

// Pipeline stage definitions with educational content
const PIPELINE_STAGES = {
  ingest: {
    id: 'ingest',
    name: 'Ingest',
    icon: FilePlus,
    color: '#646cff',
    description: 'Files are discovered and read from your source folders.',
    details: [
      'Scans configured source folders for new or modified files',
      'Extracts raw text using Tika (for documents) or OCR (for images)',
      'Stores file metadata: path, size, extension, timestamps',
      'Creates initial RawFile records in the database'
    ],
    inputLabel: 'Source Files',
    outputLabel: 'Raw Text'
  },
  segment: {
    id: 'segment',
    name: 'Segment',
    icon: Scissors,
    color: '#f97316',
    description: 'Long documents are split into searchable chunks.',
    details: [
      'Breaks large documents into smaller segments (~1000-1500 tokens)',
      'Respects sentence and paragraph boundaries',
      'Adds configurable overlap between chunks for context continuity',
      'Detects content type (HTML, Markdown, plain text) for smart splitting',
      'Creates Entry records for each segment'
    ],
    inputLabel: 'Raw Text',
    outputLabel: 'Text Chunks'
  },
  enrich: {
    id: 'enrich',
    name: 'Enrich',
    icon: Sparkles,
    color: '#ffc517',
    description: 'AI analyzes each segment to extract metadata.',
    details: [
      'Sends each segment to the LLM with a structured prompt',
      'Extracts: title, summary, tags, themes, sentiment, entities',
      'Detects category from folder structure',
      'Calculates quality scores for each entry',
      'Stores enriched metadata in JSON format'
    ],
    inputLabel: 'Text Chunks',
    outputLabel: 'Enriched Entries'
  },
  embed: {
    id: 'embed',
    name: 'Embed',
    icon: Binary,
    color: '#42b883',
    description: 'Text is converted to vector embeddings for semantic search.',
    details: [
      'Creates a combined text from: title, summary, tags, and content',
      'Sends to embedding model (e.g., nomic-embed-text)',
      'Receives a 768-dimensional vector representing meaning',
      'Stores vector in pgvector for fast similarity search',
      'Enables finding related content by meaning, not just keywords'
    ],
    inputLabel: 'Enriched Entries',
    outputLabel: 'Vector Embeddings'
  },
  search: {
    id: 'search',
    name: 'Searchable',
    icon: Search,
    color: '#ec4899',
    description: 'Content is now fully indexed and searchable.',
    details: [
      'Hybrid search combines vector similarity + keyword matching',
      'Vector search finds semantically related content',
      'Keyword search uses PostgreSQL full-text search (BM25)',
      'Results can be filtered by author, category, tags, etc.',
      'Similarity scores show how closely results match your query'
    ],
    inputLabel: 'Vector Embeddings',
    outputLabel: 'Search Results'
  }
}

function Dashboard() {
  const [metrics, setMetrics] = useState(null)
  const [workerState, setWorkerState] = useState(null)
  const [pipelineProgress, setPipelineProgress] = useState(null)
  const [loading, setLoading] = useState(true)
  const [lastUpdate, setLastUpdate] = useState(null)
  const [expandedStage, setExpandedStage] = useState(null)
  const [animatingCounts, setAnimatingCounts] = useState({})

  const fetchMetrics = async () => {
    try {
      const res = await fetch('/api/system/metrics')
      const data = await res.json()
      
      // Animate count changes
      if (metrics) {
        const newAnimating = {}
        if (data.files.total !== metrics.files.total) newAnimating.files = true
        if (data.entries.total !== metrics.entries.total) newAnimating.segments = true
        if (data.entries.enriched !== metrics.entries.enriched) newAnimating.enriched = true
        if (data.entries.embedded !== metrics.entries.embedded) newAnimating.embedded = true
        setAnimatingCounts(newAnimating)
        setTimeout(() => setAnimatingCounts({}), 600)
      }
      
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

  // Get stage status based on metrics and worker state
  const getStageStatus = (stageId) => {
    if (!metrics || !workerState) return 'idle'
    
    const isProcessing = pipelineProgress?.[stageId]?.total > 0 && 
                         pipelineProgress?.[stageId]?.percent < 100
    
    if (stageId === 'ingest') {
      if (pipelineProgress?.ingest?.phase === 'scanning' || 
          pipelineProgress?.ingest?.phase === 'processing') return 'processing'
      if (metrics.files.total > 0) return 'complete'
      return 'idle'
    }
    if (stageId === 'segment') {
      if (metrics.entries.total > 0) return 'complete'
      if (workerState.segment) return 'processing'
      return 'idle'
    }
    if (stageId === 'enrich') {
      if (isProcessing) return 'processing'
      if (metrics.entries.enriched === metrics.entries.total && metrics.entries.total > 0) return 'complete'
      if (metrics.entries.pending > 0) return 'pending'
      return 'idle'
    }
    if (stageId === 'embed') {
      if (isProcessing) return 'processing'
      if (metrics.entries.embedded === metrics.entries.total && metrics.entries.total > 0) return 'complete'
      if (metrics.entries.enriched > metrics.entries.embedded) return 'pending'
      return 'idle'
    }
    if (stageId === 'search') {
      if (metrics.entries.embedded > 0) return 'complete'
      return 'idle'
    }
    return 'idle'
  }

  // Get count for each stage
  const getStageCount = (stageId) => {
    if (!metrics) return 0
    switch (stageId) {
      case 'ingest': return metrics.files.total
      case 'segment': return metrics.entries.total
      case 'enrich': return metrics.entries.enriched
      case 'embed': return metrics.entries.embedded
      case 'search': return metrics.entries.embedded
      default: return 0
    }
  }

  // Get pending count for each stage
  const getStagePending = (stageId) => {
    if (!metrics) return 0
    switch (stageId) {
      case 'ingest': return metrics.files.pending || 0
      case 'segment': return 0
      case 'enrich': return metrics.entries.pending || 0
      case 'embed': return (metrics.entries.enriched - metrics.entries.embedded) || 0
      case 'search': return 0
      default: return 0
    }
  }

  if (loading) return <div className={styles.loading}>Loading metrics...</div>

  const enrichedPct = ((metrics.entries.enriched / (metrics.entries.total || 1)) * 100).toFixed(1)
  const embeddedPct = ((metrics.entries.embedded / (metrics.entries.total || 1)) * 100).toFixed(1)
  const stageOrder = ['ingest', 'segment', 'enrich', 'embed', 'search']

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

      {/* Pipeline Visualization */}
      <div className={`${styles.section} ${styles.pipelineSection}`}>
        <div className={styles.pipelineHeader}>
          <h2><Zap size={18} /> RAG Pipeline</h2>
          <span className={styles.pipelineHint}>
            <Info size={14} /> Click any stage to learn more
          </span>
        </div>
        
        <div className={styles.pipelineFlow}>
          {stageOrder.map((stageId, index) => {
            const stage = PIPELINE_STAGES[stageId]
            const status = getStageStatus(stageId)
            const count = getStageCount(stageId)
            const pending = getStagePending(stageId)
            const isExpanded = expandedStage === stageId
            const isAnimating = animatingCounts[stageId === 'ingest' ? 'files' : 
                                                 stageId === 'segment' ? 'segments' :
                                                 stageId === 'enrich' ? 'enriched' : 'embedded']
            const StageIcon = stage.icon
            
            return (
              <div key={stageId} className={styles.stageWrapper}>
                {/* Stage Card */}
                <div 
                  className={`${styles.stageCard} ${styles[status]} ${isExpanded ? styles.expanded : ''}`}
                  onClick={() => setExpandedStage(isExpanded ? null : stageId)}
                  style={{ '--stage-color': stage.color }}
                >
                  <div className={styles.stageIcon}>
                    <StageIcon size={24} />
                    {status === 'processing' && (
                      <div className={styles.processingRing}></div>
                    )}
                  </div>
                  
                  <div className={styles.stageInfo}>
                    <h3>{stage.name}</h3>
                    <div className={`${styles.stageCount} ${isAnimating ? styles.pulse : ''}`}>
                      {count.toLocaleString()}
                    </div>
                    {pending > 0 && (
                      <div className={styles.stagePending}>
                        +{pending.toLocaleString()} pending
                      </div>
                    )}
                  </div>
                  
                  <div className={styles.stageStatus}>
                    <span className={`${styles.statusDot} ${styles[status]}`}></span>
                    <span className={styles.statusLabel}>{status}</span>
                  </div>
                  
                  <div className={styles.expandIcon}>
                    {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                  </div>
                </div>
                
                {/* Expanded Details */}
                {isExpanded && (
                  <div className={styles.stageDetails}>
                    <p className={styles.stageDescription}>{stage.description}</p>
                    <ul className={styles.stageDetailsList}>
                      {stage.details.map((detail, i) => (
                        <li key={i}>{detail}</li>
                      ))}
                    </ul>
                    <div className={styles.stageIO}>
                      <span><strong>Input:</strong> {stage.inputLabel}</span>
                      <ArrowRight size={14} />
                      <span><strong>Output:</strong> {stage.outputLabel}</span>
                    </div>
                  </div>
                )}
                
                {/* Arrow to next stage */}
                {index < stageOrder.length - 1 && (
                  <div className={`${styles.stageArrow} ${status === 'processing' ? styles.active : ''}`}>
                    <ArrowRight size={20} />
                  </div>
                )}
              </div>
            )
          })}
        </div>
        
        {/* Pipeline Summary */}
        <div className={styles.pipelineSummary}>
          <div className={styles.summaryItem}>
            <span className={styles.summaryLabel}>Files Processed</span>
            <span className={styles.summaryValue}>{metrics.files.processed} / {metrics.files.total}</span>
          </div>
          <div className={styles.summaryItem}>
            <span className={styles.summaryLabel}>Entries Enriched</span>
            <span className={styles.summaryValue}>{metrics.entries.enriched} / {metrics.entries.total}</span>
          </div>
          <div className={styles.summaryItem}>
            <span className={styles.summaryLabel}>Searchable</span>
            <span className={styles.summaryValue}>{metrics.entries.embedded} entries</span>
          </div>
        </div>
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
