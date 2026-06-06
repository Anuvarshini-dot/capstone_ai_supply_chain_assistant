import React from 'react'
import { useAppContext } from '../context/AppContext'
import './Logs.css'

const RISK_COLOR = { high: '#ef4444', medium: '#f59e0b', low: '#22c55e', unknown: '#94a3b8' }

function LogStep({ entry, index, isLast }) {
  return (
    <div className={`log-step ${isLast ? 'log-step--last' : ''}`}>
      <div className="log-step__connector">
        <div className="log-step__dot">{entry.icon}</div>
        {!isLast && <div className="log-step__line" />}
      </div>

      <div className="log-step__card">
        <div className="log-step__header">
          <span className="log-step__name">{entry.step}</span>
          <span className="log-step__ms">{entry.ms}ms</span>
        </div>

        <p className="log-step__detail">{entry.detail}</p>
        {entry.sub_query && (
          <p className="log-step__sub-query">❓ {entry.sub_query}</p>
        )}

        <div className="log-step__meta">
          {entry.risk_level && (
            <span className="log-pill" style={{ color: RISK_COLOR[entry.risk_level], borderColor: RISK_COLOR[entry.risk_level], background: `${RISK_COLOR[entry.risk_level]}18` }}>
              {entry.risk_level.toUpperCase()}
            </span>
          )}
          {entry.confidence != null && (
            <span className="log-pill log-pill--neutral">Confidence {entry.confidence}%</span>
          )}
          {entry.docs_retrieved != null && (
            <span className="log-pill log-pill--neutral">{entry.docs_retrieved} docs</span>
          )}
          {entry.profile_count != null && (
            <span className="log-pill log-pill--neutral">{entry.profile_count} profiles</span>
          )}
          {entry.shipment_count != null && (
            <span className="log-pill log-pill--neutral">{entry.shipment_count} shipments</span>
          )}
          {entry.chromadb_hits != null && (
            <span className="log-pill log-pill--chroma">ChromaDB {entry.chromadb_hits} hits</span>
          )}
          {entry.findings_count != null && (
            <span className="log-pill log-pill--neutral">{entry.findings_count} findings</span>
          )}
          {entry.rows_returned != null && (
            <span className="log-pill log-pill--neutral">{entry.rows_returned} rows</span>
          )}
          {entry.anomalies != null && (
            <span className="log-pill log-pill--neutral">{entry.anomalies} anomalies</span>
          )}
          {entry.count != null && (
            <span className="log-pill log-pill--neutral">{entry.count} recommendations</span>
          )}
            {entry.agents?.length > 0 && !entry.sub_queries && entry.agents.map(a => (
            <span key={a} className="log-pill log-pill--agent">{a}</span>
          ))}
        </div>

        {entry.sub_queries && Object.keys(entry.sub_queries).length > 0 && (
          <div className="log-plan">
            {Object.entries(entry.sub_queries).map(([agent, q]) => (
              <div key={agent} className="log-plan__row">
                <span className="log-plan__agent">{agent}</span>
                <span className="log-plan__arrow">→</span>
                <span className="log-plan__q">{q}</span>
              </div>
            ))}
          </div>
        )}

        {entry.top_finding && (
          <div className="log-step__finding">
            <span className="log-step__finding-label">Top finding</span>
            <span className="log-step__finding-text">{entry.top_finding}</span>
          </div>
        )}

        {entry.entities_found?.length > 0 && (
          <div className="log-step__entities">
            <span className="log-step__entities-label">Entities</span>
            {entry.entities_found.map(e => (
              <span key={e} className="log-pill log-pill--entity">{e}</span>
            ))}
          </div>
        )}

        {entry.affected_suppliers?.length > 0 && (
          <div className="log-step__entities">
            <span className="log-step__entities-label">Suppliers</span>
            {entry.affected_suppliers.map(s => (
              <span key={s} className="log-pill log-pill--entity">{s}</span>
            ))}
          </div>
        )}

        {entry.warehouses_at_risk?.length > 0 && (
          <div className="log-step__entities">
            <span className="log-step__entities-label">Warehouses</span>
            {entry.warehouses_at_risk.map(w => (
              <span key={w} className="log-pill log-pill--entity">{w}</span>
            ))}
          </div>
        )}

        {entry.anomaly_types?.length > 0 && (
          <div className="log-step__entities">
            <span className="log-step__entities-label">Anomalies</span>
            {entry.anomaly_types.map(t => (
              <span key={t} className="log-pill log-pill--warn">{t}</span>
            ))}
          </div>
        )}

        {entry.sql_queries?.length > 0 && (
          <details className="log-sql">
            <summary className="log-sql__toggle">{entry.sql_queries.length} SQL query/queries executed</summary>
            {entry.sql_queries.map((q, i) => (
              <pre key={i} className="log-sql__code">{q}</pre>
            ))}
          </details>
        )}
      </div>
    </div>
  )
}

export default function Logs() {
  const { executionLog, queryHistory } = useAppContext()
  const lastQuery = queryHistory[0]?.query

  const totalMs = executionLog.reduce((s, e) => s + (e.ms || 0), 0)

  return (
    <div className="logs-page">
      <div className="logs-header">
        <div className="logs-header__title">Execution Trace</div>
        {lastQuery && (
          <div className="logs-header__query">
            <span className="logs-header__query-label">Last query:</span>
            <span className="logs-header__query-text">{lastQuery}</span>
          </div>
        )}
        {executionLog.length > 0 && (
          <div className="logs-header__summary">
            {executionLog.length} steps · {totalMs}ms total
          </div>
        )}
      </div>

      {executionLog.length === 0 ? (
        <div className="logs-empty">
          <div className="logs-empty__icon">🔍</div>
          <p>No query run yet. Ask a question on the Query tab to see the execution trace here.</p>
        </div>
      ) : (
        <div className="logs-timeline">
          {executionLog.map((entry, i) => (
            <LogStep key={i} entry={entry} index={i} isLast={i === executionLog.length - 1} />
          ))}
        </div>
      )}
    </div>
  )
}
