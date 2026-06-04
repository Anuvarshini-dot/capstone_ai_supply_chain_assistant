import React, { useState, useRef, useEffect } from 'react'
import { useAppContext } from '../../context/AppContext'
import './ChatInput.css'

const SEVERITY_OPTIONS      = ['', 'low', 'medium', 'high']
const STATUS_OPTIONS        = ['', 'delivered', 'delayed', 'in_transit', 'cancelled']
const RISK_TIER_OPTIONS     = ['', 'low', 'medium', 'high']
const SHIPPING_MODE_OPTIONS = ['', 'Air', 'Sea', 'Road', 'Rail']
const INVENTORY_OPTIONS     = ['', 'healthy', 'low', 'critical', 'stockout']

const SAMPLE_QUERIES = [
  'Which suppliers are causing the most delivery delays?',
  'Who are the highest performing suppliers?',
  'Which warehouses have critical inventory levels?',
  'What shipments are at risk in the LATAM region?',
  'Which products have the most stockouts?',
  'Compare on-time delivery rates across shipping modes',
]

export default function ChatInput({ onSubmit, loading }) {
  const { activeFilters, setActiveFilters } = useAppContext()
  const [query, setQuery]         = useState('')
  const [showFilters, setShowFilters] = useState(false)
  const textareaRef = useRef(null)

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 120) + 'px'
    }
  }, [query])

  const handleSubmit = (e) => {
    e?.preventDefault()
    if (!query.trim() || loading) return
    onSubmit(query.trim(), activeFilters)
    setQuery('')
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  const handleFilter = (key, val) => setActiveFilters(prev => ({ ...prev, [key]: val }))

  const activeCount = Object.values(activeFilters).filter(Boolean).length

  return (
    <div className="chat-input-wrap">
      {/* Sample queries — shown only when no messages yet */}
      <div className="sample-bar">
        {SAMPLE_QUERIES.map((q, i) => (
          <button key={i} className="sample-chip" onClick={() => setQuery(q)}>
            {q}
          </button>
        ))}
      </div>

      {/* Filters */}
      {showFilters && (
        <div className="filter-bar">
          <div className="filter-grid">
            <div className="filter-field">
              <label>Supplier Risk Tier</label>
              <select value={activeFilters.risk_tier || ''} onChange={e => handleFilter('risk_tier', e.target.value)}>
                {RISK_TIER_OPTIONS.map(s => <option key={s} value={s}>{s || 'Any'}</option>)}
              </select>
            </div>
            <div className="filter-field">
              <label>Shipment Status</label>
              <select value={activeFilters.shipment_status || ''} onChange={e => handleFilter('shipment_status', e.target.value)}>
                {STATUS_OPTIONS.map(s => <option key={s} value={s}>{s || 'Any'}</option>)}
              </select>
            </div>
            <div className="filter-field">
              <label>Shipping Mode</label>
              <select value={activeFilters.shipping_mode || ''} onChange={e => handleFilter('shipping_mode', e.target.value)}>
                {SHIPPING_MODE_OPTIONS.map(s => <option key={s} value={s}>{s || 'Any'}</option>)}
              </select>
            </div>
            <div className="filter-field">
              <label>Severity</label>
              <select value={activeFilters.severity || ''} onChange={e => handleFilter('severity', e.target.value)}>
                {SEVERITY_OPTIONS.map(s => <option key={s} value={s}>{s || 'Any'}</option>)}
              </select>
            </div>
            <div className="filter-field">
              <label>Inventory Status</label>
              <select value={activeFilters.inventory_status || ''} onChange={e => handleFilter('inventory_status', e.target.value)}>
                {INVENTORY_OPTIONS.map(s => <option key={s} value={s}>{s || 'Any'}</option>)}
              </select>
            </div>
          </div>
          {activeCount > 0 && (
            <button className="clear-filters" onClick={() => setActiveFilters({
              risk_tier: '', shipment_status: '', shipping_mode: '',
              severity: '', inventory_status: ''
            })}>
              Clear filters
            </button>
          )}
        </div>
      )}

      {/* Input row */}
      <form className="input-row" onSubmit={handleSubmit}>
        <button
          type="button"
          className={`filter-btn ${showFilters ? 'active' : ''}`}
          onClick={() => setShowFilters(v => !v)}
          title="Filters"
        >
          ⚙ {activeCount > 0 && <span className="filter-dot" />}
        </button>

        <textarea
          ref={textareaRef}
          className="chat-textarea"
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={handleKey}
          placeholder="Ask about supply chain risks... (Enter to send, Shift+Enter for new line)"
          rows={1}
          disabled={loading}
        />

        <button type="submit" className={`send-btn ${loading ? 'loading' : ''}`} disabled={loading || !query.trim()}>
          {loading ? <span className="spinner" /> : '↑'}
        </button>
      </form>
    </div>
  )
}
