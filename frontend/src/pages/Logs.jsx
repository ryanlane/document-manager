import { useState, useEffect, useRef, useCallback } from 'react'
import { 
  ArrowLeft, RefreshCw, Filter, Clock, FileText, Layers, Sparkles, 
  Binary, AlertCircle, CheckCircle, Info, ChevronDown, ChevronUp,
  Pause, Play, Search, X, Download, Zap, Trash2, RotateCcw
} from 'lucide-react'
import { Link } from 'react-router-dom'
import styles from './Logs.module.css'

// Stage configuration
const STAGES = {
  all: { label: 'All Stages', icon: Layers, color: '#646cff' },
  ingest: { label: 'Ingest', icon: FileText, color: '#646cff' },
  segment: { label: 'Segment', icon: Layers, color: '#f97316' },
  enrich: { label: 'Enrich', icon: Sparkles, color: '#ffc517' },
  embed: { label: 'Embed', icon: Binary, color: '#42b883' },
  worker: { label: 'Worker', icon: Zap, color: '#ec4899' }
}

// Level configuration
const LEVELS = {
  all: { label: 'All Levels', color: '#888' },
  INFO: { label: 'Info', color: '#42b883' },
  WARNING: { label: 'Warning', color: '#ffc517' },
  ERROR: { label: 'Error', color: '#ff6b6b' }
}

// Important event patterns to highlight
const IMPORTANT_PATTERNS = [
  { pattern: /Starting.*Phase/i, type: 'phase', icon: Zap },
  { pattern: /Enriching entry/i, type: 'llm', icon: Sparkles },
  { pattern: /Enriched entry/i, type: 'success', icon: CheckCircle },
  { pattern: /Created \d+ entries/i, type: 'success', icon: CheckCircle },
  { pattern: /Generated embedding/i, type: 'embed', icon: Binary },
  { pattern: /Batch complete/i, type: 'success', icon: CheckCircle },
  { pattern: /New file detected|Ingesting file/i, type: 'newfile', icon: FileText },
  { pattern: /ERROR|failed|Failed/i, type: 'error', icon: AlertCircle },
  { pattern: /WARNING|Skipping/i, type: 'warning', icon: AlertCircle },
  { pattern: /Worker loop started/i, type: 'phase', icon: Play },
  { pattern: /Cycle complete/i, type: 'complete', icon: CheckCircle }
]

