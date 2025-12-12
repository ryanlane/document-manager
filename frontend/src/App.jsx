import { useState } from 'react'
import { Search, BookOpen, FileText } from 'lucide-react'

function App() {
  const [query, setQuery] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)

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
        body: JSON.stringify({ query, k: 5 }),
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
    <div className="container">
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
                  <strong>{source.title || 'Untitled'}</strong>
                  <br />
                  <small style={{ marginLeft: '24px' }}>{source.path}</small>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default App
