import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import DOMPurify from 'dompurify'
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

  const isHtml = file.filename.toLowerCase().endsWith('.html')

  const getProcessedHtml = (htmlContent) => {
    if (!htmlContent) return ''
    
    // Parse HTML to extract body
    const parser = new DOMParser()
    const doc = parser.parseFromString(htmlContent, 'text/html')

    // Transform links
    const links = doc.getElementsByTagName('a')
    Array.from(links).forEach(link => {
      const href = link.getAttribute('href')
      if (!href) return

      if (href.includes('asstr.org')) {
        const newHref = href.replace(/^https?:\/\/(www\.)?asstr\.org/, '')
        link.setAttribute('href', newHref || '/')
      } else if (!href.match(/^(https?:|mailto:|#)/)) {
        // Relative link - rewrite to use resolver
        link.setAttribute('href', `/resolve?from=${id}&to=${encodeURIComponent(href)}`)
      }
    })

    // Transform images
    const images = doc.getElementsByTagName('img')
    Array.from(images).forEach(img => {
      const src = img.getAttribute('src')
      if (src && !src.match(/^(https?:|data:)/)) {
        // Relative image - rewrite to use proxy
        img.setAttribute('src', `/api/files/${id}/proxy/${src}`)
      }
    })

    const bodyContent = doc.body.innerHTML
    
    // Sanitize content
    return DOMPurify.sanitize(bodyContent, {
      USE_PROFILES: { html: true },
      FORBID_TAGS: ['script', 'style', 'iframe', 'object', 'embed', 'link', 'meta', 'head', 'title'],
    })
  }

  const getProcessedText = (text) => {
    if (!text) return ''
    // Remove the specific boilerplate found in some .txt files
    let processed = text.replace(/<!--ADULTSONLY-->[\s\S]*?Note: This story was dynamically reformatted for online reading convenience\.\s*<\/font>/i, '')
    // Remove the shorter boilerplate ending in <pre>
    processed = processed.replace(/<!--ADULTSONLY-->[\s\S]*?<pre>/i, '')
    
    // Reflow paragraphs:
    // 1. Split by double newlines (paragraph breaks)
    // 2. Replace single newlines within paragraphs with spaces
    // 3. Join back with double newlines
    return processed
      .split(/\n\s*\n/)
      .map(para => para.replace(/\n/g, ' ').replace(/\s+/g, ' ').trim())
      .join('\n\n')
      .trim()
  }

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <button onClick={() => navigate(-1)} className={styles.backBtn}>
          <ArrowLeft size={20} /> Back
        </button>
        <h1>{file.filename}</h1>
      </div>
      <article className={styles.content}>
        {isHtml ? (
          <div 
            className={styles.text}
            dangerouslySetInnerHTML={{ __html: getProcessedHtml(file.raw_text) }}
          />
        ) : (
          <div className={styles.text}>
            {getProcessedText(file.raw_text)}
          </div>
        )}
      </article>
    </div>
  )
}

export default DocumentView
