import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  confirmPasswordReset,
  login,
  register as apiRegister,
  requestPasswordReset,
} from '../services/api'
import { formatApiError } from '../utils/errors'
import './Login.css'

const Login = () => {
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [userType, setUserType] = useState('coach')
  const [coachSignupCode, setCoachSignupCode] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [searchParams] = useSearchParams()
  const hasResetParams = searchParams.has('uid') && searchParams.has('token')
  const [authMode, setAuthMode] = useState(hasResetParams ? 'reset' : 'login')
  const [registerSuccess, setRegisterSuccess] = useState('')
  const navigate = useNavigate()
  const showRegister = authMode === 'register'
  const showForgot = authMode === 'forgot'
  const showReset = authMode === 'reset'

  const handleLogin = async (event) => {
    event.preventDefault()
    setError('')
    setRegisterSuccess('')
    setLoading(true)

    try {
      const response = await login(username, password)
      const ut = response.user?.user_type
      const dest = ut === 'head_coach' ? '/head' : ut === 'coach' ? '/coach' : '/athlete'
      navigate(dest, { replace: true })
    } catch (err) {
      setError(formatApiError(err, 'Login failed.'))
    } finally {
      setLoading(false)
    }
  }

  const handleRegister = async (event) => {
    event.preventDefault()
    setError('')
    setRegisterSuccess('')
    setLoading(true)

    try {
      if (userType === 'athlete' && username.includes('_')) {
        setError('For athlete accounts, enter the base username without underscores. The system adds the numeric prefix.')
        return
      }
      const extras = userType === 'coach' ? { coach_signup_code: coachSignupCode } : {}
      await apiRegister(username, email, password, userType, extras)
      setRegisterSuccess('Account created. You can log in now.')
      setAuthMode('login')
      setEmail('')
      setPassword('')
      setCoachSignupCode('')
    } catch (err) {
      setError(formatApiError(err, 'Registration failed.'))
    } finally {
      setLoading(false)
    }
  }

  const handlePasswordResetRequest = async (event) => {
    event.preventDefault()
    setError('')
    setRegisterSuccess('')
    setLoading(true)

    try {
      await requestPasswordReset(email)
      setRegisterSuccess('If that email exists, a reset link has been sent.')
    } catch (err) {
      setError(formatApiError(err, 'Password reset request failed.'))
    } finally {
      setLoading(false)
    }
  }

  const handlePasswordResetConfirm = async (event) => {
    event.preventDefault()
    setError('')
    setRegisterSuccess('')
    if (password !== confirmPassword) {
      setError('Passwords do not match.')
      return
    }
    setLoading(true)

    try {
      await confirmPasswordReset(searchParams.get('uid'), searchParams.get('token'), password)
      setRegisterSuccess('Password reset. You can log in now.')
      setAuthMode('login')
      setPassword('')
      setConfirmPassword('')
      navigate('/login', { replace: true })
    } catch (err) {
      setError(formatApiError(err, 'Password reset failed.'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-container">
      <div className="login-grid">
        <div className="login-intro">
          <div className="login-eyebrow">Secure system access</div>
          <h1>115 Weightlifting</h1>
          <p className="login-intro-copy">
            Role-specific access for coach planning, athlete execution, and performance review in one unified interface.
          </p>
          <div className="login-intro-list">
            <div className="login-intro-item">
              <span className="label">Programming</span>
              <span className="value">Structured week plans</span>
            </div>
            <div className="login-intro-item">
              <span className="label">Tracking</span>
              <span className="value">Completion, logs, and PR history</span>
            </div>
            <div className="login-intro-item">
              <span className="label">Analysis</span>
              <span className="value">Charts and Sinclair scoring</span>
            </div>
          </div>
        </div>

        <div className="login-card">
          <div className="login-card-frame">
            <div className="login-eyebrow">Role-aware access</div>
            <h2>
              {showRegister ? 'Create account' : showForgot ? 'Reset password' : showReset ? 'Choose new password' : 'Log in'}
            </h2>
            <p className="login-subtitle">115 Weightlifting</p>
            {showRegister ? (
              <form onSubmit={handleRegister}>
                <div className="form-group">
                  <label htmlFor="reg-username">Username</label>
                  <input
                    id="reg-username"
                    type="text"
                    value={username}
                    onChange={(event) => {
                      const value = userType === 'athlete'
                        ? event.target.value.replaceAll('_', '')
                        : event.target.value
                      setUsername(value)
                    }}
                    required
                    autoComplete="username"
                  />
                  {userType === 'athlete' && (
                    <p className="form-hint">
                      Enter only the base athlete name. The system will assign the `000_`, `001_`, `002_` prefix.
                    </p>
                  )}
                </div>
                <div className="form-group">
                  <label htmlFor="reg-email">Email</label>
                  <input
                    id="reg-email"
                    type="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    required
                    autoComplete="email"
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="reg-password">Password (min 8)</label>
                  <input
                    id="reg-password"
                    type="password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    required
                    minLength={8}
                    autoComplete="new-password"
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="user_type">Role</label>
                  <select id="user_type" value={userType} onChange={(event) => setUserType(event.target.value)}>
                    <option value="coach">Coach</option>
                    <option value="athlete">Athlete</option>
                  </select>
                </div>
                {userType === 'coach' && (
                  <div className="form-group">
                    <label htmlFor="coach_signup_code">Coach signup code</label>
                    <input
                      id="coach_signup_code"
                      type="password"
                      value={coachSignupCode}
                      onChange={(event) => setCoachSignupCode(event.target.value)}
                      required
                      autoComplete="off"
                      placeholder="Provided by program administrator"
                    />
                    <p className="form-hint">
                      Ask your program administrator for this code. Coach accounts are gated to prevent unauthorized program authorship.
                    </p>
                  </div>
                )}
                {error && <div className="login-error">{error}</div>}
                {registerSuccess && <div className="login-success">{registerSuccess}</div>}
                <button type="submit" className="login-btn" disabled={loading}>
                  {loading ? 'Creating...' : 'Create account'}
                </button>
              </form>
            ) : showForgot ? (
              <form onSubmit={handlePasswordResetRequest}>
                <div className="form-group">
                  <label htmlFor="reset-email">Account email</label>
                  <input
                    id="reset-email"
                    type="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    required
                    autoComplete="email"
                  />
                </div>
                <p className="form-hint">
                  If this email belongs to an account, a reset link will be sent. In local Docker, the link prints in backend logs.
                </p>
                {error && <div className="login-error">{error}</div>}
                {registerSuccess && <div className="login-success">{registerSuccess}</div>}
                <button type="submit" className="login-btn" disabled={loading}>
                  {loading ? 'Sending...' : 'Send reset link'}
                </button>
              </form>
            ) : showReset ? (
              <form onSubmit={handlePasswordResetConfirm}>
                <div className="form-group">
                  <label htmlFor="new-password">New password</label>
                  <input
                    id="new-password"
                    type="password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    required
                    minLength={8}
                    autoComplete="new-password"
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="confirm-new-password">Confirm new password</label>
                  <input
                    id="confirm-new-password"
                    type="password"
                    value={confirmPassword}
                    onChange={(event) => setConfirmPassword(event.target.value)}
                    required
                    minLength={8}
                    autoComplete="new-password"
                  />
                </div>
                {error && <div className="login-error">{error}</div>}
                {registerSuccess && <div className="login-success">{registerSuccess}</div>}
                <button type="submit" className="login-btn" disabled={loading}>
                  {loading ? 'Resetting...' : 'Reset password'}
                </button>
              </form>
            ) : (
              <form onSubmit={handleLogin}>
                <div className="form-group">
                  <label htmlFor="username">Username</label>
                  <input
                    id="username"
                    type="text"
                    value={username}
                    onChange={(event) => setUsername(event.target.value)}
                    required
                    autoComplete="username"
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="password">Password</label>
                  <input
                    id="password"
                    type="password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    required
                    autoComplete="current-password"
                  />
                </div>
                {error && <div className="login-error">{error}</div>}
                {registerSuccess && <div className="login-success">{registerSuccess}</div>}
                <button type="submit" className="login-btn" disabled={loading}>
                  {loading ? 'Logging in...' : 'Log in'}
                </button>
                <p className="login-register">
                  <button type="button" className="link-btn" onClick={() => { setAuthMode('forgot'); setError(''); setRegisterSuccess('') }}>Forgot password?</button>
                </p>
              </form>
            )}
            <p className="login-register">
              {showRegister ? (
                <>Already have an account? <button type="button" className="link-btn" onClick={() => { setAuthMode('login'); setError(''); setRegisterSuccess('') }}>Log in</button></>
              ) : showForgot || showReset ? (
                <>Remembered it? <button type="button" className="link-btn" onClick={() => { setAuthMode('login'); setError(''); setRegisterSuccess('') }}>Log in</button></>
              ) : (
                <>No account? <button type="button" className="link-btn" onClick={() => { setAuthMode('register'); setError(''); setRegisterSuccess('') }}>Register</button></>
              )}
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Login
