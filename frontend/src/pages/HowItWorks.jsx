import { useState, useEffect } from 'react'
import { Info, Cpu, Database, Search, FileText, Zap, BookOpen, ArrowRight, ChevronDown, ChevronUp, Calculator } from 'lucide-react'
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
        'Detects series information from filenames'
      ],
      techNote: 'Files are stored in PostgreSQL with their full text for fast retrieval.'
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
        'Extracts links/URLs for relationship mapping'
      ],
      techNote: 'Overlap ensures context isn\'t lost at chunk boundaries. Each chunk becomes an "entry" in the database.'
    },
    {
      id: 'enrich',
      title: '3. Enrich (LLM)',
      icon: <Cpu size={24} />,
      color: '#FF9800',
      summary: 'An LLM analyzes each chunk and extracts structured metadata.',
      details: [
        'Sends chunk text to local Ollama LLM',
        'Extracts: title, author, tags, summary',
        'Detects category from folder structure',
        'Calculates quality score (0-1)',
        'Runs in parallel (3 workers)',
        'Retries failed entries up to 3 times'
      ],
      techNote: 'This is the most time-consuming step. Each entry requires an LLM inference call.'
    },
    {
      id: 'embed',
      title: '4. Embed',
      icon: <Database size={24} />,
      color: '#9C27B0',
      summary: 'Text is converted into a 768-dimensional vector for semantic search.',
      details: [
        'Creates embedding combining: title, author, summary, tags, content',
        'Uses nomic-embed-text model (768 dimensions)',
        'Stored using pgvector extension in PostgreSQL',
        'Also creates BM25 search vector for keyword search',
        'Processed in batches of 10 with 4 parallel workers'
      ],
      techNote: 'Embeddings capture semantic meaning, allowing search to find related content even with different words.'
    },
    {
      id: 'search',
      title: '5. Search',
      icon: <Search size={24} />,
      color: '#E91E63',
      summary: 'Your query is embedded and compared against all entries.',
      details: [
        'Query text is converted to an embedding vector',
        'Hybrid search combines vector similarity (70%) + keyword match (30%)',
        'Supports filtering by author, category, tags, file type',
        'Returns top-k most similar entries',
        'Results include similarity scores for transparency'
      ],
      techNote: 'Cosine distance measures how "close" two vectors are in semantic space.'
    }
  ]

  const glossaryTerms = [
    { term: 'Embedding', definition: 'A numerical vector (list of numbers) that represents the meaning of text. Similar meanings produce similar vectors.' },
    { term: 'Vector', definition: 'An ordered list of numbers. In this system, a 768-dimensional vector (768 numbers) represents each text chunk.' },
    { term: 'Cosine Similarity', definition: 'A measure of how similar two vectors are, based on the angle between them. 1.0 = identical, 0 = unrelated.' },
    { term: 'RAG', definition: 'Retrieval-Augmented Generation. Finding relevant documents first, then using them as context for an LLM to answer questions.' },
    { term: 'Semantic Search', definition: 'Finding content by meaning rather than exact keywords. "car" can match "automobile" or "vehicle".' },
    { term: 'BM25', definition: 'A traditional keyword ranking algorithm. Good for exact matches. Combined with vector search for hybrid ranking.' },
    { term: 'Token', definition: 'A unit of text (roughly a word or word-piece). LLMs process text as tokens. ~4 characters per token.' },
    { term: 'Chunk/Segment', definition: 'A portion of a document. Long documents are split into chunks for better search precision.' },
    { term: 'pgvector', definition: 'PostgreSQL extension for storing and searching vector embeddings efficiently.' }
  ]

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1><BookOpen /> How Archive Brain Works</h1>
        <p className={styles.subtitle}>
          Understanding the RAG pipeline from raw files to semantic search
        </p>
      </header>

      {/* Pipeline Visualization */}
      <section className={styles.pipelineSection}>
        <h2>The Processing Pipeline</h2>
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
