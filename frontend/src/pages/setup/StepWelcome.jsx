import React from 'react'
import { Rocket, Server, Zap, FolderOpen, Info } from 'lucide-react'
import styles from '../Setup.module.css'

/**
 * Welcome step component for the setup wizard.
 * Displays an introduction and overview of features.
 *
 * @param {Object} firstRunData - Data about first-run detection
 * @param {boolean} firstRunData.has_files - Whether files were detected
 * @param {number} firstRunData.file_count - Number of detected files
 */
const StepWelcome = ({ firstRunData }) => {
  return (
    <div className={styles.stepContent}>
      <div className={styles.welcomeHero}>
        <Rocket size={64} className={styles.heroIcon} />
        <h1>Welcome to Archive Brain</h1>
        <p className={styles.heroSubtitle}>
          Let's get your document archive set up. This wizard will guide you through
          configuring your system for optimal performance.
        </p>
      </div>

      <div className={styles.welcomeFeatures}>
        <div className={styles.feature}>
          <Server size={24} />
          <div>
            <h3>Smart Indexing</h3>
            <p>Automatically extract and organize content from your documents</p>
          </div>
        </div>
        <div className={styles.feature}>
          <Zap size={24} />
          <div>
            <h3>Semantic Search</h3>
            <p>Find documents by meaning, not just keywords</p>
          </div>
        </div>
        <div className={styles.feature}>
          <FolderOpen size={24} />
          <div>
            <h3>Your Data, Your Control</h3>
            <p>Everything runs locally - your documents never leave your machine</p>
          </div>
        </div>
      </div>

      {firstRunData?.has_files && (
        <div className={styles.infoBox}>
          <Info size={20} />
          <span>
            We detected {firstRunData.file_count.toLocaleString()} existing files.
            This wizard will help you configure how they're processed.
          </span>
        </div>
      )}
    </div>
  )
}

export default StepWelcome
