import { useState, useEffect } from 'react'
import { 
  Loader2, 
  CheckCircle2, 
  XCircle, 
  AlertCircle, 
  Clock,
  Download,
  FolderSync,
  Settings,
  Database,
  RefreshCw,
  X,
  ChevronDown,
  ChevronUp
} from 'lucide-react'
import styles from './JobsPanel.module.css'

const API_BASE = '/api'

// Map job types to icons and labels
const JOB_TYPE_INFO = {
  model_pull: { icon: Download, label: 'Model Download', color: 'blue' },
  folder_scan: { icon: FolderSync, label: 'Folder Scan', color: 'green' },
  config_import: { icon: Settings, label: 'Config Import', color: 'purple' },
  vacuum: { icon: Database, label: 'Database Vacuum', color: 'orange' },
  reindex: { icon: RefreshCw, label: 'Reindex', color: 'cyan' },
  embed: { icon: Database, label: 'Embedding', color: 'pink' }
}

// Status icons
const STATUS_ICONS = {
  pending: Clock,
  running: Loader2,
  completed: CheckCircle2,
  failed: XCircle,
  cancelled: AlertCircle
}

function JobItem({ job, onCancel, onDelete }) {
  const typeInfo = JOB_TYPE_INFO[job.type] || { icon: Settings, label: job.type, color: 'gray' }
  const TypeIcon = typeInfo.icon
  const StatusIcon = STATUS_ICONS[job.status] || Clock
  
  const isActive = job.status === 'pending' || job.status === 'running'
  const isRunning = job.status === 'running'
  
  // Format metadata for display
  const getMetadataDisplay = () => {
    if (!job.metadata) return null
    if (job.type === 'model_pull' && job.metadata.model_name) {
      return job.metadata.model_name
    }
    if (job.type === 'folder_scan' && job.metadata.folder_path) {
      return job.metadata.folder_path
    }
    return null
  }
  
  const metadataDisplay = getMetadataDisplay()
  
  return (
    <div className={`${styles.jobItem} ${styles[job.status]}`}>
      <div className={styles.jobIcon} data-color={typeInfo.color}>
        <TypeIcon size={18} />
      </div>
      
      <div className={styles.jobInfo}>
        <div className={styles.jobHeader}>
          <span className={styles.jobType}>{typeInfo.label}</span>
          {metadataDisplay && (
            <span className={styles.jobMeta}>{metadataDisplay}</span>
          )}
        </div>
        
        <div className={styles.jobStatus}>
          <StatusIcon size={14} className={isRunning ? styles.spinner : ''} />
          <span>{job.message || job.status}</span>
        </div>
        
        {isRunning && job.progress != null && (
          <div className={styles.progressBar}>
            <div 
              className={styles.progressFill} 
              style={{ width: `${job.progress}%` }}
            />
            <span className={styles.progressText}>{job.progress}%</span>
          </div>
        )}
        
        {job.error && (
          <div className={styles.jobError}>{job.error}</div>
        )}
      </div>
      
      <div className={styles.jobActions}>
        {isActive && (
          <button 
            className={styles.cancelBtn}
            onClick={() => onCancel(job.id)}
            title="Cancel job"
          >
            <X size={14} />
          </button>
        )}
        {!isActive && (
          <button 
            className={styles.deleteBtn}
            onClick={() => onDelete(job.id)}
            title="Remove from list"
          >
            <X size={14} />
          </button>
        )}
      </div>
    </div>
  )
}

export default function JobsPanel({ 
  showRecent = true, 
  maxRecent = 5,
  pollInterval = 2000,
  compact = false 
}) {
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState(true)

  const fetchJobs = async () => {
    try {
      const endpoint = showRecent 
        ? `${API_BASE}/jobs/recent?limit=${maxRecent}`
        : `${API_BASE}/jobs/active`
      const res = await fetch(endpoint)
      if (res.ok) {
        const data = await res.json()
        setJobs(data.jobs || [])
      }
    } catch (err) {
      console.error('Failed to fetch jobs:', err)
    }
    setLoading(false)
  }

  useEffect(() => {
    fetchJobs()
    const interval = setInterval(fetchJobs, pollInterval)
    return () => clearInterval(interval)
  }, [showRecent, maxRecent, pollInterval])

  const handleCancel = async (jobId) => {
    try {
      await fetch(`${API_BASE}/jobs/${jobId}/cancel`, { method: 'POST' })
      fetchJobs()
    } catch (err) {
      console.error('Failed to cancel job:', err)
    }
  }

  const handleDelete = async (jobId) => {
    try {
      await fetch(`${API_BASE}/jobs/${jobId}`, { method: 'DELETE' })
      fetchJobs()
    } catch (err) {
      console.error('Failed to delete job:', err)
    }
  }

  // Don't render if no jobs and in compact mode
  if (compact && jobs.length === 0) {
    return null
  }

  const activeJobs = jobs.filter(j => j.status === 'pending' || j.status === 'running')
  const hasActive = activeJobs.length > 0

  return (
    <div className={`${styles.panel} ${compact ? styles.compact : ''}`}>
      <div 
        className={styles.header}
        onClick={() => setExpanded(!expanded)}
      >
        <div className={styles.headerTitle}>
          {hasActive && <Loader2 size={16} className={styles.spinner} />}
          <span>Background Jobs</span>
          {hasActive && <span className={styles.activeBadge}>{activeJobs.length} active</span>}
        </div>
        <button className={styles.expandBtn}>
          {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>
      </div>
      
      {expanded && (
        <div className={styles.content}>
          {loading ? (
            <div className={styles.loading}>
              <Loader2 size={20} className={styles.spinner} />
              <span>Loading jobs...</span>
            </div>
          ) : jobs.length === 0 ? (
            <div className={styles.empty}>
              <Clock size={24} />
              <span>No background jobs</span>
            </div>
          ) : (
            <div className={styles.jobsList}>
              {jobs.map(job => (
                <JobItem 
                  key={job.id} 
                  job={job} 
                  onCancel={handleCancel}
                  onDelete={handleDelete}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
