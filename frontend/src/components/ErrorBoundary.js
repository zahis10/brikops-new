import React from 'react';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('[ErrorBoundary] Uncaught error:', error, errorInfo);
  }

  handleRefresh = () => {
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div
          dir="rtl"
          style={{
            minHeight: '100vh',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: '#f8fafc',
            fontFamily: 'system-ui, -apple-system, sans-serif',
            padding: '24px',
          }}
        >
          <div
            style={{
              textAlign: 'center',
              maxWidth: '400px',
              width: '100%',
            }}
          >
            <div style={{ fontSize: '64px', marginBottom: '16px' }}>😕</div>
            <h1
              style={{
                fontSize: '24px',
                fontWeight: 700,
                color: '#1e293b',
                marginBottom: '8px',
              }}
            >
              משהו השתבש
            </h1>
            <p
              style={{
                fontSize: '16px',
                color: '#64748b',
                marginBottom: '24px',
                lineHeight: 1.6,
              }}
            >
              נסה לרענן את הדף. אם הבעיה חוזרת, פנה לתמיכה.
            </p>
            <button
              onClick={this.handleRefresh}
              style={{
                background: '#f59e0b',
                color: '#ffffff',
                border: 'none',
                borderRadius: '8px',
                padding: '12px 32px',
                fontSize: '16px',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'background 0.2s',
              }}
              onMouseOver={(e) => (e.target.style.background = '#d97706')}
              onMouseOut={(e) => (e.target.style.background = '#f59e0b')}
            >
              רענן את הדף
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
