import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import styles from './DocumentView.module.css'

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

  if (loading) return <div className={styles.loading}>Loading...</div>
  if (error) return <div className={styles.error}>Error: {error}</div>
  if (!file) return <div className={styles.error}>File not found</div>

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <button onClick={() => navigate(-1)} className={styles.backBtn}>
          <ArrowLeft size={20} /> Back
        </button>
        <h1>{file.filename}</h1>
      </div>
      <article className={styles.content}>
        <div className={styles.text}>
          {file.raw_text}
        </div>
      </article>
    </div>
  )
}

export default DocumentView
