import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { login, register as apiRegister } from '../services/api'
import { formatApiError } from '../utils/errors'
import './Login.css'

const Login = () => {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [userType, setUserType] = useState('coach')
  const [coachSignupCode, setCoachSignupCode] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [showRegister, setShowRegister] = useState(false)
  const [registerSuccess, setRegisterSuccess] = useState('')
  const navigate = useNavigate()

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
      const extras = userType === 'coach' ? { coach_signup_code: coachSignupCode } : {}
      await apiRegister(username, password, userType, extras)
      setRegisterSuccess('Account created. You can log in now.')
      setShowRegister(false)
      setPassword('')
      setCoachSignupCode('')
    } catch (err) {
      setError(formatApiError(err, 'Registration failed.'))
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
            <h2>{showRegister ? 'Create account' : 'Log in'}</h2>
            <p className="login-subtitle">115 Weightlifting</p>
            {showRegister ? (
              <form onSubmit={handleRegister}>
                <div className="form-group">
                  <label htmlFor="reg-username">Username</label>
                  <input
                    id="reg-username"
                    type="text"
                    value={username}
                    onChange={(event) => setUsername(event.target.value)}
                    required
                    autoComplete="username"
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
              </form>
            )}
            <p className="login-register">
              {showRegister ? (
                <>Already have an account? <button type="button" className="link-btn" onClick={() => { setShowRegister(false); setError(''); setRegisterSuccess('') }}>Log in</button></>
              ) : (
                <>No account? <button type="button" className="link-btn" onClick={() => { setShowRegister(true); setError(''); setRegisterSuccess('') }}>Register</button></>
              )}
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Login
