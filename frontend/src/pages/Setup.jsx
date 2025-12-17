import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Rocket,
  CheckCircle2,
  AlertCircle,
  ArrowRight,
  ArrowLeft,
  Server,
  FolderOpen,
  Zap,
  FileType,
  Play,
  Loader2,
  RefreshCw,
  Info,
  Settings,
  ChevronDown,
  ChevronUp
} from 'lucide-react'
import styles from './Setup.module.css'

const API_BASE = '/api'

// Step definitions
const STEPS = [
  { id: 'welcome', title: 'Welcome', icon: Rocket },
  { id: 'health', title: 'System Check', icon: CheckCircle2 },
  { id: 'llm', title: 'LLM Provider', icon: Server },
  { id: 'sources', title: 'Source Folders', icon: FolderOpen },
  { id: 'indexing', title: 'Indexing Mode', icon: Zap },
  { id: 'extensions', title: 'File Types', icon: FileType },
  { id: 'start', title: 'Start Processing', icon: Play }
]

function Setup() {
  const navigate = useNavigate()
  const [currentStep, setCurrentStep] = useState(0)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  
  // Health check data
  const [healthData, setHealthData] = useState(null)
  const [healthLoading, setHealthLoading] = useState(false)
  
  // First-run data
  const [firstRunData, setFirstRunData] = useState(null)
  
  // LLM Settings
  const [llmProvider, setLlmProvider] = useState('ollama')
  const [ollamaModels, setOllamaModels] = useState([])
  const [selectedModel, setSelectedModel] = useState('')
  const [selectedEmbeddingModel, setSelectedEmbeddingModel] = useState('nomic-embed-text')
  const [loadingModels, setLoadingModels] = useState(false)
  
  // Source folders
  const [availableMounts, setAvailableMounts] = useState([])
  const [selectedFolders, setSelectedFolders] = useState([])
  const [sourcesData, setSourcesData] = useState({ include: [], exclude: [] })
  
  // Indexing mode
  const [indexingMode, setIndexingMode] = useState('fast_scan')
  
  // File types
  const [extensions, setExtensions] = useState([])
  const [extensionPreset, setExtensionPreset] = useState('documents')
  
  // Advanced panel visibility
  const [showAdvanced, setShowAdvanced] = useState(false)
  
  // Environment variable overrides
  const [envOverrides, setEnvOverrides] = useState({})

  useEffect(() => {
    loadInitialData()
  }, [])

  const loadInitialData = async () => {
    setLoading(true)
    try {
      // Check first-run status
      const firstRunRes = await fetch(`${API_BASE}/system/first-run`)
      if (firstRunRes.ok) {
        const data = await firstRunRes.json()
        setFirstRunData(data)
        
        // If setup is already complete, redirect to home
        if (data.setup_complete) {
          navigate('/')
          return
        }
        
        // Pre-populate with current settings
        setIndexingMode(data.indexing_mode || 'fast_scan')
        if (data.current_settings?.source_folders) {
          setSelectedFolders(data.current_settings.source_folders)
        }
        if (data.current_settings?.extensions) {
          setExtensions(data.current_settings.extensions)
        }
      }
      
      // Load available mounts
      const mountsRes = await fetch(`${API_BASE}/settings/sources/mounts`)
      if (mountsRes.ok) {
        const data = await mountsRes.json()
        setAvailableMounts(data.mounts || [])
      }
      
      // Load sources
      const sourcesRes = await fetch(`${API_BASE}/settings/sources`)
      if (sourcesRes.ok) {
        const data = await sourcesRes.json()
        setSourcesData(data)
        if (data.include?.length > 0) {
          setSelectedFolders(data.include)
        }
      }
      
      // Load extensions
      const extRes = await fetch(`${API_BASE}/settings/extensions`)
      if (extRes.ok) {
        const data = await extRes.json()
        if (data.extensions?.length > 0) {
          setExtensions(data.extensions)
        }
      }
      
      // Load env overrides
      const envRes = await fetch(`${API_BASE}/settings/env-overrides`)
      if (envRes.ok) {
        const data = await envRes.json()
        setEnvOverrides(data.overrides || {})
      }
      
      // Run health check
      await runHealthCheck()
      
      // Load Ollama models
      await loadOllamaModels()
      
    } catch (err) {
      console.error('Failed to load initial data:', err)
    }
    setLoading(false)
  }

  const runHealthCheck = async () => {
    setHealthLoading(true)
    try {
      const res = await fetch(`${API_BASE}/system/health-check`)
      if (res.ok) {
        setHealthData(await res.json())
      }
    } catch (err) {
      console.error('Health check failed:', err)
    }
    setHealthLoading(false)
  }
  
  // Check if a setting path is set by env var
  const isEnvSet = (path) => envOverrides[path]?.locked === true
  const getEnvVarName = (path) => envOverrides[path]?.env_var
  const hasAnyEnvOverrides = () => Object.keys(envOverrides).length > 0

  const loadOllamaModels = async () => {
    setLoadingModels(true)
    try {
      const res = await fetch(`${API_BASE}/settings/ollama/models`)
      if (res.ok) {
        const data = await res.json()
        const models = Array.isArray(data) ? data : (data.models || [])
        setOllamaModels(models)
        
        // Auto-select first chat model if none selected
        if (!selectedModel && models.length > 0) {
          const chatModel = models.find(m => !m.name?.includes('embed')) || models[0]
          setSelectedModel(chatModel.name || chatModel)
        }
        
        // Auto-select embedding model
        const embedModel = models.find(m => m.name?.includes('embed') || m.name?.includes('nomic'))
        if (embedModel) {
          setSelectedEmbeddingModel(embedModel.name || embedModel)
        }
      }
    } catch (err) {
      console.error('Failed to load models:', err)
    }
    setLoadingModels(false)
  }

  const toggleFolder = (folder) => {
    setSelectedFolders(prev => 
      prev.includes(folder)
        ? prev.filter(f => f !== folder)
        : [...prev, folder]
    )
  }

  const applyExtensionPreset = (preset) => {
    setExtensionPreset(preset)
    switch (preset) {
      case 'documents':
        setExtensions(['.txt', '.md', '.html', '.pdf', '.docx'])
        break
      case 'images':
        setExtensions(['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.tif'])
        break
      case 'everything':
        setExtensions([
          '.txt', '.md', '.html', '.pdf', '.docx',
          '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.tif'
        ])
        break
      default:
        break
    }
  }

  const saveSettings = async () => {
    setSaving(true)
    try {
      // Save source folders
      await fetch(`${API_BASE}/settings/sources`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          include: selectedFolders,
          exclude: sourcesData.exclude || []
        })
      })
      
      // Save extensions
      await fetch(`${API_BASE}/settings/extensions`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ extensions })
      })
      
      // Save indexing mode
      await fetch(`${API_BASE}/settings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ indexing_mode: indexingMode })
      })
      
      // If a model was selected, update LLM settings
      if (selectedModel) {
        const llmRes = await fetch(`${API_BASE}/settings/llm`)
        if (llmRes.ok) {
          const current = await llmRes.json()
          await fetch(`${API_BASE}/settings/llm`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              ...current,
              provider: llmProvider,
              ollama: {
                ...current.ollama,
                model: selectedModel,
                embedding_model: selectedEmbeddingModel
              }
            })
          })
        }
      }
      
    } catch (err) {
      console.error('Failed to save settings:', err)
    }
    setSaving(false)
  }

  const completeSetup = async () => {
    setSaving(true)
    try {
      // Save all settings first
      await saveSettings()
      
      // Mark setup as complete
      const res = await fetch(`${API_BASE}/system/complete-setup`, { method: 'POST' })
      if (res.ok) {
        // Start the worker
        await fetch(`${API_BASE}/worker/state`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ running: true })
        })
        
        // Navigate to dashboard
        navigate('/dashboard')
      }
    } catch (err) {
      console.error('Failed to complete setup:', err)
    }
    setSaving(false)
  }

  const nextStep = () => {
    if (currentStep < STEPS.length - 1) {
      setCurrentStep(currentStep + 1)
    }
  }

  const prevStep = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1)
    }
  }

  const canProceed = () => {
    switch (STEPS[currentStep].id) {
      case 'health':
        // Allow proceeding even with warnings, but not errors
        return healthData && healthData.status !== 'error'
      case 'sources':
        return selectedFolders.length > 0
      case 'extensions':
        return extensions.length > 0
      default:
        return true
    }
  }

  const getStatusColor = (status) => {
    switch (status) {
      case 'ok': return styles.statusOk
      case 'warning': return styles.statusWarning
      case 'error': return styles.statusError
      default: return ''
    }
  }

  const getStatusIcon = (status) => {
    switch (status) {
      case 'ok': return <CheckCircle2 size={18} />
      case 'warning': return <AlertCircle size={18} />
      case 'error': return <AlertCircle size={18} />
      default: return null
    }
  }

  // Render step content
  const renderStepContent = () => {
    const step = STEPS[currentStep]
    
    switch (step.id) {
      case 'welcome':
        return (
          <div className={styles.stepContent}>
            <div className={styles.welcomeHero}>
              <Rocket size={64} className={styles.heroIcon} />
              <h1>Welcome to Archive Brain</h1>
              <p className={styles.heroSubtitle}>
                Let's get your document archive set up. This wizard will guide you through
                configuring your system for optimal performance.
              </p>
            </div>
            
            <div className={styles.welcomeFeatures}>
              <div className={styles.feature}>
                <Server size={24} />
                <div>
                  <h3>Smart Indexing</h3>
                  <p>Automatically extract and organize content from your documents</p>
                </div>
              </div>
              <div className={styles.feature}>
                <Zap size={24} />
                <div>
                  <h3>Semantic Search</h3>
                  <p>Find documents by meaning, not just keywords</p>
                </div>
              </div>
              <div className={styles.feature}>
                <FolderOpen size={24} />
                <div>
                  <h3>Your Data, Your Control</h3>
                  <p>Everything runs locally - your documents never leave your machine</p>
                </div>
              </div>
            </div>
            
            {firstRunData?.has_files && (
              <div className={styles.infoBox}>
                <Info size={20} />
                <span>
                  We detected {firstRunData.file_count.toLocaleString()} existing files.
                  This wizard will help you configure how they're processed.
                </span>
              </div>
            )}
          </div>
        )
      
      case 'health':
        return (
          <div className={styles.stepContent}>
            <h2>System Health Check</h2>
            <p className={styles.stepDescription}>
              Checking your system configuration to ensure everything is ready.
            </p>
            
            {healthLoading ? (
              <div className={styles.loadingState}>
                <Loader2 size={32} className={styles.spinner} />
                <span>Running health checks...</span>
              </div>
            ) : healthData ? (
              <>
                <div className={`${styles.overallStatus} ${getStatusColor(healthData.status)}`}>
                  {getStatusIcon(healthData.status)}
                  <span>
                    {healthData.status === 'ok' && 'All systems ready!'}
                    {healthData.status === 'warning' && 'System ready with some warnings'}
                    {healthData.status === 'error' && 'Some issues need attention'}
                  </span>
                </div>
                
                <div className={styles.healthChecks}>
                  {Object.entries(healthData.checks).map(([key, check]) => (
                    <div key={key} className={`${styles.healthCheck} ${getStatusColor(check.status)}`}>
                      <div className={styles.healthCheckHeader}>
                        {getStatusIcon(check.status)}
                        <span className={styles.healthCheckName}>
                          {key.charAt(0).toUpperCase() + key.slice(1)}
                        </span>
                      </div>
                      <p className={styles.healthCheckMessage}>{check.message}</p>
                      {check.fix && (
                        <p className={styles.healthCheckFix}>
                          <strong>Fix:</strong> {check.fix}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
                
                <button 
                  className={styles.refreshButton}
                  onClick={runHealthCheck}
                  disabled={healthLoading}
                >
                  <RefreshCw size={16} />
                  Re-run Checks
                </button>
              </>
            ) : (
              <div className={styles.errorState}>
                <AlertCircle size={32} />
                <span>Failed to run health check</span>
                <button onClick={runHealthCheck}>Retry</button>
              </div>
            )}
          </div>
        )
      
      case 'llm':
        return (
          <div className={styles.stepContent}>
            <h2>LLM Configuration</h2>
            <p className={styles.stepDescription}>
              Select which AI model provider to use for document analysis.
            </p>
            
            <div className={styles.providerCards}>
              <div 
                className={`${styles.providerCard} ${llmProvider === 'ollama' ? styles.selected : ''}`}
                onClick={() => setLlmProvider('ollama')}
              >
                <Server size={32} />
                <h3>Ollama (Local)</h3>
                <p>Run models locally on your hardware. Private and free.</p>
                {llmProvider === 'ollama' && <CheckCircle2 className={styles.checkmark} />}
              </div>
              
              <div 
                className={`${styles.providerCard} ${llmProvider === 'openai' ? styles.selected : ''} ${styles.disabled}`}
                title="Coming soon"
              >
                <Server size={32} />
                <h3>OpenAI</h3>
                <p>Use GPT-4 and other OpenAI models. Requires API key.</p>
                <span className={styles.comingSoon}>Coming Soon</span>
              </div>
            </div>
            
            {llmProvider === 'ollama' && (
              <div className={styles.modelSelection}>
                <h3>Select Models</h3>
                
                {/* Env override notice */}
                {(isEnvSet('ollama.model') || isEnvSet('ollama.embedding_model')) && (
                  <div className={styles.infoBox}>
                    <Info size={20} />
                    <span>
                      Some models are pre-configured via environment variables. 
                      You can change them here or keep the defaults.
                    </span>
                  </div>
                )}
                
                {loadingModels ? (
                  <div className={styles.loadingState}>
                    <Loader2 size={24} className={styles.spinner} />
                    <span>Loading available models...</span>
                  </div>
                ) : ollamaModels.length > 0 ? (
                  <>
                    <div className={styles.formGroup}>
                      <label>
                        Chat Model
                        {isEnvSet('ollama.model') && (
                          <span className={styles.envBadge} title={`Default from ${getEnvVarName('ollama.model')}`}>
                            ENV
                          </span>
                        )}
                      </label>
                      <select 
                        value={selectedModel}
                        onChange={(e) => setSelectedModel(e.target.value)}
                      >
                        {ollamaModels.map(model => (
                          <option key={model.name || model} value={model.name || model}>
                            {model.name || model}
                          </option>
                        ))}
                      </select>
                      <span className={styles.hint}>Used for generating summaries and tags</span>
                    </div>
                    
                    <div className={styles.formGroup}>
                      <label>
                        Embedding Model
                        {isEnvSet('ollama.embedding_model') && (
                          <span className={styles.envBadge} title={`Default from ${getEnvVarName('ollama.embedding_model')}`}>
                            ENV
                          </span>
                        )}
                      </label>
                      <select 
                        value={selectedEmbeddingModel}
                        onChange={(e) => setSelectedEmbeddingModel(e.target.value)}
                      >
                        {ollamaModels.map(model => (
                          <option key={model.name || model} value={model.name || model}>
                            {model.name || model}
                          </option>
                        ))}
                      </select>
                      <span className={styles.hint}>Used for semantic search (nomic-embed-text recommended)</span>
                    </div>
                  </>
                ) : (
                  <div className={styles.warningBox}>
                    <AlertCircle size={20} />
                    <div>
                      <p>No models found in Ollama.</p>
                      <p className={styles.hint}>
                        Pull a model first: <code>ollama pull phi4-mini</code>
                      </p>
                    </div>
                  </div>
                )}
                
                <button 
                  className={styles.refreshButton}
                  onClick={loadOllamaModels}
                  disabled={loadingModels}
                >
                  <RefreshCw size={16} />
                  Refresh Models
                </button>
              </div>
            )}
          </div>
        )
      
      case 'sources':
        return (
          <div className={styles.stepContent}>
            <h2>Source Folders</h2>
            <p className={styles.stepDescription}>
              Select which folders to index. Only mounted volumes are shown.
            </p>
            
            {availableMounts.length > 0 ? (
              <div className={styles.folderList}>
                {availableMounts.map(mount => (
                  <div 
                    key={mount.path}
                    className={`${styles.folderItem} ${selectedFolders.includes(mount.path) ? styles.selected : ''}`}
                    onClick={() => toggleFolder(mount.path)}
                  >
                    <div className={styles.folderCheckbox}>
                      {selectedFolders.includes(mount.path) && <CheckCircle2 size={20} />}
                    </div>
                    <FolderOpen size={24} />
                    <div className={styles.folderInfo}>
                      <span className={styles.folderPath}>{mount.path}</span>
                      <span className={styles.folderMeta}>
                        {mount.file_count?.toLocaleString() || 0} files
                        {mount.total_size && ` • ${(mount.total_size / 1024 / 1024).toFixed(1)} MB`}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className={styles.warningBox}>
                <AlertCircle size={20} />
                <div>
                  <p>No mounted folders found.</p>
                  <p className={styles.hint}>
                    Mount volumes in docker-compose.yml and restart the container.
                  </p>
                </div>
              </div>
            )}
            
            {selectedFolders.length > 0 && (
              <div className={styles.infoBox}>
                <Info size={20} />
                <span>{selectedFolders.length} folder(s) selected for indexing</span>
              </div>
            )}
          </div>
        )
      
      case 'indexing':
        return (
          <div className={styles.stepContent}>
            <h2>Indexing Strategy</h2>
            <p className={styles.stepDescription}>
              Choose how deeply to analyze your documents. You can change this later.
            </p>
            
            <div className={styles.indexingOptions}>
              <div 
                className={`${styles.indexingOption} ${indexingMode === 'fast_scan' ? styles.selected : ''}`}
                onClick={() => setIndexingMode('fast_scan')}
              >
                <div className={styles.optionHeader}>
                  <Zap size={24} />
                  <div>
                    <h3>Fast Scan</h3>
                    <span className={styles.badge}>Recommended</span>
                  </div>
                  {indexingMode === 'fast_scan' && <CheckCircle2 className={styles.checkmark} />}
                </div>
                <p>Extract text and create embeddings only. Minimal LLM calls for quick indexing.</p>
                <ul className={styles.optionDetails}>
                  <li>✓ Text extraction</li>
                  <li>✓ Semantic search</li>
                  <li>✗ AI-generated titles</li>
                  <li>✗ Summaries & tags</li>
                </ul>
                <span className={styles.optionTiming}>~10 min for 10,000 files</span>
              </div>
              
              <div 
                className={`${styles.indexingOption} ${indexingMode === 'full_enrichment' ? styles.selected : ''}`}
                onClick={() => setIndexingMode('full_enrichment')}
              >
                <div className={styles.optionHeader}>
                  <Settings size={24} />
                  <h3>Full Enrichment</h3>
                  {indexingMode === 'full_enrichment' && <CheckCircle2 className={styles.checkmark} />}
                </div>
                <p>Complete AI analysis including titles, summaries, tags, and themes.</p>
                <ul className={styles.optionDetails}>
                  <li>✓ Text extraction</li>
                  <li>✓ Semantic search</li>
                  <li>✓ AI-generated titles</li>
                  <li>✓ Summaries & tags</li>
                </ul>
                <span className={styles.optionTiming}>~2-4 hours for 10,000 files</span>
              </div>
              
              <div 
                className={`${styles.indexingOption} ${indexingMode === 'custom' ? styles.selected : ''}`}
                onClick={() => {
                  setIndexingMode('custom')
                  setShowAdvanced(true)
                }}
              >
                <div className={styles.optionHeader}>
                  <Settings size={24} />
                  <h3>Custom</h3>
                  {indexingMode === 'custom' && <CheckCircle2 className={styles.checkmark} />}
                </div>
                <p>Fine-tune which processing steps to enable.</p>
                <span className={styles.optionTiming}>Configurable in Dashboard</span>
              </div>
            </div>
            
            {indexingMode === 'custom' && (
              <div className={styles.advancedPanel}>
                <button 
                  className={styles.advancedToggle}
                  onClick={() => setShowAdvanced(!showAdvanced)}
                >
                  {showAdvanced ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                  Advanced Options
                </button>
                
                {showAdvanced && (
                  <div className={styles.advancedContent}>
                    <p className={styles.hint}>
                      Custom processing options can be configured from the Dashboard after setup.
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>
        )
      
      case 'extensions':
        return (
          <div className={styles.stepContent}>
            <h2>File Types</h2>
            <p className={styles.stepDescription}>
              Select which file types to index.
            </p>
            
            <div className={styles.presetButtons}>
              <button 
                className={`${styles.presetButton} ${extensionPreset === 'documents' ? styles.selected : ''}`}
                onClick={() => applyExtensionPreset('documents')}
              >
                Documents Only
              </button>
              <button 
                className={`${styles.presetButton} ${extensionPreset === 'images' ? styles.selected : ''}`}
                onClick={() => applyExtensionPreset('images')}
              >
                Images Only
              </button>
              <button 
                className={`${styles.presetButton} ${extensionPreset === 'everything' ? styles.selected : ''}`}
                onClick={() => applyExtensionPreset('everything')}
              >
                Everything
              </button>
            </div>
            
            <div className={styles.extensionsList}>
              <h4>Selected Extensions</h4>
              <div className={styles.extensionTags}>
                {extensions.map(ext => (
                  <span key={ext} className={styles.extensionTag}>
                    {ext}
                  </span>
                ))}
              </div>
            </div>
            
            <div className={styles.infoBox}>
              <Info size={20} />
              <span>You can add more file types later from Settings.</span>
            </div>
          </div>
        )
      
      case 'start':
        return (
          <div className={styles.stepContent}>
            <h2>Ready to Start!</h2>
            <p className={styles.stepDescription}>
              Review your settings and start processing.
            </p>
            
            <div className={styles.summaryCard}>
              <h3>Configuration Summary</h3>
              
              <div className={styles.summaryRow}>
                <span className={styles.summaryLabel}>LLM Provider</span>
                <span className={styles.summaryValue}>{llmProvider}</span>
              </div>
              
              {llmProvider === 'ollama' && selectedModel && (
                <div className={styles.summaryRow}>
                  <span className={styles.summaryLabel}>Chat Model</span>
                  <span className={styles.summaryValue}>{selectedModel}</span>
                </div>
              )}
              
              <div className={styles.summaryRow}>
                <span className={styles.summaryLabel}>Source Folders</span>
                <span className={styles.summaryValue}>{selectedFolders.length} folder(s)</span>
              </div>
              
              <div className={styles.summaryRow}>
                <span className={styles.summaryLabel}>Indexing Mode</span>
                <span className={styles.summaryValue}>
                  {indexingMode === 'fast_scan' && 'Fast Scan'}
                  {indexingMode === 'full_enrichment' && 'Full Enrichment'}
                  {indexingMode === 'custom' && 'Custom'}
                </span>
              </div>
              
              <div className={styles.summaryRow}>
                <span className={styles.summaryLabel}>File Types</span>
                <span className={styles.summaryValue}>{extensions.length} type(s)</span>
              </div>
            </div>
            
            <div className={styles.startActions}>
              <button 
                className={styles.startButton}
                onClick={completeSetup}
                disabled={saving}
              >
                {saving ? (
                  <>
                    <Loader2 size={20} className={styles.spinner} />
                    Starting...
                  </>
                ) : (
                  <>
                    <Play size={20} />
                    Start Processing
                  </>
                )}
              </button>
              
              <p className={styles.hint}>
                Processing will begin in the background. You can monitor progress from the Dashboard.
              </p>
            </div>
          </div>
        )
      
      default:
        return null
    }
  }

  if (loading) {
    return (
      <div className={styles.loadingContainer}>
        <Loader2 size={48} className={styles.spinner} />
        <span>Loading setup wizard...</span>
      </div>
    )
  }

  return (
    <div className={styles.setupContainer}>
      {/* Progress sidebar */}
      <div className={styles.sidebar}>
        <div className={styles.sidebarHeader}>
          <Rocket size={24} />
          <span>Setup Wizard</span>
        </div>
        
        <div className={styles.stepList}>
          {STEPS.map((step, index) => (
            <div 
              key={step.id}
              className={`${styles.stepItem} ${index === currentStep ? styles.active : ''} ${index < currentStep ? styles.completed : ''}`}
              onClick={() => index <= currentStep && setCurrentStep(index)}
            >
              <div className={styles.stepIndicator}>
                {index < currentStep ? (
                  <CheckCircle2 size={20} />
                ) : (
                  <span>{index + 1}</span>
                )}
              </div>
              <span className={styles.stepTitle}>{step.title}</span>
            </div>
          ))}
        </div>
      </div>
      
      {/* Main content */}
      <div className={styles.mainContent}>
        <div className={styles.stepWrapper}>
          {renderStepContent()}
        </div>
        
        {/* Navigation */}
        <div className={styles.navigation}>
          <button 
            className={styles.navButton}
            onClick={prevStep}
            disabled={currentStep === 0}
          >
            <ArrowLeft size={20} />
            Back
          </button>
          
          <div className={styles.stepProgress}>
            Step {currentStep + 1} of {STEPS.length}
          </div>
          
          {currentStep < STEPS.length - 1 && (
            <button 
              className={`${styles.navButton} ${styles.primary}`}
              onClick={nextStep}
              disabled={!canProceed()}
            >
              Next
              <ArrowRight size={20} />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

export default Setup
