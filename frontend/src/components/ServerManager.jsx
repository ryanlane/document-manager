import { useState, useEffect } from 'react';
import styles from './ServerManager.module.css';

const STATUS_ICONS = {
  online: '🟢',
  offline: '🔴',
  error: '🟠',
  unknown: '⚪'
};

function ServerCard({ server, onTest, onDelete, onEdit, onPullModel }) {
  const [expanded, setExpanded] = useState(false);
  const [testing, setTesting] = useState(false);
  const [pullModel, setPullModel] = useState('');
  const [pulling, setPulling] = useState(false);

  const handleTest = async () => {
    setTesting(true);
    await onTest(server.id);
    setTesting(false);
  };

  const handlePull = async () => {
    if (!pullModel.trim()) return;
    setPulling(true);
    await onPullModel(server.id, pullModel.trim());
    setPullModel('');
    setPulling(false);
  };

  const statusIcon = STATUS_ICONS[server.status] || '❓';

  return (
    <div className={`${styles.serverCard} ${styles[server.status]}`}>
      <div className={styles.serverHeader} onClick={() => setExpanded(!expanded)}>
        <div className={styles.serverInfo}>
          <span className={styles.statusIcon}>{statusIcon}</span>
          <span className={styles.serverName}>{server.name}</span>
          {!server.enabled && <span className={styles.disabledBadge}>Disabled</span>}
          {server.worker_count > 0 && (
            <span className={styles.workerBadge}>
              {server.worker_count} worker{server.worker_count > 1 ? 's' : ''}
            </span>
          )}
        </div>
        <div className={styles.serverActions}>
          <button 
            className={styles.testBtn} 
            onClick={(e) => { e.stopPropagation(); handleTest(); }}
            disabled={testing}
          >
            {testing ? '⏳' : '🔌'} Test
          </button>
          <span className={styles.expandBtn}>{expanded ? '▲' : '▼'}</span>
        </div>
      </div>

      <div className={styles.serverUrl}>{server.url}</div>

      {expanded && (
        <div className={styles.serverDetails}>
          <div className={styles.detailRow}>
            <span className={styles.detailLabel}>Status:</span>
            <span className={`${styles.detailValue} ${styles[server.status]}`}>
              {server.status}
              {server.status_message && ` - ${server.status_message}`}
            </span>
          </div>

          <div className={styles.detailRow}>
            <span className={styles.detailLabel}>Priority:</span>
            <span className={styles.detailValue}>{server.priority}</span>
          </div>

          {server.capabilities && (
            <div className={styles.detailRow}>
              <span className={styles.detailLabel}>Capabilities:</span>
              <span className={styles.detailValue}>
                {Object.entries(server.capabilities)
                  .filter(([, v]) => v)
                  .map(([k]) => k)
                  .join(', ') || 'None detected'}
              </span>
            </div>
          )}

          {server.models_available && server.models_available.length > 0 && (
            <div className={styles.modelsSection}>
              <span className={styles.detailLabel}>Models ({server.models_available.length}):</span>
              <div className={styles.modelsList}>
                {server.models_available.map(model => (
                  <span key={model} className={styles.modelTag}>{model}</span>
                ))}
              </div>
            </div>
          )}

          {server.last_health_check && (
            <div className={styles.detailRow}>
              <span className={styles.detailLabel}>Last check:</span>
              <span className={styles.detailValue}>
                {new Date(server.last_health_check).toLocaleString()}
              </span>
            </div>
          )}

          <div className={styles.pullSection}>
            <input
              type="text"
              placeholder="Model name to pull (e.g. llama3.2:3b)"
              value={pullModel}
              onChange={(e) => setPullModel(e.target.value)}
              className={styles.pullInput}
            />
            <button 
              className={styles.pullBtn}
              onClick={handlePull}
              disabled={pulling || !pullModel.trim()}
            >
              {pulling ? '⏳' : '⬇️'} Pull
            </button>
          </div>

          <div className={styles.cardActions}>
            <button 
              className={styles.editBtn}
              onClick={() => onEdit(server)}
            >
              ✏️ Edit
            </button>
            <button 
              className={styles.deleteBtn}
              onClick={() => onDelete(server.id)}
              disabled={server.worker_count > 0}
              title={server.worker_count > 0 ? 'Stop workers first' : 'Delete server'}
            >
              🗑️ Delete
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function AddServerModal({ onClose, onAdd }) {
  const [name, setName] = useState('');
  const [url, setUrl] = useState('');
  const [priority, setPriority] = useState(0);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim() || !url.trim()) {
      setError('Name and URL are required');
      return;
    }

    setSaving(true);
    setError(null);

    try {
      const result = await onAdd({ name: name.trim(), url: url.trim(), priority });
      if (result.error) {
        setError(result.error);
      } else {
        onClose();
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className={styles.modalOverlay} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <h3>Add Ollama Server</h3>
        
        <form onSubmit={handleSubmit}>
          <div className={styles.formGroup}>
            <label>Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. oak-server"
              autoFocus
            />
          </div>

          <div className={styles.formGroup}>
            <label>URL</label>
            <input
              type="text"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="e.g. http://192.168.1.19:11434"
            />
          </div>

          <div className={styles.formGroup}>
            <label>Priority (higher = preferred)</label>
            <input
              type="number"
              value={priority}
              onChange={(e) => setPriority(parseInt(e.target.value) || 0)}
              min="0"
              max="100"
            />
          </div>

          {error && <div className={styles.formError}>{error}</div>}

          <div className={styles.formActions}>
            <button type="button" onClick={onClose} className={styles.cancelBtn}>
              Cancel
            </button>
            <button type="submit" disabled={saving} className={styles.submitBtn}>
              {saving ? 'Adding...' : 'Add Server'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function WorkerCommandModal({ onClose, serverId }) {
  const [command, setCommand] = useState('');
  const [notes, setNotes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const fetchCommand = async () => {
      try {
        const url = serverId 
          ? `/api/workers/command?server_id=${serverId}`
          : '/api/workers/command';
        const res = await fetch(url);
        if (res.ok) {
          const data = await res.json();
          setCommand(data.command);
          setNotes(data.notes || []);
        }
      } catch (err) {
        console.error('Failed to fetch worker command:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchCommand();
  }, [serverId]);

  const handleCopy = () => {
    navigator.clipboard.writeText(command);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={styles.modalOverlay} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <h3>Add External Worker</h3>
        
        <p className={styles.modalDesc}>
          Run this command on any machine with Docker to add a worker:
        </p>

        {loading ? (
          <div className={styles.loading}>Loading...</div>
        ) : (
          <>
            <div className={styles.commandBlock}>
              <pre>{command}</pre>
              <button onClick={handleCopy} className={styles.copyBtn}>
                {copied ? '✓ Copied!' : '📋 Copy'}
              </button>
            </div>

            {notes.length > 0 && (
              <ul className={styles.notesList}>
                {notes.map((note, i) => (
                  <li key={i}>{note}</li>
                ))}
              </ul>
            )}
          </>
        )}

        <div className={styles.formActions}>
          <button onClick={onClose} className={styles.submitBtn}>
            Done
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ServerManager() {
  const [servers, setServers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [showWorkerModal, setShowWorkerModal] = useState(false);
  const [selectedServerId, setSelectedServerId] = useState(null);
  const [testingAll, setTestingAll] = useState(false);

  const fetchServers = async () => {
    try {
      const res = await fetch('/api/servers');
      if (res.ok) {
        const data = await res.json();
        setServers(data.servers || []);
      }
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchServers();
    // Refresh every 30 seconds
    const interval = setInterval(fetchServers, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleAdd = async (serverData) => {
    try {
      const res = await fetch('/api/servers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(serverData)
      });
      
      if (res.ok) {
        await fetchServers();
        return { success: true };
      } else {
        const data = await res.json();
        return { error: data.detail || 'Failed to add server' };
      }
    } catch (err) {
      return { error: err.message };
    }
  };

  const handleTest = async (serverId) => {
    try {
      await fetch(`/api/servers/${serverId}/test`, { method: 'POST' });
      await fetchServers();
    } catch (err) {
      console.error('Test failed:', err);
    }
  };

  const handleTestAll = async () => {
    setTestingAll(true);
    try {
      await fetch('/api/servers/test-all', { method: 'POST' });
      await fetchServers();
    } catch (err) {
      console.error('Test all failed:', err);
    } finally {
      setTestingAll(false);
    }
  };

  const handleDelete = async (serverId) => {
    if (!confirm('Are you sure you want to delete this server?')) return;
    
    try {
      const res = await fetch(`/api/servers/${serverId}`, { method: 'DELETE' });
      if (res.ok) {
        await fetchServers();
      } else {
        const data = await res.json();
        alert(data.detail || 'Failed to delete server');
      }
    } catch (err) {
      alert('Failed to delete server: ' + err.message);
    }
  };

  const handleEdit = (server) => {
    // TODO: Implement edit modal
    console.log('Edit server:', server);
  };

  const handlePullModel = async (serverId, modelName) => {
    try {
      const res = await fetch(`/api/servers/${serverId}/pull-model`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: modelName })
      });
      
      if (res.ok) {
        const data = await res.json();
        alert(`Started pulling ${modelName}. Job ID: ${data.job_id}`);
      } else {
        const data = await res.json();
        alert(data.detail || 'Failed to start pull');
      }
    } catch (err) {
      alert('Failed to pull model: ' + err.message);
    }
  };

  const handleShowWorkerCommand = (serverId = null) => {
    setSelectedServerId(serverId);
    setShowWorkerModal(true);
  };

  const onlineCount = servers.filter(s => s.status === 'online').length;

  if (loading) {
    return <div className={styles.loading}>Loading servers...</div>;
  }

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h3>
          🖥️ Compute Servers
          <span className={styles.serverCount}>
            {onlineCount}/{servers.length} online
          </span>
        </h3>
        <div className={styles.headerActions}>
          <button 
            className={styles.testAllBtn}
            onClick={handleTestAll}
            disabled={testingAll}
          >
            {testingAll ? '⏳' : '🔌'} Test All
          </button>
          <button 
            className={styles.addWorkerBtn}
            onClick={() => handleShowWorkerCommand()}
          >
            👷 Add Worker
          </button>
          <button 
            className={styles.addBtn}
            onClick={() => setShowAddModal(true)}
          >
            ➕ Add Server
          </button>
        </div>
      </div>

      {error && (
        <div className={styles.error}>Error: {error}</div>
      )}

      {servers.length === 0 ? (
        <div className={styles.noServers}>
          <p>No Ollama servers configured</p>
          <p className={styles.hint}>
            Add a server to enable distributed processing across multiple machines
          </p>
        </div>
      ) : (
        <div className={styles.serversList}>
          {servers.map(server => (
            <ServerCard
              key={server.id}
              server={server}
              onTest={handleTest}
              onDelete={handleDelete}
              onEdit={handleEdit}
              onPullModel={handlePullModel}
            />
          ))}
        </div>
      )}

      {showAddModal && (
        <AddServerModal
          onClose={() => setShowAddModal(false)}
          onAdd={handleAdd}
        />
      )}

      {showWorkerModal && (
        <WorkerCommandModal
          onClose={() => setShowWorkerModal(false)}
          serverId={selectedServerId}
        />
      )}
    </div>
  );
}
