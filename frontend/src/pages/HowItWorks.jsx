import { useState, useEffect } from 'react'
import { Info, Cpu, Database, Search, FileText, Zap, BookOpen, ArrowRight, ChevronDown, ChevronUp, Calculator, Layers, Target, FileCheck } from 'lucide-react'
import styles from './HowItWorks.module.css'

function HowItWorks() {
  const [enrichmentConfig, setEnrichmentConfig] = useState(null)
  const [expandedStage, setExpandedStage] = useState(null)
  const [similarityText1, setSimilarityText1] = useState('')
  const [similarityText2, setSimilarityText2] = useState('')
  const [similarityResult, setSimilarityResult] = useState(null)
  const [calculatingScore, setCalculatingScore] = useState(false)

  useEffect(() => {
    fetch('/api/config/enrichment')
      .then(res => res.json())
      .then(data => setEnrichmentConfig(data))
      .catch(err => console.error(err))
  }, [])

  const calculateSimilarity = async () => {
    if (!similarityText1.trim() || !similarityText2.trim()) return
    
    setCalculatingScore(true)
    try {
      const res = await fetch('/api/similarity', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text1: similarityText1, text2: similarityText2 })
      })
      const data = await res.json()
      setSimilarityResult(data)
    } catch (err) {
      console.error(err)
      setSimilarityResult({ error: 'Failed to calculate similarity' })
    } finally {
      setCalculatingScore(false)
    }
  }

  const stages = [
    {
      id: 'ingest',
      title: '1. Ingest',
      icon: <FileText size={24} />,
      color: '#4CAF50',
      summary: 'Files are read from disk and their text content is extracted.',
      details: [
        'Scans configured directories for new or updated files',
        'Supports .txt, .md, .html, and more (PDF/DOCX via Tika)',
        'Computes SHA256 hash to detect changes',
        'Extracts raw text content',
        'Detects series information from filenames',
        'Stores author_key and source for filtering'
      ],
      techNote: 'Files are stored in PostgreSQL with their full text. Each file becomes a "document" in the system.'
    },
    {
      id: 'segment',
      title: '2. Segment',
      icon: <Zap size={24} />,
      color: '#2196F3',
      summary: 'Long documents are split into smaller, searchable chunks.',
      details: [
        'Splits on paragraph boundaries (double newlines)',
        'Limits chunks to ~4000 characters (~1000 tokens)',
        'Adds 200 character overlap between chunks for context',
        'Preserves markdown headers as context markers',
        'Deduplicates identical content across files',
        'Each chunk inherits source/author from parent document'
      ],
      techNote: 'Average document has ~66 chunks. Each chunk becomes an "entry" in the database for fine-grained search.'
    },
    {
      id: 'doc-enrich',
      title: '3a. Doc Enrich',
      icon: <FileCheck size={24} />,
      color: '#a855f7',
      summary: 'Documents are summarized at the doc-level for fast coarse search.',
      details: [
        'Generates a doc_summary from first ~4000 chars of document',
        'LLM extracts title, category, and key themes',
        'Much faster than enriching every chunk individually',
        'Doc-level metadata can be inherited by chunks',
        'Enables two-stage search (search docs first, then chunks)'
      ],
      techNote: 'Doc enrichment is ~66x faster than chunk enrichment since we process 1 doc instead of 66 chunks.'
    },
    {
      id: 'doc-embed',
      title: '3b. Doc Embed',
      icon: <Target size={24} />,
      color: '#06b6d4',
      summary: 'Document summaries are embedded for Stage 1 vector search.',
      details: [
        'Creates doc_embedding (768 dims) from doc_summary',
        'Creates doc_search_vector (tsvector) for keyword search',
        'Uses IVFFlat index (lists=200) for fast approximate search',
        'Only ~125k docs to search vs 8M+ chunks',
        'Enables sub-50ms doc-level retrieval'
      ],
      techNote: 'Searching 125k doc embeddings is ~60x faster than searching 8M chunk embeddings.'
    },
    {
      id: 'chunk-enrich',
      title: '4a. Chunk Enrich',
      icon: <Cpu size={24} />,
      color: '#ffc517',
      summary: 'Chunks can inherit metadata from docs or be enriched individually.',
      details: [
        'Chunks inherit title, summary, category from parent doc',
        'Inheritance is instant (no LLM calls needed)',
        'High-value chunks can be deep-enriched with full LLM analysis',
        'Extracts: title, author, tags, summary, entities',
        'Quality scoring for prioritizing important content'
      ],
      techNote: 'Inheritance reduced enrichment time by ~410k LLM calls. Only high-value chunks need individual enrichment.'
    },
    {
      id: 'chunk-embed',
      title: '4b. Chunk Embed',
      icon: <Database size={24} />,
      color: '#ff6464',
      summary: 'Chunk text is embedded for Stage 2 fine-grained search.',
      details: [
        'Creates embedding combining: title, author, summary, tags, content',
        'Uses nomic-embed-text model (768 dimensions)',
        'Stored using pgvector with IVFFlat index (lists=2000)',
        'Also creates BM25 search vector for keyword search',
        'Only searched within top docs from Stage 1'
      ],
      techNote: 'With IVFFlat indexing and ivfflat.probes=10, chunk search is ~10ms within filtered doc set.'
    },
    {
      id: 'search',
      title: '5. Two-Stage Search',
      icon: <Search size={24} />,
      color: '#E91E63',
      summary: 'Queries use doc-level search first, then chunk-level for precision.',
      details: [
        'Stage 1: Search doc embeddings to find top 20 relevant documents (~20ms)',
        'Stage 2: Search chunk embeddings only within those docs (~10ms)',
        'Uses Reciprocal Rank Fusion (RRF) to combine vector + keyword scores',
        'RRF formula: score = 0.7/(60+vector_rank) + 0.3/(60+keyword_rank)',
        'Supports filtering by author, category, tags, file type',
        'Total search time: ~50-80ms for 8M+ chunks'
      ],
      techNote: 'Two-stage search is ~10x faster than flat search while maintaining quality through RRF ranking.'
    }
  ]

  const glossaryTerms = [
    { term: 'Two-Stage Search', definition: 'First search at doc-level (fast, coarse), then search chunks within top docs (precise). Dramatically faster for large collections.' },
    { term: 'RRF (Reciprocal Rank Fusion)', definition: 'A ranking algorithm that combines multiple score sources by their rank positions. More robust than raw score combination.' },
    { term: 'IVFFlat Index', definition: 'Inverted File Flat index for approximate nearest neighbor search. Clusters vectors into lists for faster querying.' },
    { term: 'Embedding', definition: 'A numerical vector (768 numbers) that represents the meaning of text. Similar meanings produce similar vectors.' },
    { term: 'Cosine Similarity', definition: 'A measure of how similar two vectors are, based on the angle between them. 1.0 = identical, 0 = unrelated.' },
    { term: 'RAG', definition: 'Retrieval-Augmented Generation. Finding relevant documents first, then using them as context for an LLM to answer questions.' },
    { term: 'BM25', definition: 'A traditional keyword ranking algorithm. Good for exact matches. Combined with vector search for hybrid ranking.' },
    { term: 'Inheritance', definition: 'Copying doc-level metadata (title, summary, category) to chunks, avoiding expensive per-chunk LLM calls.' },
    { term: 'pgvector', definition: 'PostgreSQL extension for storing and searching vector embeddings efficiently with support for various index types.' }
  ]

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1><BookOpen /> How Archive Brain Works</h1>
        <p className={styles.subtitle}>
          A two-stage RAG pipeline for searching 8M+ entries in under 100ms
        </p>
      </header>

      {/* Pipeline Visualization */}
      <section className={styles.pipelineSection}>
        <h2>The Processing Pipeline</h2>
        <p className={styles.pipelineIntro}>
          Archive Brain uses a two-stage architecture: documents are enriched and embedded at both the 
          <strong> doc-level</strong> (for fast coarse search) and <strong>chunk-level</strong> (for precise retrieval).
          This enables sub-100ms search across millions of entries.
        </p>
        <div className={styles.pipeline}>
          {stages.map((stage, index) => (
            <div key={stage.id} className={styles.stageWrapper}>
              <div 
                className={`${styles.stage} ${expandedStage === stage.id ? styles.expanded : ''}`}
                style={{ borderColor: stage.color }}
                onClick={() => setExpandedStage(expandedStage === stage.id ? null : stage.id)}
              >
                <div className={styles.stageHeader} style={{ background: stage.color }}>
                  {stage.icon}
                  <span>{stage.title}</span>
                  {expandedStage === stage.id ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                </div>
                <div className={styles.stageSummary}>{stage.summary}</div>
                
                {expandedStage === stage.id && (
                  <div className={styles.stageDetails}>
                    <ul>
                      {stage.details.map((detail, i) => (
                        <li key={i}>{detail}</li>
                      ))}
                    </ul>
                    <div className={styles.techNote}>
                      <Info size={14} /> {stage.techNote}
                    </div>
                  </div>
                )}
              </div>
              {index < stages.length - 1 && (
                <ArrowRight className={styles.arrow} size={24} />
              )}
            </div>
          ))}
        </div>
      </section>

      {/* Similarity Calculator (E10) */}
      <section className={styles.calculatorSection}>
        <h2><Calculator size={24} /> Vector Similarity Calculator</h2>
        <p className={styles.sectionDesc}>
          Compare two pieces of text and see how similar they are in vector space. 
          This demonstrates how semantic search finds related content.
        </p>
        
        <div className={styles.calculatorGrid}>
          <div className={styles.textInput}>
            <label>Text 1</label>
            <textarea
              value={similarityText1}
              onChange={(e) => setSimilarityText1(e.target.value)}
              placeholder="Enter first text to compare..."
              rows={4}
            />
          </div>
          <div className={styles.textInput}>
            <label>Text 2</label>
            <textarea
              value={similarityText2}
              onChange={(e) => setSimilarityText2(e.target.value)}
              placeholder="Enter second text to compare..."
              rows={4}
            />
          </div>
        </div>
        
        <button 
          className={styles.calculateBtn}
          onClick={calculateSimilarity}
          disabled={calculatingScore || !similarityText1.trim() || !similarityText2.trim()}
        >
          {calculatingScore ? 'Calculating...' : 'Calculate Similarity'}
        </button>

        {similarityResult && !similarityResult.error && (
          <div className={styles.similarityResult}>
            <div className={styles.scoreDisplay}>
              <span className={styles.scoreLabel}>Similarity Score:</span>
              <span className={styles.scoreValue} style={{
                color: similarityResult.similarity > 0.7 ? '#4CAF50' : 
                       similarityResult.similarity > 0.4 ? '#FF9800' : '#f44336'
              }}>
                {(similarityResult.similarity * 100).toFixed(1)}%
              </span>
            </div>
            <div className={styles.scoreBar}>
              <div 
                className={styles.scoreFill} 
                style={{ width: `${similarityResult.similarity * 100}%` }}
              />
            </div>
            <p className={styles.scoreExplanation}>
              {similarityResult.similarity > 0.8 && "Very similar! These texts have closely related meanings."}
              {similarityResult.similarity > 0.6 && similarityResult.similarity <= 0.8 && "Moderately similar. These texts share some semantic overlap."}
              {similarityResult.similarity > 0.4 && similarityResult.similarity <= 0.6 && "Somewhat related. There's some connection in meaning."}
              {similarityResult.similarity <= 0.4 && "Not very similar. These texts have different meanings."}
            </p>
          </div>
        )}
      </section>

      {/* Current Enrichment Prompt (E5) */}
      <section className={styles.promptSection}>
        <h2><Cpu size={24} /> Current Enrichment Prompt</h2>
        <p className={styles.sectionDesc}>
          This is the exact prompt sent to the LLM for each document chunk. 
          The model extracts metadata in JSON format.
        </p>
        
        {enrichmentConfig && (
          <div className={styles.promptDisplay}>
            <div className={styles.promptMeta}>
              <span><strong>Model:</strong> {enrichmentConfig.model || 'Not configured'}</span>
              <span><strong>Max Text Length:</strong> {enrichmentConfig.max_text_length} chars</span>
            </div>
            <pre className={styles.promptTemplate}>
              {enrichmentConfig.prompt_template}
            </pre>
            <p className={styles.promptNote}>
              <Info size={14} /> Edit this prompt in <code>config/config.yaml</code> to customize metadata extraction.
            </p>
          </div>
        )}
      </section>

      {/* Glossary (E9) */}
      <section className={styles.glossarySection}>
        <h2><BookOpen size={24} /> Glossary</h2>
        <div className={styles.glossaryGrid}>
          {glossaryTerms.map((item, i) => (
            <div key={i} className={styles.glossaryItem}>
              <dt>{item.term}</dt>
              <dd>{item.definition}</dd>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}

export default HowItWorks
