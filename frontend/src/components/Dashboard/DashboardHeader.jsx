import React from 'react'
import { Clock } from 'lucide-react'
import styles from './DashboardHeader.module.css'

/**
 * Dashboard header with title and last update timestamp.
 *
 * @param {Date|null} lastUpdate - Timestamp of last data refresh
 */
const DashboardHeader = ({ lastUpdate }) => {
  return (
    <div className={styles.header}>
      <h1>Dashboard</h1>
      {lastUpdate && (
        <span className={styles.lastUpdate}>
          <Clock size={14} /> {lastUpdate.toLocaleTimeString()}
        </span>
      )}
    </div>
  )
}

export default DashboardHeader
