import { CheckCircle2, AlertCircle } from 'lucide-react'

/**
 * Get CSS class name for a status value
 * @param {string} status - 'ok', 'warning', or 'error'
 * @returns {string} CSS class name
 */
export const getStatusColor = (status, styles) => {
  switch (status) {
    case 'ok': return styles.statusOk
    case 'warning': return styles.statusWarning
    case 'error': return styles.statusError
    default: return ''
  }
}

/**
 * Get icon component for a status value
 * @param {string} status - 'ok', 'warning', or 'error'
 * @returns {JSX.Element} Icon component
 */
export const getStatusIcon = (status) => {
  switch (status) {
    case 'ok': return <CheckCircle2 size={18} />
    case 'warning': return <AlertCircle size={18} />
    case 'error': return <AlertCircle size={18} />
    default: return null
  }
}

/**
 * Check if a setting path is locked by environment variable
 * @param {string} path - Setting path (e.g., 'ollama.model')
 * @param {Object} envOverrides - Environment overrides object
 * @returns {boolean}
 */
export const isEnvSet = (path, envOverrides) => {
  return envOverrides[path]?.locked === true
}

/**
 * Get environment variable name for a setting path
 * @param {string} path - Setting path
 * @param {Object} envOverrides - Environment overrides object
 * @returns {string|undefined}
 */
export const getEnvVarName = (path, envOverrides) => {
  return envOverrides[path]?.env_var
}

/**
 * Check if any environment overrides exist
 * @param {Object} envOverrides - Environment overrides object
 * @returns {boolean}
 */
export const hasAnyEnvOverrides = (envOverrides) => {
  return Object.keys(envOverrides).length > 0
}
