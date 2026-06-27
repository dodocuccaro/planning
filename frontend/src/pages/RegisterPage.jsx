import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

export default function RegisterPage() {
  const { register } = useAuth()
  const navigate     = useNavigate()

  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm]   = useState('')
  const [error, setError]       = useState('')
  const [loading, setLoading]   = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    if (password !== confirm) {
      setError('Le password non coincidono.')
      return
    }
    if (password.length < 6) {
      setError('La password deve contenere almeno 6 caratteri.')
      return
    }
    setLoading(true)
    try {
      await register(email, password)
      navigate('/chat')
    } catch (err) {
      setError(err.response?.data?.error || 'Errore di connessione.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-brand">
          <span className="auth-icon">📦</span>
          <h1>Retail Planning Tool</h1>
          <p>Crea il tuo account</p>
        </div>

        <form onSubmit={handleSubmit} className="auth-form">
          <div className="form-field">
            <label>Email</label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="nome@azienda.it"
              required
              autoFocus
            />
          </div>
          <div className="form-field">
            <label>Password</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="Minimo 6 caratteri"
              required
            />
          </div>
          <div className="form-field">
            <label>Conferma password</label>
            <input
              type="password"
              value={confirm}
              onChange={e => setConfirm(e.target.value)}
              placeholder="Ripeti la password"
              required
            />
          </div>

          {error && <p className="auth-error">{error}</p>}

          <button type="submit" className="btn btn-primary btn-full" disabled={loading}>
            {loading ? 'Registrazione...' : 'Crea account'}
          </button>
        </form>

        <p className="auth-footer">
          Hai già un account? <Link to="/login">Accedi</Link>
        </p>
      </div>
    </div>
  )
}
