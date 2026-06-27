import { createContext, createElement, useContext, useState, useCallback } from 'react'
import axios from 'axios'

const AuthContext = createContext(null)

const BACKEND = import.meta.env.VITE_BACKEND_URL || ''

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem('token'))
  const [user, setUser]   = useState(() => {
    try { return JSON.parse(localStorage.getItem('user')) } catch { return null }
  })

  const login = useCallback(async (email, password) => {
    const res = await axios.post(`${BACKEND}/api/auth/login`, { email, password })
    localStorage.setItem('token', res.data.token)
    localStorage.setItem('user', JSON.stringify(res.data.user))
    setToken(res.data.token)
    setUser(res.data.user)
    return res.data
  }, [])

  const register = useCallback(async (email, password) => {
    const res = await axios.post(`${BACKEND}/api/auth/register`, { email, password })
    localStorage.setItem('token', res.data.token)
    localStorage.setItem('user', JSON.stringify(res.data.user))
    setToken(res.data.token)
    setUser(res.data.user)
    return res.data
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    setToken(null)
    setUser(null)
  }, [])

  return createElement(
    AuthContext.Provider,
    { value: { token, user, login, register, logout, isAuthenticated: !!token } },
    children,
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
