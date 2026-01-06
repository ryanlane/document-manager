import React from 'react'
import { Zap, Settings, CheckCircle2, ChevronUp, ChevronDown } from 'lucide-react'
import styles from '../Setup.module.css'

/**
 * Indexing mode selection step for the setup wizard.
 *
 * @param {string} indexingMode - Selected mode ('fast_scan', 'full_enrichment', 'custom')
 * @param {function} setIndexingMode - Function to update indexing mode
 * @param {boolean} showAdvanced - Whether advanced panel is expanded
 * @param {function} setShowAdvanced - Function to toggle advanced panel
 */
const StepIndexing = ({ indexingMode, setIndexingMode, showAdvanced, setShowAdvanced }) => {
  return (
    <div className={styles.stepContent}>
      <h2>Indexing Strategy</h2>
      <p className={styles.stepDescription}>
        Choose how deeply to analyze your documents. You can change this later.
      </p>

      <div className={styles.indexingOptions}>
        <div
          className={`${styles.indexingOption} ${indexingMode === 'fast_scan' ? styles.selected : ''}`}
          onClick={() => setIndexingMode('fast_scan')}
        >
          <div className={styles.optionHeader}>
            <Zap size={24} />
            <div>
              <h3>Fast Scan</h3>
              <span className={styles.badge}>Recommended</span>
            </div>
            {indexingMode === 'fast_scan' && <CheckCircle2 className={styles.checkmark} />}
          </div>
          <p>Extract text and create embeddings only. Minimal LLM calls for quick indexing.</p>
          <ul className={styles.optionDetails}>
            <li>✓ Text extraction</li>
            <li>✓ Semantic search</li>
            <li>✗ AI-generated titles</li>
            <li>✗ Summaries & tags</li>
          </ul>
          <span className={styles.optionTiming}>~10 min for 10,000 files</span>
        </div>

        <div
          className={`${styles.indexingOption} ${indexingMode === 'full_enrichment' ? styles.selected : ''}`}
          onClick={() => setIndexingMode('full_enrichment')}
        >
          <div className={styles.optionHeader}>
            <Settings size={24} />
            <h3>Full Enrichment</h3>
            {indexingMode === 'full_enrichment' && <CheckCircle2 className={styles.checkmark} />}
          </div>
          <p>Complete AI analysis including titles, summaries, tags, and themes.</p>
          <ul className={styles.optionDetails}>
            <li>✓ Text extraction</li>
            <li>✓ Semantic search</li>
            <li>✓ AI-generated titles</li>
            <li>✓ Summaries & tags</li>
          </ul>
          <span className={styles.optionTiming}>~2-4 hours for 10,000 files</span>
        </div>

        <div
          className={`${styles.indexingOption} ${indexingMode === 'custom' ? styles.selected : ''}`}
          onClick={() => {
            setIndexingMode('custom')
            setShowAdvanced(true)
          }}
        >
          <div className={styles.optionHeader}>
            <Settings size={24} />
            <h3>Custom</h3>
            {indexingMode === 'custom' && <CheckCircle2 className={styles.checkmark} />}
          </div>
          <p>Fine-tune which processing steps to enable.</p>
          <span className={styles.optionTiming}>Configurable in Dashboard</span>
        </div>
      </div>

      {indexingMode === 'custom' && (
        <div className={styles.advancedPanel}>
          <button
            className={styles.advancedToggle}
            onClick={() => setShowAdvanced(!showAdvanced)}
          >
            {showAdvanced ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            Advanced Options
          </button>

          {showAdvanced && (
            <div className={styles.advancedContent}>
              <p className={styles.hint}>
                Custom processing options can be configured from the Dashboard after setup.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default StepIndexing
