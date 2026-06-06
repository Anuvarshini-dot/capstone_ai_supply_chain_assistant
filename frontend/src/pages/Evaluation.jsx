import React from 'react'
import { useAppContext } from '../context/AppContext'
import './Evaluation.css'

const METRIC_META = {
  retrieval_quality:     { label: 'Retrieval Quality',    icon: '🔍', desc: 'Avg hybrid score (semantic + BM25) of retrieved docs, plus how many score above the quality threshold.' },
  context_coverage:      { label: 'Context Coverage',     icon: '🗂️', desc: 'How many distinct entity types (shipment, supplier, warehouse) appear in the retrieved context — broader coverage means richer grounding.' },
  answer_relevancy:      { label: 'Answer Relevancy',     icon: '🎯', desc: 'Query ↔ Answer: is the answer relevant to both the question and the supply chain risk assessment purpose? Risk context (stockouts, delays, supplier tiers) is expected and not penalised.' },
  faithfulness:          { label: 'Faithfulness',          icon: '📌', desc: 'Context ↔ Answer: is every claim in the answer supported by the retrieved context? Low score signals hallucination risk.' },
  contextual_relevancy:  { label: 'Contextual Relevancy', icon: '🔗', desc: 'Query ↔ Context: were the right documents retrieved for this query? Low score means retrieval surfaced irrelevant records.' },
  deepeval_unavailable:  { label: 'DeepEval',             icon: '⚠',  desc: null },
  deepeval_error:        { label: 'DeepEval Error',        icon: '⚠',  desc: null },
}

function ScoreBar({ score, threshold }) {
  if (score == null) return <div className="score-bar-empty">—</div>
  const pct = Math.round(score * 100)
  const color = score >= threshold ? 'var(--success, #22c55e)' : '#ef4444'
  return (
    <div className="eval-score-bar">
      <div className="eval-score-bar__fill" style={{ width: `${pct}%`, background: color }} />
    </div>
  )
}

function MetricCard({ metricKey, data }) {
  const meta = METRIC_META[metricKey] || { label: metricKey, icon: '📊', desc: null }
  const passed = data.passed
  const score  = data.score

  return (
    <div className={`eval-card ${passed === true ? 'eval-card--pass' : passed === false ? 'eval-card--fail' : 'eval-card--na'}`}>
      <div className="eval-card__header">
        <div className="eval-card__title">
          <span className="eval-card__icon">{meta.icon}</span>
          <span className="eval-card__name">{meta.label}</span>
        </div>
        <div className="eval-card__right">
          {score != null && (
            <span className="eval-card__score">{(score * 100).toFixed(0)}%</span>
          )}
          {passed === true  && <span className="eval-badge eval-badge--pass">PASS</span>}
          {passed === false && <span className="eval-badge eval-badge--fail">FAIL</span>}
          {passed == null   && <span className="eval-badge eval-badge--na">N/A</span>}
        </div>
      </div>

      <ScoreBar score={score} threshold={data.threshold ?? 0.5} />

      {data.threshold != null && (
        <div className="eval-card__threshold">threshold {(data.threshold * 100).toFixed(0)}%</div>
      )}

      {data.reason && (
        <p className="eval-card__reason">{data.reason}</p>
      )}

      {data.details && Object.keys(data.details).length > 0 && (
        <div className="eval-card__details">
          {Object.entries(data.details).map(([k, v]) => (
            <span key={k} className="eval-detail-chip">
              {k.replace(/_/g, ' ')}: <strong>{typeof v === 'number' ? (Number.isInteger(v) ? v : v.toFixed(3)) : v}</strong>
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

export default function Evaluation() {
  const { lastResult } = useAppContext()

  const evaluation    = lastResult?.evaluation ?? {}
  const confidence    = lastResult?.confidence_score ?? null
  const routedAgents  = lastResult?.routed_agents ?? []
  const numIncidents  = lastResult?.retrieved_incidents?.length ?? 0

  const hasMetrics = Object.keys(evaluation).length > 0

  if (!lastResult) {
    return (
      <div className="eval-page">
        <div className="eval-empty">
          <div className="eval-empty__icon">📊</div>
          <h2>No query evaluated yet</h2>
          <p>Run a query on the Query tab first. Evaluation metrics will appear here dynamically after each retrieval.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="eval-page">
      <div className="eval-header">
        <div>
          <h1 className="eval-title">DeepEval Metrics</h1>
          <p className="eval-subtitle">Live evaluation for the most recent retrieval</p>
        </div>
        <div className="eval-header__badges">
          {confidence != null && (
            <div className="eval-stat">
              <span className="eval-stat__label">Agent Confidence</span>
              <span className="eval-stat__value">{(confidence * 100).toFixed(0)}%</span>
            </div>
          )}
          {numIncidents > 0 && (
            <div className="eval-stat">
              <span className="eval-stat__label">Docs Retrieved</span>
              <span className="eval-stat__value">{numIncidents}</span>
            </div>
          )}
          {routedAgents.length > 0 && (
            <div className="eval-stat">
              <span className="eval-stat__label">Agents Used</span>
              <span className="eval-stat__value">{routedAgents.join(', ')}</span>
            </div>
          )}
        </div>
      </div>

      {!hasMetrics ? (
        <div className="eval-empty">
          <p>No evaluation metrics available for this result.</p>
        </div>
      ) : (
        <div className="eval-grid">
          {Object.entries(evaluation).map(([key, data]) => (
            <MetricCard key={key} metricKey={key} data={data} />
          ))}
        </div>
      )}

      <div className="eval-note">
        <strong>Answer Relevancy</strong> uses a domain-aware GEval judge that understands risk
        context (stockouts, delays, supplier tiers) is expected output, not noise.{' '}
        <strong>Faithfulness</strong> and <strong>Contextual Relevancy</strong> use standard
        DeepEval LLM judges covering the remaining RAG triangle edges (context↔answer,
        query↔context).{' '}
        <strong>Retrieval Quality</strong> and <strong>Context Coverage</strong> are computed
        directly from document scores and metadata — no LLM required.
        All metrics update automatically after each new query.
      </div>
    </div>
  )
}
