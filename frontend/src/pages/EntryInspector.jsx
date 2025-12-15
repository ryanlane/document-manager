import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate, Link, useSearchParams } from 'react-router-dom'
import { 
  ArrowLeft, FileText, Layers, Sparkles, Binary, Search, 
  ChevronDown, ChevronUp, Copy, Check, RefreshCw, AlertCircle,
  Hash, Clock, User, Tag, Folder, ExternalLink, Info, Code,
  Activity, Zap, ArrowRight, CheckCircle
} from 'lucide-react'
import styles from './EntryInspector.module.css'

// Pipeline stage definitions
const PIPELINE_STAGES = [
  { id: 'ingest', name: 'Ingest', icon: FileText, color: '#646cff' },
  { id: 'segment', name: 'Segment', icon: Layers, color: '#f97316' },
  { id: 'enrich', name: 'Enrich', icon: Sparkles, color: '#ffc517' },
  { id: 'embed', name: 'Embed', icon: Binary, color: '#42b883' }
]

function EntryInspector() {
  const { entryId } = useParams()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  
  const [inspection, setInspection] = useState(null)
  const [nearby, setNearby] = useState(null)
  const [embeddingViz, setEmbeddingViz] = useState(null)
  const [entries, setEntries] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  
  // Expandable sections
  const [expandedSections, setExpandedSections] = useState({
    journey: true,
    text: false,
    prompt: false,
    response: false,
    embedding: true,
    nearby: true
  })
  
  // Copy feedback
  const [copied, setCopied] = useState(null)
  
  // Entry list for sidebar
  const [showEntryList, setShowEntryList] = useState(!entryId)
  const [entryFilter, setEntryFilter] = useState('all')

  const fetchInspection = useCallback(async (id) => {
    if (!id) return
    setLoading(true)
    setError(null)
    
    try {
      const [inspectRes, nearbyRes, vizRes] = await Promise.all([
        fetch(`/api/entries/${id}/inspect`),
        fetch(`/api/entries/${id}/nearby?k=8`),
        fetch(`/api/entries/${id}/embedding-viz`)
      ])
      
      if (!inspectRes.ok) throw new Error('Entry not found')
      
      const inspectData = await inspectRes.json()
      setInspection(inspectData)
      
      if (nearbyRes.ok) {
        const nearbyData = await nearbyRes.json()
        setNearby(nearbyData)
      }
      
      if (vizRes.ok) {
        const vizData = await vizRes.json()
        setEmbeddingViz(vizData)
      }
      
      setLoading(false)
    } catch (err) {
      setError(err.message)
      setLoading(false)
    }
  }, [])

  const fetchEntries = useCallback(async () => {
    try {
      const params = new URLSearchParams({ limit: '100' })
      if (entryFilter === 'enriched') params.append('status', 'enriched')
      if (entryFilter === 'pending') params.append('status', 'pending')
      if (entryFilter === 'embedded') params.append('has_embedding', 'true')
      
      const res = await fetch(`/api/entries/list?${params}`)
      const data = await res.json()
      setEntries(data.entries || [])
    } catch (err) {
      console.error('Failed to fetch entries:', err)
    }
  }, [entryFilter])

  useEffect(() => {
    fetchEntries()
  }, [fetchEntries])

  useEffect(() => {
    if (entryId) {
      fetchInspection(entryId)
      setShowEntryList(false)
    }
  }, [entryId, fetchInspection])

  const toggleSection = (section) => {
    setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }))
  }

  const copyToClipboard = async (text, label) => {
    await navigator.clipboard.writeText(text)
    setCopied(label)
    setTimeout(() => setCopied(null), 2000)
  }

  const getStatusColor = (status) => {
    switch (status) {
      case 'complete':
      case 'enriched': return '#42b883'
      case 'pending': return '#ffc517'
      case 'error': return '#ff6b6b'
      default: return '#888'
    }
  }

  const formatNumber = (num) => {
    if (num === null || num === undefined) return 'N/A'
    return typeof num === 'number' ? num.toFixed(4) : num
  }

  if (!entryId && showEntryList) {
    return (
      <div className={styles.page}>
        <div className={styles.header}>
          <div className={styles.title}>
            <Link to="/dashboard" className={styles.backBtn}>
              <ArrowLeft size={20} />
            </Link>
            <h1>Entry Inspector</h1>
          </div>
        </div>
        
        <div className={styles.intro}>
          <Info size={20} />
          <p>
            Select an entry to inspect its full journey through the RAG pipeline.
            You'll see the raw text, enrichment prompt, LLM response, embedding visualization, 
            and semantically similar entries.
          </p>
        </div>
        
        <div className={styles.filterBar}>
          <label>Filter:</label>
          <select value={entryFilter} onChange={(e) => setEntryFilter(e.target.value)}>
            <option value="all">All Entries</option>
            <option value="enriched">Enriched</option>
            <option value="pending">Pending</option>
            <option value="embedded">With Embedding</option>
          </select>
          <span className={styles.entryCount}>{entries.length} entries</span>
        </div>
        
        <div className={styles.entryGrid}>
          {entries.map(entry => (
            <Link 
              to={`/entry/${entry.id}`} 
              key={entry.id} 
              className={styles.entryCard}
            >
              <div className={styles.entryCardHeader}>
                <span className={styles.entryId}>#{entry.id}</span>
                <span 
                  className={styles.entryStatus}
                  style={{ color: getStatusColor(entry.status) }}
                >
                  {entry.status}
                </span>
              </div>
              <h3>{entry.title || 'Untitled'}</h3>
              <p className={styles.entrySummary}>{entry.summary || 'No summary'}</p>
              <div className={styles.entryMeta}>
                {entry.category && <span><Folder size={12} /> {entry.category}</span>}
                {entry.has_embedding && <span><Binary size={12} /> Embedded</span>}
              </div>
              <div className={styles.entryFile}>
                <FileText size={12} /> {entry.filename}
              </div>
            </Link>
          ))}
        </div>
      </div>
    )
  }

  if (loading) {
    return (
      <div className={styles.page}>
        <div className={styles.loading}>
          <RefreshCw size={24} className={styles.spin} />
          <span>Loading entry inspection...</span>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className={styles.page}>
        <div className={styles.error}>
          <AlertCircle size={24} />
          <span>Error: {error}</span>
          <Link to="/entry" className={styles.backLink}>Back to entry list</Link>
        </div>
      </div>
    )
  }

  if (!inspection) return null

  const { entry, source_file, enrichment, embedding, pipeline_journey } = inspection

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div className={styles.title}>
          <button onClick={() => navigate(-1)} className={styles.backBtn}>
            <ArrowLeft size={20} />
          </button>
          <h1>Entry Inspector</h1>
          <span className={styles.entryIdBadge}>#{entry.id}</span>
        </div>
        <div className={styles.headerActions}>
          <Link to="/entry" className={styles.listBtn}>
            <Layers size={16} /> All Entries
          </Link>
          <button onClick={() => fetchInspection(entryId)} className={styles.refreshBtn}>
            <RefreshCw size={16} /> Refresh
          </button>
        </div>
      </div>

      {/* Entry Overview */}
      <div className={styles.overview}>
        <div className={styles.overviewMain}>
          <h2>{entry.title || 'Untitled Entry'}</h2>
          {entry.summary && <p className={styles.summary}>{entry.summary}</p>}
        </div>
        <div className={styles.overviewMeta}>
          {entry.author && (
            <span><User size={14} /> {entry.author}</span>
          )}
          {entry.category && (
            <span><Folder size={14} /> {entry.category}</span>
          )}
          {entry.tags && entry.tags.length > 0 && (
            <span><Tag size={14} /> {entry.tags.join(', ')}</span>
          )}
          <span 
            className={styles.statusBadge}
            style={{ backgroundColor: getStatusColor(entry.status) }}
          >
            {entry.status}
          </span>
        </div>
      </div>

      {/* Pipeline Journey */}
      <div className={styles.section}>
        <div 
          className={styles.sectionHeader}
          onClick={() => toggleSection('journey')}
        >
          <h3><Activity size={18} /> Pipeline Journey</h3>
          {expandedSections.journey ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
        </div>
        
        {expandedSections.journey && (
          <div className={styles.sectionContent}>
            <div className={styles.pipelineFlow}>
              {pipeline_journey.stages.map((stage, index) => {
                const stageConfig = PIPELINE_STAGES.find(s => s.id === stage.name.toLowerCase()) || PIPELINE_STAGES[0]
                const StageIcon = stageConfig.icon
                
                return (
                  <div key={stage.name} className={styles.pipelineStage}>
                    <div 
                      className={`${styles.stageNode} ${styles[stage.status]}`}
                      style={{ '--stage-color': stageConfig.color }}
                    >
                      <StageIcon size={20} />
                      {stage.status === 'complete' && <CheckCircle size={12} className={styles.statusIcon} />}
                    </div>
                    <div className={styles.stageInfo}>
                      <strong>{stage.name}</strong>
                      <span>{stage.description}</span>
                    </div>
                    {index < pipeline_journey.stages.length - 1 && (
                      <div className={styles.stageArrow}>
                        <ArrowRight size={16} />
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
            
            {source_file && (
              <div className={styles.sourceFile}>
                <FileText size={16} />
                <Link to={`/document/${source_file.id}`} className={styles.fileLink}>
                  {source_file.filename}
                </Link>
                <span className={styles.filePath}>{source_file.path}</span>
                {source_file.series_name && (
                  <span className={styles.seriesBadge}>
                    {source_file.series_name} #{source_file.series_number}
                  </span>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Raw Entry Text */}
      <div className={styles.section}>
        <div 
          className={styles.sectionHeader}
          onClick={() => toggleSection('text')}
        >
          <h3><FileText size={18} /> Entry Text</h3>
          <div className={styles.sectionActions}>
            <span className={styles.charCount}>{entry.entry_text?.length || 0} chars</span>
            {expandedSections.text ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
          </div>
        </div>
        
        {expandedSections.text && (
          <div className={styles.sectionContent}>
            <div className={styles.codeBlock}>
              <button 
                className={styles.copyBtn}
                onClick={() => copyToClipboard(entry.entry_text, 'text')}
              >
                {copied === 'text' ? <Check size={14} /> : <Copy size={14} />}
              </button>
              <pre>{entry.entry_text}</pre>
            </div>
            <div className={styles.textMeta}>
              <span>Segment {entry.entry_index + 1}</span>
              <span>Characters: {entry.char_start} - {entry.char_end}</span>
              {entry.content_hash && <span>Hash: {entry.content_hash.slice(0, 12)}...</span>}
            </div>
          </div>
        )}
      </div>

      {/* Enrichment Prompt */}
      <div className={styles.section}>
        <div 
          className={styles.sectionHeader}
          onClick={() => toggleSection('prompt')}
        >
          <h3><Sparkles size={18} /> Enrichment Prompt</h3>
          <div className={styles.sectionActions}>
            <span className={styles.charCount}>{enrichment.prompt_length_chars} chars</span>
            {expandedSections.prompt ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
          </div>
        </div>
        
        {expandedSections.prompt && (
          <div className={styles.sectionContent}>
            <p className={styles.sectionDescription}>
              This is the actual prompt sent to the LLM for extracting metadata from this entry.
            </p>
            <div className={styles.codeBlock}>
              <button 
                className={styles.copyBtn}
                onClick={() => copyToClipboard(enrichment.actual_prompt, 'prompt')}
              >
                {copied === 'prompt' ? <Check size={14} /> : <Copy size={14} />}
              </button>
              <pre className={styles.prompt}>{enrichment.actual_prompt}</pre>
            </div>
          </div>
        )}
      </div>

      {/* Raw JSON Response */}
      <div className={styles.section}>
        <div 
          className={styles.sectionHeader}
          onClick={() => toggleSection('response')}
        >
          <h3><Code size={18} /> LLM Response (extra_meta)</h3>
          {expandedSections.response ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
        </div>
        
        {expandedSections.response && (
          <div className={styles.sectionContent}>
            <p className={styles.sectionDescription}>
              The raw JSON response from the LLM, stored in the entry's extra_meta field.
            </p>
            {enrichment.raw_response ? (
              <div className={styles.codeBlock}>
                <button 
                  className={styles.copyBtn}
                  onClick={() => copyToClipboard(JSON.stringify(enrichment.raw_response, null, 2), 'response')}
                >
                  {copied === 'response' ? <Check size={14} /> : <Copy size={14} />}
                </button>
                <pre className={styles.json}>
                  {JSON.stringify(enrichment.raw_response, null, 2)}
                </pre>
              </div>
            ) : (
              <div className={styles.noData}>No enrichment response yet</div>
            )}
          </div>
        )}
      </div>

      {/* Embedding Visualization */}
      <div className={styles.section}>
        <div 
          className={styles.sectionHeader}
          onClick={() => toggleSection('embedding')}
        >
          <h3><Binary size={18} /> Embedding Vector</h3>
          {expandedSections.embedding ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
        </div>
        
        {expandedSections.embedding && (
          <div className={styles.sectionContent}>
            {embedding ? (
              <>
                <p className={styles.sectionDescription}>
                  This entry's meaning is encoded as a {embedding.dimensions}-dimensional vector. 
                  The heatmap below shows averaged values across 64 buckets.
                </p>
                
                <div className={styles.embeddingStats}>
                  <div className={styles.stat}>
                    <span className={styles.statLabel}>Dimensions</span>
                    <span className={styles.statValue}>{embedding.dimensions}</span>
                  </div>
                  <div className={styles.stat}>
                    <span className={styles.statLabel}>Min</span>
                    <span className={styles.statValue}>{formatNumber(embedding.min)}</span>
                  </div>
                  <div className={styles.stat}>
                    <span className={styles.statLabel}>Max</span>
                    <span className={styles.statValue}>{formatNumber(embedding.max)}</span>
                  </div>
                  <div className={styles.stat}>
                    <span className={styles.statLabel}>Mean</span>
                    <span className={styles.statValue}>{formatNumber(embedding.mean)}</span>
                  </div>
                  <div className={styles.stat}>
                    <span className={styles.statLabel}>Std Dev</span>
                    <span className={styles.statValue}>{formatNumber(embedding.std)}</span>
                  </div>
                  <div className={styles.stat}>
                    <span className={styles.statLabel}>Norm</span>
                    <span className={styles.statValue}>{formatNumber(embedding.norm)}</span>
                  </div>
                </div>
                
                {embeddingViz?.visualization && (
                  <div className={styles.embeddingViz}>
                    <h4>Vector Heatmap (64 buckets)</h4>
                    <div className={styles.heatmap}>
                      {embeddingViz.visualization.buckets.map((value, i) => (
                        <div 
                          key={i}
                          className={styles.heatmapCell}
                          style={{ 
                            backgroundColor: `rgba(100, 108, 255, ${value})`,
                            opacity: 0.3 + value * 0.7
                          }}
                          title={`Bucket ${i}: ${embeddingViz.visualization.raw_buckets[i].toFixed(4)}`}
                        />
                      ))}
                    </div>
                    <div className={styles.heatmapLegend}>
                      <span>Low</span>
                      <div className={styles.legendGradient}></div>
                      <span>High</span>
                    </div>
                  </div>
                )}
                
                <div className={styles.vectorSample}>
                  <h4>Sample Values</h4>
                  <div className={styles.vectorValues}>
                    <div>
                      <span className={styles.vectorLabel}>First 10:</span>
                      <code>[{embedding.first_10_values?.map(v => v.toFixed(3)).join(', ')}]</code>
                    </div>
                    <div>
                      <span className={styles.vectorLabel}>Last 10:</span>
                      <code>[{embedding.last_10_values?.map(v => v.toFixed(3)).join(', ')}]</code>
                    </div>
                  </div>
                </div>
              </>
            ) : (
              <div className={styles.noData}>
                <Binary size={32} />
                <span>No embedding generated yet</span>
                <p>This entry needs to be enriched first, then the embedding will be generated.</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Nearby Entries */}
      <div className={styles.section}>
        <div 
          className={styles.sectionHeader}
          onClick={() => toggleSection('nearby')}
        >
          <h3><Search size={18} /> Nearby in Vector Space</h3>
          <span className={styles.nearbyCount}>{nearby?.nearby?.length || 0} similar</span>
          {expandedSections.nearby ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
        </div>
        
        {expandedSections.nearby && (
          <div className={styles.sectionContent}>
            {nearby?.nearby && nearby.nearby.length > 0 ? (
              <>
                <p className={styles.sectionDescription}>
                  These entries are closest to this one in the 768-dimensional embedding space.
                  Higher similarity means more semantically related content.
                </p>
                <div className={styles.nearbyList}>
                  {nearby.nearby.map((n, index) => (
                    <Link 
                      to={`/entry/${n.id}`} 
                      key={n.id} 
                      className={styles.nearbyItem}
                    >
                      <div className={styles.nearbyRank}>#{index + 1}</div>
                      <div className={styles.nearbyInfo}>
                        <h4>{n.title || 'Untitled'}</h4>
                        <p>{n.summary}</p>
                        <div className={styles.nearbyMeta}>
                          {n.category && <span><Folder size={12} /> {n.category}</span>}
                          <span><FileText size={12} /> {n.filename}</span>
                        </div>
                      </div>
                      <div className={styles.similarityScore}>
                        <div 
                          className={styles.similarityBar}
                          style={{ width: `${n.similarity * 100}%` }}
                        />
                        <span>{(n.similarity * 100).toFixed(1)}%</span>
                      </div>
                    </Link>
                  ))}
                </div>
              </>
            ) : (
              <div className={styles.noData}>
                {entry.has_embedding 
                  ? 'No similar entries found'
                  : 'Embedding required to find similar entries'}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default EntryInspector
