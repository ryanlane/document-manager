import React, { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import styles from './CollapsibleSection.module.css'

/**
 * Collapsible section component with a clickable header that toggles content visibility.
 *
 * @param {React.ReactNode} title - Title/header content (can be string or JSX)
 * @param {React.ReactNode} children - Content to show/hide when toggled
 * @param {boolean} defaultCollapsed - Whether the section starts collapsed (default: false)
 * @param {React.ReactNode} headerRight - Optional content to display on the right side of header
 * @param {string} className - Optional additional className for the container
 */
const CollapsibleSection = ({
  title,
  children,
  defaultCollapsed = false,
  headerRight,
  className = ''
}) => {
  const [collapsed, setCollapsed] = useState(defaultCollapsed)

  return (
    <div className={`${styles.section} ${className}`}>
      <div className={styles.header} onClick={() => setCollapsed(!collapsed)}>
        <div className={styles.headerLeft}>
          <button className={styles.collapseBtn} type="button">
            {collapsed ? <ChevronRight size={16} /> : <ChevronDown size={16} />}
          </button>
          <div className={styles.title}>{title}</div>
        </div>
        {headerRight && (
          <div className={styles.headerRight} onClick={(e) => e.stopPropagation()}>
            {headerRight}
          </div>
        )}
      </div>
      {!collapsed && (
        <div className={styles.content}>
          {children}
        </div>
      )}
    </div>
  )
}

export default CollapsibleSection
