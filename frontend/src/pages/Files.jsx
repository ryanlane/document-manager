import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { FileText, ArrowLeft, ArrowRight } from 'lucide-react'
import styles from './Files.module.css'

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
    <div className={styles.page}>
      <div className={styles.header}>
        <h1>Ingested Files ({total.toLocaleString()})</h1>
      </div>

      {loading ? (
        <div className={styles.loading}>Loading...</div>
      ) : (
        <div className={styles.list}>
          {files.map(file => (
            <div key={file.id} className={styles.item}>
              <FileText size={20} className={styles.itemIcon} />
              <div className={styles.itemContent}>
                <Link to={`/document/${file.id}`}>
                  {file.filename}
                </Link>
                <small>{file.path}</small>
              </div>
              <span className={styles.itemDate}>
                {new Date(file.created_at).toLocaleDateString()}
              </span>
            </div>
          ))}
        </div>
      )}

      <div className={styles.pagination}>
        <button 
          onClick={() => setPage(p => Math.max(1, p - 1))}
          disabled={page === 1}
        >
          <ArrowLeft size={16} /> Prev
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
