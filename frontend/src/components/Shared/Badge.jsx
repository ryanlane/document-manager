import React from 'react'
import styles from './Badge.module.css'

/**
 * Badge component for displaying status indicators, tags, and labels.
 *
 * @param {React.ReactNode} children - Badge content (text, icon, or combination)
 * @param {string} variant - Visual variant: 'default', 'success', 'warning', 'error', 'info', 'primary' (default: 'default')
 * @param {string} size - Size variant: 'sm', 'md' (default: 'md')
 * @param {React.Component} icon - Optional icon component to display before text
 * @param {string} className - Optional additional className
 * @param {string} title - Optional tooltip text
 */
const Badge = ({
  children,
  variant = 'default',
  size = 'md',
  icon: Icon,
  className = '',
  title
}) => {
  return (
    <span
      className={`${styles.badge} ${styles[variant]} ${styles[size]} ${className}`}
      title={title}
    >
      {Icon && <Icon size={12} />}
      {children}
    </span>
  )
}

export default Badge
