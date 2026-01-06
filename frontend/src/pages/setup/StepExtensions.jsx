import React from 'react'
import { Info } from 'lucide-react'
import styles from '../Setup.module.css'

/**
 * File type selection step for the setup wizard.
 *
 * @param {Array<string>} extensions - Selected file extensions
 * @param {string} extensionPreset - Selected preset ('documents', 'images', 'everything')
 * @param {function} applyExtensionPreset - Function to apply a preset
 */
const StepExtensions = ({ extensions, extensionPreset, applyExtensionPreset }) => {
  return (
    <div className={styles.stepContent}>
      <h2>File Types</h2>
      <p className={styles.stepDescription}>
        Select which file types to index.
      </p>

      <div className={styles.presetButtons}>
        <button
          className={`${styles.presetButton} ${extensionPreset === 'documents' ? styles.selected : ''}`}
          onClick={() => applyExtensionPreset('documents')}
        >
          Documents Only
        </button>
        <button
          className={`${styles.presetButton} ${extensionPreset === 'images' ? styles.selected : ''}`}
          onClick={() => applyExtensionPreset('images')}
        >
          Images Only
        </button>
        <button
          className={`${styles.presetButton} ${extensionPreset === 'everything' ? styles.selected : ''}`}
          onClick={() => applyExtensionPreset('everything')}
        >
          Everything
        </button>
      </div>

      <div className={styles.extensionsList}>
        <h4>Selected Extensions</h4>
        <div className={styles.extensionTags}>
          {extensions.map(ext => (
            <span key={ext} className={styles.extensionTag}>
              {ext}
            </span>
          ))}
        </div>
      </div>

      <div className={styles.infoBox}>
        <Info size={20} />
        <span>You can add more file types later from Settings.</span>
      </div>
    </div>
  )
}

export default StepExtensions
