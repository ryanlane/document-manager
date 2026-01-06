import React from 'react'
import { HardDrive, FileText } from 'lucide-react'
import { Skeleton } from '../Shared'
import styles from './SecondaryStatsRow.module.css'

/**
 * Format bytes to human-readable size
 */
const formatBytes = (bytes) => {
  if (!bytes) return '0 B'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
  return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB'
}

/**
 * Secondary stats row showing storage, files, and extensions.
 *
 * @param {Object} storage - Storage statistics
 * @param {Object} counts - File counts
 * @param {Array} extensions - File extensions with counts
 */
const SecondaryStatsRow = ({ storage, counts, extensions }) => {
  return (
    <div className={styles.secondaryRow}>
      <div className={styles.miniCard}>
        <HardDrive size={18} color="#888" />
        <div>
          <span className={styles.miniLabel}>Storage</span>
          {storage ? (
            <span className={styles.miniValue}>{formatBytes(storage.total_bytes)}</span>
          ) : (
            <Skeleton width="4rem" height="1.2rem" />
          )}
        </div>
      </div>

      <div className={styles.miniCard}>
        <FileText size={18} color="#646cff" />
        <div>
          <span className={styles.miniLabel}>Files</span>
          {counts ? (
            <span className={styles.miniValue}>
              {counts.files.processed?.toLocaleString()} / {counts.files.total?.toLocaleString()}
            </span>
          ) : (
            <Skeleton width="5rem" height="1.2rem" />
          )}
        </div>
      </div>

      {extensions && extensions.length > 0 && (
        <div className={styles.extPills}>
          {extensions.slice(0, 6).map(ext => (
            <span key={ext.ext} className={styles.extPill}>
              {ext.ext} <strong>{ext.count.toLocaleString()}</strong>
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

export default SecondaryStatsRow
