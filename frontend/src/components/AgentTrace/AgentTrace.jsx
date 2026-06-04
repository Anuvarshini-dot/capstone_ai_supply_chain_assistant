import React, { useState } from 'react';
import './AgentTrace.css';

const AGENT_CONFIG = {
  supplier: { label: 'Supplier Risk Agent', icon: '🏭', color: '#4f8ef7' },
  shipment: { label: 'Shipment Agent', icon: '🚢', color: '#f59e0b' },
  inventory: { label: 'Inventory Agent', icon: '📦', color: '#22c55e' },
};

const RISK_COLOR = { high: '#ef4444', medium: '#f59e0b', low: '#22c55e' };

export default function AgentTrace({ agentFindings = {}, anomalyCorrelations = [], confidence = 0 }) {
  const [openAgent, setOpenAgent] = useState(null);

  return (
    <div className="agent-trace">
      <div className="agent-trace__header">
        <h3>Agent Analysis Trace</h3>
        <div className="confidence-pill">
          Overall Confidence: <strong>{(confidence * 100).toFixed(0)}%</strong>
        </div>
      </div>

      <div className="agent-list">
        {Object.entries(agentFindings).map(([key, data]) => {
          const cfg = AGENT_CONFIG[key] || { label: key, icon: '🤖', color: '#94a3b8' };
          const isOpen = openAgent === key;
          const riskColor = RISK_COLOR[data.risk_level] || '#94a3b8';

          return (
            <div key={key} className={`agent-card ${isOpen ? 'open' : ''}`}>
              <button
                className="agent-card__header"
                onClick={() => setOpenAgent(isOpen ? null : key)}
                style={{ '--agent-color': cfg.color }}
              >
                <div className="agent-card__left">
                  <span className="agent-icon">{cfg.icon}</span>
                  <span className="agent-name">{cfg.label}</span>
                </div>
                <div className="agent-card__right">
                  <span className="risk-badge" style={{ color: riskColor, borderColor: riskColor }}>
                    {data.risk_level || 'unknown'}
                  </span>
                  <span className="conf-text">
                    {((data.confidence || 0) * 100).toFixed(0)}% conf
                  </span>
                  <span className="chevron">{isOpen ? '▲' : '▼'}</span>
                </div>
              </button>

              {isOpen && (
                <div className="agent-card__body">
                  <p className="agent-summary">{data.summary}</p>

                  {data.findings?.length > 0 && (
                    <div className="agent-findings">
                      <span className="findings-label">Key Findings</span>
                      <ul>
                        {data.findings.map((f, i) => <li key={i}>{f}</li>)}
                      </ul>
                    </div>
                  )}

                  {data.affected_suppliers?.length > 0 && (
                    <div className="agent-tags">
                      <span className="tag-label">Affected Suppliers</span>
                      {data.affected_suppliers.map((s, i) => (
                        <span key={i} className="tag">{s}</span>
                      ))}
                    </div>
                  )}

                  {data.at_risk_warehouses?.length > 0 && (
                    <div className="agent-tags">
                      <span className="tag-label">At-Risk Warehouses</span>
                      {data.at_risk_warehouses.map((w, i) => (
                        <span key={i} className="tag">{w}</span>
                      ))}
                    </div>
                  )}

                  {data.stockout_probability != null && (
                    <p className="stockout-prob">
                      Stockout Probability: <strong>{(data.stockout_probability * 100).toFixed(0)}%</strong>
                    </p>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {anomalyCorrelations.length > 0 && (
        <div className="anomaly-section">
          <div className="anomaly-section__title">
            Correlated Anomalies Detected
          </div>
          {anomalyCorrelations.map((a, i) => (
            <div key={i} className={`anomaly-card anomaly-${a.severity}`}>
              <div className="anomaly-type">{a.type?.replace(/_/g, ' ')}</div>
              <p>{a.description}</p>
              {a.agents_involved?.length > 0 && (
                <div className="anomaly-agents">
                  {a.agents_involved.map(ag => (
                    <span key={ag} className="tag small">{ag}</span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
