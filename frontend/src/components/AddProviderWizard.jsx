import { useState, useEffect } from 'react'
import { 
  Server, Cloud, Cpu, Wifi, WifiOff, Check, X, Loader2, 
  ChevronRight, ChevronLeft, AlertCircle, Eye, EyeOff,
  Terminal, Copy, ExternalLink, Zap
} from 'lucide-react'
import styles from './AddProviderWizard.module.css'

const API_BASE = '/api'

// Provider type definitions
const PROVIDER_TYPES = {
  ollama_local: {
    id: 'ollama_local',
    name: 'Local Ollama',
    description: 'Ollama running on this machine or in Docker',
    icon: Cpu,
    provider_type: 'ollama',
    presets: [
      { label: 'Docker (same compose)', url: 'http://ollama:11434' },
      { label: 'Host (Windows/Mac)', url: 'http://host.docker.internal:11434' },
      { label: 'Host (Linux)', url: 'http://172.17.0.1:11434' },
    ]
  },
  ollama_network: {
    id: 'ollama_network',
    name: 'Network Ollama',
    description: 'Ollama on another machine on your network',
    icon: Server,
    provider_type: 'ollama',
    presets: []
  },
  ollama_cloud: {
    id: 'ollama_cloud',
    name: 'Cloud GPU (Ollama)',
    description: 'Ollama on a rented cloud VM (vast.ai, runpod, etc.)',
    icon: Cloud,
    provider_type: 'ollama',
    presets: []
  },
  openai: {
    id: 'openai',
    name: 'OpenAI',
    description: 'GPT-4o, GPT-4, GPT-3.5, embeddings',
    icon: Zap,
    provider_type: 'openai',
    url: 'https://api.openai.com/v1',
    models: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo', 'text-embedding-3-small']
  },
  anthropic: {
    id: 'anthropic',
    name: 'Anthropic',
    description: 'Claude 3.5 Sonnet, Claude 3 Opus/Haiku',
    icon: Cloud,
    provider_type: 'anthropic',
    url: 'https://api.anthropic.com',
    models: ['claude-3-5-sonnet-20241022', 'claude-3-5-haiku-20241022', 'claude-3-opus-20240229']
  }
}

