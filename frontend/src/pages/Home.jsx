import React, { useRef, useEffect } from 'react'
import ChatMessage from '../components/ChatMessage/ChatMessage'
import ChatInput from '../components/ChatInput/ChatInput'
import { useQuery } from '../hooks/useSupplyChain'
import { useAppContext } from '../context/AppContext'
import './Home.css'

export default function Home() {
  const { loading, runQuery, error } = useQuery()
  const { messages, addMessage } = useAppContext()
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const handleSubmit = async (query, filters) => {
    addMessage({ role: 'user', content: query })

    const cleanFilters = filters
      ? Object.fromEntries(Object.entries(filters).filter(([, v]) => v))
      : null

    const result = await runQuery(query, cleanFilters || null, 5)

    if (result) {
      addMessage({ role: 'assistant', content: result })
    } else {
      addMessage({
        role: 'error',
        content: error || 'Something went wrong. Please check that the backend is running and try again.'
      })
    }
  }

  return (
    <div className="chat-page">
      {/* Message thread */}
      <div className="chat-thread">
        {messages.length === 0 && (
          <div className="chat-empty">
            <div className="chat-empty__icon">⚡</div>
            <h2>What supply chain risk can I help you investigate?</h2>
            <p>Ask me anything about supplier delays, shipment disruptions, inventory shortages, or transportation costs. Pick a question below or type your own.</p>
          </div>
        )}

        {messages.map((msg, i) => (
          <ChatMessage key={i} message={msg} />
        ))}

        {loading && (
          <div className="chat-msg chat-msg--ai">
            <div className="ai-avatar">AI</div>
            <div className="chat-bubble chat-bubble--ai thinking">
              <span className="dot" /><span className="dot" /><span className="dot" />
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Sticky input at bottom */}
      <ChatInput onSubmit={handleSubmit} loading={loading} />
    </div>
  )
}
