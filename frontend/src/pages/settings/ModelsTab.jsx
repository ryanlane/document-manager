import React, { useState, useEffect } from 'react'
import { 
  Brain, 
  RefreshCw, 
  Check, 
  X, 
  AlertCircle,
  Loader2,
  Trash2,
  ChevronDown,
  ChevronUp,
  Download,
  Cloud,
  Lock,
  Image,
  MessageSquare
} from 'lucide-react'
import styles from '../Settings.module.css'

const API_BASE = '/api'

export default function ModelsTab({
  providers,
  llmSettings,
  envOverrides,
  onSaveLLMSettings,
  saving
}) {
  const [ollamaModels, setOllamaModels] = useState([])
  const [modelCatalog, setModelCatalog] = useState([])
  const [pullingModels, setPullingModels] = useState({})
  const [showCatalog, setShowCatalog] = useState(false)
  const [catalogFilter, setCatalogFilter] = useState('')
  const [catalogSort, setCatalogSort] = useState('popular')
  const [loadingModels, setLoadingModels] = useState(false)

  // Local state for form
  const [localSettings, setLocalSettings] = useState({
    chatModel: '',
    embedModel: '',
    visionModel: ''
  })

  useEffect(() => {
    setLocalSettings({
      chatModel: llmSettings.chatModel || '',
      embedModel: llmSettings.embedModel || '',
      visionModel: llmSettings.visionModel || ''
    })
  }, [llmSettings])

  useEffect(() => {
    if (providers.filter(p => p.provider_type === 'ollama' && p.status === 'online').length > 0) {
      loadOllamaModels()
    }
  }, [providers])

  const loadOllamaModels = async () => {
    setLoadingModels(true)
    try {
      const onlineServers = providers.filter(p => p.provider_type === 'ollama' && p.status === 'online')
      const allModels = []
      for (const server of onlineServers) {
        if (server.models_available) {
          allModels.push(...server.models_available.map(m => ({
            name: m,
            server: server.name,
            serverId: server.id
          })))
        }
      }
      setOllamaModels(allModels)
    } catch (err) {
      console.error('Failed to load Ollama models:', err)
    }
    setLoadingModels(false)
  }

  const loadModelCatalog = async () => {
    try {
      const res = await fetch(`${API_BASE}/models/catalog`)
      if (res.ok) {
        setModelCatalog(await res.json())
      }
    } catch (err) {
      console.error('Failed to load model catalog:', err)
    }
  }

  const pullModel = async (modelName, serverId) => {
    const key = `${serverId}:${modelName}`
    setPullingModels(prev => ({ ...prev, [key]: { progress: 0, status: 'starting' } }))
    
    try {
      const res = await fetch(`${API_BASE}/models/pull`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: modelName, server_id: serverId })
      })
      
      if (!res.ok) {
        throw new Error('Pull request failed')
      }

      const reader = res.body?.getReader()
      if (!reader) throw new Error('No response stream')

      const decoder = new TextDecoder()
      
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        
        const text = decoder.decode(value)
        const lines = text.split('\n').filter(Boolean)
        
        for (const line of lines) {
          try {
            const data = JSON.parse(line)
            if (data.status === 'downloading' || data.status === 'pulling') {
              const progress = data.completed && data.total 
                ? Math.round((data.completed / data.total) * 100)
                : 0
              setPullingModels(prev => ({ 
                ...prev, 
                [key]: { progress, status: data.status } 
              }))
            } else if (data.status === 'success') {
              setPullingModels(prev => {
                const updated = { ...prev }
                delete updated[key]
                return updated
              })
              loadOllamaModels()
            } else if (data.error) {
              throw new Error(data.error)
            }
          } catch (e) {
            // Ignore parse errors for incomplete chunks
          }
        }
      }
    } catch (err) {
      console.error('Failed to pull model:', err)
      setPullingModels(prev => ({ 
        ...prev, 
        [key]: { progress: 0, status: 'error', error: err.message } 
      }))
      setTimeout(() => {
        setPullingModels(prev => {
          const updated = { ...prev }
          delete updated[key]
          return updated
        })
      }, 3000)
    }
  }

  const deleteModel = async (modelName, serverId) => {
    if (!confirm(`Delete model "${modelName}"?`)) return
    
    try {
      await fetch(`${API_BASE}/models/${encodeURIComponent(modelName)}?server_id=${serverId}`, {
        method: 'DELETE'
      })
      loadOllamaModels()
    } catch (err) {
      console.error('Failed to delete model:', err)
      alert('Failed to delete model: ' + err.message)
    }
  }

  const isEnvLocked = (key) => envOverrides[key]?.isLocked
  const getEnvVarName = (key) => envOverrides[key]?.envVar

  const getFilteredCatalogModels = () => {
    let models = [...modelCatalog]
    
    if (catalogFilter) {
      const lowerFilter = catalogFilter.toLowerCase()
      models = models.filter(m => 
        m.name.toLowerCase().includes(lowerFilter) ||
        m.description?.toLowerCase().includes(lowerFilter)
      )
    }
    
    switch (catalogSort) {
      case 'name':
        models.sort((a, b) => a.name.localeCompare(b.name))
        break
      case 'size':
        models.sort((a, b) => (a.size_gb || 0) - (b.size_gb || 0))
        break
      case 'popular':
      default:
        models.sort((a, b) => (b.pulls || 0) - (a.pulls || 0))
    }
    
    return models
  }

  const handleSave = () => {
    onSaveLLMSettings(localSettings)
  }

  const cloudProviders = providers.filter(p => p.provider_type !== 'ollama' && p.enabled)

  return (
    <div className={styles.section}>
      <div className={styles.sectionHeader}>
        <div>
          <h2>Model Configuration</h2>
          <p className={styles.description}>
            Select which models to use for chat, embeddings, and vision tasks.
          </p>
        </div>
      </div>

      {/* Model Selection */}
      <div className={styles.modelSelectors}>
        {/* Chat Model */}
        <div className={styles.modelField}>
          <label>
            <MessageSquare size={16} /> Chat Model
            {isEnvLocked('chatModel') && (
              <span className={styles.envLock} title={`Set by ${getEnvVarName('chatModel')}`}>
                <Lock size={12} /> ENV
              </span>
            )}
          </label>
          <select
            value={localSettings.chatModel}
            onChange={e => setLocalSettings(prev => ({ ...prev, chatModel: e.target.value }))}
            disabled={isEnvLocked('chatModel')}
          >
            <option value="">Select a model...</option>
            {ollamaModels.length > 0 && (
              <optgroup label="Ollama Models">
                {ollamaModels.map((m, i) => (
                  <option key={`ollama-${i}`} value={m.name}>
                    {m.name} ({m.server})
                  </option>
                ))}
              </optgroup>
            )}
            {cloudProviders.map(provider => (
              <optgroup key={provider.id} label={`${provider.name} (${provider.provider_type})`}>
                {(provider.models_available || []).map(model => (
                  <option key={model} value={`${provider.provider_type}/${model}`}>
                    {model}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
          <small>Used for document categorization, summarization, and chat</small>
        </div>

        {/* Embedding Model */}
        <div className={styles.modelField}>
          <label>
            <Brain size={16} /> Embedding Model
            {isEnvLocked('embedModel') && (
              <span className={styles.envLock} title={`Set by ${getEnvVarName('embedModel')}`}>
                <Lock size={12} /> ENV
              </span>
            )}
          </label>
          <select
            value={localSettings.embedModel}
            onChange={e => setLocalSettings(prev => ({ ...prev, embedModel: e.target.value }))}
            disabled={isEnvLocked('embedModel')}
          >
            <option value="">Select a model...</option>
            {ollamaModels.filter(m => m.name.includes('embed') || m.name.includes('nomic') || m.name.includes('mxbai')).length > 0 ? (
              <optgroup label="Embedding Models">
                {ollamaModels
                  .filter(m => m.name.includes('embed') || m.name.includes('nomic') || m.name.includes('mxbai'))
                  .map((m, i) => (
                    <option key={`embed-${i}`} value={m.name}>
                      {m.name} ({m.server})
                    </option>
                  ))}
              </optgroup>
            ) : null}
            <optgroup label="All Ollama Models">
              {ollamaModels.map((m, i) => (
                <option key={`all-${i}`} value={m.name}>
                  {m.name} ({m.server})
                </option>
              ))}
            </optgroup>
          </select>
          <small>Used for semantic search and document similarity</small>
        </div>

        {/* Vision Model */}
        <div className={styles.modelField}>
          <label>
            <Image size={16} /> Vision Model (Optional)
            {isEnvLocked('visionModel') && (
              <span className={styles.envLock} title={`Set by ${getEnvVarName('visionModel')}`}>
                <Lock size={12} /> ENV
              </span>
            )}
          </label>
          <select
            value={localSettings.visionModel}
            onChange={e => setLocalSettings(prev => ({ ...prev, visionModel: e.target.value }))}
            disabled={isEnvLocked('visionModel')}
          >
            <option value="">None (skip image analysis)</option>
            {ollamaModels.filter(m => m.name.includes('llava') || m.name.includes('vision') || m.name.includes('bakllava')).length > 0 ? (
              <optgroup label="Vision Models">
                {ollamaModels
                  .filter(m => m.name.includes('llava') || m.name.includes('vision') || m.name.includes('bakllava'))
                  .map((m, i) => (
                    <option key={`vision-${i}`} value={m.name}>
                      {m.name} ({m.server})
                    </option>
                  ))}
              </optgroup>
            ) : null}
            {cloudProviders.filter(p => ['openai', 'anthropic', 'google'].includes(p.provider_type)).map(provider => (
              <optgroup key={provider.id} label={`${provider.name} Vision`}>
                {provider.provider_type === 'openai' && (
                  <>
                    <option value="openai/gpt-4o">gpt-4o</option>
                    <option value="openai/gpt-4-vision-preview">gpt-4-vision-preview</option>
                  </>
                )}
                {provider.provider_type === 'anthropic' && (
                  <>
                    <option value="anthropic/claude-3-opus-20240229">claude-3-opus</option>
                    <option value="anthropic/claude-3-sonnet-20240229">claude-3-sonnet</option>
                  </>
                )}
                {provider.provider_type === 'google' && (
                  <option value="google/gemini-pro-vision">gemini-pro-vision</option>
                )}
              </optgroup>
            ))}
          </select>
          <small>Used for analyzing images in documents</small>
        </div>

        <button 
          className={styles.saveBtn} 
          onClick={handleSave}
          disabled={saving}
        >
          {saving ? <Loader2 size={16} className={styles.spinner} /> : <Check size={16} />}
          Save Model Settings
        </button>
      </div>

      {/* Cloud Provider Model Info */}
      {cloudProviders.length > 0 && (
        <div className={styles.cloudInfo}>
          <h3><Cloud size={16} /> Cloud Provider Models</h3>
          <p>Models from your configured cloud providers are available in the dropdowns above.</p>
          <div className={styles.cloudProviderList}>
            {cloudProviders.map(p => (
              <div key={p.id} className={styles.cloudProviderItem}>
                <strong>{p.name}</strong> ({p.provider_type})
                {p.status === 'online' ? (
                  <Check size={14} className={styles.connected} />
                ) : (
                  <AlertCircle size={14} className={styles.warning} />
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Ollama Model Library */}
      {providers.filter(p => p.provider_type === 'ollama' && p.status === 'online').length > 0 && (
        <div className={styles.modelLibrary}>
          <div className={styles.libraryHeader}>
            <h3>Ollama Model Library</h3>
            <div className={styles.libraryActions}>
              <button 
                onClick={loadOllamaModels} 
                disabled={loadingModels}
                className={styles.refreshBtn}
              >
                <RefreshCw size={14} className={loadingModels ? styles.spinner : ''} />
                Refresh
              </button>
              <button 
                onClick={() => {
                  setShowCatalog(!showCatalog)
                  if (!showCatalog && modelCatalog.length === 0) {
                    loadModelCatalog()
                  }
                }}
                className={styles.catalogBtn}
              >
                {showCatalog ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                {showCatalog ? 'Hide Catalog' : 'Browse Catalog'}
              </button>
            </div>
          </div>

          {/* Installed Models */}
          <div className={styles.installedModels}>
            <h4>Installed Models ({ollamaModels.length})</h4>
            {loadingModels ? (
              <div className={styles.loadingSmall}><Loader2 size={16} className={styles.spinner} /> Loading...</div>
            ) : ollamaModels.length === 0 ? (
              <p className={styles.noModels}>No models installed. Browse the catalog to pull models.</p>
            ) : (
              <div className={styles.modelGrid}>
                {ollamaModels.map((model, idx) => (
                  <div key={`${model.serverId}-${model.name}-${idx}`} className={styles.modelCard}>
                    <div className={styles.modelName}>{model.name}</div>
                    <div className={styles.modelServer}>{model.server}</div>
                    <button 
                      onClick={() => deleteModel(model.name, model.serverId)}
                      className={styles.deleteModelBtn}
                      title="Delete model"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Model Catalog */}
          {showCatalog && (
            <div className={styles.catalogSection}>
              <h4>Model Catalog</h4>
              <div className={styles.catalogControls}>
                <input
                  type="text"
                  placeholder="Filter models..."
                  value={catalogFilter}
                  onChange={e => setCatalogFilter(e.target.value)}
                  className={styles.catalogSearch}
                />
                <select 
                  value={catalogSort} 
                  onChange={e => setCatalogSort(e.target.value)}
                  className={styles.catalogSortSelect}
                >
                  <option value="popular">Most Popular</option>
                  <option value="name">Name</option>
                  <option value="size">Size</option>
                </select>
              </div>
              
              {modelCatalog.length === 0 ? (
                <div className={styles.loadingSmall}><Loader2 size={16} className={styles.spinner} /> Loading catalog...</div>
              ) : (
                <div className={styles.catalogGrid}>
                  {getFilteredCatalogModels().slice(0, 20).map(model => {
                    const firstServer = providers.find(p => p.provider_type === 'ollama' && p.status === 'online')
                    const pullKey = firstServer ? `${firstServer.id}:${model.name}` : null
                    const isPulling = pullKey && pullingModels[pullKey]
                    const isInstalled = ollamaModels.some(m => m.name === model.name)
                    
                    return (
                      <div key={model.name} className={styles.catalogCard}>
                        <div className={styles.catalogCardHeader}>
                          <span className={styles.catalogModelName}>{model.name}</span>
                          {model.size_gb && <span className={styles.modelSize}>{model.size_gb}GB</span>}
                        </div>
                        <p className={styles.catalogDescription}>{model.description}</p>
                        <div className={styles.catalogCardFooter}>
                          {model.pulls && <span className={styles.pullCount}>{model.pulls.toLocaleString()} pulls</span>}
                          {isInstalled ? (
                            <span className={styles.installedBadge}><Check size={12} /> Installed</span>
                          ) : isPulling ? (
                            <div className={styles.pullProgress}>
                              <div 
                                className={styles.pullProgressBar} 
                                style={{ width: `${isPulling.progress}%` }}
                              />
                              <span>{isPulling.progress}%</span>
                            </div>
                          ) : (
                            <button 
                              onClick={() => firstServer && pullModel(model.name, firstServer.id)}
                              disabled={!firstServer}
                              className={styles.pullBtn}
                            >
                              <Download size={14} /> Pull
                            </button>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
