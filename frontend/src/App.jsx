import { createHashRouter, RouterProvider, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './hooks/useAuth'
import LoginPage    from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import ChatPage     from './pages/ChatPage'

function RequireAuth({ children }) {
  const { isAuthenticated } = useAuth()
  return isAuthenticated ? children : <Navigate to="/login" replace />
}

function RedirectIfAuth({ children }) {
  const { isAuthenticated } = useAuth()
  return isAuthenticated ? <Navigate to="/chat" replace /> : children
}

const router = createHashRouter([
  { path: '/',         element: <Navigate to="/chat" replace /> },
  { path: '/login',    element: <RedirectIfAuth><LoginPage /></RedirectIfAuth> },
  { path: '/register', element: <RedirectIfAuth><RegisterPage /></RedirectIfAuth> },
  { path: '/chat',     element: <RequireAuth><ChatPage /></RequireAuth> },
])

export default function App() {
  return (
    <AuthProvider>
      <RouterProvider router={router} />
    </AuthProvider>
  )
}
