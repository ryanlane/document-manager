import React from 'react'
import { Loader2, RefreshCw, AlertCircle } from 'lucide-react'
import { getStatusColor, getStatusIcon } from './setupUtils'
import styles from '../Setup.module.css'

/**
 * Health check step component for the setup wizard.
 * Displays system health status and individual component checks.
 *
 * @param {Object} healthData - Health check results
 * @param {string} healthData.status - Overall status ('ok', 'warning', 'error')
 * @param {Object} healthData.checks - Individual check results
 * @param {boolean} healthLoading - Whether health check is in progress
 * @param {function} runHealthCheck - Function to trigger health check
 */
const StepHealth = ({ healthData, healthLoading, runHealthCheck }) => {
  return (
    <div className={styles.stepContent}>
      <h2>System Health Check</h2>
      <p className={styles.stepDescription}>
        Checking your system configuration to ensure everything is ready.
      </p>

      {healthLoading ? (
        <div className={styles.loadingState}>
          <Loader2 size={32} className={styles.spinner} />
          <span>Running health checks...</span>
        </div>
      ) : healthData ? (
        <>
          <div className={`${styles.overallStatus} ${getStatusColor(healthData.status, styles)}`}>
            {getStatusIcon(healthData.status)}
            <span>
              {healthData.status === 'ok' && 'All systems ready!'}
              {healthData.status === 'warning' && 'System ready with some warnings'}
              {healthData.status === 'error' && 'Some issues need attention'}
            </span>
          </div>

          <div className={styles.healthChecks}>
            {Object.entries(healthData.checks).map(([key, check]) => (
              <div key={key} className={`${styles.healthCheck} ${getStatusColor(check.status, styles)}`}>
                <div className={styles.healthCheckHeader}>
                  {getStatusIcon(check.status)}
                  <span className={styles.healthCheckName}>
                    {key.charAt(0).toUpperCase() + key.slice(1)}
                  </span>
                </div>
                <p className={styles.healthCheckMessage}>{check.message}</p>
                {check.fix && (
                  <p className={styles.healthCheckFix}>
                    <strong>Fix:</strong> {check.fix}
                  </p>
                )}
              </div>
            ))}
          </div>

          <button
            className={styles.refreshButton}
            onClick={runHealthCheck}
            disabled={healthLoading}
          >
            <RefreshCw size={16} />
            Re-run Checks
          </button>
        </>
      ) : (
        <div className={styles.errorState}>
          <AlertCircle size={32} />
          <span>Failed to run health check</span>
          <button onClick={runHealthCheck}>Retry</button>
        </div>
      )}
    </div>
  )
}

export default StepHealth
