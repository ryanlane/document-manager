import React from 'react'
import styles from './Skeleton.module.css'

/**
 * Skeleton loader component for displaying placeholder content while data is loading.
 *
 * @param {string} width - Width of the skeleton (default: '100%')
 * @param {string} height - Height of the skeleton (default: '1rem')
 * @param {object} style - Additional inline styles
 */
const Skeleton = ({ width = '100%', height = '1rem', style = {} }) => (
  <div
    className={styles.skeleton}
    style={{ width, height, ...style }}
  />
)

export default Skeleton
