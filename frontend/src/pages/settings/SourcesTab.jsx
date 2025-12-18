import { useState, useEffect } from 'react'
import { 
  FolderPlus, 
  Check, 
  X, 
  Trash2,
  Plus,
  ExternalLink,
  ArrowRight
} from 'lucide-react'
import styles from '../Settings.module.css'

const API_BASE = '/api'

export default function SourcesTab({ 
  sources, 
  availableMounts, 
  onRefresh 
}) {
  const [newExclude, setNewExclude] = useState('')
  const [hostMappings, setHostMappings] = useState({})
  const [newMapping, setNewMapping] = useState({ container: '', host: '' })

  useEffect(() => {
    loadHostMappings()
  }, [])

  const loadHostMappings = async () => {
    try {
      const res = await fetch(`${API_BASE}/settings/host-path-mappings`)
      if (res.ok) {
        const data = await res.json()
        setHostMappings(data.mappings || {})
      }
    } catch (err) {
      console.error('Failed to load host path mappings:', err)
    }
  }

  const addHostMapping = async () => {
    if (!newMapping.container || !newMapping.host) return
    try {
      const res = await fetch(`${API_BASE}/settings/host-path-mappings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          container_path: newMapping.container, 
          host_path: newMapping.host 
        })
      })
      if (res.ok) {
        setNewMapping({ container: '', host: '' })
        loadHostMappings()
      }
    } catch (err) {
      alert('Failed to add mapping')
    }
  }

  const removeHostMapping = async (containerPath) => {
    try {
      await fetch(`${API_BASE}/settings/host-path-mappings`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ container_path: containerPath, host_path: '' })
      })
      loadHostMappings()
    } catch (err) {
      alert('Failed to remove mapping')
    }
  }

  const addSourceFolder = async (path) => {
    try {
      const res = await fetch(`${API_BASE}/settings/sources/include`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path })
      })
      if (res.ok) onRefresh()
    } catch (err) {
      alert('Failed to add folder')
    }
  }

  const removeSourceFolder = async (path) => {
    if (!confirm(`Remove source folder?\n${path}`)) return
    try {
      await fetch(`${API_BASE}/settings/sources/include`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path })
      })
      onRefresh()
    } catch (err) {
      alert('Failed to remove folder')
    }
  }

  const addExcludePattern = async () => {
    if (!newExclude.trim()) return
    try {
      const res = await fetch(`${API_BASE}/settings/sources/exclude`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pattern: newExclude.trim() })
      })
      if (res.ok) {
        setNewExclude('')
        onRefresh()
      }
    } catch (err) {
      alert('Failed to add pattern')
    }
  }

  const removeExcludePattern = async (pattern) => {
    try {
      await fetch(`${API_BASE}/settings/sources/exclude`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pattern })
      })
      onRefresh()
    } catch (err) {
      alert('Failed to remove pattern')
    }
  }

  return (
    <div className={styles.section}>
      <h2>Source Folders</h2>
      <p className={styles.description}>
        Folders mounted from your host system that will be indexed.
      </p>

      {/* Available Mounts */}
      <div className={styles.mountsList}>
        <h4>Available Folders</h4>
        {availableMounts.mounts?.length > 0 ? (
          <div className={styles.mountsGrid}>
            {availableMounts.mounts.map((mount, idx) => {
              const isAdded = sources.include?.some(s => s.path === mount.path)
              return (
                <div key={idx} className={`${styles.mount} ${isAdded ? styles.added : ''}`}>
                  <div className={styles.mountInfo}>
                    <span className={styles.mountName}>{mount.name}</span>
                    <span className={styles.mountStats}>{mount.file_count} files</span>
                  </div>
                  {isAdded ? (
                    <button onClick={() => removeSourceFolder(mount.path)} className={styles.removeBtn}>
                      <Trash2 size={14} />
                    </button>
                  ) : (
                    <button onClick={() => addSourceFolder(mount.path)} className={styles.addMountBtn}>
                      <Plus size={14} />
                    </button>
                  )}
                </div>
              )
            })}
          </div>
        ) : (
          <p className={styles.noMounts}>No folders mounted. See below for how to add volumes.</p>
        )}
      </div>

      {/* How to Add Folders Guide */}
      <details className={styles.mountGuide}>
        <summary className={styles.guideHeader}>
          <FolderPlus size={16} /> How to Add Folders
        </summary>
        <div className={styles.guideContent}>
          <p>
            Archive Brain runs in Docker, so folders from your system must be "mounted" into the container.
            Edit your <code>docker-compose.yml</code> file and add volumes to the <code>api</code> and <code>worker</code> services.
          </p>
          
          <h5>Example: Adding a folder</h5>
          <div className={styles.codeBlock}>
            <pre>{`services:
  api:
    volumes:
      - ./archive_root:/data/archive        # Default
      - /path/to/your/files:/data/archive/my-files  # Add this line
      
  worker:
    volumes:
      - ./archive_root:/data/archive        # Default  
      - /path/to/your/files:/data/archive/my-files  # Add same line here`}</pre>
            <button 
              className={styles.copyBtn}
              onClick={() => {
                navigator.clipboard.writeText(`      - /path/to/your/files:/data/archive/my-files`)
                alert('Copied to clipboard!')
              }}
            >
              Copy
            </button>
          </div>
          
          <h5>Common Scenarios</h5>
          <div className={styles.scenarioList}>
            <div className={styles.scenario}>
              <strong>📁 Local folder:</strong>
              <code>- /home/user/documents:/data/archive/documents</code>
            </div>
            <div className={styles.scenario}>
              <strong>💾 External drive:</strong>
              <code>- /mnt/external:/data/archive/external</code>
            </div>
            <div className={styles.scenario}>
              <strong>🌐 Network share (NFS/SMB):</strong>
              <code>- /mnt/nas/files:/data/archive/nas</code>
            </div>
          </div>
          
          <p className={styles.guideNote}>
            <strong>After editing:</strong> Run <code>docker compose up -d</code> to apply changes.
            The new folder will appear in "Available Folders" above.
          </p>
        </div>
      </details>

      {/* Active Sources */}
      <div className={styles.activeList}>
        <h4>Active Sources ({sources.include?.length || 0})</h4>
        {sources.include?.map((folder, idx) => (
          <div key={idx} className={styles.activeItem}>
            {folder.exists ? <Check size={14} className={styles.ok} /> : <X size={14} className={styles.missing} />}
            <span>{folder.path}</span>
            <span className={styles.count}>{folder.file_count} files</span>
            <button onClick={() => removeSourceFolder(folder.path)}><Trash2 size={14} /></button>
          </div>
        ))}
      </div>

      {/* Exclude Patterns */}
      <div className={styles.excludeSection}>
        <h4>Exclude Patterns</h4>
        <div className={styles.excludeList}>
          {sources.exclude?.map((pattern, idx) => (
            <span key={idx} className={styles.excludeTag}>
              {pattern}
              <button onClick={() => removeExcludePattern(pattern)}><X size={12} /></button>
            </span>
          ))}
        </div>
        <div className={styles.addExclude}>
          <input
            type="text"
            value={newExclude}
            onChange={(e) => setNewExclude(e.target.value)}
            placeholder="**/pattern/**"
            onKeyDown={(e) => e.key === 'Enter' && addExcludePattern()}
          />
          <button onClick={addExcludePattern}><Plus size={16} /></button>
        </div>
      </div>

      {/* Host Path Mappings */}
      <div className={styles.hostMappingsSection}>
        <h4><ExternalLink size={16} /> Host Path Mappings</h4>
        <p className={styles.description}>
          Map container paths to your actual file system paths. This helps you locate original files when viewing document metadata.
        </p>
        
        {Object.keys(hostMappings).length > 0 ? (
          <div className={styles.mappingsList}>
            {Object.entries(hostMappings).map(([containerPath, hostPath]) => (
              <div key={containerPath} className={styles.mappingItem}>
                <code className={styles.mappingPath}>{containerPath}</code>
                <ArrowRight size={14} className={styles.mappingArrow} />
                <code className={styles.mappingPath}>{hostPath}</code>
                <button 
                  onClick={() => removeHostMapping(containerPath)} 
                  className={styles.removeMappingBtn}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
        ) : (
          <p className={styles.noMappings}>
            No mappings configured. Add mappings to see original file paths in document metadata.
          </p>
        )}
        
        <div className={styles.addMapping}>
          <input
            type="text"
            value={newMapping.container}
            onChange={(e) => setNewMapping(prev => ({ ...prev, container: e.target.value }))}
            placeholder="/data/archive/docs"
            className={styles.mappingInput}
          />
          <ArrowRight size={14} className={styles.mappingArrow} />
          <input
            type="text"
            value={newMapping.host}
            onChange={(e) => setNewMapping(prev => ({ ...prev, host: e.target.value }))}
            placeholder="C:\Users\Me\Documents"
            className={styles.mappingInput}
          />
          <button onClick={addHostMapping} disabled={!newMapping.container || !newMapping.host}>
            <Plus size={16} />
          </button>
        </div>
      </div>
    </div>
  )
}