export default function AddProviderWizard({ isOpen, onClose, onSuccess }) {
  const [step, setStep] = useState(1)
  const [selectedType, setSelectedType] = useState(null)
  const [config, setConfig] = useState({
    name: '',
    url: '',
    api_key: '',
    default_model: ''
  })
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState(null)
  const [showApiKey, setShowApiKey] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [workerCommand, setWorkerCommand] = useState(null)

  // Reset state when opened
  useEffect(() => {
    if (isOpen) {
      setStep(1)
      setSelectedType(null)
      setConfig({ name: '', url: '', api_key: '', default_model: '' })
      setTestResult(null)
      setError(null)
      setWorkerCommand(null)
    }
  }, [isOpen])

  const selectType = (typeId) => {
    const type = PROVIDER_TYPES[typeId]
    setSelectedType(typeId)
    
    // Pre-fill defaults
    if (type.url) {
      setConfig(prev => ({ ...prev, url: type.url, name: type.name }))
    } else {
      setConfig(prev => ({ ...prev, name: '', url: '' }))
    }
    
    setStep(2)
  }

  const applyPreset = (preset) => {
    setConfig(prev => ({ ...prev, url: preset.url }))
  }

  const testConnection = async () => {
    setTesting(true)
    setTestResult(null)
    setError(null)
    
    try {
      const type = PROVIDER_TYPES[selectedType]
      
      // Create a temporary test
      const resp = await fetch(`${API_BASE}/servers/test-connection`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url: config.url,
          provider_type: type.provider_type,
          api_key: config.api_key || null
        })
      })
      
      const data = await resp.json()
      setTestResult(data)
      
      if (data.connected) {
        // Auto-fill name if not set
        if (!config.name && data.models?.length > 0) {
          const type = PROVIDER_TYPES[selectedType]
          setConfig(prev => ({ ...prev, name: type.name }))
        }
      }
    } catch (err) {
      setTestResult({ connected: false, error: err.message })
    } finally {
      setTesting(false)
    }
  }

  const saveProvider = async () => {
    setSaving(true)
    setError(null)
    
    try {
      const type = PROVIDER_TYPES[selectedType]
      
      const resp = await fetch(`${API_BASE}/servers`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: config.name,
          url: config.url,
          provider_type: type.provider_type,
          api_key: config.api_key || null,
          default_model: config.default_model || null,
          enabled: true
        })
      })
      
      if (!resp.ok) {
        const errData = await resp.json()
        throw new Error(errData.detail || 'Failed to save provider')
      }
      
      const data = await resp.json()
      
      // For Ollama providers, offer to add a worker
      if (type.provider_type === 'ollama') {
        // Get worker command
        const cmdResp = await fetch(`${API_BASE}/workers/command?server_id=${data.id}`)
        if (cmdResp.ok) {
          const cmdData = await cmdResp.json()
          setWorkerCommand(cmdData.command)
        }
        setStep(4) // Success + worker step
      } else {
        // Cloud provider - go to success
        setStep(4)
      }
      
      onSuccess?.(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const copyCommand = () => {
    if (workerCommand) {
      navigator.clipboard.writeText(workerCommand)
    }
  }

  if (!isOpen) return null

  const type = selectedType ? PROVIDER_TYPES[selectedType] : null
  const isCloudProvider = type?.provider_type !== 'ollama'

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.wizard} onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className={styles.header}>
          <h2>Add LLM Provider</h2>
          <button className={styles.closeBtn} onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        {/* Progress */}
        <div className={styles.progress}>
          <div className={`${styles.step} ${step >= 1 ? styles.active : ''} ${step > 1 ? styles.complete : ''}`}>
            <span>1</span> Choose Type
          </div>
          <ChevronRight size={16} />
          <div className={`${styles.step} ${step >= 2 ? styles.active : ''} ${step > 2 ? styles.complete : ''}`}>
            <span>2</span> Configure
          </div>
          <ChevronRight size={16} />
          <div className={`${styles.step} ${step >= 3 ? styles.active : ''} ${step > 3 ? styles.complete : ''}`}>
            <span>3</span> Test
          </div>
          <ChevronRight size={16} />
          <div className={`${styles.step} ${step >= 4 ? styles.active : ''}`}>
            <span>4</span> Done
          </div>
        </div>

        {/* Step 1: Choose Type */}
        {step === 1 && (
          <div className={styles.content}>
            <p className={styles.stepDescription}>
              What kind of LLM provider would you like to add?
            </p>
            
            <div className={styles.typeGrid}>
              <div className={styles.typeSection}>
                <h4>🖥️ Self-Hosted (Ollama)</h4>
                <div className={styles.typeCards}>
                  {['ollama_local', 'ollama_network', 'ollama_cloud'].map(id => {
                    const t = PROVIDER_TYPES[id]
                    const Icon = t.icon
                    return (
                      <button 
                        key={id} 
                        className={styles.typeCard}
                        onClick={() => selectType(id)}
                      >
                        <Icon size={24} />
                        <strong>{t.name}</strong>
                        <span>{t.description}</span>
                      </button>
                    )
                  })}
                </div>
              </div>
              
              <div className={styles.typeSection}>
                <h4>☁️ Cloud APIs</h4>
                <div className={styles.typeCards}>
                  {['openai', 'anthropic'].map(id => {
                    const t = PROVIDER_TYPES[id]
                    const Icon = t.icon
                    return (
                      <button 
                        key={id} 
                        className={styles.typeCard}
                        onClick={() => selectType(id)}
                      >
                        <Icon size={24} />
                        <strong>{t.name}</strong>
                        <span>{t.description}</span>
                      </button>
                    )
                  })}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Step 2: Configure */}
        {step === 2 && type && (
          <div className={styles.content}>
            <p className={styles.stepDescription}>
              Configure your {type.name} connection
            </p>
            
            {/* Name */}
            <div className={styles.field}>
              <label>Display Name</label>
              <input
                type="text"
                value={config.name}
                onChange={e => setConfig(prev => ({ ...prev, name: e.target.value }))}
                placeholder={`e.g., ${type.name}`}
              />
            </div>
            
            {/* URL for Ollama */}
            {!isCloudProvider && (
              <>
                <div className={styles.field}>
                  <label>Server URL</label>
                  <input
                    type="text"
                    value={config.url}
                    onChange={e => setConfig(prev => ({ ...prev, url: e.target.value }))}
                    placeholder="http://..."
                  />
                </div>
                
                {/* Presets */}
                {type.presets?.length > 0 && (
                  <div className={styles.presets}>
                    <span>Quick fill:</span>
                    {type.presets.map((preset, i) => (
                      <button key={i} onClick={() => applyPreset(preset)}>
                        {preset.label}
                      </button>
                    ))}
                  </div>
                )}
                
                {selectedType === 'ollama_network' && (
                  <div className={styles.hint}>
                    <AlertCircle size={14} />
                    Enter the IP address of the machine running Ollama (e.g., http://192.168.1.100:11434)
                  </div>
                )}
                
                {selectedType === 'ollama_cloud' && (
                  <div className={styles.hint}>
                    <AlertCircle size={14} />
                    Use the public IP or hostname of your cloud VM. Make sure port 11434 is open.
                  </div>
                )}
              </>
            )}
            
            {/* API Key for cloud providers */}
            {isCloudProvider && (
              <div className={styles.field}>
                <label>API Key</label>
                <div className={styles.apiKeyInput}>
                  <input
                    type={showApiKey ? 'text' : 'password'}
                    value={config.api_key}
                    onChange={e => setConfig(prev => ({ ...prev, api_key: e.target.value }))}
                    placeholder={type.provider_type === 'openai' ? 'sk-...' : 'sk-ant-...'}
                  />
                  <button onClick={() => setShowApiKey(!showApiKey)}>
                    {showApiKey ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
                <small>
                  Get your API key from{' '}
                  {type.provider_type === 'openai' && (
                    <a href="https://platform.openai.com/api-keys" target="_blank" rel="noopener">
                      OpenAI Dashboard <ExternalLink size={12} />
                    </a>
                  )}
                  {type.provider_type === 'anthropic' && (
                    <a href="https://console.anthropic.com/settings/keys" target="_blank" rel="noopener">
                      Anthropic Console <ExternalLink size={12} />
                    </a>
                  )}
                </small>
              </div>
            )}
            
            {error && (
              <div className={styles.error}>
                <AlertCircle size={16} /> {error}
              </div>
            )}
            
            <div className={styles.actions}>
              <button className={styles.backBtn} onClick={() => setStep(1)}>
                <ChevronLeft size={16} /> Back
              </button>
              <button 
                className={styles.nextBtn} 
                onClick={() => setStep(3)}
                disabled={!config.name || (!isCloudProvider && !config.url) || (isCloudProvider && !config.api_key)}
              >
                Next <ChevronRight size={16} />
              </button>
            </div>
          </div>
        )}

        {/* Step 3: Test */}
        {step === 3 && type && (
          <div className={styles.content}>
            <p className={styles.stepDescription}>
              Test the connection to {config.name || type.name}
            </p>
            
            <div className={styles.testSection}>
              <div className={styles.testInfo}>
                <div><strong>Provider:</strong> {type.name}</div>
                <div><strong>URL:</strong> {config.url}</div>
                {isCloudProvider && <div><strong>API Key:</strong> ••••{config.api_key.slice(-4)}</div>}
              </div>
              
              <button 
                className={styles.testBtn}
                onClick={testConnection}
                disabled={testing}
              >
                {testing ? (
                  <><Loader2 size={16} className={styles.spin} /> Testing...</>
                ) : (
                  <><Wifi size={16} /> Test Connection</>
                )}
              </button>
              
              {testResult && (
                <div className={`${styles.testResult} ${testResult.connected ? styles.success : styles.failure}`}>
                  {testResult.connected ? (
                    <>
                      <Check size={20} />
                      <div>
                        <strong>Connected!</strong>
                        <span>{testResult.models?.length || 0} models available</span>
                      </div>
                    </>
                  ) : (
                    <>
                      <WifiOff size={20} />
                      <div>
                        <strong>Connection failed</strong>
                        <span>{testResult.error}</span>
                      </div>
                    </>
                  )}
                </div>
              )}
            </div>
            
            {error && (
              <div className={styles.error}>
                <AlertCircle size={16} /> {error}
              </div>
            )}
            
            <div className={styles.actions}>
              <button className={styles.backBtn} onClick={() => setStep(2)}>
                <ChevronLeft size={16} /> Back
              </button>
              <button 
                className={styles.saveBtn}
                onClick={saveProvider}
                disabled={saving || !testResult?.connected}
              >
                {saving ? (
                  <><Loader2 size={16} className={styles.spin} /> Saving...</>
                ) : (
                  <><Check size={16} /> Save Provider</>
                )}
              </button>
            </div>
          </div>
        )}

        {/* Step 4: Done */}
        {step === 4 && type && (
          <div className={styles.content}>
            <div className={styles.successBanner}>
              <Check size={32} />
              <h3>{config.name} added successfully!</h3>
            </div>
            
            {/* Worker command for Ollama providers */}
            {!isCloudProvider && workerCommand && (
              <div className={styles.workerSection}>
                <h4>🚀 Add a Worker (Optional)</h4>
                <p>
                  To process documents using this server, you can run a worker on any machine 
                  that can connect to your database.
                </p>
                
                <div className={styles.commandBlock}>
                  <pre>{workerCommand}</pre>
                  <button onClick={copyCommand} title="Copy to clipboard">
                    <Copy size={16} />
                  </button>
                </div>
                
                <small>
                  Paste this command on any machine with Docker installed. 
                  The worker will automatically register and start processing.
                </small>
              </div>
            )}
            
            {/* Cloud provider info */}
            {isCloudProvider && (
              <div className={styles.cloudInfo}>
                <p>
                  You can now select {type.name} models in the <strong>Models</strong> tab.
                </p>
                <small>
                  Note: Cloud APIs incur usage costs. Monitor your usage in the provider dashboard.
                </small>
              </div>
            )}
            
            <div className={styles.actions}>
              <button className={styles.doneBtn} onClick={onClose}>
                Done
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
