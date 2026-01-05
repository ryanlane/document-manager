import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { 
  ArrowLeft, 
  RefreshCw, 
  Info, 
  ChevronDown, 
  ChevronUp,
  FileText,
  Calendar,
  User,
  Tag,
  Folder,
  HardDrive,
  Hash,
  Clock,
  Layers,
  Copy,
  Check,
  ExternalLink,
  Download
} from 'lucide-react'
import DOMPurify from 'dompurify'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import styles from './DocumentView.module.css'

function DocumentView() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [file, setFile] = useState(null)
  const [content, setContent] = useState('')
  const [contentLoading, setContentLoading] = useState(false)
  const [contentError, setContentError] = useState(null)
  const [metadata, setMetadata] = useState(null)
  const [showMetadata, setShowMetadata] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [reEnriching, setReEnriching] = useState(false)
  const [copied, setCopied] = useState(null)

  useEffect(() => {
    let cancelled = false

    const load = async () => {
      setLoading(true)
      setError(null)
      setFile(null)
      setContent('')
      setContentError(null)
      setContentLoading(false)
      setMetadata(null)
      setShowMetadata(false)

      try {
        const res = await fetch(`/api/files/${id}`)
        if (!res.ok) throw new Error('Failed to load file')
        const data = await res.json()
        if (cancelled) return
        setFile(data)
        setLoading(false)

        const name = (data.filename || '').toLowerCase()
        const previewable =
          name.endsWith('.txt') ||
          name.endsWith('.md') ||
          name.endsWith('.markdown') ||
          name.endsWith('.html') ||
          name.endsWith('.htm')

        if (!previewable) return

        setContentLoading(true)
        try {
          const contentRes = await fetch(`/api/files/${id}/content`)
          if (!contentRes.ok) throw new Error('Failed to load file content')
          const text = await contentRes.text()
          if (cancelled) return
          setContent(text)
        } catch (err) {
          if (cancelled) return
          console.error(err)
          setContentError(err.message)
        } finally {
          if (!cancelled) setContentLoading(false)
        }
      } catch (err) {
        if (cancelled) return
        console.error(err)
        setError(err.message)
        setLoading(false)
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [id])

  const loadMetadata = async () => {
    if (metadata) {
      setShowMetadata(!showMetadata)
      return
    }
    try {
      const res = await fetch(`/api/files/${id}/metadata`)
      if (res.ok) {
        setMetadata(await res.json())
        setShowMetadata(true)
      }
    } catch (err) {
      console.error('Failed to load metadata:', err)
    }
  }

  const copyToClipboard = async (text, field) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(field)
      setTimeout(() => setCopied(null), 2000)
    } catch (err) {
      console.error('Failed to copy:', err)
    }
  }

  const handleReEnrich = async () => {
    setReEnriching(true)
    try {
      const res = await fetch(`/api/files/${id}/re-enrich`, { method: 'POST' })
      const data = await res.json()
      alert(data.message || 'Queued for re-enrichment')
    } catch (err) {
      alert('Failed to queue for re-enrichment')
    } finally {
      setReEnriching(false)
    }
  }

  if (loading) return <div className={styles.loading}>Loading...</div>
  if (error) return <div className={styles.error}>Error: {error}</div>
  if (!file) return <div className={styles.error}>File not found</div>

  const filename = file.filename.toLowerCase()
  const isHtml = filename.endsWith('.html')
  const isMarkdown = filename.endsWith('.md') || filename.endsWith('.markdown')

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
        <div className={styles.headerActions}>
          <a 
            href={`/api/files/${id}/content`}
            target="_blank"
            rel="noopener noreferrer"
            className={styles.openSourceBtn}
            title="Open original source file"
          >
            <ExternalLink size={16} />
            Open Source
          </a>
          <a 
            href={`/api/files/${id}/content`}
            download
            className={styles.downloadBtn}
            title="Download original file"
          >
            <Download size={16} />
          </a>
          <button 
            onClick={loadMetadata}
            className={`${styles.metadataBtn} ${showMetadata ? styles.active : ''}`}
            title="Show file metadata"
          >
            <Info size={16} />
            Metadata
            {showMetadata ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
          <button 
            onClick={handleReEnrich} 
            disabled={reEnriching}
            className={styles.reEnrichBtn}
            title="Re-analyze this file with the LLM"
          >
            <RefreshCw size={16} className={reEnriching ? styles.spin : ''} />
            {reEnriching ? 'Queuing...' : 'Re-enrich'}
          </button>
        </div>
      </div>

      {/* Metadata Panel */}
      {showMetadata && metadata && (
        <div className={styles.metadataPanel}>
          {/* File Location */}
          <div className={styles.metaSection}>
            <h3><Folder size={16} /> File Location</h3>
            <div className={styles.metaRow}>
              <span className={styles.metaLabel}>Container Path:</span>
              <code className={styles.metaValue}>{metadata.paths.container}</code>
              <button 
                onClick={() => copyToClipboard(metadata.paths.container, 'container')}
                className={styles.copyBtn}
                title="Copy path"
              >
                {copied === 'container' ? <Check size={14} /> : <Copy size={14} />}
              </button>
            </div>
            {metadata.paths.host ? (
              <div className={styles.metaRow}>
                <span className={styles.metaLabel}>Host Path:</span>
                <code className={styles.metaValue}>{metadata.paths.host}</code>
                <button 
                  onClick={() => copyToClipboard(metadata.paths.host, 'host')}
                  className={styles.copyBtn}
                  title="Copy path"
                >
                  {copied === 'host' ? <Check size={14} /> : <Copy size={14} />}
                </button>
              </div>
            ) : (
              <div className={styles.metaNote}>
                <ExternalLink size={14} />
                <span>Configure host path mapping in Settings → Sources to see the original file location</span>
              </div>
            )}
          </div>

          {/* File Info */}
          <div className={styles.metaSection}>
            <h3><FileText size={16} /> File Info</h3>
            <div className={styles.metaGrid}>
              <div className={styles.metaItem}>
                <HardDrive size={14} />
                <span>{metadata.file_info.size_formatted}</span>
              </div>
              <div className={styles.metaItem}>
                <FileText size={14} />
                <span>{metadata.file_info.file_type} ({metadata.file_info.extension})</span>
              </div>
              {metadata.file_info.modified && (
                <div className={styles.metaItem}>
                  <Calendar size={14} />
                  <span>Modified: {new Date(metadata.file_info.modified).toLocaleDateString()}</span>
                </div>
              )}
              <div className={styles.metaItem}>
                <Layers size={14} />
                <span>{metadata.processing.entry_count} chunk{metadata.processing.entry_count !== 1 ? 's' : ''}</span>
              </div>
            </div>
            {metadata.file_info.sha256 && (
              <div className={styles.metaRow}>
                <span className={styles.metaLabel}>SHA256:</span>
                <code className={styles.metaValueSmall}>{metadata.file_info.sha256}</code>
                <button 
                  onClick={() => copyToClipboard(metadata.file_info.sha256, 'sha256')}
                  className={styles.copyBtn}
                  title="Copy hash"
                >
                  {copied === 'sha256' ? <Check size={14} /> : <Copy size={14} />}
                </button>
              </div>
            )}
          </div>

          {/* Enrichment Data */}
          {(metadata.enrichment.title || metadata.enrichment.author || metadata.enrichment.tags?.length > 0) && (
            <div className={styles.metaSection}>
              <h3><Tag size={16} /> Enrichment</h3>
              {metadata.enrichment.title && (
                <div className={styles.metaRow}>
                  <span className={styles.metaLabel}>Title:</span>
                  <span className={styles.metaValue}>{metadata.enrichment.title}</span>
                </div>
              )}
              {metadata.enrichment.author && (
                <div className={styles.metaRow}>
                  <span className={styles.metaLabel}>Author:</span>
                  <span className={styles.metaValue}>{metadata.enrichment.author}</span>
                </div>
              )}
              {metadata.enrichment.category && (
                <div className={styles.metaRow}>
                  <span className={styles.metaLabel}>Category:</span>
                  <span className={styles.metaValue}>{metadata.enrichment.category}</span>
                </div>
              )}
              {metadata.enrichment.tags?.length > 0 && (
                <div className={styles.metaTags}>
                  {metadata.enrichment.tags.map((tag, i) => (
                    <span key={i} className={styles.tag}>{tag}</span>
                  ))}
                </div>
              )}
              {metadata.enrichment.summary && (
                <div className={styles.metaSummary}>
                  <span className={styles.metaLabel}>Summary:</span>
                  <p>{metadata.enrichment.summary}</p>
                </div>
              )}
            </div>
          )}

          {/* Series Info */}
          {metadata.series && (
            <div className={styles.metaSection}>
              <h3><Layers size={16} /> Series</h3>
              <div className={styles.metaRow}>
                <span className={styles.metaLabel}>Series:</span>
                <span className={styles.metaValue}>
                  {metadata.series.name} - Part {metadata.series.number}
                  {metadata.series.total && ` of ${metadata.series.total}`}
                </span>
              </div>
            </div>
          )}

          {/* Processing Status */}
          <div className={styles.metaSection}>
            <h3><Clock size={16} /> Processing</h3>
            <div className={styles.metaGrid}>
              <div className={styles.metaItem}>
                <span className={`${styles.statusDot} ${metadata.processing.status === 'ok' ? styles.ok : styles.error}`} />
                <span>File: {metadata.processing.status}</span>
              </div>
              <div className={styles.metaItem}>
                <span className={`${styles.statusDot} ${metadata.processing.doc_status === 'embedded' ? styles.ok : styles.pending}`} />
                <span>Doc: {metadata.processing.doc_status}</span>
              </div>
            </div>
          </div>
        </div>
      )}

      <article className={styles.content}>
        {contentLoading ? (
          <div className={styles.loading}>Loading content...</div>
        ) : contentError ? (
          <div className={styles.error}>Error: {contentError}</div>
        ) : isHtml ? (
          <div 
            className={styles.text}
            dangerouslySetInnerHTML={{ __html: getProcessedHtml(content) }}
          />
        ) : isMarkdown ? (
          <div className={`${styles.text} ${styles.markdown}`}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {content || ''}
            </ReactMarkdown>
          </div>
        ) : (
          <div className={styles.text}>
            {getProcessedText(content)}
          </div>
        )}
      </article>
    </div>
  )
}

export default DocumentView
