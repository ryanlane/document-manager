import { useState, useEffect } from 'react'
import { 
  Settings as SettingsIcon, 
  Server, 
  Brain, 
  FolderPlus, 
  FileType, 
  RefreshCw, 
  Loader2
} from 'lucide-react'
import WorkersTab from './WorkersTab'
import ModelsTab from './ModelsTab'
import SourcesTab from './SourcesTab'
import FileTypesTab from './FileTypesTab'
import styles from '../Settings.module.css'

const API_BASE = '/api'

function Settings() {
  const [activeTab, setActiveTab] = useState('workers')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  
  // Environment variable overrides
  const [envOverrides, setEnvOverrides] = useState({})
  
  // LLM Providers (unified - Ollama + Cloud)
  const [providers, setProviders] = useState([])
  const [loadingProviders, setLoadingProviders] = useState(false)
  
  // LLM Settings (model selections)
  const [llmSettings, setLlmSettings] = useState({
    chatModel: '',
    embedModel: '',
    visionModel: ''
  })
  
  // Source Settings
  const [sources, setSources] = useState({ include: [], exclude: [] })
  const [availableMounts, setAvailableMounts] = useState({ mounts: [] })
  
  // Extension Settings
  const [extensions, setExtensions] = useState([])

  useEffect(() => {
    loadAll()
  }, [])

  const loadAll = async () => {
    setLoading(true)
    await Promise.all([
      loadProviders(),
      loadSettings()
    ])
    setLoading(false)
  }

  const loadProviders = async () => {
    setLoadingProviders(true)
    try {
      const res = await fetch(`${API_BASE}/servers`)
      if (res.ok) {
        const data = await res.json()
        setProviders(data.servers || [])
      }
    } catch (err) {
      console.error('Failed to load providers:', err)
    }
    setLoadingProviders(false)
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
      
      if (llmRes.ok) {
        const data = await llmRes.json()
        setLlmSettings({
          chatModel: data.ollama?.model || data.chatModel || '',
          embedModel: data.ollama?.embedding_model || data.embedModel || '',
          visionModel: data.ollama?.vision_model || data.visionModel || ''
        })
      }
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

  const saveLLMSettings = async (settings) => {
    setSaving(true)
    try {
      await fetch(`${API_BASE}/settings/llm`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ollama: {
            model: settings.chatModel,
            embedding_model: settings.embedModel,
            vision_model: settings.visionModel
          }
        })
      })
      await loadSettings()
    } catch (err) {
      alert('Failed to save settings: ' + err.message)
    }
    setSaving(false)
  }

  const tabs = [
    { id: 'workers', label: 'LLM Workers', icon: Server },
    { id: 'models', label: 'Models', icon: Brain },
    { id: 'sources', label: 'Sources', icon: FolderPlus },
    { id: 'extensions', label: 'File Types', icon: FileType }
  ]

  if (loading) {
    return (
      <div className={styles.loading}>
        <Loader2 className={styles.spinner} size={32} />
        <span>Loading settings...</span>
      </div>
    )
  }

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <SettingsIcon size={28} />
        <h1>Settings</h1>
        <button className={styles.refreshAll} onClick={loadAll} title="Refresh all">
          <RefreshCw size={16} />
        </button>
      </div>

      {/* Tab Navigation */}
      <div className={styles.tabs}>
        {tabs.map(tab => {
          const Icon = tab.icon
          return (
            <button
              key={tab.id}
              className={`${styles.tab} ${activeTab === tab.id ? styles.active : ''}`}
              onClick={() => setActiveTab(tab.id)}
            >
              <Icon size={16} />
              {tab.label}
            </button>
          )
        })}
      </div>

      {/* Tab Content */}
      <div className={styles.content}>
        {activeTab === 'workers' && (
          <WorkersTab
            providers={providers}
            loadingProviders={loadingProviders}
            onRefresh={loadProviders}
          />
        )}

        {activeTab === 'models' && (
          <ModelsTab
            providers={providers}
            llmSettings={llmSettings}
            envOverrides={envOverrides}
            onSaveLLMSettings={saveLLMSettings}
            saving={saving}
          />
        )}

        {activeTab === 'sources' && (
          <SourcesTab
            sources={sources}
            availableMounts={availableMounts}
            onRefresh={loadSettings}
          />
        )}

        {activeTab === 'extensions' && (
          <FileTypesTab
            extensions={extensions}
            setExtensions={setExtensions}
            saving={saving}
            setSaving={setSaving}
          />
        )}
      </div>
    </div>
  )
}

export default Settings