function Logs() {
  const [logs, setLogs] = useState([])
  const [parsedLogs, setParsedLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [refreshInterval, setRefreshInterval] = useState(2000)
  const [stageFilter, setStageFilter] = useState('all')
  const [levelFilter, setLevelFilter] = useState('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [showFilters, setShowFilters] = useState(true)
  const [autoScroll, setAutoScroll] = useState(true)
  const [stats, setStats] = useState({ total: 0, info: 0, warning: 0, error: 0 })
  const logsEndRef = useRef(null)
  const containerRef = useRef(null)

  // Parse a log line into structured data
  const parseLogLine = useCallback((line, index) => {
    // Strip any leading level prefix (e.g., "INFO\n") that might be on the line
    const cleanLine = line.replace(/^(INFO|WARNING|ERROR|DEBUG)\s*\n?/, '').trim()

    // Format: 2024-12-15 10:30:45,123 - module_name - LEVEL - Message
    // Module name can contain dots (e.g., src.segment.segment_entries)
    const match = cleanLine.match(/^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2},\d{3})\s+-\s+([\w.]+)\s+-\s+(\w+)\s+-\s+(.*)$/)

    if (match) {
      const [, timestamp, module, level, message] = match
      
      // Determine stage from module name
      let stage = 'worker'
      if (module.includes('ingest')) stage = 'ingest'
      else if (module.includes('segment')) stage = 'segment'
      else if (module.includes('enrich')) stage = 'enrich'
      else if (module.includes('embed')) stage = 'embed'
      
      // Find important pattern match
      let eventType = null
      let EventIcon = null
      for (const { pattern, type, icon } of IMPORTANT_PATTERNS) {
        if (pattern.test(message) || pattern.test(level)) {
          eventType = type
          EventIcon = icon
          break
        }
      }
      
      // Extract timing info if present
      const timeMatch = message.match(/(\d+\.?\d*)\s*(ms|s|seconds|milliseconds)/i)
      const timing = timeMatch ? { value: parseFloat(timeMatch[1]), unit: timeMatch[2] } : null
      
      // Extract entry/file ID if present
      const idMatch = message.match(/(?:entry|file)\s+(\d+)/i)
      const entityId = idMatch ? parseInt(idMatch[1]) : null
      
      return {
        id: index,
        raw: line,
        timestamp: new Date(timestamp.replace(',', '.')),
        timestampStr: timestamp,
        module,
        level,
        message,
        stage,
        eventType,
        EventIcon,
        timing,
        entityId,
        isImportant: eventType !== null
      }
    }
    
    // Unparseable line - treat as continuation or raw
    return {
      id: index,
      raw: line,
      timestamp: null,
      timestampStr: '',
      module: '',
      level: 'INFO',
      message: line,
      stage: 'worker',
      eventType: null,
      EventIcon: null,
      timing: null,
      entityId: null,
      isImportant: false
    }
  }, [])

  const fetchLogs = useCallback(async () => {
    try {
      const res = await fetch('/api/worker/logs?lines=100')
      if (!res.ok) {
        console.error(`Failed to fetch logs: ${res.status} ${res.statusText}`)
        setLoading(false)
        return
      }
      
      const data = await res.json()
      const lines = data.lines || []
      setLogs(lines)
      
      // Parse all lines with error handling
      const parsed = lines
        .map((line, i) => {
          try {
            return parseLogLine(line.trim(), i)
          } catch (err) {
            console.error('Error parsing log line:', err, line)
            return null
          }
        })
        .filter(l => l && l.message && l.message.trim())
      
      setParsedLogs(parsed)
      
      // Calculate stats
      const newStats = { total: parsed.length, info: 0, warning: 0, error: 0 }
      parsed.forEach(log => {
        if (log.level === 'INFO') newStats.info++
        else if (log.level === 'WARNING') newStats.warning++
        else if (log.level === 'ERROR') newStats.error++
      })
      setStats(newStats)
      
      setLoading(false)
    } catch (err) {
      console.error('Error fetching logs:', err)
      setLoading(false)
    }
  }, [parseLogLine])

  useEffect(() => {
    fetchLogs()
    let interval
    if (autoRefresh) {
      interval = setInterval(fetchLogs, refreshInterval)
    }
    return () => interval && clearInterval(interval)
  }, [autoRefresh, refreshInterval, fetchLogs])

  useEffect(() => {
    if (autoScroll && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [parsedLogs, autoScroll])

  // Filter logs
  const filteredLogs = parsedLogs.filter(log => {
    if (stageFilter !== 'all' && log.stage !== stageFilter) return false
    if (levelFilter !== 'all' && log.level !== levelFilter) return false
    if (searchQuery && !log.message.toLowerCase().includes(searchQuery.toLowerCase())) return false
    return true
  })

  const getLogClass = (log) => {
    const classes = [styles.logLine]
    if (log.level === 'ERROR') classes.push(styles.logError)
    else if (log.level === 'WARNING') classes.push(styles.logWarning)
    if (log.isImportant) classes.push(styles.logImportant)
    if (log.eventType === 'phase') classes.push(styles.logPhase)
    if (log.eventType === 'success') classes.push(styles.logSuccess)
    return classes.join(' ')
  }

  const formatTimestamp = (log) => {
    if (!log.timestamp) return ''
    return log.timestamp.toLocaleTimeString('en-US', { 
      hour12: false, 
      hour: '2-digit', 
      minute: '2-digit', 
      second: '2-digit' 
    })
  }

  const downloadLogs = () => {
    const content = logs.join('\n')
    const blob = new Blob([content], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `worker-logs-${new Date().toISOString().slice(0,10)}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }

  const rotateLogs = async () => {
    if (!confirm('Rotate logs? This will archive the current log file and start fresh.')) return
    try {
      const res = await fetch('/api/worker/logs/rotate', { method: 'POST' })
      const data = await res.json()
      if (data.message) {
        alert(data.message)
        fetchLogs()
      }
    } catch (err) {
      console.error('Failed to rotate logs:', err)
      alert('Failed to rotate logs')
    }
  }

  const clearLogs = async () => {
    if (!confirm('Clear all logs? This cannot be undone.')) return
    try {
      const res = await fetch('/api/worker/logs', { method: 'DELETE' })
      const data = await res.json()
      if (data.message) {
        alert(data.message)
        fetchLogs()
      }
    } catch (err) {
      console.error('Failed to clear logs:', err)
      alert('Failed to clear logs')
    }
  }

  const StageIcon = STAGES[stageFilter]?.icon || Layers

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div className={styles.title}>
          <Link to="/dashboard" className={styles.backBtn}>
            <ArrowLeft size={20} />
          </Link>
          <h1>Processing Logs</h1>
        </div>
        <div className={styles.headerControls}>
          <button 
            className={`${styles.iconBtn} ${showFilters ? styles.active : ''}`}
            onClick={() => setShowFilters(!showFilters)}
            title="Toggle filters"
          >
            <Filter size={18} />
          </button>
          <button 
            className={styles.iconBtn}
            onClick={downloadLogs}
            title="Download logs"
          >
            <Download size={18} />
          </button>
          <button 
            className={styles.iconBtn}
            onClick={rotateLogs}
            title="Rotate logs (archive old, start fresh)"
          >
            <RotateCcw size={18} />
          </button>
          <button 
            className={`${styles.iconBtn} ${styles.danger}`}
            onClick={clearLogs}
            title="Clear all logs"
          >
            <Trash2 size={18} />
          </button>
          <button onClick={fetchLogs} className={styles.refreshBtn}>
            <RefreshCw size={16} className={autoRefresh ? styles.spinning : ''} /> Refresh
          </button>
        </div>
      </div>

      {/* Stats Bar */}
      <div className={styles.statsBar}>
        <div className={styles.statItem}>
          <span className={styles.statValue}>{stats.total}</span>
          <span className={styles.statLabel}>Total</span>
        </div>
        <div className={`${styles.statItem} ${styles.statInfo}`}>
          <Info size={14} />
          <span className={styles.statValue}>{stats.info}</span>
          <span className={styles.statLabel}>Info</span>
        </div>
        <div className={`${styles.statItem} ${styles.statWarning}`}>
          <AlertCircle size={14} />
          <span className={styles.statValue}>{stats.warning}</span>
          <span className={styles.statLabel}>Warnings</span>
        </div>
        <div className={`${styles.statItem} ${styles.statError}`}>
          <AlertCircle size={14} />
          <span className={styles.statValue}>{stats.error}</span>
          <span className={styles.statLabel}>Errors</span>
        </div>
      </div>

      {/* Filters Panel */}
      {showFilters && (
        <div className={styles.filtersPanel}>
          <div className={styles.filterGroup}>
            <label>Stage</label>
            <div className={styles.stageButtons}>
              {Object.entries(STAGES).map(([key, { label, icon: Icon, color }]) => (
                <button
                  key={key}
                  className={`${styles.stageBtn} ${stageFilter === key ? styles.active : ''}`}
                  onClick={() => setStageFilter(key)}
                  style={{ '--stage-color': color }}
                >
                  <Icon size={14} />
                  <span>{label}</span>
                </button>
              ))}
            </div>
          </div>

          <div className={styles.filterGroup}>
            <label>Level</label>
            <div className={styles.levelButtons}>
              {Object.entries(LEVELS).map(([key, { label, color }]) => (
                <button
                  key={key}
                  className={`${styles.levelBtn} ${levelFilter === key ? styles.active : ''}`}
                  onClick={() => setLevelFilter(key)}
                  style={{ '--level-color': color }}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          <div className={styles.filterGroup}>
            <label>Search</label>
            <div className={styles.searchBox}>
              <Search size={14} />
              <input
                type="text"
                placeholder="Search logs..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
              {searchQuery && (
                <button className={styles.clearSearch} onClick={() => setSearchQuery('')}>
                  <X size={14} />
                </button>
              )}
            </div>
          </div>

          <div className={styles.filterGroup}>
            <label>Options</label>
            <div className={styles.optionsRow}>
              <label className={styles.checkbox}>
                <input
                  type="checkbox"
                  checked={autoRefresh}
                  onChange={(e) => setAutoRefresh(e.target.checked)}
                />
                <span>Auto-refresh</span>
              </label>
              <label className={styles.checkbox}>
                <input
                  type="checkbox"
                  checked={autoScroll}
                  onChange={(e) => setAutoScroll(e.target.checked)}
                />
                <span>Auto-scroll</span>
              </label>
              <select 
                className={styles.intervalSelect}
                value={refreshInterval} 
                onChange={(e) => setRefreshInterval(Number(e.target.value))}
                disabled={!autoRefresh}
              >
                <option value={1000}>1s</option>
                <option value={2000}>2s</option>
                <option value={5000}>5s</option>
                <option value={10000}>10s</option>
              </select>
            </div>
          </div>
        </div>
      )}

      {/* Results Summary */}
      <div className={styles.resultsSummary}>
        Showing {filteredLogs.length} of {parsedLogs.length} log entries
        {(stageFilter !== 'all' || levelFilter !== 'all' || searchQuery) && (
          <button 
            className={styles.clearFilters}
            onClick={() => { setStageFilter('all'); setLevelFilter('all'); setSearchQuery(''); }}
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Logs Container */}
      {loading ? (
        <div className={styles.loading}>Loading logs...</div>
      ) : filteredLogs.length === 0 ? (
        <div className={styles.noLogs}>
          {parsedLogs.length === 0 
            ? 'No logs available. The worker may need to be restarted to enable logging.'
            : 'No logs match the current filters.'}
        </div>
      ) : (
        <div className={styles.container} ref={containerRef}>
          <div className={styles.content}>
            {filteredLogs.map((log) => {
              const StageIcon = STAGES[log.stage]?.icon
              return (
                <div key={log.id} className={getLogClass(log)}>
                  <span className={styles.logTime}>{formatTimestamp(log)}</span>
                  <span className={`${styles.logStage} ${styles[log.stage]}`}>
                    {StageIcon && <StageIcon size={12} />}
                  </span>
                  <span className={`${styles.logLevel} ${styles[log.level.toLowerCase()]}`}>
                    {log.level}
                  </span>
                  <span className={styles.logMessage}>
                    {log.EventIcon && <log.EventIcon size={12} className={styles.eventIcon} />}
                    {log.message}
                    {log.timing && (
                      <span className={styles.logTiming}>
                        <Clock size={10} /> {log.timing.value}{log.timing.unit}
                      </span>
                    )}
                  </span>
                </div>
              )
            })}
            <div ref={logsEndRef} />
          </div>
        </div>
      )}
    </div>
  )
}

export default Logs
