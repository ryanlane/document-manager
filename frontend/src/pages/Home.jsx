import { useState, useEffect } from 'react'
import { Search, BookOpen, FileText, Server, Info, Zap, Type, Layers } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import styles from './Home.module.css'

function Home() {
  const [query, setQuery] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState(null)
  const [selectedModel, setSelectedModel] = useState(localStorage.getItem('archive_brain_model') || '')
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [showExplainer, setShowExplainer] = useState(false)
  const [searchMode, setSearchMode] = useState(localStorage.getItem('search_mode') || 'hybrid')
  const [searchExplanation, setSearchExplanation] = useState(null)
  const [filters, setFilters] = useState({
    author: '',
    tags: '',
    extension: '',
    category: ''
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
    setSearchExplanation(null)

    const activeFilters = {}
    if (filters.author) activeFilters.author = filters.author
    if (filters.extension) activeFilters.extension = filters.extension
    if (filters.category) activeFilters.category = filters.category
    if (filters.tags) activeFilters.tags = filters.tags.split(',').map(t => t.trim()).filter(Boolean)

    try {
      // Fetch explained search results if explainer is on
      if (showExplainer) {
        const explainRes = await fetch(`/api/search/explain?query=${encodeURIComponent(query)}&k=5&mode=${searchMode}`)
        const explainData = await explainRes.json()
        setSearchExplanation(explainData)
      }

      const response = await fetch('/api/ask', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          query, 
          k: 5,
          model: selectedModel,
          filters: Object.keys(activeFilters).length > 0 ? activeFilters : null,
          search_mode: searchMode
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

  const handleSearchModeChange = (mode) => {
    setSearchMode(mode)
    localStorage.setItem('search_mode', mode)
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
            {showAdvanced ? 'Hide Filters' : 'Filters'}
          </button>
          
          <button 
            type="button" 
            className={`${styles.advancedBtn} ${showExplainer ? styles.explainerActive : ''}`}
            onClick={() => setShowExplainer(!showExplainer)}
            title="Show detailed search explanation"
          >
            <Info size={14} /> {showExplainer ? 'Hide Explainer' : 'Explain Search'}
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

        {/* Search Mode Selector */}
        <div className={styles.searchModeRow}>
          <span className={styles.searchModeLabel}>Search Mode:</span>
          <div className={styles.searchModeButtons}>
            <button
              type="button"
              className={`${styles.modeBtn} ${searchMode === 'vector' ? styles.active : ''}`}
              onClick={() => handleSearchModeChange('vector')}
              title="Semantic search using vector embeddings"
            >
              <Zap size={14} /> Semantic
            </button>
            <button
              type="button"
              className={`${styles.modeBtn} ${searchMode === 'keyword' ? styles.active : ''}`}
              onClick={() => handleSearchModeChange('keyword')}
              title="Traditional keyword matching (BM25)"
            >
              <Type size={14} /> Keyword
            </button>
            <button
              type="button"
              className={`${styles.modeBtn} ${searchMode === 'hybrid' ? styles.active : ''}`}
              onClick={() => handleSearchModeChange('hybrid')}
              title="Combines semantic (70%) and keyword (30%) search"
            >
              <Layers size={14} /> Hybrid
            </button>
          </div>
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
            <input 
              type="text" 
              placeholder="Category (e.g. story, docs)"
              value={filters.category}
              onChange={e => setFilters({...filters, category: e.target.value})}
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

      {/* Search Explainer Display */}
      {showExplainer && searchExplanation && (
        <div className={styles.explainerCard}>
          <h3><Info size={18} /> Search Explanation</h3>
          
          <div className={styles.explainerSection}>
            <h4>Query Analysis</h4>
            <p><strong>Your query:</strong> "{searchExplanation.query}"</p>
            <p><strong>Search mode:</strong> {searchExplanation.search_mode}</p>
            {searchExplanation.search_mode === 'hybrid' && (
              <p className={styles.explainerNote}>
                Hybrid mode combines semantic similarity (70%) with keyword matching (30%)
              </p>
            )}
          </div>

          {searchExplanation.results && searchExplanation.results.length > 0 && (
            <div className={styles.explainerSection}>
              <h4>Result Scores</h4>
              <div className={styles.scoreTable}>
                <div className={styles.scoreHeader}>
                  <span>Document</span>
                  <span>Similarity</span>
                  {searchExplanation.search_mode === 'hybrid' && <span>Keyword Score</span>}
                </div>
                {searchExplanation.results.map((r, i) => (
                  <div key={i} className={styles.scoreRow}>
                    <span className={styles.scoreTitle}>{r.title || r.filename}</span>
                    <span className={styles.scoreValue}>
                      {(r.similarity_score * 100).toFixed(1)}%
                    </span>
                    {searchExplanation.search_mode === 'hybrid' && (
                      <span className={styles.scoreValue}>
                        {r.bm25_score ? r.bm25_score.toFixed(2) : 'N/A'}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className={styles.explainerSection}>
            <h4>How This Works</h4>
            <p>
              {searchExplanation.search_mode === 'vector' && 
                "Your query was converted into a 768-dimensional vector using the embedding model, then compared against document vectors using cosine similarity."}
              {searchExplanation.search_mode === 'keyword' && 
                "Traditional keyword matching using BM25 algorithm to find documents containing your search terms."}
              {searchExplanation.search_mode === 'hybrid' && 
                "Combined semantic understanding (vector similarity) with keyword matching for better accuracy."}
            </p>
          </div>
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
