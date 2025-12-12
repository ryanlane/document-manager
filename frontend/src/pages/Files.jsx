import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { FileText, ArrowLeft, ArrowRight } from 'lucide-react'

function Files() {
  const [files, setFiles] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const limit = 50

  useEffect(() => {
    fetchFiles()
  }, [page])

  const fetchFiles = async () => {
    setLoading(true)
    try {
      const skip = (page - 1) * limit
      const res = await fetch(`/api/files?skip=${skip}&limit=${limit}`)
      const data = await res.json()
      setFiles(data.items)
      setTotal(data.total)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const totalPages = Math.ceil(total / limit)

  return (
    <div className="container">
      <div style={{ width: '100%', maxWidth: '800px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1>Ingested Files ({total})</h1>
        <Link to="/" className="back-btn">Back to Search</Link>
      </div>

      {loading ? (
        <div>Loading...</div>
      ) : (
        <div className="files-list" style={{ width: '100%', maxWidth: '800px' }}>
          {files.map(file => (
            <div key={file.id} className="file-item" style={{ 
              background: '#1a1a1a', 
              padding: '1rem', 
              marginBottom: '0.5rem', 
              borderRadius: '8px',
              display: 'flex',
              alignItems: 'center',
              gap: '1rem'
            }}>
              <FileText size={20} />
              <div style={{ flex: 1, overflow: 'hidden' }}>
                <Link to={`/document/${file.id}`} style={{ fontWeight: 'bold', display: 'block', textDecoration: 'none', color: 'inherit' }}>
                  {file.filename}
                </Link>
                <small style={{ color: '#888', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', display: 'block' }}>
                  {file.path}
                </small>
              </div>
              <span style={{ fontSize: '0.8rem', color: '#666' }}>
                {new Date(file.created_at).toLocaleDateString()}
              </span>
            </div>
          ))}
        </div>
      )}

      <div className="pagination" style={{ display: 'flex', gap: '1rem', marginTop: '1rem', alignItems: 'center' }}>
        <button 
          onClick={() => setPage(p => Math.max(1, p - 1))}
          disabled={page === 1}
        >
          <ArrowLeft size={16} /> Previous
        </button>
        <span>Page {page} of {totalPages || 1}</span>
        <button 
          onClick={() => setPage(p => Math.min(totalPages, p + 1))}
          disabled={page === totalPages || totalPages === 0}
        >
          Next <ArrowRight size={16} />
        </button>
      </div>
    </div>
  )
}

export default Files
