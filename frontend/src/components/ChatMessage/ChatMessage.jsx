import React, { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import IncidentTable from '../IncidentTable/IncidentTable'
import RecommendationCard from '../RecommendationCard/RecommendationCard'
import './ChatMessage.css'

const AGENT_CONFIG = {
  supplier:  { label: 'Supplier Risk Agent', icon: '🏭', accent: '#4f8ef7' },
  shipment:  { label: 'Shipment Agent',      icon: '🚢', accent: '#f59e0b' },
  inventory: { label: 'Inventory Agent',     icon: '📦', accent: '#22c55e' },
}

const RISK_COLOR = { high: '#ef4444', medium: '#f59e0b', low: '#22c55e' }

function AgentCard({ agentKey, data }) {
  const cfg = AGENT_CONFIG[agentKey] || { label: agentKey, icon: '🤖', accent: '#94a3b8' }
  const riskColor = RISK_COLOR[data.risk_level] || '#94a3b8'

  return (
    <div className="agent-card-inline" style={{ '--agent-accent': cfg.accent }}>
      <div className="agent-card-inline__header">
        <div className="agent-card-inline__title">
          <span className="agent-card-inline__icon">{cfg.icon}</span>
          <span className="agent-card-inline__name">{cfg.label}</span>
        </div>
        <div className="agent-card-inline__badges">
          <span className="risk-pill" style={{ color: riskColor, borderColor: riskColor, background: `${riskColor}18` }}>
            {(data.risk_level || 'unknown').toUpperCase()}
          </span>
          <span className="conf-pill">{((data.confidence || 0) * 100).toFixed(0)}% conf</span>
        </div>
      </div>

      <p className="agent-card-inline__summary">{data.summary}</p>

      {data.findings?.length > 0 && (
        <ul className="agent-card-inline__findings">
          {data.findings.map((f, i) => <li key={i}>{f}</li>)}
        </ul>
      )}

      <div className="agent-card-inline__tags-row">
        {data.top_performers?.length > 0 && (
          <div className="tags-group">
            <span className="tags-label tags-label--good">Top</span>
            {data.top_performers.map((s, i) => <span key={i} className="chip chip--good">{s}</span>)}
          </div>
        )}
        {data.low_performers?.length > 0 && (
          <div className="tags-group">
            <span className="tags-label tags-label--bad">Low</span>
            {data.low_performers.map((s, i) => <span key={i} className="chip chip--bad">{s}</span>)}
          </div>
        )}
        {data.best_routes?.length > 0 && (
          <div className="tags-group">
            <span className="tags-label tags-label--good">Best Routes</span>
            {data.best_routes.map((r, i) => <span key={i} className="chip chip--good">{r}</span>)}
          </div>
        )}
        {data.worst_routes?.length > 0 && (
          <div className="tags-group">
            <span className="tags-label tags-label--bad">At-Risk Routes</span>
            {data.worst_routes.map((r, i) => <span key={i} className="chip chip--bad">{r}</span>)}
          </div>
        )}
        {data.top_fulfillment?.length > 0 && (
          <div className="tags-group">
            <span className="tags-label tags-label--good">High Fulfillment</span>
            {data.top_fulfillment.map((p, i) => <span key={i} className="chip chip--good">{p}</span>)}
          </div>
        )}
        {data.low_fulfillment?.length > 0 && (
          <div className="tags-group">
            <span className="tags-label tags-label--bad">Low Fulfillment</span>
            {data.low_fulfillment.map((p, i) => <span key={i} className="chip chip--bad">{p}</span>)}
          </div>
        )}
        {data.avg_fulfillment_rate != null && data.avg_fulfillment_rate > 0 && (
          <div className="tags-group">
            <span className="tags-label">Avg Fulfillment</span>
            <span className="chip">{(data.avg_fulfillment_rate * 100).toFixed(0)}%</span>
          </div>
        )}
      </div>
    </div>
  )
}

export default function ChatMessage({ message }) {
  const [openSection, setOpenSection] = useState(null)
  const toggle = (s) => setOpenSection(p => p === s ? null : s)

  if (message.role === 'user') {
    return (
      <div className="chat-msg chat-msg--user">
        <div className="chat-bubble chat-bubble--user">{message.content}</div>
      </div>
    )
  }

  if (message.role === 'error') {
    return (
      <div className="chat-msg chat-msg--error">
        <div className="chat-bubble chat-bubble--error">{message.content}</div>
      </div>
    )
  }

  const { answer, retrieved_incidents, recommendations, agent_findings, anomaly_correlations, confidence_score, routed_agents } = message.content
  const agentKeys = Object.keys(agent_findings || {})
  const isSpecialist = agentKeys.length > 0

  return (
    <div className="chat-msg chat-msg--ai">
      <div className="ai-avatar">AI</div>

      <div className="chat-content">
        {isSpecialist ? (
          <>
            {/* Individual agent output cards — hidden for SQL queries */}
            {!routed_agents?.includes('nlsql') && (
              <div className="agent-outputs-section">
                <div className="section-eyebrow">Agent Analysis</div>
                <div className="agent-outputs-grid">
                  {agentKeys.map(key => (
                    <AgentCard key={key} agentKey={key} data={agent_findings[key]} />
                  ))}
                </div>
              </div>
            )}

            {/* Anomaly correlations — inline warning strip (specialist path only) */}
            {!routed_agents?.includes('nlsql') && anomaly_correlations?.length > 0 && (
              <div className="anomaly-strip">
                <div className="anomaly-strip__title">Correlated Anomalies</div>
                {anomaly_correlations.map((a, i) => (
                  <div key={i} className={`anomaly-row anomaly-row--${a.severity}`}>
                    <span className="anomaly-row__type">{a.type?.replace(/_/g, ' ')}</span>
                    <span className="anomaly-row__desc">{a.description}</span>
                  </div>
                ))}
              </div>
            )}

            {/* SQL path — markdown-rendered answer bubble */}
            {routed_agents?.includes('nlsql') ? (
              <div className="chat-bubble chat-bubble--ai sql-answer">
                <ReactMarkdown>{answer}</ReactMarkdown>
              </div>
            ) : (
              /* Specialist path — executive summary block */
              <div className="summary-block">
                <div className="summary-block__label">
                  <span className="summary-block__icon">✦</span> Executive Summary
                </div>
                <p className="summary-block__text">{answer}</p>
                <div className="summary-block__meta">
                  <span>Confidence <strong>{(confidence_score * 100).toFixed(0)}%</strong></span>
                  <span className="meta-dot">·</span>
                  <span>{retrieved_incidents?.length ?? 0} incidents analysed</span>
                </div>
              </div>
            )}

            {/* Collapsible sections */}
            <div className="chat-sections">
              {recommendations?.length > 0 && (
                <div className="chat-section">
                  <button className={`section-toggle ${openSection === 'rec' ? 'open' : ''}`} onClick={() => toggle('rec')}>
                    <span>💡 Recommendations ({recommendations.length})</span>
                    <span className="chevron">{openSection === 'rec' ? '▲' : '▼'}</span>
                  </button>
                  {openSection === 'rec' && (
                    <div className="section-body">
                      {recommendations.map((rec, i) => <RecommendationCard key={i} recommendation={rec} index={i} />)}
                    </div>
                  )}
                </div>
              )}

              {retrieved_incidents?.length > 0 && (() => {
                const shipments = retrieved_incidents.filter(
                  inc => !inc.metadata?.doc_type || inc.metadata?.doc_type === 'shipment'
                )
                return shipments.length > 0 ? (
                  <div className="chat-section">
                    <button className={`section-toggle ${openSection === 'incidents' ? 'open' : ''}`} onClick={() => toggle('incidents')}>
                      <span>📋 Retrieved Shipments ({shipments.length})</span>
                      <span className="chevron">{openSection === 'incidents' ? '▲' : '▼'}</span>
                    </button>
                    {openSection === 'incidents' && (
                      <div className="section-body">
                        <IncidentTable incidents={shipments} title="" />
                      </div>
                    )}
                  </div>
                ) : null
              })()}
            </div>
          </>
        ) : (
          /* Base agent — plain answer */
          <div className="chat-bubble chat-bubble--ai">
            <div className="ai-label">Answer</div>
            <p className="ai-answer">{answer}</p>
          </div>
        )}
      </div>
    </div>
  )
}
