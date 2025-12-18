import { 
  Server, 
  Cloud, 
  RefreshCw, 
  Check, 
  X, 
  AlertCircle,
  Loader2,
  Trash2,
  Plus,
  Wifi,
  WifiOff,
  Power,
  Cpu,
  Activity
} from 'lucide-react'
import AddProviderWizard from '../../components/AddProviderWizard'
import WorkersPanel from '../../components/WorkersPanel'
import WorkerSchedule from '../../components/WorkerSchedule'
import styles from '../Settings.module.css'

const API_BASE = '/api'

export default function WorkersTab({ 
  providers, 
  loadingProviders, 
  onRefresh,
  testingProvider,
  setTestingProvider
}) {
  const [showAddWizard, setShowAddWizard] = React.useState(false)

  const toggleProvider = async (id, enabled) => {
    try {
      await fetch(`${API_BASE}/servers/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled })
      })
      onRefresh()
    } catch (err) {
      console.error('Failed to toggle provider:', err)
    }
  }

  const deleteProvider = async (id, name) => {
    if (!confirm(`Delete provider "${name}"?\n\nThis will also remove any associated workers.`)) return
    try {
      await fetch(`${API_BASE}/servers/${id}`, { method: 'DELETE' })
      onRefresh()
    } catch (err) {
      alert('Failed to delete provider: ' + err.message)
    }
  }

  const testProvider = async (id) => {
    setTestingProvider(id)
    try {
      const res = await fetch(`${API_BASE}/servers/${id}/test`, { method: 'POST' })
      if (res.ok) {
        onRefresh()
      }
    } catch (err) {
      console.error('Failed to test provider:', err)
    }
    setTestingProvider(null)
  }

  return (
    <div className={styles.section}>
      {/* Add Provider Wizard */}
      <AddProviderWizard 
        isOpen={showAddWizard} 
        onClose={() => setShowAddWizard(false)}
        onSuccess={() => onRefresh()}
      />

      {/* Header */}
      <div className={styles.sectionHeader}>
        <div>
          <h2>LLM Providers</h2>
          <p className={styles.description}>
            Add Ollama servers or cloud APIs to power document processing.
          </p>
        </div>
        <button 
          className={styles.addBtn} 
          onClick={() => setShowAddWizard(true)}
        >
          <Plus size={16} /> Add Provider
        </button>
      </div>

      {/* Provider Overview */}
      <div className={styles.providerStats}>
        <div className={styles.stat}>
          <Cpu size={16} />
          <span>
            {providers.filter(p => p.provider_type === 'ollama' && p.status === 'online').length} Ollama servers online
          </span>
        </div>
        <div className={styles.stat}>
          <Cloud size={16} />
          <span>
            {providers.filter(p => p.provider_type !== 'ollama' && p.status === 'online').length} Cloud APIs configured
          </span>
        </div>
      </div>

      {/* Providers List */}
      <div className={styles.providersList}>
        {loadingProviders ? (
          <div className={styles.loadingSmall}><Loader2 className={styles.spinner} size={16} /> Loading...</div>
        ) : providers.length === 0 ? (
          <div className={styles.emptyState}>
            <Server size={32} />
            <p>No LLM providers configured</p>
            <small>Add Ollama servers or cloud APIs to start processing documents</small>
            <button className={styles.addBtn} onClick={() => setShowAddWizard(true)}>
              <Plus size={16} /> Add Your First Provider
            </button>
          </div>
        ) : (
          <>
            {/* Ollama Providers */}
            {providers.filter(p => p.provider_type === 'ollama').length > 0 && (
              <div className={styles.providerGroup}>
                <h4><Cpu size={16} /> Ollama Servers</h4>
                {providers.filter(p => p.provider_type === 'ollama').map(provider => (
                  <div key={provider.id} className={`${styles.provider} ${provider.enabled ? '' : styles.disabled}`}>
                    <div className={styles.providerStatus}>
                      {!provider.enabled ? (
                        <Power size={18} className={styles.pausedIcon} />
                      ) : provider.status === 'online' ? (
                        <Wifi size={18} className={styles.connected} />
                      ) : provider.status === 'offline' ? (
                        <WifiOff size={18} className={styles.disconnected} />
                      ) : (
                        <AlertCircle size={18} className={styles.unknown} />
                      )}
                    </div>
                    
                    <div className={styles.providerInfo}>
                      <div className={styles.providerName}>
                        {provider.name}
                        {!provider.enabled && <span className={styles.disabledBadge}>Disabled</span>}
                        {provider.worker_count > 0 && (
                          <span className={styles.workerBadge}>
                            <Activity size={12} /> {provider.worker_count} worker{provider.worker_count > 1 ? 's' : ''}
                          </span>
                        )}
                      </div>
                      <code className={styles.providerUrl}>{provider.url}</code>
                      <div className={styles.providerMeta}>
                        {provider.status === 'online' && (
                          <span>{provider.models_available?.length || 0} models</span>
                        )}
                        {provider.capabilities?.chat && <span className={styles.capBadge}>Chat</span>}
                        {provider.capabilities?.embedding && <span className={styles.capBadge}>Embed</span>}
                        {provider.capabilities?.vision && <span className={styles.capBadge}>Vision</span>}
                        {provider.status_message && provider.status !== 'online' && (
                          <span className={styles.errorText}>{provider.status_message}</span>
                        )}
                      </div>
                    </div>
                    
                    <div className={styles.providerActions}>
                      <button 
                        onClick={() => toggleProvider(provider.id, !provider.enabled)}
                        className={provider.enabled ? styles.running : styles.pausedBtn}
                        title={provider.enabled ? 'Disable' : 'Enable'}
                      >
                        <Power size={14} />
                      </button>
                      <button 
                        onClick={() => testProvider(provider.id)}
                        disabled={testingProvider === provider.id || !provider.enabled}
                        title="Test connection"
                      >
                        {testingProvider === provider.id ? (
                          <Loader2 size={16} className={styles.spinner} />
                        ) : (
                          <RefreshCw size={16} />
                        )}
                      </button>
                      <button 
                        onClick={() => deleteProvider(provider.id, provider.name)}
                        className={styles.deleteBtn}
                        title="Delete"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Cloud Providers */}
            {providers.filter(p => p.provider_type !== 'ollama').length > 0 && (
              <div className={styles.providerGroup}>
                <h4><Cloud size={16} /> Cloud APIs</h4>
                {providers.filter(p => p.provider_type !== 'ollama').map(provider => (
                  <div key={provider.id} className={`${styles.provider} ${provider.enabled ? '' : styles.disabled}`}>
                    <div className={styles.providerStatus}>
                      {!provider.enabled ? (
                        <Power size={18} className={styles.pausedIcon} />
                      ) : provider.status === 'online' ? (
                        <Check size={18} className={styles.connected} />
                      ) : provider.status === 'unconfigured' ? (
                        <AlertCircle size={18} className={styles.warning} />
                      ) : (
                        <X size={18} className={styles.disconnected} />
                      )}
                    </div>
                    
                    <div className={styles.providerInfo}>
                      <div className={styles.providerName}>
                        {provider.name}
                        <span className={styles.typeBadge}>{provider.provider_type}</span>
                        {!provider.enabled && <span className={styles.disabledBadge}>Disabled</span>}
                      </div>
                      <div className={styles.providerMeta}>
                        {provider.has_api_key ? (
                          <span className={styles.keyConfigured}>✓ API Key configured</span>
                        ) : (
                          <span className={styles.keyMissing}>⚠ API Key required</span>
                        )}
                        {provider.default_model && <span>Model: {provider.default_model}</span>}
                      </div>
                    </div>
                    
                    <div className={styles.providerActions}>
                      <button 
                        onClick={() => toggleProvider(provider.id, !provider.enabled)}
                        className={provider.enabled ? styles.running : styles.pausedBtn}
                        title={provider.enabled ? 'Disable' : 'Enable'}
                      >
                        <Power size={14} />
                      </button>
                      <button 
                        onClick={() => testProvider(provider.id)}
                        disabled={testingProvider === provider.id || !provider.enabled}
                        title="Test connection"
                      >
                        {testingProvider === provider.id ? (
                          <Loader2 size={16} className={styles.spinner} />
                        ) : (
                          <RefreshCw size={16} />
                        )}
                      </button>
                      <button 
                        onClick={() => deleteProvider(provider.id, provider.name)}
                        className={styles.deleteBtn}
                        title="Delete"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>

      {/* Active Workers Section */}
      {providers.filter(p => p.provider_type === 'ollama' && p.status === 'online').length > 0 && (
        <div className={styles.workersSection}>
          <WorkersPanel compact={false} refreshInterval={15000} />
        </div>
      )}

      {/* Worker Schedule Section */}
      <div className={styles.scheduleSection}>
        <WorkerSchedule />
      </div>
    </div>
  )
}

// Need React for useState
import React from 'react'
