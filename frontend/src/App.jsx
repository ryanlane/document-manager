import { useState, useEffect } from 'react'
import { Search, BookOpen, FileText, Activity, Server, X } from 'lucide-react'

function App() {
  const [query, setQuery] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState(null)
  const [selectedModel, setSelectedModel] = useState('')
  const [viewingFile, setViewingFile] = useState(null)

  useEffect(() => {
    fetch('/api/system/status')
      .then(res => res.json())
      .then(data => {
        setStatus(data)
        if (data.ollama && data.ollama.chat_model) {
          setSelectedModel(data.ollama.chat_model)
        }
      })
      .catch(err => console.error("Failed to fetch status", err))
  }, [])

  const handleSearch = async (e) => {
    e.preventDefault()
    if (!query.trim()) return

    setLoading(true)
    setResult(null)

    try {
      const response = await fetch('/api/ask', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          query, 
          k: 5,
          model: selectedModel 
        }),
      })
      
      const data = await response.json()
      setResult(data)
    } catch (error) {
      console.error('Error:', error)
      setResult({ answer: 'Error connecting to the archive brain.', sources: [] })
    } finally {
      setLoading(false)
    }
  }

  const handleViewFile = async (e, fileId) => {
    e.preventDefault()
    try {
      const res = await fetch(`/api/files/${fileId}`)
      if (res.ok) {
        const data = await res.json()
        setViewingFile(data)
      } else {
        console.error("Failed to load file")
      }
    } catch (err) {
      console.error(err)
    }
  }

  return (
    <div className="container">
      {viewingFile && (
        <div className="reader-overlay">
          <div className="reader-modal">
            <div className="reader-header">
              <h2>{viewingFile.filename}</h2>
              <button onClick={() => setViewingFile(null)} className="close-btn">
                <X size={24} />
              </button>
            </div>
            <div className="reader-content">
              <pre>{viewingFile.raw_text}</pre>
            </div>
          </div>
        </div>
      )}

      <h1>
        <BookOpen style={{ verticalAlign: 'middle', marginRight: '10px' }} />
        Archive Brain
      </h1>
      
      <form className="search-box" onSubmit={handleSearch}>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask your archive a question..."
        />
        
        {status && status.ollama.available_models && (
          <select 
            value={selectedModel} 
            onChange={(e) => setSelectedModel(e.target.value)}
            className="model-select"
            title="Select Chat Model"
          >
            {status.ollama.available_models.map(model => (
              <option key={model} value={model}>{model}</option>
            ))}
          </select>
        )}

        <button type="submit" disabled={loading}>
          {loading ? 'Thinking...' : <Search size={20} />}
        </button>
      </form>

      {result && (
        <div className="result-card">
          <h3>Answer</h3>
          <div style={{ whiteSpace: 'pre-wrap', lineHeight: '1.6' }}>
            {result.answer}
          </div>

          {result.sources && result.sources.length > 0 && (
            <div className="sources">
              <h4>Sources</h4>
              {result.sources.map((source, index) => (
                <div key={index} className="source-item">
                  <FileText size={16} style={{ verticalAlign: 'middle', marginRight: '5px' }} />
                  <strong>
                    {source.file_id ? (
                      <a 
                        href="#" 
                        onClick={(e) => handleViewFile(e, source.file_id)}
                        className="source-link"
                      >
                        {source.title || 'Untitled'}
                      </a>
                    ) : (
                      source.title || 'Untitled'
                    )}
                  </strong>
                  <br />
                  <small style={{ marginLeft: '24px' }}>{source.path}</small>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {status && (
        <footer className="status-footer">
          <div className="status-group">
            <Server size={14} />
            <span className={`status-indicator ${status.ollama.status}`}></span>
            <span>Ollama</span>
          </div>
          <div className="status-group">
            <span className="status-label">Chat:</span>
            <span className="status-value">{selectedModel || status.ollama.chat_model}</span>
          </div>
          <div className="status-group">
            <span className="status-label">Embed:</span>
            <span className="status-value">{status.ollama.embedding_model}</span>
          </div>
        </footer>
      )}
    </div>
  )
}

export default App
