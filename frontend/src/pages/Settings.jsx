import { useState, useEffect } from 'react'
import { 
  Settings as SettingsIcon, 
  Server, 
  Cloud, 
  FolderPlus, 
  FileType, 
  RefreshCw, 
  Check, 
  X, 
  AlertCircle,
  Eye,
  EyeOff,
  Loader2,
  Trash2,
  Plus,
  Download,
  HardDrive,
  Wifi,
  WifiOff,
  Monitor,
  Container,
  Globe,
  Network,
  Zap,
  Power
} from 'lucide-react'
import styles from './Settings.module.css'

const API_BASE = '/api'

function Settings() {
  const [activeTab, setActiveTab] = useState('workers')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  
  // Environment variable overrides
  const [envOverrides, setEnvOverrides] = useState({})
  
  // LLM Endpoints (Workers)
  const [endpoints, setEndpoints] = useState([])
  const [loadingEndpoints, setLoadingEndpoints] = useState(false)
  const [showAddEndpoint, setShowAddEndpoint] = useState(false)
  const [newEndpoint, setNewEndpoint] = useState({ name: '', url: '', type: 'ollama' })
  const [testingEndpoint, setTestingEndpoint] = useState(null)
  
  // LLM Settings
  const [llmSettings, setLlmSettings] = useState({
    provider: 'ollama',
    ollama: { url: 'http://ollama:11434', model: '', embedding_model: 'nomic-embed-text', vision_model: '' },
    openai: { api_key: '', model: 'gpt-4o-mini', embedding_model: 'text-embedding-3-small' },
    anthropic: { api_key: '', model: 'claude-3-haiku-20240307' }
  })
  const [showApiKey, setShowApiKey] = useState({ openai: false, anthropic: false })
  const [ollamaModels, setOllamaModels] = useState([])
  const [loadingModels, setLoadingModels] = useState(false)
  
  // Model Catalog
  const [modelCatalog, setModelCatalog] = useState(null)
  const [loadingCatalog, setLoadingCatalog] = useState(false)
  const [pullingModels, setPullingModels] = useState({}) // { modelName: { status, progress, message } }
  const [catalogFilter, setCatalogFilter] = useState('all') // 'all', 'installed', or category name
  
  // Source Settings
  const [sources, setSources] = useState({ include: [], exclude: [] })
  const [availableMounts, setAvailableMounts] = useState({ mounts: [] })
  const [newExclude, setNewExclude] = useState('')
  
  // Extension Settings
  const [extensions, setExtensions] = useState([])
  const [newExtension, setNewExtension] = useState('')

  useEffect(() => {
    loadAll()
  }, [])

  const loadAll = async () => {
    setLoading(true)
    await Promise.all([
      loadEndpoints(),
      loadSettings(),
      loadOllamaModels(),
      loadModelCatalog()
    ])
    setLoading(false)
  }

  const loadEndpoints = async () => {
    setLoadingEndpoints(true)
    try {
      const res = await fetch(`${API_BASE}/settings/llm-endpoints`)
      if (res.ok) {
        setEndpoints(await res.json())
      }
    } catch (err) {
      console.error('Failed to load endpoints:', err)
    }
    setLoadingEndpoints(false)
  }

  const loadSettings = async () => {
    try {
      const [llmRes, srcRes, extRes, mountsRes, envRes] = await Promise.all([
        fetch(`${API_BASE}/settings/llm`),
        fetch(`${API_BASE}/settings/sources`),
        fetch(`${API_BASE}/settings/extensions`),
        fetch(`${API_BASE}/settings/sources/mounts`),
        fetch(`${API_BASE}/settings/env-overrides`)
      ])
      
      if (llmRes.ok) setLlmSettings(await llmRes.json())
      if (srcRes.ok) setSources(await srcRes.json())
      if (extRes.ok) {
        const data = await extRes.json()
        setExtensions(data.extensions || [])
      }
      if (mountsRes.ok) setAvailableMounts(await mountsRes.json())
      if (envRes.ok) {
        const data = await envRes.json()
        setEnvOverrides(data.overrides || {})
      }
    } catch (err) {
      console.error('Failed to load settings:', err)
    }
  }

  // Check if a setting path is locked by env var
  const isEnvLocked = (path) => {
    return envOverrides[path]?.locked === true
  }

  // Get env var name for a locked setting
  const getEnvVarName = (path) => {
    return envOverrides[path]?.env_var
  }

  const loadOllamaModels = async () => {
    setLoadingModels(true)
    try {
      const res = await fetch(`${API_BASE}/settings/ollama/models`)
      if (res.ok) {
        const data = await res.json()
        // API returns { models: [...], url: "..." }
        setOllamaModels(Array.isArray(data) ? data : (data.models || []))
      }
    } catch (err) {
      console.error('Failed to load models:', err)
    }
    setLoadingModels(false)
  }

  const loadModelCatalog = async () => {
    setLoadingCatalog(true)
    try {
      const res = await fetch(`${API_BASE}/settings/ollama/catalog`)
      if (res.ok) {
        setModelCatalog(await res.json())
      }
    } catch (err) {
      console.error('Failed to load model catalog:', err)
    }
    setLoadingCatalog(false)
  }

  const pullModel = async (modelName) => {
    setPullingModels(prev => ({ ...prev, [modelName]: { status: 'starting', progress: 0, message: 'Starting download...' } }))
    
    try {
      const res = await fetch(`${API_BASE}/settings/ollama/models/pull`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: modelName })
      })
      
      if (res.ok) {
        // Poll for progress
        const pollProgress = async () => {
          try {
            const statusRes = await fetch(`${API_BASE}/settings/ollama/models/pull/${encodeURIComponent(modelName)}`)
            if (statusRes.ok) {
              const status = await statusRes.json()
              setPullingModels(prev => ({ ...prev, [modelName]: status }))
              
              if (status.status === 'pulling') {
                setTimeout(pollProgress, 1000)
              } else if (status.status === 'complete') {
                // Refresh models list
                await loadOllamaModels()
                await loadModelCatalog()
                // Remove from pulling after a delay
                setTimeout(() => {
                  setPullingModels(prev => {
                    const updated = { ...prev }
                    delete updated[modelName]
                    return updated
                  })
                }, 3000)
              }
            }
          } catch (err) {
            console.error('Failed to poll progress:', err)
          }
        }
        setTimeout(pollProgress, 500)
      }
    } catch (err) {
      setPullingModels(prev => ({ ...prev, [modelName]: { status: 'error', message: err.message } }))
    }
  }

  const deleteModel = async (modelName) => {
    if (!confirm(`Delete model "${modelName}"? This cannot be undone.`)) return
    
    try {
      const res = await fetch(`${API_BASE}/settings/ollama/models/${encodeURIComponent(modelName)}`, {
        method: 'DELETE'
      })
      if (res.ok) {
        await loadOllamaModels()
        await loadModelCatalog()
      } else {
        alert('Failed to delete model')
      }
    } catch (err) {
      alert(`Error: ${err.message}`)
    }
  }

  const getFilteredCatalogModels = () => {
    if (!modelCatalog?.models) return []
    
    return modelCatalog.models.filter(model => {
      if (catalogFilter === 'all') return true
      if (catalogFilter === 'installed') return model.installed
      if (catalogFilter === 'recommended') return model.recommended
      return model.category === catalogFilter
    })
  }

  // === Endpoint Management ===
  const addEndpoint = async () => {
    if (!newEndpoint.name || !newEndpoint.url) return
    try {
      const res = await fetch(`${API_BASE}/settings/llm-endpoints`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newEndpoint)
      })
      if (res.ok) {
        setNewEndpoint({ name: '', url: '', type: 'ollama' })
        setShowAddEndpoint(false)
        loadEndpoints()
      }
    } catch (err) {
      alert('Failed to add endpoint')
    }
  }

  const toggleEndpoint = async (id, enabled) => {
    try {
      await fetch(`${API_BASE}/settings/llm-endpoints/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled })
      })
      loadEndpoints()
    } catch (err) {
      console.error('Failed to toggle endpoint:', err)
    }
  }

  const deleteEndpoint = async (id, name) => {
    if (!confirm(`Delete endpoint "${name}"?`)) return
    try {
      await fetch(`${API_BASE}/settings/llm-endpoints/${id}`, { method: 'DELETE' })
      loadEndpoints()
    } catch (err) {
      alert('Failed to delete endpoint')
    }
  }

  const testEndpoint = async (id) => {
    setTestingEndpoint(id)
    try {
      const res = await fetch(`${API_BASE}/settings/llm-endpoints/${id}/test`, { method: 'POST' })
      if (res.ok) {
        const result = await res.json()
        setEndpoints(prev => prev.map(ep => 
          ep.id === id ? { ...ep, status: { connected: result.connected, models: result.models.length, error: result.error } } : ep
        ))
      }
    } catch (err) {
      console.error('Failed to test endpoint:', err)
    }
    setTestingEndpoint(null)
  }

  // === LLM Settings ===
  const saveLLMSettings = async () => {
    setSaving(true)
    try {
      await fetch(`${API_BASE}/settings/llm`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(llmSettings)
      })
    } catch (err) {
      alert('Failed to save settings')
    }
    setSaving(false)
  }

  // === Source Management ===
  const addSourceFolder = async (path) => {
    try {
      const res = await fetch(`${API_BASE}/settings/sources/include`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path })
      })
      if (res.ok) loadSettings()
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
      loadSettings()
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
        loadSettings()
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
      loadSettings()
    } catch (err) {
      alert('Failed to remove pattern')
    }
  }

  // === Extension Management ===
  const saveExtensions = async () => {
    setSaving(true)
    try {
      await fetch(`${API_BASE}/settings/extensions`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ extensions })
      })
    } catch (err) {
      alert('Failed to save extensions')
    }
    setSaving(false)
  }

  const toggleExtension = (ext) => {
    if (extensions.includes(ext)) {
      setExtensions(extensions.filter(e => e !== ext))
    } else {
      setExtensions([...extensions, ext])
    }
  }

  // Get models by capability
  const getModels = (capability) => {
    if (!Array.isArray(ollamaModels)) return []
    return ollamaModels.filter(m => m.capabilities?.[capability])
  }

  if (loading) {
    return (
      <div className={styles.container}>
        <div className={styles.loading}>
          <Loader2 className={styles.spinner} />
          Loading settings...
        </div>
      </div>
    )
  }

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <h1><SettingsIcon size={24} /> Settings</h1>
      </header>

      <div className={styles.tabs}>
        <button 
          className={`${styles.tab} ${activeTab === 'workers' ? styles.active : ''}`}
          onClick={() => setActiveTab('workers')}
        >
          <Network size={16} /> LLM Workers
        </button>
        <button 
          className={`${styles.tab} ${activeTab === 'models' ? styles.active : ''}`}
          onClick={() => setActiveTab('models')}
        >
          <Zap size={16} /> Models
        </button>
        <button 
          className={`${styles.tab} ${activeTab === 'sources' ? styles.active : ''}`}
          onClick={() => setActiveTab('sources')}
        >
          <FolderPlus size={16} /> Sources
        </button>
        <button 
          className={`${styles.tab} ${activeTab === 'extensions' ? styles.active : ''}`}
          onClick={() => setActiveTab('extensions')}
        >
          <FileType size={16} /> File Types
        </button>
      </div>

      <div className={styles.content}>
        {/* === LLM Workers Tab === */}
        {activeTab === 'workers' && (
          <div className={styles.section}>
            <div className={styles.sectionHeader}>
              <div>
                <h2>LLM Workers</h2>
                <p className={styles.description}>
                  Configure Ollama endpoints across your network for distributed processing.
                </p>
              </div>
              <button 
                className={styles.addBtn} 
                onClick={() => setShowAddEndpoint(!showAddEndpoint)}
              >
                <Plus size={16} /> Add Endpoint
              </button>
            </div>

            {/* Add Endpoint Form */}
            {showAddEndpoint && (
              <div className={styles.addForm}>
                <div className={styles.formRow}>
                  <input
                    type="text"
                    placeholder="Name (e.g., Oak Server)"
                    value={newEndpoint.name}
                    onChange={(e) => setNewEndpoint(p => ({ ...p, name: e.target.value }))}
                  />
                  <input
                    type="text"
                    placeholder="URL (e.g., http://192.168.1.19:11434)"
                    value={newEndpoint.url}
                    onChange={(e) => setNewEndpoint(p => ({ ...p, url: e.target.value }))}
                  />
                  <button onClick={addEndpoint} disabled={!newEndpoint.name || !newEndpoint.url}>
                    <Check size={16} /> Add
                  </button>
                  <button onClick={() => setShowAddEndpoint(false)} className={styles.cancelBtn}>
                    <X size={16} />
                  </button>
                </div>
                <small>
                  Common endpoints: <code>http://ollama:11434</code> (Docker), 
                  <code>http://host.docker.internal:11434</code> (Host), 
                  <code>http://192.168.x.x:11434</code> (Network)
                </small>
              </div>
            )}

            {/* Endpoints List */}
            <div className={styles.endpointsList}>
              {loadingEndpoints ? (
                <div className={styles.loadingSmall}><Loader2 className={styles.spinner} size={16} /> Loading...</div>
              ) : endpoints.length === 0 ? (
                <div className={styles.emptyState}>
                  <Server size={32} />
                  <p>No LLM endpoints configured</p>
                  <small>Add Ollama servers on your network to distribute processing</small>
                </div>
              ) : (
                endpoints.map(ep => (
                  <div key={ep.id} className={`${styles.endpoint} ${ep.enabled ? '' : styles.paused}`}>
                    <div className={styles.endpointStatus}>
                      {!ep.enabled ? (
                        <Power size={18} className={styles.pausedIcon} />
                      ) : ep.status?.connected ? (
                        <Wifi size={18} className={styles.connected} />
                      ) : (
                        <WifiOff size={18} className={styles.disconnected} />
                      )}
                    </div>
                    
                    <div className={styles.endpointInfo}>
                      <div className={styles.endpointName}>
                        {ep.name}
                        {!ep.enabled && <span className={styles.pausedBadge}>Paused</span>}
                      </div>
                      <code className={styles.endpointUrl}>{ep.url}</code>
                      <div className={styles.endpointMeta}>
                        {ep.enabled && ep.status?.connected && <span>{ep.status.models} models</span>}
                        {ep.capabilities?.map(c => (
                          <span key={c} className={styles.capBadge}>{c}</span>
                        ))}
                        {ep.enabled && ep.status?.error && <span className={styles.errorText}>{ep.status.error}</span>}
                      </div>
                    </div>
                    
                    <div className={styles.endpointActions}>
                      <button 
                        onClick={() => toggleEndpoint(ep.id, !ep.enabled)}
                        className={`${styles.pauseBtn} ${ep.enabled ? styles.running : styles.pausedBtn}`}
                        title={ep.enabled ? 'Pause this worker' : 'Resume this worker'}
                      >
                        {ep.enabled ? (
                          <><Power size={14} /> Pause</>
                        ) : (
                          <><Power size={14} /> Resume</>
                        )}
                      </button>
                      <button 
                        onClick={() => testEndpoint(ep.id)}
                        disabled={testingEndpoint === ep.id || !ep.enabled}
                        title="Test connection"
                      >
                        {testingEndpoint === ep.id ? (
                          <Loader2 size={16} className={styles.spinner} />
                        ) : (
                          <RefreshCw size={16} />
                        )}
                      </button>
                      <button 
                        onClick={() => deleteEndpoint(ep.id, ep.name)}
                        className={styles.deleteBtn}
                        title="Delete"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Quick Add Presets */}
            <div className={styles.presets}>
              <h4>Quick Add</h4>
              <div className={styles.presetBtns}>
                <button onClick={() => {
                  setNewEndpoint({ name: 'Docker Ollama', url: 'http://ollama:11434', type: 'ollama' })
                  setShowAddEndpoint(true)
                }}>
                  <Container size={14} /> Docker
                </button>
                <button onClick={() => {
                  setNewEndpoint({ name: 'Host Ollama', url: 'http://host.docker.internal:11434', type: 'ollama' })
                  setShowAddEndpoint(true)
                }}>
                  <Monitor size={14} /> Host (Win/Mac)
                </button>
                <button onClick={() => {
                  setNewEndpoint({ name: 'Host Ollama', url: 'http://172.17.0.1:11434', type: 'ollama' })
                  setShowAddEndpoint(true)
                }}>
                  <Monitor size={14} /> Host (Linux)
                </button>
                <button onClick={() => {
                  const ip = prompt('Enter network IP:', '192.168.1.')
                  if (ip) {
                    setNewEndpoint({ name: `Network (${ip})`, url: `http://${ip}:11434`, type: 'ollama' })
                    setShowAddEndpoint(true)
                  }
                }}>
                  <Globe size={14} /> Network...
                </button>
              </div>
            </div>
          </div>
        )}

        {/* === Models Tab === */}
        {activeTab === 'models' && (
          <div className={styles.section}>
            <div className={styles.sectionHeader}>
              <div>
                <h2>Model Configuration</h2>
                <p className={styles.description}>
                  Select which models to use for each task type.
                </p>
              </div>
              <button onClick={loadOllamaModels} disabled={loadingModels} className={styles.refreshBtn}>
                {loadingModels ? <Loader2 size={16} className={styles.spinner} /> : <RefreshCw size={16} />}
                Refresh
              </button>
            </div>

            {/* Installed Models Overview */}
            {ollamaModels.length > 0 && (
              <div className={styles.installedModels}>
                <h4><HardDrive size={14} /> Installed Models ({ollamaModels.length})</h4>
                <div className={styles.modelChips}>
                  {ollamaModels.map(m => (
                    <div key={m.name} className={styles.modelChip}>
                      <span>{m.name}</span>
                      <span className={styles.chipSize}>{m.size_human}</span>
                      {m.capabilities?.chat && <span title="Chat">💬</span>}
                      {m.capabilities?.embedding && <span title="Embedding">📊</span>}
                      {m.capabilities?.vision && <span title="Vision">👁️</span>}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Model Selectors */}
            <div className={styles.modelGrid}>
              <div className={styles.modelSelect}>
                <label>
                  Chat Model
                  {isEnvLocked('ollama.model') && (
                    <span className={styles.envBadge} title={`Default from ${getEnvVarName('ollama.model')} env var`}>
                      ENV
                    </span>
                  )}
                </label>
                <select
                  value={llmSettings.ollama?.model || ''}
                  onChange={(e) => setLlmSettings(prev => ({
                    ...prev,
                    ollama: { ...prev.ollama, model: e.target.value }
                  }))}
                >
                  <option value="">Select...</option>
                  {getModels('chat').map(m => (
                    <option key={m.name} value={m.name}>{m.name} ({m.size_human})</option>
                  ))}
                </select>
                <small>Used for text enrichment and summaries</small>
              </div>

              <div className={styles.modelSelect}>
                <label>
                  Embedding Model
                  {isEnvLocked('ollama.embedding_model') && (
                    <span className={styles.envBadge} title={`Default from ${getEnvVarName('ollama.embedding_model')} env var`}>
                      ENV
                    </span>
                  )}
                </label>
                <select
                  value={llmSettings.ollama?.embedding_model || ''}
                  onChange={(e) => setLlmSettings(prev => ({
                    ...prev,
                    ollama: { ...prev.ollama, embedding_model: e.target.value }
                  }))}
                >
                  <option value="">Select...</option>
                  {getModels('embedding').map(m => (
                    <option key={m.name} value={m.name}>{m.name} ({m.size_human})</option>
                  ))}
                </select>
                <small>Used for semantic search (must match existing!)</small>
              </div>

              <div className={styles.modelSelect}>
                <label>
                  Vision Model
                  {isEnvLocked('ollama.vision_model') && (
                    <span className={styles.envBadge} title={`Default from ${getEnvVarName('ollama.vision_model')} env var`}>
                      ENV
                    </span>
                  )}
                </label>
                <select
                  value={llmSettings.ollama?.vision_model || ''}
                  onChange={(e) => setLlmSettings(prev => ({
                    ...prev,
                    ollama: { ...prev.ollama, vision_model: e.target.value }
                  }))}
                >
                  <option value="">Select...</option>
                  {getModels('vision').map(m => (
                    <option key={m.name} value={m.name}>{m.name} ({m.size_human})</option>
                  ))}
                </select>
                <small>Used for image analysis</small>
              </div>
            </div>

            <div className={styles.actions}>
              <button className={styles.saveBtn} onClick={saveLLMSettings} disabled={saving}>
                {saving ? <Loader2 className={styles.spinner} size={16} /> : <Check size={16} />}
                Save Models
              </button>
            </div>

            {/* Cloud Providers (collapsed) */}
            <details className={styles.cloudProviders}>
              <summary><Cloud size={14} /> Cloud API Providers (Optional)</summary>
              <div className={styles.cloudContent}>
                <div className={styles.cloudProvider}>
                  <h4>OpenAI</h4>
                  <div className={styles.apiKeyRow}>
                    <input
                      type={showApiKey.openai ? 'text' : 'password'}
                      value={llmSettings.openai?.api_key || ''}
                      onChange={(e) => setLlmSettings(prev => ({
                        ...prev,
                        openai: { ...prev.openai, api_key: e.target.value }
                      }))}
                      placeholder="sk-..."
                    />
                    <button onClick={() => setShowApiKey(p => ({ ...p, openai: !p.openai }))}>
                      {showApiKey.openai ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                </div>
                <div className={styles.cloudProvider}>
                  <h4>Anthropic</h4>
                  <div className={styles.apiKeyRow}>
                    <input
                      type={showApiKey.anthropic ? 'text' : 'password'}
                      value={llmSettings.anthropic?.api_key || ''}
                      onChange={(e) => setLlmSettings(prev => ({
                        ...prev,
                        anthropic: { ...prev.anthropic, api_key: e.target.value }
                      }))}
                      placeholder="sk-ant-..."
                    />
                    <button onClick={() => setShowApiKey(p => ({ ...p, anthropic: !p.anthropic }))}>
                      {showApiKey.anthropic ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                </div>
              </div>
            </details>

            {/* Model Library - Download New Models */}
            <div className={styles.modelLibrary}>
              <div className={styles.sectionHeader}>
                <div>
                  <h3><Download size={18} /> Model Library</h3>
                  <p className={styles.description}>
                    Browse and install models from the catalog.
                  </p>
                </div>
                <button onClick={loadModelCatalog} disabled={loadingCatalog} className={styles.refreshBtn}>
                  {loadingCatalog ? <Loader2 size={16} className={styles.spinner} /> : <RefreshCw size={16} />}
                </button>
              </div>

              {/* GPU VRAM Info & Selector */}
              <div className={styles.vramSelector}>
                <label>Your GPU VRAM:</label>
                <select 
                  value={modelCatalog?.gpu_info?.vram_gb?.toFixed(0) || '0'}
                  onChange={(e) => {
                    const vram = parseFloat(e.target.value)
                    fetch(`${API_BASE}/settings`, {
                      method: 'PUT',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ gpu_vram_gb: vram })
                    }).then(() => loadModelCatalog())
                  }}
                  className={styles.vramSelect}
                >
                  <option value="0">CPU Only (No GPU)</option>
                  {modelCatalog?.vram_tiers?.map(tier => (
                    <option key={tier} value={tier}>{tier}GB VRAM</option>
                  ))}
                  <option value="48">48GB+ VRAM</option>
                </select>
                {modelCatalog?.gpu_info?.source === 'detected' && (
                  <span className={styles.detectedBadge}>Auto-detected</span>
                )}
                {modelCatalog?.recommendations && (
                  <span className={styles.recTip}>
                    ★ {modelCatalog.models?.filter(m => m.recommended).length} models recommended for your hardware
                  </span>
                )}
              </div>

              {/* Category Filter */}
              <div className={styles.catalogFilters}>
                <button 
                  className={`${styles.filterBtn} ${catalogFilter === 'all' ? styles.active : ''}`}
                  onClick={() => setCatalogFilter('all')}
                >
                  All
                </button>
                <button 
                  className={`${styles.filterBtn} ${styles.recommendedFilter} ${catalogFilter === 'recommended' ? styles.active : ''}`}
                  onClick={() => setCatalogFilter('recommended')}
                >
                  ★ Recommended
                </button>
                <button 
                  className={`${styles.filterBtn} ${catalogFilter === 'installed' ? styles.active : ''}`}
                  onClick={() => setCatalogFilter('installed')}
                >
                  Installed ({modelCatalog?.installed_count || 0})
                </button>
                {modelCatalog?.categories && Object.entries(modelCatalog.categories).map(([key, cat]) => (
                  <button 
                    key={key}
                    className={`${styles.filterBtn} ${catalogFilter === key ? styles.active : ''}`}
                    onClick={() => setCatalogFilter(key)}
                  >
                    {cat.name}
                  </button>
                ))}
              </div>

              {/* Model Cards */}
              <div className={styles.catalogGrid}>
                {getFilteredCatalogModels().map(model => {
                  const pullState = pullingModels[model.name]
                  const isPulling = pullState?.status === 'pulling' || pullState?.status === 'starting'
                  const isComplete = pullState?.status === 'complete'
                  
                  return (
                    <div key={model.name} className={`${styles.catalogCard} ${model.installed ? styles.installed : ''} ${model.recommended ? styles.recommended : ''}`}>
                      <div className={styles.catalogCardHeader}>
                        <h4>
                          {model.display_name}
                          {model.recommended && <span className={styles.recommendedBadge}>★ Recommended</span>}
                        </h4>
                        <span className={styles.catalogCategory}>{model.category}</span>
                      </div>
                      <p className={styles.catalogDesc}>{model.description}</p>
                      <div className={styles.catalogMeta}>
                        <span>{model.size_gb}GB</span>
                        <span>VRAM: {model.vram_required_gb}GB+</span>
                      </div>
                      <div className={styles.catalogActions}>
                        {model.installed ? (
                          <>
                            <span className={styles.installedBadge}><Check size={14} /> Installed</span>
                            <button 
                              className={styles.deleteModelBtn}
                              onClick={() => deleteModel(model.name)}
                              title="Delete model"
                            >
                              <Trash2 size={14} />
                            </button>
                          </>
                        ) : isPulling ? (
                          <div className={styles.pullProgress}>
                            <Loader2 size={14} className={styles.spinner} />
                            <span>{pullState.progress || 0}%</span>
                            <div className={styles.progressBar}>
                              <div 
                                className={styles.progressFill} 
                                style={{ width: `${pullState.progress || 0}%` }}
                              />
                            </div>
                          </div>
                        ) : isComplete ? (
                          <span className={styles.installedBadge}><Check size={14} /> Downloaded!</span>
                        ) : (
                          <button 
                            className={styles.installBtn}
                            onClick={() => pullModel(model.name)}
                          >
                            <Download size={14} /> Install
                          </button>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>

              {modelCatalog?.recommendations && (
                <div className={styles.recommendations}>
                  <div className={styles.recHeader}>
                    <h4>💡 Recommended for your GPU ({modelCatalog.recommendations.vram_tier}GB+ VRAM)</h4>
                    <button 
                      className={styles.useRecBtn}
                      onClick={() => {
                        const recs = modelCatalog.recommendations
                        setLlmSettings(prev => ({
                          ...prev,
                          ollama: {
                            ...prev.ollama,
                            model: recs.chat || prev.ollama?.model || '',
                            embedding_model: recs.embedding || prev.ollama?.embedding_model || '',
                            vision_model: recs.vision || prev.ollama?.vision_model || ''
                          }
                        }))
                      }}
                      title="Set all model selections to recommended values"
                    >
                      <Check size={14} /> Use Recommended
                    </button>
                  </div>
                  <div className={styles.recList}>
                    {modelCatalog.recommendations.chat && (
                      <span>Chat: <strong>{modelCatalog.recommendations.chat}</strong></span>
                    )}
                    {modelCatalog.recommendations.embedding && (
                      <span>Embedding: <strong>{modelCatalog.recommendations.embedding}</strong></span>
                    )}
                    {modelCatalog.recommendations.vision && (
                      <span>Vision: <strong>{modelCatalog.recommendations.vision}</strong></span>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* === Sources Tab === */}
        {activeTab === 'sources' && (
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
          </div>
        )}

        {/* === File Types Tab === */}
        {activeTab === 'extensions' && (
          <div className={styles.section}>
            <h2>File Types</h2>
            <p className={styles.description}>
              Select which file types to process and index.
            </p>

            <div className={styles.extCategories}>
              {[
                { name: 'Documents', exts: ['.txt', '.md', '.pdf', '.docx', '.doc', '.html', '.rtf'] },
                { name: 'Images', exts: ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff'] },
                { name: 'E-books', exts: ['.epub', '.mobi'] },
                { name: 'Data', exts: ['.csv', '.json', '.xml', '.yaml'] }
              ].map(cat => (
                <div key={cat.name} className={styles.extCategory}>
                  <h4>{cat.name}</h4>
                  <div className={styles.extToggles}>
                    {cat.exts.map(ext => (
                      <label key={ext} className={styles.extToggle}>
                        <input
                          type="checkbox"
                          checked={extensions.includes(ext)}
                          onChange={() => toggleExtension(ext)}
                        />
                        <span>{ext}</span>
                      </label>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            {/* Custom Extension */}
            <div className={styles.customExt}>
              <input
                type="text"
                value={newExtension}
                onChange={(e) => setNewExtension(e.target.value)}
                placeholder="Add custom extension..."
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && newExtension) {
                    const ext = newExtension.startsWith('.') ? newExtension : '.' + newExtension
                    if (!extensions.includes(ext)) {
                      setExtensions([...extensions, ext])
                    }
                    setNewExtension('')
                  }
                }}
              />
            </div>

            <div className={styles.actions}>
              <button className={styles.saveBtn} onClick={saveExtensions} disabled={saving}>
                {saving ? <Loader2 className={styles.spinner} size={16} /> : <Check size={16} />}
                Save File Types
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default Settings
