import { useState, useEffect } from 'react'
import { Search, BookOpen, FileText, Server } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import styles from './Home.module.css'

function Home() {
  const [query, setQuery] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState(null)
  const [selectedModel, setSelectedModel] = useState(localStorage.getItem('archive_brain_model') || '')
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [filters, setFilters] = useState({
    author: '',
    tags: '',
    extension: ''
  })
  const navigate = useNavigate()

  useEffect(() => {
    fetch('/api/system/status')
      .then(res => res.json())
      .then(data => {
        setStatus(data)
        if (data.ollama && data.ollama.chat_model) {
          if (!localStorage.getItem('archive_brain_model')) {
            setSelectedModel(data.ollama.chat_model)
          }
        }
      })
      .catch(err => console.error("Failed to fetch status", err))
  }, [])

  const handleSearch = async (e) => {
    e.preventDefault()
    if (!query.trim()) return

    setLoading(true)
    setResult(null)

    const activeFilters = {}
    if (filters.author) activeFilters.author = filters.author
    if (filters.extension) activeFilters.extension = filters.extension
    if (filters.tags) activeFilters.tags = filters.tags.split(',').map(t => t.trim()).filter(Boolean)

    try {
      const response = await fetch('/api/ask', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          query, 
          k: 5,
          model: selectedModel,
          filters: Object.keys(activeFilters).length > 0 ? activeFilters : null
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

  return (
    <div className={styles.page}>
      <h1 className={styles.title}>
        <BookOpen />
        Archive Brain
      </h1>
      
      <form className={styles.searchForm} onSubmit={handleSearch}>
        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask your archive a question..."
          className={styles.searchInput}
          rows={4}
        />
        
        <div className={styles.searchControls}>
          <button 
            type="button" 
            className={styles.advancedBtn}
            onClick={() => setShowAdvanced(!showAdvanced)}
          >
            {showAdvanced ? 'Hide Filters' : 'Advanced Filters'}
          </button>

          {status && status.ollama.available_models && (
            <select 
              value={selectedModel} 
              onChange={(e) => {
                setSelectedModel(e.target.value)
                localStorage.setItem('archive_brain_model', e.target.value)
              }}
              className={styles.modelSelect}
              title="Select Chat Model"
            >
              {status.ollama.available_models.map(model => (
                <option key={model} value={model}>{model}</option>
              ))}
            </select>
          )}

          <button type="submit" disabled={loading} className={styles.searchButton}>
            {loading ? 'Thinking...' : <Search size={20} />}
          </button>
        </div>

        {showAdvanced && (
          <div className={styles.advancedFilters}>
            <input 
              type="text" 
              placeholder="Author (e.g. John Doe)"
              value={filters.author}
              onChange={e => setFilters({...filters, author: e.target.value})}
            />
            <input 
              type="text" 
              placeholder="Tags (comma separated)"
              value={filters.tags}
              onChange={e => setFilters({...filters, tags: e.target.value})}
            />
            <select 
              value={filters.extension}
              onChange={e => setFilters({...filters, extension: e.target.value})}
            >
              <option value="">All File Types</option>
              <option value=".txt">Text (.txt)</option>
              <option value=".html">HTML (.html)</option>
              <option value=".md">Markdown (.md)</option>
            </select>
          </div>
        )}
      </form>

      {result && (
        <div className={styles.resultCard}>
          <h3>Answer</h3>
          <div className={styles.answer}>
            {result.answer}
          </div>

          {result.sources && result.sources.length > 0 && (
            <div className={styles.sources}>
              <h4>Sources</h4>
              {result.sources.map((source, index) => (
                <div key={index} className={styles.sourceItem}>
                  <span className={styles.sourceLink}>
                    <FileText size={16} />
                    {source.file_id ? (
                      <a 
                        href={`/document/${source.file_id}`}
                        onClick={(e) => {
                            e.preventDefault();
                            navigate(`/document/${source.file_id}`);
                        }}
                      >
                        {source.title || 'Untitled'}
                      </a>
                    ) : (
                      source.title || 'Untitled'
                    )}
                  </span>
                  <small className={styles.sourcePath}>{source.path}</small>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {status && (
        <footer className={styles.statusFooter}>
          <div className={styles.statusGroup}>
            <Server size={14} />
            <span className={`${styles.statusIndicator} ${status.ollama.status === 'online' ? styles.online : ''}`}></span>
            <span>Ollama</span>
          </div>
          <div className={styles.statusGroup}>
            <span className={styles.statusLabel}>Chat:</span>
            <span className={styles.statusValue}>{selectedModel || status.ollama.chat_model}</span>
          </div>
          <div className={styles.statusGroup}>
            <span className={styles.statusLabel}>Embed:</span>
            <span className={styles.statusValue}>{status.ollama.embedding_model}</span>
          </div>
        </footer>
      )}
    </div>
  )
}

export default Home
