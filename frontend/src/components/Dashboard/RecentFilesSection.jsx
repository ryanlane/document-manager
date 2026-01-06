import React from 'react'
import { Link } from 'react-router-dom'
import { FileText } from 'lucide-react'
import styles from './RecentFilesSection.module.css'

/**
 * Recent files section showing recently processed files.
 *
 * @param {Array} recentFiles - Array of recent file objects
 */
const RecentFilesSection = ({ recentFiles }) => {
  if (!recentFiles || recentFiles.length === 0) {
    return null
  }

  return (
    <div className={styles.recentSection}>
      <h3>Recent Files</h3>
      <div className={styles.recentList}>
        {recentFiles.map(file => (
          <Link to={`/document/${file.id}`} key={file.id} className={styles.recentItem}>
            <FileText size={14} />
            <span className={styles.recentName}>{file.filename}</span>
            <span className={`${styles.recentStatus} ${styles[file.status]}`}>
              {file.status}
            </span>
          </Link>
        ))}
      </div>
    </div>
  )
}

export default RecentFilesSection
