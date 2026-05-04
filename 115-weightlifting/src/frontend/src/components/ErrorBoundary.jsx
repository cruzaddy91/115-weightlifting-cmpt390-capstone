import { Component } from 'react'

class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, info) {
    if (typeof console !== 'undefined' && console.error) {
      console.error('Unhandled UI error:', error, info)
    }
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (!this.state.hasError) {
      return this.props.children
    }
    return (
      <div role="alert" className="error-boundary">
        <h1>Something went wrong.</h1>
        <p>The dashboard hit an unexpected error. Reload the page or try again.</p>
        <pre className="error-boundary-details">
          {this.state.error && this.state.error.toString ? this.state.error.toString() : 'Unknown error'}
        </pre>
        <button type="button" onClick={this.handleReset}>Try again</button>
      </div>
    )
  }
}

export default ErrorBoundary
