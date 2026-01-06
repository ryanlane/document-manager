import React from 'react'
import { Loader2, Clock } from 'lucide-react'
import Skeleton from './Skeleton'
import styles from './ProgressBar.module.css'

/**
 * Progress bar component with optional ETA display and status indicators.
 *
 * @param {number} percent - Completion percentage (0-100)
 * @param {string} color - Color for the progress fill
 * @param {string} label - Main label for the progress bar
 * @param {string} sublabel - Optional subtitle below the progress bar
 * @param {boolean} loading - Whether to show skeleton loader
 * @param {boolean} active - Whether the process is currently active (shows spinner)
 * @param {object} eta - ETA object with eta_string and rate_per_min properties
 * @param {boolean} paused - Whether the process is paused
 */
const ProgressBar = ({ percent, color, label, sublabel, loading, active, eta, paused }) => (
  <div className={styles.progressItem}>
    <div className={styles.progressLabel}>
      <span className={styles.progressTitle}>
        {active && !paused && <Loader2 size={14} className={styles.spin} />}
        {label}
      </span>
      <div className={styles.progressRight}>
        {paused ? (
          <span className={styles.etaTag} title="Processing paused">
            <Clock size={10} /> ∞
          </span>
        ) : eta && eta.eta_string && eta.eta_string !== 'Complete' && (
          <span className={styles.etaTag} title={`Rate: ${eta.rate_per_min || 0}/min`}>
            <Clock size={10} /> {eta.eta_string}
          </span>
        )}
        {loading ? (
          <Skeleton width="3rem" height="1rem" />
        ) : (
          <span className={styles.progressPct}>{percent?.toFixed(1) ?? 0}%</span>
        )}
      </div>
    </div>
    <div className={styles.progressTrack}>
      <div
        className={styles.progressFill}
        style={{ width: `${percent ?? 0}%`, backgroundColor: color }}
      />
    </div>
    {sublabel && <span className={styles.progressSub}>{sublabel}</span>}
  </div>
)

export default ProgressBar
