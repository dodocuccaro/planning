import { useState, useRef, useEffect } from 'react'
import axios from 'axios'
import { useAuth } from '../hooks/useAuth'
import UploadPrompt from '../components/UploadPrompt'
import ColumnMappingConfirm from '../components/ColumnMappingConfirm'
import ChatMessage from '../components/ChatMessage'
import ChatInput from '../components/ChatInput'

const BACKEND = import.meta.env.VITE_BACKEND_URL || ''

// Upload states: 'idle' | 'mapping' | 'ready'
export default function ChatPage() {
  const { token, user, logout } = useAuth()

  const [uploadState, setUploadState]   = useState('idle')
  const [parseResult, setParseResult]   = useState(null)
  const [sessionId, setSessionId]       = useState(null)
  const [sessionMeta, setSessionMeta]   = useState(null)

  const [conversation, setConversation] = useState([])
  const [loading, setLoading]           = useState(false)
  const [pendingIntent, setPendingIntent] = useState(null)

  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [conversation, loading])

  function handleParsed(data) {
    if (data.needs_confirmation === false) {
      // Multi-sheet or auto-confirmed format — skip mapping screen
      handleConfirmed(data)
    } else {
      setParseResult(data)
      setUploadState('mapping')
    }
  }

  function handleConfirmed(data) {
    setSessionId(data.session_id)
    setSessionMeta(data)
    setUploadState('ready')
  }

  async function sendMessage(text, clarificationAnswer = null, resolvedIntent = null) {
    const userMsg = { role: 'user', content: text }
    setConversation(prev => [...prev, userMsg])
    setLoading(true)

    // Build history as simple role/content pairs for the API
    const historyForApi = conversation.map(m => ({
      role:    m.role,
      content: typeof m.content === 'string' ? m.content : m.payload?.text || '',
    }))

    try {
      const body = {
        session_id: sessionId,
        message:    text,
        history:    historyForApi,
      }
      if (clarificationAnswer) body.clarification_answer = clarificationAnswer
      if (pendingIntent)        body.pending_intent       = pendingIntent
      if (resolvedIntent)       body.resolved_intent      = resolvedIntent

      const res = await axios.post(`${BACKEND}/api/chat`, body, {
        headers: { Authorization: `Bearer ${token}` }
      })

      const data = res.data

      if (data.type === 'clarification') {
        setPendingIntent(data.pending_intent)
        setConversation(prev => [...prev, {
          role:    'assistant',
          content: data.payload?.text || '',
          payload: data.payload,
        }])
      } else {
        setPendingIntent(null)
        setConversation(prev => [...prev, {
          role:    'assistant',
          content: data.payload?.text || '',
          payload: data.payload,
        }])
      }
    } catch (err) {
      const errText = err.response?.data?.error || 'Errore di connessione.'
      setConversation(prev => [...prev, {
        role: 'assistant',
        content: errText,
        payload: { type: 'empty', text: errText },
      }])
    } finally {
      setLoading(false)
    }
  }

  function handleOptionClick(option) {
    if (pendingIntent) {
      sendMessage(option, option, null)
    } else {
      sendMessage(option)
    }
  }

  function resetUpload() {
    setUploadState('idle')
    setParseResult(null)
    setSessionId(null)
    setSessionMeta(null)
    setConversation([])
    setPendingIntent(null)
  }

  return (
    <div className="chat-page">
      {/* Header */}
      <header className="chat-header">
        <div className="chat-header-left">
          <span className="header-icon">📦</span>
          <span className="header-title">Retail Planning Tool</span>
          {sessionMeta && (
            <span className="session-badge">
              {sessionMeta.product_count} prodotti · {sessionMeta.years?.join(', ')}
            </span>
          )}
        </div>
        <div className="chat-header-right">
          {uploadState === 'ready' && (
            <button className="btn btn-ghost" onClick={resetUpload}>
              Cambia file
            </button>
          )}
          <span className="user-email">{user?.email}</span>
          <button className="btn btn-ghost" onClick={logout}>Esci</button>
        </div>
      </header>

      {/* Body */}
      <div className="chat-body">
        {uploadState === 'idle' && (
          <div className="chat-center">
            <h2>Carica i dati del tuo gestionale</h2>
            <p>Carica un file Excel con almeno 3 anni di dati storici. Qualsiasi formato è accettato — il sistema rileva automaticamente le colonne.</p>
            <UploadPrompt onParsed={handleParsed} />
          </div>
        )}

        {uploadState === 'mapping' && parseResult && (
          <div className="chat-center">
            <ColumnMappingConfirm parseResult={parseResult} onConfirmed={handleConfirmed} />
          </div>
        )}

        {uploadState === 'ready' && (
          <div className="chat-messages">
            {conversation.length === 0 && (
              <div className="chat-empty-state">
                <p>Dati caricati. Cosa vuoi sapere?</p>
                <div className="example-queries">
                  {[
                    'Mostrami le vendite per categoria negli ultimi 3 anni',
                    'Di che colore dovrei comprare le giacche per la prossima stagione?',
                    'Recap vendite per fornitore dal 2022 ad oggi',
                  ].map(q => (
                    <button key={q} className="btn btn-outline example-btn" onClick={() => sendMessage(q)}>
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {conversation.map((msg, i) => (
              <ChatMessage key={i} message={msg} onOptionClick={handleOptionClick} />
            ))}

            {loading && (
              <div className="msg msg-assistant">
                <div className="msg-bubble msg-bubble-assistant loading-bubble">
                  <span className="dot" /><span className="dot" /><span className="dot" />
                </div>
              </div>
            )}

            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Input bar */}
      {uploadState === 'ready' && (
        <div className="chat-footer">
          <ChatInput onSend={sendMessage} disabled={loading} />
        </div>
      )}
    </div>
  )
}
