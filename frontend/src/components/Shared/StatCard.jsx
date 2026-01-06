import React from 'react'
import Skeleton from './Skeleton'
import styles from './StatCard.module.css'

/**
 * Stat card component for displaying statistics with an icon, title, value, and optional subtitle.
 *
 * @param {React.Component} icon - Icon component to display (e.g., from lucide-react)
 * @param {string} color - Color for the icon
 * @param {string} title - Title/label for the stat
 * @param {number} value - Numeric value to display
 * @param {string} sub - Optional subtitle/additional info
 * @param {boolean} loading - Whether to show skeleton loader
 */
const StatCard = ({ icon: Icon, color, title, value, sub, loading }) => (
  <div className={styles.statCard}>
    <div className={styles.statIcon}>
      <Icon color={color} size={24} />
    </div>
    <div className={styles.statContent}>
      <span className={styles.statTitle}>{title}</span>
      {loading ? (
        <Skeleton height="2rem" width="80%" />
      ) : (
        <span className={styles.statValue}>{value?.toLocaleString() ?? '-'}</span>
      )}
      {sub && <span className={styles.statSub}>{sub}</span>}
    </div>
  </div>
)

export default StatCard
