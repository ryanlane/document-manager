import { useState, useEffect, useCallback, memo } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, RefreshCw, Loader, Layers, User, FileText, Palette, Settings, Database, FileStack, BarChart3, Zap } from 'lucide-react'
import { Link } from 'react-router-dom'
import { 
  ScatterChart, 
  Scatter, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer, 
  Cell 
} from 'recharts'
import styles from './EmbeddingViz.module.css'

// Color palettes for different groupings
const CATEGORY_COLORS = [
  '#646cff', '#f97316', '#ffc517', '#42b883', '#ec4899', 
  '#8b5cf6', '#06b6d4', '#10b981', '#f59e0b', '#ef4444'
]

const AUTHOR_COLORS = [
  '#3b82f6', '#14b8a6', '#f59e0b', '#8b5cf6', '#ec4899',
  '#06b6d4', '#10b981', '#f97316', '#6366f1', '#84cc16'
]

const FILE_TYPE_COLORS = {
  '.txt': '#646cff',
  '.md': '#42b883',
  '.pdf': '#ff6b6b',
  '.html': '#f97316',
  '.jpg': '#ec4899',
  '.jpeg': '#ec4899',
  '.png': '#a855f7',
  '.gif': '#ffc517',
  'unknown': '#888'
}

function EmbeddingViz() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [statsLoading, setStatsLoading] = useState(true)
  const [stats, setStats] = useState(null)
  const [points, setPoints] = useState([])
  const [dimensions, setDimensions] = useState(2)
  const [algorithm, setAlgorithm] = useState('tsne')
  const [source, setSource] = useState('docs') // 'docs' or 'entries'
  const [colorBy, setColorBy] = useState('category')
  const [categories, setCategories] = useState([])
  const [authors, setAuthors] = useState([])
  const [fileTypes, setFileTypes] = useState([])
  const [selectedCategory, setSelectedCategory] = useState(null)
  const [selectedAuthor, setSelectedAuthor] = useState(null)
  const [hoveredPoint, setHoveredPoint] = useState(null)
  const [isGenerating, setIsGenerating] = useState(false)
  const [autoLoad, setAutoLoad] = useState(false)

  // Fetch quick stats first (fast endpoint)
  const fetchStats = async () => {
    setStatsLoading(true)
    try {
      const res = await fetch('/api/embeddings/stats')
      if (res.ok) {
        const data = await res.json()
        setStats(data)
      }
    } catch (error) {
      console.error('Error fetching stats:', error)
    }
    setStatsLoading(false)
  }

  const fetchVisualization = async () => {
    setIsGenerating(true)
    setLoading(true)
    try {
      const params = new URLSearchParams({
        dimensions: dimensions.toString(),
        algorithm: algorithm,
        source: source,
        limit: '1000'
      })
      
      if (selectedCategory) {
        params.append('category', selectedCategory)
      }
      if (selectedAuthor) {
        params.append('author', selectedAuthor)
      }

      const res = await fetch(`/api/embeddings/visualize?${params}`)
      if (!res.ok) {
        console.error('Failed to fetch visualization:', res.status)
        setLoading(false)
        setIsGenerating(false)
        return
      }

      const data = await res.json()
      setPoints(data.points || [])
      setCategories(data.categories || [])
      setAuthors(data.authors || [])
      setFileTypes(data.file_types || [])
    } catch (error) {
      console.error('Error fetching visualization:', error)
    }
    setLoading(false)
    setIsGenerating(false)
  }

  // Load stats immediately on mount
  useEffect(() => {
    fetchStats()
  }, [])

  // Don't auto-load heavy visualization - let user click Generate
  useEffect(() => {
    if (autoLoad) {
      fetchVisualization()
    }
  }, [autoLoad])

  const getColorForPoint = (point) => {
    if (colorBy === 'category') {
      const idx = categories.indexOf(point.category)
      return CATEGORY_COLORS[idx % CATEGORY_COLORS.length]
    } else if (colorBy === 'author') {
      const idx = authors.indexOf(point.author)
      return AUTHOR_COLORS[idx % AUTHOR_COLORS.length]
    } else if (colorBy === 'file_type') {
      return FILE_TYPE_COLORS[point.file_type] || FILE_TYPE_COLORS['unknown']
    }
    return '#646cff'
  }

  const getLegendItems = () => {
    if (colorBy === 'category') {
      return categories.map((cat, idx) => ({
        label: cat,
        color: CATEGORY_COLORS[idx % CATEGORY_COLORS.length]
      }))
    } else if (colorBy === 'author') {
      return authors.map((author, idx) => ({
        label: author,
        color: AUTHOR_COLORS[idx % AUTHOR_COLORS.length]
      }))
    } else if (colorBy === 'file_type') {
      return fileTypes.map(ft => ({
        label: ft,
        color: FILE_TYPE_COLORS[ft] || FILE_TYPE_COLORS['unknown']
      }))
    }
    return []
  }

  const handlePointClick = (point) => {
    if (source === 'docs' && point && point.file_id) {
      navigate(`/document/${point.file_id}`)
    } else if (point && point.entry_id) {
      navigate(`/entry/${point.entry_id}`)
    }
  }

  // Memoized tooltip to prevent re-render loops
  const CustomTooltip = useCallback(({ active, payload }) => {
    if (active && payload && payload.length > 0) {
      const point = payload[0].payload
      return (
        <div className={styles.tooltip}>
          <div className={styles.tooltipTitle}>{point.title}</div>
          {source === 'docs' && point.filename && (
            <div className={styles.tooltipInfo}>
              <span className={styles.tooltipLabel}>File:</span> {point.filename}
            </div>
          )}
          <div className={styles.tooltipInfo}>
            <span className={styles.tooltipLabel}>Category:</span> {point.category}
          </div>
          <div className={styles.tooltipInfo}>
            <span className={styles.tooltipLabel}>Author:</span> {point.author}
          </div>
          <div className={styles.tooltipInfo}>
            <span className={styles.tooltipLabel}>Type:</span> {point.file_type}
          </div>
          {point.summary && (
            <div className={styles.tooltipSummary}>{point.summary}</div>
          )}
          {source === 'docs' && point.entry_count !== undefined && (
            <div className={styles.tooltipInfo}>
              <span className={styles.tooltipLabel}>Chunks:</span> {point.entry_count}
            </div>
          )}
          <div className={styles.tooltipHint}>Click to view {source === 'docs' ? 'document' : 'entry'}</div>
        </div>
      )
    }
    return null
  }, [source])

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <Link to="/" className={styles.backLink}>
          <ArrowLeft size={20} />
          <span>Back to Home</span>
        </Link>
        <h1 className={styles.title}>Embedding Space Visualization</h1>
        <p className={styles.subtitle}>
          Explore how your documents are organized in semantic vector space
        </p>
      </div>

      {/* Quick Stats Section - loads first */}
      <div className={styles.statsSection}>
        {statsLoading ? (
          <div className={styles.statsLoading}>
            <Loader size={20} className={styles.spinner} />
            <span>Loading embedding stats...</span>
          </div>
        ) : stats ? (
          <div className={styles.statsGrid}>
            <div className={styles.statCard}>
              <BarChart3 size={24} />
              <div className={styles.statInfo}>
                <span className={styles.statValue}>{stats.total_docs?.toLocaleString() || 0}</span>
                <span className={styles.statLabel}>Documents with Embeddings</span>
              </div>
            </div>
            <div className={styles.statCard}>
              <FileText size={24} />
              <div className={styles.statInfo}>
                <span className={styles.statValue}>{stats.total_entries?.toLocaleString() || 0}</span>
                <span className={styles.statLabel}>Chunks with Embeddings</span>
              </div>
            </div>
            <div className={styles.statCard}>
              <Layers size={24} />
              <div className={styles.statInfo}>
                <span className={styles.statValue}>{stats.embedding_dim || '—'}</span>
                <span className={styles.statLabel}>Embedding Dimensions</span>
              </div>
            </div>
            <div className={styles.statCard}>
              <Zap size={24} />
              <div className={styles.statInfo}>
                <span className={styles.statValue}>{stats.model || 'Unknown'}</span>
                <span className={styles.statLabel}>Embedding Model</span>
              </div>
            </div>
          </div>
        ) : null}
      </div>

      <div className={styles.controls}>
        <div className={styles.controlGroup}>
          <label className={styles.controlLabel}>
            <Settings size={16} />
            Algorithm
          </label>
          <select 
            value={algorithm} 
            onChange={(e) => setAlgorithm(e.target.value)}
            className={styles.select}
          >
            <option value="tsne">t-SNE</option>
            <option value="umap">UMAP</option>
          </select>
        </div>

        <div className={styles.controlGroup}>
          <label className={styles.controlLabel}>
            <Database size={16} />
            Source
          </label>
          <div className={styles.sourceToggle}>
            <button
              className={`${styles.sourceBtn} ${source === 'docs' ? styles.active : ''}`}
              onClick={() => setSource('docs')}
              title="Visualize document-level embeddings (Stage 1 search targets)"
            >
              <FileStack size={14} />
              Docs
            </button>
            <button
              className={`${styles.sourceBtn} ${source === 'entries' ? styles.active : ''}`}
              onClick={() => setSource('entries')}
              title="Visualize chunk-level embeddings (Stage 2 search targets)"
            >
              <FileText size={14} />
              Chunks
            </button>
          </div>
        </div>

        <div className={styles.controlGroup}>
          <label className={styles.controlLabel}>
            <Layers size={16} />
            Dimensions
          </label>
          <select 
            value={dimensions} 
            onChange={(e) => setDimensions(parseInt(e.target.value))}
            className={styles.select}
          >
            <option value="2">2D</option>
            <option value="3">3D (Coming Soon)</option>
          </select>
        </div>

        <div className={styles.controlGroup}>
          <label className={styles.controlLabel}>
            <Palette size={16} />
            Color By
          </label>
          <select 
            value={colorBy} 
            onChange={(e) => setColorBy(e.target.value)}
            className={styles.select}
          >
            <option value="category">Category</option>
            <option value="author">Author</option>
            <option value="file_type">File Type</option>
          </select>
        </div>

        <div className={styles.controlGroup}>
          <label className={styles.controlLabel}>
            <Layers size={16} />
            Filter Category
          </label>
          <select 
            value={selectedCategory || ''} 
            onChange={(e) => setSelectedCategory(e.target.value || null)}
            className={styles.select}
          >
            <option value="">All Categories</option>
            {categories.map(cat => (
              <option key={cat} value={cat}>{cat}</option>
            ))}
          </select>
        </div>

        <div className={styles.controlGroup}>
          <label className={styles.controlLabel}>
            <User size={16} />
            Filter Author
          </label>
          <select 
            value={selectedAuthor || ''} 
            onChange={(e) => setSelectedAuthor(e.target.value || null)}
            className={styles.select}
          >
            <option value="">All Authors</option>
            {authors.map(author => (
              <option key={author} value={author}>{author}</option>
            ))}
          </select>
        </div>

        <button 
          className={styles.generateBtn}
          onClick={fetchVisualization}
          disabled={isGenerating}
        >
          {isGenerating ? (
            <>
              <Loader size={16} className={styles.spinner} />
              Generating...
            </>
          ) : points.length === 0 ? (
            <>
              <BarChart3 size={16} />
              Generate Visualization
            </>
          ) : (
            <>
              <RefreshCw size={16} />
              Regenerate
            </>
          )}
        </button>
      </div>

      {/* Show prompt to generate if not yet loaded */}
      {!isGenerating && !loading && points.length === 0 ? (
        <div className={styles.promptContainer}>
          <div className={styles.promptCard}>
            <BarChart3 size={64} strokeWidth={1} />
            <h3>Ready to Visualize</h3>
            <p>
              Click "Generate Visualization" to create a {dimensions}D scatter plot of your 
              {source === 'docs' ? ' documents' : ' chunks'} using {algorithm.toUpperCase()}.
            </p>
            <p className={styles.promptHint}>
              <Zap size={14} />
              This computation may take 10-30 seconds for large datasets
            </p>
            <button 
              className={styles.generateBtnLarge}
              onClick={fetchVisualization}
            >
              <BarChart3 size={20} />
              Generate Visualization
            </button>
          </div>
        </div>
      ) : isGenerating ? (
        <div className={styles.loadingContainer}>
          <Loader size={48} className={styles.spinner} />
          <p>Generating {dimensions}D {source === 'docs' ? 'document' : 'chunk'} visualization using {algorithm.toUpperCase()}...</p>
          <p className={styles.loadingHint}>This may take 10-30 seconds for large datasets</p>
        </div>
      ) : points.length > 0 ? (
        <>
          <div className={styles.vizContainer}>
            <ResponsiveContainer width="100%" height={600}>
              <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                <XAxis 
                  type="number" 
                  dataKey="x" 
                  name="Component 1"
                  stroke="#888"
                  tick={{ fill: '#888' }}
                />
                <YAxis 
                  type="number" 
                  dataKey="y" 
                  name="Component 2"
                  stroke="#888"
                  tick={{ fill: '#888' }}
                />
                <Tooltip content={CustomTooltip} cursor={{ strokeDasharray: '3 3' }} />
                <Scatter 
                  data={points} 
                  fill="#646cff"
                  onClick={(data) => handlePointClick(data)}
                  style={{ cursor: 'pointer' }}
                >
                  {points.map((point, index) => (
                    <Cell key={`cell-${index}`} fill={getColorForPoint(point)} />
                  ))}
                </Scatter>
              </ScatterChart>
            </ResponsiveContainer>
          </div>

          <div className={styles.legend}>
            <h3 className={styles.legendTitle}>Legend ({points.length} {source === 'docs' ? 'documents' : 'chunks'})</h3>
            <div className={styles.legendItems}>
              {getLegendItems().map((item, idx) => (
                <div key={idx} className={styles.legendItem}>
                  <div 
                    className={styles.legendColor} 
                    style={{ backgroundColor: item.color }}
                  />
                  <span className={styles.legendLabel}>{item.label}</span>
                </div>
              ))}
            </div>
          </div>

          <div className={styles.info}>
            <h3>What am I looking at?</h3>
            <p>
              This visualization shows your {source === 'docs' ? 'documents' : 'chunks'} as points in a reduced-dimensional space. 
              {source === 'docs' ? 'Documents' : 'Chunks'} that are semantically similar (have similar meanings) appear closer together.
            </p>
            <div className={styles.infoSection}>
              <h4>Two-Stage Search Architecture</h4>
              <ul>
                <li><strong>Docs view:</strong> Shows document-level embeddings used in Stage 1 of search (broad retrieval)</li>
                <li><strong>Chunks view:</strong> Shows entry-level embeddings used in Stage 2 of search (precision ranking)</li>
              </ul>
            </div>
            <div className={styles.infoSection}>
              <h4>Algorithm Options</h4>
              <ul>
                <li><strong>t-SNE:</strong> Focuses on preserving local structure - nearby points are very similar</li>
                <li><strong>UMAP:</strong> Better at preserving global structure - clusters represent topic groups</li>
              </ul>
            </div>
            <div className={styles.infoSection}>
              <h4>Interactions</h4>
              <ul>
                <li><strong>Hover</strong> over any point to see details</li>
                <li><strong>Click</strong> any point to inspect that {source === 'docs' ? 'document' : 'entry'} in detail</li>
              </ul>
            </div>
          </div>
        </>
      ) : null}
    </div>
  )
}

export default EmbeddingViz
