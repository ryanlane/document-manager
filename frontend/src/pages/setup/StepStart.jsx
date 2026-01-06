import React from 'react'
import { Loader2, Play } from 'lucide-react'
import styles from '../Setup.module.css'

/**
 * Final step for the setup wizard - summary and start button.
 *
 * @param {string} llmProvider - Selected LLM provider
 * @param {string} selectedModel - Selected chat model
 * @param {Array<string>} selectedFolders - Selected source folders
 * @param {string} indexingMode - Selected indexing mode
 * @param {Array<string>} extensions - Selected file extensions
 * @param {boolean} saving - Whether setup is being saved
 * @param {function} completeSetup - Function to finalize and start setup
 */
const StepStart = ({
  llmProvider,
  selectedModel,
  selectedFolders,
  indexingMode,
  extensions,
  saving,
  completeSetup
}) => {
  return (
    <div className={styles.stepContent}>
      <h2>Ready to Start!</h2>
      <p className={styles.stepDescription}>
        Review your settings and start processing.
      </p>

      <div className={styles.summaryCard}>
        <h3>Configuration Summary</h3>

        <div className={styles.summaryRow}>
          <span className={styles.summaryLabel}>LLM Provider</span>
          <span className={styles.summaryValue}>{llmProvider}</span>
        </div>

        {llmProvider === 'ollama' && selectedModel && (
          <div className={styles.summaryRow}>
            <span className={styles.summaryLabel}>Chat Model</span>
            <span className={styles.summaryValue}>{selectedModel}</span>
          </div>
        )}

        <div className={styles.summaryRow}>
          <span className={styles.summaryLabel}>Source Folders</span>
          <span className={styles.summaryValue}>{selectedFolders.length} folder(s)</span>
        </div>

        <div className={styles.summaryRow}>
          <span className={styles.summaryLabel}>Indexing Mode</span>
          <span className={styles.summaryValue}>
            {indexingMode === 'fast_scan' && 'Fast Scan'}
            {indexingMode === 'full_enrichment' && 'Full Enrichment'}
            {indexingMode === 'custom' && 'Custom'}
          </span>
        </div>

        <div className={styles.summaryRow}>
          <span className={styles.summaryLabel}>File Types</span>
          <span className={styles.summaryValue}>{extensions.length} type(s)</span>
        </div>
      </div>

      <div className={styles.startActions}>
        <button
          className={styles.startButton}
          onClick={completeSetup}
          disabled={saving}
        >
          {saving ? (
            <>
              <Loader2 size={20} className={styles.spinner} />
              Starting...
            </>
          ) : (
            <>
              <Play size={20} />
              Start Processing
            </>
          )}
        </button>

        <p className={styles.hint}>
          Processing will begin in the background. You can monitor progress from the Dashboard.
        </p>
      </div>
    </div>
  )
}

export default StepStart
