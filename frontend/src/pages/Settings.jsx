import { useState, useEffect, useCallback } from 'react'
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
  Globe
} from 'lucide-react'
import styles from './Settings.module.css'

const API_BASE = '/api'

function Settings() {
  const [activeTab, setActiveTab] = useState('llm')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState(null)
  
  // LLM Settings
  const [llmSettings, setLlmSettings] = useState({
    provider: 'ollama',
    ollama: { url: 'http://ollama:11434', model: 'dolphin-phi', embedding_model: 'nomic-embed-text', vision_model: 'llava' },
    openai: { api_key: '', model: 'gpt-4o-mini', embedding_model: 'text-embedding-3-small', vision_model: 'gpt-4o' },
    anthropic: { api_key: '', model: 'claude-3-haiku-20240307' }
  })
  const [showApiKey, setShowApiKey] = useState({ openai: false, anthropic: false })
  
  // Ollama Models & Status
  const [ollamaModels, setOllamaModels] = useState([])
  const [ollamaStatus, setOllamaStatus] = useState({ connected: false, server_type: 'docker', version: null, error: null })
  const [ollamaPresets, setOllamaPresets] = useState({})
  const [popularModels, setPopularModels] = useState({ chat: [], embedding: [], vision: [] })
  const [loadingModels, setLoadingModels] = useState(false)
  const [showModelDownload, setShowModelDownload] = useState(null) // 'chat', 'embedding', 'vision', or null
  const [pullingModel, setPullingModel] = useState(null)
  const [pullProgress, setPullProgress] = useState({})
  const [customOllamaUrl, setCustomOllamaUrl] = useState('')
  
  // Source Settings
  const [sources, setSources] = useState({ include: [], exclude: [] })
  const [availableMounts, setAvailableMounts] = useState({ mounts: [], instructions: null })
  const [browsePath, setBrowsePath] = useState('/data/archive')
  const [browseItems, setBrowseItems] = useState([])
  const [showFolderBrowser, setShowFolderBrowser] = useState(false)
  const [newFolder, setNewFolder] = useState('')
  const [newExclude, setNewExclude] = useState('')
  
  // Extension Settings
  const [extensions, setExtensions] = useState([])
  const [newExtension, setNewExtension] = useState('')

  useEffect(() => {
    loadSettings()
  }, [])

  // Poll for pull progress
  useEffect(() => {
    if (!pullingModel) return
    
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/settings/ollama/models/pull/${encodeURIComponent(pullingModel)}`)
        if (res.ok) {
          const data = await res.json()
          setPullProgress(prev => ({ ...prev, [pullingModel]: data }))
          
          if (data.status === 'complete' || data.status === 'error') {
            setPullingModel(null)
            if (data.status === 'complete') {
              loadOllamaModels()
            }
          }
        }
      } catch (err) {
        console.error('Failed to get pull status:', err)
      }
    }, 1000)
    
    return () => clearInterval(interval)
  }, [pullingModel])

  const loadSettings = async () => {
    setLoading(true)
    try {
      const [llmRes, sourcesRes, extRes, presetsRes, mountsRes] = await Promise.all([
        fetch(`${API_BASE}/settings/llm`),
        fetch(`${API_BASE}/settings/sources`),
        fetch(`${API_BASE}/settings/extensions`),
        fetch(`${API_BASE}/settings/ollama/presets`),
        fetch(`${API_BASE}/settings/sources/mounts`)
      ])
      
      if (llmRes.ok) {
        const data = await llmRes.json()
        setLlmSettings(prev => ({ ...prev, ...data }))
      }
      if (sourcesRes.ok) {
        setSources(await sourcesRes.json())
      }
      if (extRes.ok) {
        const data = await extRes.json()
        setExtensions(data.extensions || [])
      }
      if (presetsRes.ok) {
        setOllamaPresets(await presetsRes.json())
      }
      if (mountsRes.ok) {
        setAvailableMounts(await mountsRes.json())
      }
      
      // Load Ollama status and models
      await loadOllamaStatus()
      await loadOllamaModels()
      await loadPopularModels()
    } catch (err) {
      console.error('Failed to load settings:', err)
    }
    setLoading(false)
  }

  const loadOllamaStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/settings/ollama/status`)
      if (res.ok) {
        const data = await res.json()
        setOllamaStatus(data)
      }
    } catch (err) {
      console.error('Failed to load Ollama status:', err)
      setOllamaStatus(prev => ({ ...prev, connected: false, error: 'Failed to check status' }))
    }
  }

  const loadBrowseItems = async (path) => {
    try {
      const res = await fetch(`${API_BASE}/settings/sources/browse?path=${encodeURIComponent(path)}`)
      if (res.ok) {
        const data = await res.json()
        setBrowsePath(data.current_path)
        setBrowseItems(data.items)
      }
    } catch (err) {
      console.error('Failed to browse directory:', err)
    }
  }

  const openFolderBrowser = () => {
    setShowFolderBrowser(true)
    loadBrowseItems('/data/archive')
  }

  const loadOllamaModels = async () => {
    setLoadingModels(true)
    try {
      const res = await fetch(`${API_BASE}/settings/ollama/models`)
      if (res.ok) {
        const data = await res.json()
        setOllamaModels(data.models || [])
      }
    } catch (err) {
      console.error('Failed to load Ollama models:', err)
    }
    setLoadingModels(false)
  }

  const loadPopularModels = async () => {
    try {
      const res = await fetch(`${API_BASE}/settings/ollama/models/popular`)
      if (res.ok) {
        setPopularModels(await res.json())
      }
    } catch (err) {
      console.error('Failed to load popular models:', err)
    }
  }

  const setOllamaPreset = async (preset, customUrl = null) => {
    setLoadingModels(true)
    try {
      const res = await fetch(`${API_BASE}/settings/ollama/preset`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ preset, custom_url: customUrl })
      })
      if (res.ok) {
        const data = await res.json()
        setLlmSettings(prev => ({
          ...prev,
          ollama: { ...prev.ollama, url: data.url }
        }))
        await loadOllamaStatus()
        await loadOllamaModels()
      }
    } catch (err) {
      console.error('Failed to set Ollama preset:', err)
    }
    setLoadingModels(false)
  }

  const pullModel = async (modelName) => {
    setPullingModel(modelName)
    setPullProgress(prev => ({ ...prev, [modelName]: { status: 'starting', progress: 0, message: 'Starting download...' } }))
    
    try {
      const res = await fetch(`${API_BASE}/settings/ollama/models/pull`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: modelName })
      })
      if (!res.ok) {
        const data = await res.json()
        setPullProgress(prev => ({ ...prev, [modelName]: { status: 'error', message: data.detail || 'Failed to start download' } }))
        setPullingModel(null)
      }
    } catch (err) {
      setPullProgress(prev => ({ ...prev, [modelName]: { status: 'error', message: err.message } }))
      setPullingModel(null)
    }
  }

  const deleteModel = async (modelName) => {
    if (!confirm(`Delete model "${modelName}"?\nThis will free up disk space but the model will need to be re-downloaded to use again.`)) return
    
    try {
      const res = await fetch(`${API_BASE}/settings/ollama/models/${encodeURIComponent(modelName)}`, {
        method: 'DELETE'
      })
      if (res.ok) {
        loadOllamaModels()
      } else {
        const data = await res.json()
        alert(data.detail || 'Failed to delete model')
      }
    } catch (err) {
      alert('Failed to delete model: ' + err.message)
    }
  }

  const getModelsForCapability = useCallback((capability) => {
    return ollamaModels.filter(m => m.capabilities?.[capability])
  }, [ollamaModels])

  const saveLLMSettings = async () => {
    setSaving(true)
    try {
      const res = await fetch(`${API_BASE}/settings/llm`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(llmSettings)
      })
      if (!res.ok) throw new Error('Failed to save')
      setTestResult({ status: 'success', message: 'Settings saved!' })
      setTimeout(() => setTestResult(null), 3000)
    } catch (err) {
      setTestResult({ status: 'error', message: 'Failed to save settings' })
    }
    setSaving(false)
  }

  const testConnection = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      await fetch(`${API_BASE}/settings/llm`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(llmSettings)
      })
      
      const res = await fetch(`${API_BASE}/settings/llm/test`, { method: 'POST' })
      const data = await res.json()
      setTestResult(data)
      
      if (data.status === 'connected') {
        loadOllamaModels()
      }
    } catch (err) {
      setTestResult({ status: 'error', message: 'Test failed: ' + err.message })
    }
    setTesting(false)
  }

  const addSourceFolder = async () => {
    if (!newFolder.trim()) return
    await addSourceFolderDirect(newFolder.trim())
    setNewFolder('')
  }

  const addSourceFolderDirect = async (path) => {
    try {
      const res = await fetch(`${API_BASE}/settings/sources/include`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path })
      })
      if (res.ok) {
        loadSettings()
      } else {
        const data = await res.json()
        alert(data.detail || 'Failed to add folder')
      }
    } catch (err) {
      alert('Failed to add folder: ' + err.message)
    }
  }

  const removeSourceFolder = async (path) => {
    if (!confirm(`Remove source folder?\n${path}`)) return
    try {
      const res = await fetch(`${API_BASE}/settings/sources/include`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path })
      })
      if (res.ok) loadSettings()
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
      const res = await fetch(`${API_BASE}/settings/sources/exclude`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pattern })
      })
      if (res.ok) loadSettings()
    } catch (err) {
      alert('Failed to remove pattern')
    }
  }

  const saveExtensions = async () => {
    setSaving(true)
    try {
      const res = await fetch(`${API_BASE}/settings/extensions`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ extensions })
      })
      if (res.ok) {
        setTestResult({ status: 'success', message: 'Extensions saved!' })
        setTimeout(() => setTestResult(null), 3000)
      }
    } catch (err) {
      alert('Failed to save extensions')
    }
    setSaving(false)
  }

  const addExtension = () => {
    let ext = newExtension.trim()
    if (!ext) return
    if (!ext.startsWith('.')) ext = '.' + ext
    if (!extensions.includes(ext)) {
      setExtensions([...extensions, ext])
    }
    setNewExtension('')
  }

  const removeExtension = (ext) => {
    setExtensions(extensions.filter(e => e !== ext))
  }

  // Custom model input
  const [customModel, setCustomModel] = useState('')

  // Model selector component for Ollama
  const ModelSelector = ({ label, capability, value, onChange, description }) => {
    const availableModels = getModelsForCapability(capability)
    const isInstalled = availableModels.some(m => m.name === value || m.name.startsWith(value + ':'))
    
    const handleCustomDownload = () => {
      if (customModel.trim()) {
        pullModel(customModel.trim())
        setCustomModel('')
      }
    }
    
    return (
      <div className={styles.modelSelector}>
        <label>{label}</label>
        <div className={styles.modelSelectRow}>
          <select
            value={value}
            onChange={(e) => onChange(e.target.value)}
            className={!isInstalled && value ? styles.modelMissing : ''}
          >
            {!value && <option value="">Select a model...</option>}
            {value && !availableModels.some(m => m.name === value) && (
              <option value={value}>{value} (not installed)</option>
            )}
            {availableModels.map(m => (
              <option key={m.name} value={m.name}>
                {m.name} ({m.parameter_size || m.size_human})
              </option>
            ))}
          </select>
          <button
            type="button"
            className={styles.downloadBtn}
            onClick={() => setShowModelDownload(showModelDownload === capability ? null : capability)}
            title="Download new model"
          >
            <Download size={16} />
          </button>
          {loadingModels && <Loader2 size={16} className={styles.spinner} />}
        </div>
        {!isInstalled && value && (
          <small className={styles.modelWarning}>
            <AlertCircle size={12} /> Model not installed. 
            <button onClick={() => pullModel(value)}>Download now</button>
          </small>
        )}
        {description && <small>{description}</small>}
        
        {/* Download panel */}
        {showModelDownload === capability && (
          <div className={styles.downloadPanel}>
            <div className={styles.downloadHeader}>
              <h4>Download {capability} model</h4>
              <button onClick={() => setShowModelDownload(null)}><X size={16} /></button>
            </div>
            
            {/* Custom model input */}
            <div className={styles.customModelRow}>
              <input
                type="text"
                placeholder="Enter any model name (e.g., llama3:8b)"
                value={customModel}
                onChange={(e) => setCustomModel(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleCustomDownload()}
              />
              <button 
                onClick={handleCustomDownload}
                disabled={!customModel.trim() || !!pullingModel}
                className={styles.pullBtn}
              >
                <Download size={14} /> Pull
              </button>
            </div>
            <small className={styles.customModelHint}>
              Browse all models at <a href="https://ollama.com/library" target="_blank" rel="noopener noreferrer">ollama.com/library</a>
            </small>
            
            <div className={styles.popularModelsHeader}>Popular {capability} models:</div>
            <div className={styles.popularModels}>
              {popularModels[capability]?.map(m => {
                const isDownloaded = ollamaModels.some(om => om.name === m.name || om.name.startsWith(m.name + ':'))
                const progress = pullProgress[m.name]
                const isPulling = pullingModel === m.name
                
                return (
                  <div key={m.name} className={`${styles.popularModel} ${isDownloaded ? styles.downloaded : ''}`}>
                    <div className={styles.modelInfo}>
                      <span className={styles.modelName}>{m.name}</span>
                      <span className={styles.modelDesc}>{m.description}</span>
                      <span className={styles.modelSize}>{m.size}</span>
                    </div>
                    {isDownloaded ? (
                      <span className={styles.installedBadge}><Check size={14} /> Installed</span>
                    ) : isPulling ? (
                      <div className={styles.pullProgress}>
                        <Loader2 size={14} className={styles.spinner} />
                        <span>{progress?.progress || 0}%</span>
                        <div className={styles.progressBar}>
                          <div style={{ width: `${progress?.progress || 0}%` }} />
                        </div>
                      </div>
                    ) : progress?.status === 'complete' ? (
                      <span className={styles.installedBadge}><Check size={14} /> Done</span>
                    ) : progress?.status === 'error' ? (
                      <span className={styles.errorBadge} title={progress.message}>Error</span>
                    ) : (
                      <button 
                        className={styles.pullBtn}
                        onClick={() => pullModel(m.name)}
                        disabled={!!pullingModel}
                      >
                        <Download size={14} /> Download
                      </button>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>
    )
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
        <h1><SettingsIcon /> Settings</h1>
        <p>Configure your Archive Brain instance</p>
      </header>

      <div className={styles.tabs}>
        <button 
          className={`${styles.tab} ${activeTab === 'llm' ? styles.active : ''}`}
          onClick={() => setActiveTab('llm')}
        >
          <Server size={18} /> LLM Provider
        </button>
        <button 
          className={`${styles.tab} ${activeTab === 'sources' ? styles.active : ''}`}
          onClick={() => setActiveTab('sources')}
        >
          <FolderPlus size={18} /> Source Folders
        </button>
        <button 
          className={`${styles.tab} ${activeTab === 'extensions' ? styles.active : ''}`}
          onClick={() => setActiveTab('extensions')}
        >
          <FileType size={18} /> File Types
        </button>
      </div>

      <div className={styles.content}>
        {/* LLM Provider Tab */}
        {activeTab === 'llm' && (
          <div className={styles.section}>
            <h2>LLM Provider Configuration</h2>
            <p className={styles.description}>
              Choose your AI provider for text enrichment, embeddings, and image analysis.
              The built-in Ollama is recommended for privacy and no API costs.
            </p>

            <div className={styles.providerSelect}>
              <label>Active Provider</label>
              <div className={styles.providerButtons}>
                <button
                  className={`${styles.providerBtn} ${llmSettings.provider === 'ollama' ? styles.selected : ''}`}
                  onClick={() => setLlmSettings(prev => ({ ...prev, provider: 'ollama' }))}
                >
                  <Server size={20} />
                  <span>Ollama</span>
                  <small>Self-hosted, Free</small>
                </button>
                <button
                  className={`${styles.providerBtn} ${llmSettings.provider === 'openai' ? styles.selected : ''}`}
                  onClick={() => setLlmSettings(prev => ({ ...prev, provider: 'openai' }))}
                >
                  <Cloud size={20} />
                  <span>OpenAI</span>
                  <small>GPT-4, Fast</small>
                </button>
                <button
                  className={`${styles.providerBtn} ${llmSettings.provider === 'anthropic' ? styles.selected : ''}`}
                  onClick={() => setLlmSettings(prev => ({ ...prev, provider: 'anthropic' }))}
                >
                  <Cloud size={20} />
                  <span>Anthropic</span>
                  <small>Claude, Quality</small>
                </button>
              </div>
            </div>

            {/* Ollama Settings */}
            {llmSettings.provider === 'ollama' && (
              <div className={styles.providerConfig}>
                <h3><Server size={16} /> Ollama Configuration</h3>
                
                {/* Connection Status Banner */}
                <div className={`${styles.connectionStatus} ${ollamaStatus.connected ? styles.connected : styles.disconnected}`}>
                  <div className={styles.statusIcon}>
                    {ollamaStatus.connected ? <Wifi size={20} /> : <WifiOff size={20} />}
                  </div>
                  <div className={styles.statusInfo}>
                    <div className={styles.statusMain}>
                      {ollamaStatus.connected ? (
                        <>
                          <strong>Connected</strong> to {ollamaStatus.server_type === 'docker' ? 'Docker Ollama' : 
                            ollamaStatus.server_type === 'localhost' ? 'Local Ollama' : 'Network Ollama'}
                        </>
                      ) : (
                        <>
                          <strong>Disconnected</strong> - Cannot reach Ollama server
                        </>
                      )}
                    </div>
                    <div className={styles.statusDetails}>
                      <code>{llmSettings.ollama?.url}</code>
                      {ollamaStatus.version && <span>v{ollamaStatus.version}</span>}
                      {ollamaStatus.connected && <span>{ollamaStatus.model_count} models</span>}
                      {ollamaStatus.error && <span className={styles.statusError}>{ollamaStatus.error}</span>}
                    </div>
                  </div>
                  <button 
                    onClick={loadOllamaStatus} 
                    disabled={loadingModels}
                    className={styles.refreshStatusBtn}
                    title="Refresh status"
                  >
                    {loadingModels ? <Loader2 size={16} className={styles.spinner} /> : <RefreshCw size={16} />}
                  </button>
                </div>

                {/* Server Presets */}
                <div className={styles.serverPresets}>
                  <label>Quick Connect</label>
                  <div className={styles.presetButtons}>
                    <button
                      className={`${styles.presetBtn} ${llmSettings.ollama?.url === 'http://ollama:11434' ? styles.active : ''}`}
                      onClick={() => setOllamaPreset('docker')}
                      title="Built-in Docker container"
                    >
                      <Container size={16} />
                      <span>Docker</span>
                      <small>Built-in</small>
                    </button>
                    <button
                      className={`${styles.presetBtn} ${llmSettings.ollama?.url === 'http://host.docker.internal:11434' ? styles.active : ''}`}
                      onClick={() => setOllamaPreset('localhost')}
                      title="Ollama on Windows/Mac host"
                    >
                      <Monitor size={16} />
                      <span>Host</span>
                      <small>Win/Mac</small>
                    </button>
                    <button
                      className={`${styles.presetBtn} ${llmSettings.ollama?.url === 'http://172.17.0.1:11434' ? styles.active : ''}`}
                      onClick={() => setOllamaPreset('localhost_linux')}
                      title="Ollama on Linux host"
                    >
                      <Monitor size={16} />
                      <span>Host</span>
                      <small>Linux</small>
                    </button>
                    <button
                      className={`${styles.presetBtn} ${
                        llmSettings.ollama?.url && 
                        !['http://ollama:11434', 'http://host.docker.internal:11434', 'http://172.17.0.1:11434'].includes(llmSettings.ollama?.url)
                          ? styles.active : ''
                      }`}
                      onClick={() => {
                        const url = prompt('Enter Ollama server URL:', customOllamaUrl || 'http://192.168.1.xxx:11434')
                        if (url) {
                          setCustomOllamaUrl(url)
                          setOllamaPreset('custom', url)
                        }
                      }}
                      title="Custom network server"
                    >
                      <Globe size={16} />
                      <span>Network</span>
                      <small>Custom</small>
                    </button>
                  </div>
                  <small>
                    <strong>Docker:</strong> Uses the built-in Ollama container. 
                    <strong> Host:</strong> Uses Ollama installed on your machine (outside Docker). 
                    <strong> Network:</strong> Another server on your network.
                  </small>
                </div>
                
                <div className={styles.formGroup}>
                  <label>Ollama URL (Advanced)</label>
                  <div className={styles.urlInputRow}>
                    <input
                      type="text"
                      value={llmSettings.ollama?.url || ''}
                      onChange={(e) => setLlmSettings(prev => ({
                        ...prev,
                        ollama: { ...prev.ollama, url: e.target.value }
                      }))}
                      placeholder="http://ollama:11434"
                    />
                    <button 
                      onClick={async () => {
                        await saveLLMSettings()
                        await loadOllamaStatus()
                        await loadOllamaModels()
                      }} 
                      disabled={loadingModels}
                      title="Apply and refresh"
                    >
                      {loadingModels ? <Loader2 size={16} className={styles.spinner} /> : <Check size={16} />}
                    </button>
                  </div>
                </div>

                {ollamaModels.length > 0 && (
                  <div className={styles.installedModels}>
                    <h4><HardDrive size={14} /> Installed Models ({ollamaModels.length})</h4>
                    <div className={styles.modelChips}>
                      {ollamaModels.map(m => (
                        <div key={m.name} className={styles.modelChip}>
                          <span className={styles.chipName}>{m.name}</span>
                          <span className={styles.chipSize}>{m.size_human}</span>
                          <span className={styles.chipCaps}>
                            {m.capabilities?.chat && <span title="Chat">💬</span>}
                            {m.capabilities?.embedding && <span title="Embedding">📊</span>}
                            {m.capabilities?.vision && <span title="Vision">👁️</span>}
                          </span>
                          <button 
                            onClick={() => deleteModel(m.name)} 
                            title="Delete model"
                            className={styles.deleteChip}
                          >
                            <Trash2 size={12} />
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className={styles.modelSelectors}>
                  <ModelSelector
                    label="Chat Model"
                    capability="chat"
                    value={llmSettings.ollama?.model || ''}
                    onChange={(val) => setLlmSettings(prev => ({
                      ...prev,
                      ollama: { ...prev.ollama, model: val }
                    }))}
                    description="Used for text enrichment, summaries, and analysis"
                  />
                  
                  <ModelSelector
                    label="Embedding Model"
                    capability="embedding"
                    value={llmSettings.ollama?.embedding_model || ''}
                    onChange={(val) => setLlmSettings(prev => ({
                      ...prev,
                      ollama: { ...prev.ollama, embedding_model: val }
                    }))}
                    description="Used for semantic search (must match existing embeddings!)"
                  />
                  
                  <ModelSelector
                    label="Vision Model"
                    capability="vision"
                    value={llmSettings.ollama?.vision_model || ''}
                    onChange={(val) => setLlmSettings(prev => ({
                      ...prev,
                      ollama: { ...prev.ollama, vision_model: val }
                    }))}
                    description="Used for image analysis and OCR enhancement"
                  />
                </div>
              </div>
            )}

            {/* OpenAI Settings */}
            {llmSettings.provider === 'openai' && (
              <div className={styles.providerConfig}>
                <h3><Cloud size={16} /> OpenAI Configuration</h3>
                <div className={styles.formGroup}>
                  <label>API Key</label>
                  <div className={styles.apiKeyInput}>
                    <input
                      type={showApiKey.openai ? 'text' : 'password'}
                      value={llmSettings.openai?.api_key || ''}
                      onChange={(e) => setLlmSettings(prev => ({
                        ...prev,
                        openai: { ...prev.openai, api_key: e.target.value }
                      }))}
                      placeholder="sk-..."
                    />
                    <button 
                      type="button"
                      onClick={() => setShowApiKey(prev => ({ ...prev, openai: !prev.openai }))}
                    >
                      {showApiKey.openai ? <EyeOff size={18} /> : <Eye size={18} />}
                    </button>
                  </div>
                  <small>Get your API key from <a href="https://platform.openai.com/api-keys" target="_blank" rel="noopener">OpenAI Dashboard</a></small>
                </div>
                <div className={styles.formRow}>
                  <div className={styles.formGroup}>
                    <label>Chat Model</label>
                    <select
                      value={llmSettings.openai?.model || 'gpt-4o-mini'}
                      onChange={(e) => setLlmSettings(prev => ({
                        ...prev,
                        openai: { ...prev.openai, model: e.target.value }
                      }))}
                    >
                      <option value="gpt-4o-mini">GPT-4o Mini (Fast, Cheap)</option>
                      <option value="gpt-4o">GPT-4o (Best)</option>
                      <option value="gpt-4-turbo">GPT-4 Turbo</option>
                      <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
                    </select>
                  </div>
                  <div className={styles.formGroup}>
                    <label>Embedding Model</label>
                    <select
                      value={llmSettings.openai?.embedding_model || 'text-embedding-3-small'}
                      onChange={(e) => setLlmSettings(prev => ({
                        ...prev,
                        openai: { ...prev.openai, embedding_model: e.target.value }
                      }))}
                    >
                      <option value="text-embedding-3-small">text-embedding-3-small</option>
                      <option value="text-embedding-3-large">text-embedding-3-large</option>
                      <option value="text-embedding-ada-002">text-embedding-ada-002</option>
                    </select>
                  </div>
                </div>
              </div>
            )}

            {/* Anthropic Settings */}
            {llmSettings.provider === 'anthropic' && (
              <div className={styles.providerConfig}>
                <h3><Cloud size={16} /> Anthropic Configuration</h3>
                <div className={styles.formGroup}>
                  <label>API Key</label>
                  <div className={styles.apiKeyInput}>
                    <input
                      type={showApiKey.anthropic ? 'text' : 'password'}
                      value={llmSettings.anthropic?.api_key || ''}
                      onChange={(e) => setLlmSettings(prev => ({
                        ...prev,
                        anthropic: { ...prev.anthropic, api_key: e.target.value }
                      }))}
                      placeholder="sk-ant-..."
                    />
                    <button 
                      type="button"
                      onClick={() => setShowApiKey(prev => ({ ...prev, anthropic: !prev.anthropic }))}
                    >
                      {showApiKey.anthropic ? <EyeOff size={18} /> : <Eye size={18} />}
                    </button>
                  </div>
                  <small>Get your API key from <a href="https://console.anthropic.com/" target="_blank" rel="noopener">Anthropic Console</a></small>
                </div>
                <div className={styles.formGroup}>
                  <label>Model</label>
                  <select
                    value={llmSettings.anthropic?.model || 'claude-3-haiku-20240307'}
                    onChange={(e) => setLlmSettings(prev => ({
                      ...prev,
                      anthropic: { ...prev.anthropic, model: e.target.value }
                    }))}
                  >
                    <option value="claude-3-haiku-20240307">Claude 3 Haiku (Fast)</option>
                    <option value="claude-3-sonnet-20240229">Claude 3 Sonnet (Balanced)</option>
                    <option value="claude-3-opus-20240229">Claude 3 Opus (Best)</option>
                  </select>
                </div>
                <p className={styles.note}>
                  <AlertCircle size={14} /> Note: Anthropic doesn't provide embeddings. 
                  Ollama will be used for embeddings when Anthropic is selected.
                </p>
              </div>
            )}

            {/* Test Result */}
            {testResult && (
              <div className={`${styles.testResult} ${styles[testResult.status]}`}>
                {testResult.status === 'connected' || testResult.status === 'success' ? (
                  <Check size={18} />
                ) : (
                  <AlertCircle size={18} />
                )}
                <span>{testResult.message}</span>
                {testResult.models?.length > 0 && (
                  <small>Available models: {testResult.models.slice(0, 5).join(', ')}</small>
                )}
              </div>
            )}

            <div className={styles.actions}>
              <button 
                className={styles.testBtn}
                onClick={testConnection}
                disabled={testing}
              >
                {testing ? <Loader2 className={styles.spinner} /> : <RefreshCw size={18} />}
                Test Connection
              </button>
              <button 
                className={styles.saveBtn}
                onClick={saveLLMSettings}
                disabled={saving}
              >
                {saving ? <Loader2 className={styles.spinner} /> : <Check size={18} />}
                Save Settings
              </button>
            </div>
          </div>
        )}

        {/* Source Folders Tab */}
        {activeTab === 'sources' && (
          <div className={styles.section}>
            <h2>Source Folders</h2>
            <p className={styles.description}>
              Configure which folders Archive Brain should scan for documents.
              All files matching the enabled extensions will be processed.
            </p>

            {/* Available Mounts Section */}
            <div className={styles.mountsSection}>
              <h3><HardDrive size={16} /> Available Folders</h3>
              <p className={styles.mountsDescription}>
                These folders are mounted from your host system and available for indexing.
                Click to add as a source folder.
              </p>
              
              {availableMounts.mounts?.length > 0 ? (
                <div className={styles.mountsList}>
                  {availableMounts.mounts.map((mount, idx) => {
                    const isAdded = sources.include?.some(s => s.path === mount.path)
                    return (
                      <div 
                        key={idx} 
                        className={`${styles.mountItem} ${isAdded ? styles.added : ''} ${!mount.accessible ? styles.inaccessible : ''}`}
                      >
                        <div className={styles.mountInfo}>
                          <span className={styles.mountName}>{mount.name}</span>
                          <span className={styles.mountPath}>{mount.path}</span>
                          <span className={styles.mountStats}>
                            {mount.file_count} files, {mount.subdir_count} folders
                          </span>
                        </div>
                        {isAdded ? (
                          <span className={styles.addedBadge}><Check size={14} /> Added</span>
                        ) : mount.accessible ? (
                          <button 
                            className={styles.addMountBtn}
                            onClick={() => addSourceFolderDirect(mount.path)}
                          >
                            <Plus size={14} /> Add
                          </button>
                        ) : (
                          <span className={styles.inaccessibleBadge}>No Access</span>
                        )}
                      </div>
                    )
                  })}
                </div>
              ) : (
                <div className={styles.noMounts}>
                  <AlertCircle size={24} />
                  <p>No folders are currently mounted.</p>
                </div>
              )}

              {/* Instructions for adding mounts */}
              <details className={styles.mountInstructions}>
                <summary>📁 How to add folders from your computer</summary>
                <div className={styles.instructionsContent}>
                  <p>
                    Since Archive Brain runs in Docker, you need to mount host folders 
                    into the container. Here's how:
                  </p>
                  <ol>
                    {availableMounts.instructions?.steps?.map((step, i) => (
                      <li key={i}>{step}</li>
                    ))}
                  </ol>
                  <div className={styles.codeExample}>
                    <strong>Example (add to docker-compose.yml under worker and api volumes):</strong>
                    <code>{availableMounts.instructions?.example || '- /your/path:/data/archive/yourfolder'}</code>
                  </div>
                  <div className={styles.commonPaths}>
                    <strong>Common mount examples:</strong>
                    <ul>
                      <li><code>- ~/Documents:/data/archive/documents</code> - Your Documents folder</li>
                      <li><code>- /mnt/nas/files:/data/archive/nas</code> - Network drive</li>
                      <li><code>- D:/Archives:/data/archive/archives</code> - Windows drive (WSL)</li>
                    </ul>
                  </div>
                </div>
              </details>
            </div>

            {/* Current Source Folders */}
            <div className={styles.folderList}>
              <h3>Active Source Folders</h3>
              {sources.include?.length > 0 ? (
                sources.include.map((folder, idx) => (
                  <div key={idx} className={styles.folderItem}>
                    <div className={styles.folderInfo}>
                      <span className={`${styles.status} ${folder.exists ? styles.ok : styles.missing}`}>
                        {folder.exists ? <Check size={14} /> : <X size={14} />}
                      </span>
                      <span className={styles.path}>{folder.path}</span>
                      {folder.exists && <span className={styles.count}>{folder.file_count} files</span>}
                    </div>
                    <button 
                      className={styles.removeBtn}
                      onClick={() => removeSourceFolder(folder.path)}
                      title="Remove folder"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                ))
              ) : (
                <p className={styles.noFolders}>No source folders configured. Add folders from the list above.</p>
              )}
              
              {/* Manual path input */}
              <details className={styles.manualAdd}>
                <summary>Add folder by path (advanced)</summary>
                <div className={styles.addFolder}>
                  <input
                    type="text"
                    value={newFolder}
                    onChange={(e) => setNewFolder(e.target.value)}
                    placeholder="/data/archive/foldername"
                    onKeyDown={(e) => e.key === 'Enter' && addSourceFolder()}
                  />
                  <button onClick={addSourceFolder}>
                    <FolderPlus size={18} /> Add
                  </button>
                </div>
              </details>
            </div>

            <div className={styles.folderList}>
              <h3>Exclude Patterns</h3>
              <p className={styles.description}>
                Glob patterns for files and folders to skip during scanning.
              </p>
              <div className={styles.excludeList}>
                {sources.exclude?.map((pattern, idx) => (
                  <div key={idx} className={styles.excludeItem}>
                    <code>{pattern}</code>
                    <button onClick={() => removeExcludePattern(pattern)}>
                      <X size={14} />
                    </button>
                  </div>
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
                <button onClick={addExcludePattern}>
                  <Plus size={18} /> Add Pattern
                </button>
              </div>
            </div>
          </div>
        )}

        {/* File Types Tab */}
        {activeTab === 'extensions' && (
          <div className={styles.section}>
            <h2>File Types</h2>
            <p className={styles.description}>
              Configure which file extensions Archive Brain should process.
            </p>

            <div className={styles.extensionCategories}>
              <div className={styles.category}>
                <h4>Text Documents</h4>
                <div className={styles.extGroup}>
                  {['.txt', '.md', '.html', '.rtf'].map(ext => (
                    <label key={ext} className={styles.extToggle}>
                      <input
                        type="checkbox"
                        checked={extensions.includes(ext)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setExtensions([...extensions, ext])
                          } else {
                            setExtensions(extensions.filter(e => e !== ext))
                          }
                        }}
                      />
                      <span>{ext}</span>
                    </label>
                  ))}
                </div>
              </div>

              <div className={styles.category}>
                <h4>Office Documents</h4>
                <div className={styles.extGroup}>
                  {['.pdf', '.docx', '.doc', '.odt', '.xlsx', '.xls'].map(ext => (
                    <label key={ext} className={styles.extToggle}>
                      <input
                        type="checkbox"
                        checked={extensions.includes(ext)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setExtensions([...extensions, ext])
                          } else {
                            setExtensions(extensions.filter(e => e !== ext))
                          }
                        }}
                      />
                      <span>{ext}</span>
                    </label>
                  ))}
                </div>
              </div>

              <div className={styles.category}>
                <h4>Images (OCR + Vision AI)</h4>
                <div className={styles.extGroup}>
                  {['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.tif'].map(ext => (
                    <label key={ext} className={styles.extToggle}>
                      <input
                        type="checkbox"
                        checked={extensions.includes(ext)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setExtensions([...extensions, ext])
                          } else {
                            setExtensions(extensions.filter(e => e !== ext))
                          }
                        }}
                      />
                      <span>{ext}</span>
                    </label>
                  ))}
                </div>
              </div>

              <div className={styles.category}>
                <h4>E-books</h4>
                <div className={styles.extGroup}>
                  {['.epub', '.mobi'].map(ext => (
                    <label key={ext} className={styles.extToggle}>
                      <input
                        type="checkbox"
                        checked={extensions.includes(ext)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setExtensions([...extensions, ext])
                          } else {
                            setExtensions(extensions.filter(e => e !== ext))
                          }
                        }}
                      />
                      <span>{ext}</span>
                    </label>
                  ))}
                </div>
              </div>
            </div>

            <div className={styles.customExt}>
              <h4>Custom Extension</h4>
              <div className={styles.addExt}>
                <input
                  type="text"
                  value={newExtension}
                  onChange={(e) => setNewExtension(e.target.value)}
                  placeholder=".xyz"
                  onKeyDown={(e) => e.key === 'Enter' && addExtension()}
                />
                <button onClick={addExtension}>
                  <Plus size={18} /> Add
                </button>
              </div>
            </div>

            <div className={styles.currentExt}>
              <h4>Currently Enabled ({extensions.length})</h4>
              <div className={styles.extList}>
                {extensions.sort().map(ext => (
                  <span key={ext} className={styles.extBadge}>
                    {ext}
                    <button onClick={() => removeExtension(ext)}>
                      <X size={12} />
                    </button>
                  </span>
                ))}
              </div>
            </div>

            <div className={styles.actions}>
              <button 
                className={styles.saveBtn}
                onClick={saveExtensions}
                disabled={saving}
              >
                {saving ? <Loader2 className={styles.spinner} /> : <Check size={18} />}
                Save Extensions
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default Settings
