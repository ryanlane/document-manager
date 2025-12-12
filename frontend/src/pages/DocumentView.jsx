import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'

function DocumentView() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch(`/api/files/${id}`)
      .then(res => {
        if (!res.ok) throw new Error('Failed to load file')
        return res.json()
      })
      .then(data => {
        setFile(data)
        setLoading(false)
      })
      .catch(err => {
        console.error(err)
        setError(err.message)
        setLoading(false)
      })
  }, [id])

  if (loading) return <div className="container">Loading...</div>
  if (error) return <div className="container">Error: {error}</div>
  if (!file) return <div className="container">File not found</div>

  return (
    <div className="document-view-container">
      <div className="document-header">
        <button onClick={() => navigate(-1)} className="back-btn">
          <ArrowLeft size={24} /> Back
        </button>
        <h1>{file.filename}</h1>
      </div>
      <article className="document-content">
        <div style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit', lineHeight: '1.6', fontSize: '1.1rem' }}>
          {file.raw_text}
        </div>
      </article>
    </div>
  )
}

export default DocumentView
