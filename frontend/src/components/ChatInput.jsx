import { useState, useRef } from 'react'

export default function ChatInput({ onSend, disabled }) {
  const [text, setText] = useState('')
  const textareaRef     = useRef(null)

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  function submit() {
    const msg = text.trim()
    if (!msg || disabled) return
    onSend(msg)
    setText('')
    textareaRef.current?.focus()
  }

  return (
    <div className="chat-input-bar">
      <textarea
        ref={textareaRef}
        value={text}
        onChange={e => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Chiedi un report o una pianificazione… es. 'giacche vendute per colore 2022-2024'"
        disabled={disabled}
        rows={1}
        className="chat-textarea"
      />
      <button
        className="btn btn-primary chat-send-btn"
        onClick={submit}
        disabled={disabled || !text.trim()}
      >
        Invia
      </button>
    </div>
  )
}
