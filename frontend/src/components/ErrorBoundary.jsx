import React from 'react'

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null, errorInfo: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true }
  }

  componentDidCatch(error, errorInfo) {
    this.setState({ error, errorInfo })
    console.error('React Error Boundary caught:', error, errorInfo)
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null })
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          padding: '40px',
          textAlign: 'center',
          fontFamily: 'system-ui, -apple-system, sans-serif',
          maxWidth: '600px',
          margin: '80px auto'
        }}>
          <div style={{
            fontSize: '48px',
            marginBottom: '20px'
          }}>
            ⚠️
          </div>
          <h1 style={{
            fontSize: '24px',
            fontWeight: '600',
            marginBottom: '16px',
            color: '#1f2937'
          }}>
            Something went wrong
          </h1>
          <p style={{
            color: '#6b7280',
            marginBottom: '24px',
            lineHeight: '1.6'
          }}>
            The application encountered an unexpected error. This might be a temporary issue.
          </p>
          
          <div style={{ display: 'flex', gap: '12px', justifyContent: 'center', marginBottom: '24px' }}>
            <button
              onClick={this.handleReset}
              style={{
                padding: '10px 20px',
                backgroundColor: '#3b82f6',
                color: 'white',
                border: 'none',
                borderRadius: '8px',
                cursor: 'pointer',
                fontWeight: '500'
              }}
            >
              Try Again
            </button>
            <button
              onClick={() => window.location.reload()}
              style={{
                padding: '10px 20px',
                backgroundColor: '#f3f4f6',
                color: '#374151',
                border: '1px solid #d1d5db',
                borderRadius: '8px',
                cursor: 'pointer',
                fontWeight: '500'
              }}
            >
              Reload Page
            </button>
          </div>

          {this.state.error && (
            <details style={{
              textAlign: 'left',
              backgroundColor: '#fef2f2',
              padding: '16px',
              borderRadius: '8px',
              fontSize: '13px'
            }}>
              <summary style={{ cursor: 'pointer', fontWeight: '500', color: '#991b1b' }}>
                Error Details
              </summary>
              <pre style={{
                marginTop: '12px',
                overflow: 'auto',
                color: '#7f1d1d',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word'
              }}>
                {this.state.error.toString()}
                {this.state.errorInfo?.componentStack}
              </pre>
            </details>
          )}
        </div>
      )
    }

    return this.props.children
  }
}

export default ErrorBoundary
