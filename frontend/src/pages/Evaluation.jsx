import React from 'react'
import { useAppContext } from '../context/AppContext'
import './Evaluation.css'

const METRIC_META = {
  // Pipeline
  retrieval_quality:            { label: 'Retrieval Quality',           icon: '🔍', desc: 'Avg hybrid score (semantic + BM25) of retrieved docs.' },
  context_coverage:             { label: 'Context Coverage',            icon: '🗂️', desc: 'Distinct entity types in retrieved context — broader = richer grounding.' },
  answer_relevancy:             { label: 'Answer Relevancy',            icon: '🎯', desc: 'Does the answer address the query? Comprehensive risk context is expected and not penalised.' },
  faithfulness:                 { label: 'Faithfulness',                icon: '📌', desc: 'Is every claim in the answer supported by retrieved context? Low score = hallucination risk.' },
  contextual_relevancy:         { label: 'Contextual Relevancy',        icon: '🔗', desc: 'Is the retrieved context useful for the query?' },
  // Supplier agent
  risk_assessment_quality:      { label: 'Risk Assessment Quality',     icon: '🏭', desc: 'Does the supplier analysis reference concrete metrics (on-time rate, defect rate, reliability score)?' },
  finding_relevance:            { label: 'Finding Relevance',           icon: '📋', desc: 'Are the agent findings relevant to the query?' },
  // Shipment agent
  delay_analysis_quality:       { label: 'Delay Analysis Quality',      icon: '🚚', desc: 'Does shipment analysis cite specific delays, carriers, or route issues?' },
  // Inventory agent
  inventory_assessment_quality: { label: 'Inventory Assessment Quality',icon: '📦', desc: 'Does inventory analysis name specific products or warehouses with concrete stock figures?' },
  // NL→SQL agent
  sql_data_accuracy:            { label: 'SQL Data Accuracy',           icon: '🗃️', desc: 'Does the SQL result contain concrete figures and named entities?' },
  // Summary
  answer_completeness:          { label: 'Answer Completeness',         icon: '✦',  desc: 'Does the final answer incorporate key insights from all agents that ran?' },
  conciseness:                  { label: 'Conciseness',                 icon: '✂️', desc: 'Is the answer focused, well-structured, and free of unnecessary repetition?' },
}

const AGENT_META = {
  supplier:  { label: 'Supplier Risk Agent',  icon: '🏭' },
  shipment:  { label: 'Shipment Agent',       icon: '🚚' },
  inventory: { label: 'Inventory Agent',      icon: '📦' },
  nlsql:     { label: 'NL→SQL Agent',         icon: '🗃️' },
}

function ScoreBar({ score, threshold }) {
  if (score == null) return <div className="score-bar-empty">—</div>
  const pct   = Math.round(score * 100)
  const color = score >= threshold ? 'var(--success, #22c55e)' : '#ef4444'
  return (
    <div className="eval-score-bar">
      <div className="eval-score-bar__fill" style={{ width: `${pct}%`, background: color }} />
    </div>
  )
}

function MetricCard({ metricKey, data }) {
  const meta   = METRIC_META[metricKey] || { label: metricKey, icon: '📊', desc: null }
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

function SectionHeader({ title, subtitle }) {
  return (
    <div className="eval-section-header">
      <span className="eval-section-header__title">{title}</span>
      {subtitle && <span className="eval-section-header__sub">{subtitle}</span>}
    </div>
  )
}

function AgentSection({ agentName, metrics }) {
  const meta = AGENT_META[agentName] || { label: agentName, icon: '🤖' }
  return (
    <div className="eval-agent-section">
      <div className="eval-agent-label">
        <span>{meta.icon}</span>
        <span>{meta.label}</span>
      </div>
      <div className="eval-grid">
        {Object.entries(metrics).map(([key, data]) => (
          <MetricCard key={key} metricKey={key} data={data} />
        ))}
      </div>
    </div>
  )
}

const PIPELINE_KEYS = ['retrieval_quality', 'context_coverage', 'answer_relevancy', 'faithfulness', 'contextual_relevancy']

export default function Evaluation() {
  const { lastResult, queryHistory } = useAppContext()
  const lastQuery = queryHistory[0]?.query

  const evaluation       = lastResult?.evaluation ?? {}
  const confidence       = lastResult?.confidence_score ?? null
  const routedAgents     = lastResult?.routed_agents ?? []
  const numIncidents     = lastResult?.retrieved_incidents?.length ?? 0

  const pipelineMetrics  = Object.fromEntries(
    Object.entries(evaluation).filter(([k]) => PIPELINE_KEYS.includes(k))
  )
  const agentEvaluations = evaluation.agent_evaluations ?? {}
  const summaryEval      = evaluation.summary_evaluation ?? {}

  const hasPipeline = Object.keys(pipelineMetrics).length > 0
  const hasAgents   = Object.keys(agentEvaluations).length > 0
  const hasSummary  = Object.keys(summaryEval).length > 0
  const hasAnything = hasPipeline || hasAgents || hasSummary

  if (!lastResult) {
    return (
      <div className="eval-page">
        <div className="eval-empty">
          <div className="eval-empty__icon">📊</div>
          <h2>No query evaluated yet</h2>
          <p>Run a query on the Query tab first. Evaluation metrics will appear here after each retrieval.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="eval-page">
      {lastQuery && (
        <div className="eval-query-banner">
          <span className="eval-query-banner__label">Query</span>
          <span className="eval-query-banner__text">{lastQuery}</span>
        </div>
      )}

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

      {!hasAnything ? (
        <div className="eval-empty">
          <p>No evaluation metrics available for this result.</p>
        </div>
      ) : (
        <>
          {hasPipeline && (
            <>
              <SectionHeader title="Pipeline Metrics" subtitle="Retrieval and answer quality across the full query pipeline" />
              <div className="eval-grid">
                {Object.entries(pipelineMetrics).map(([key, data]) => (
                  <MetricCard key={key} metricKey={key} data={data} />
                ))}
              </div>
            </>
          )}

          {hasAgents && (
            <>
              <SectionHeader title="Agent Evaluations" subtitle="Per-agent quality scores for each specialist that ran" />
              <div className="eval-agents">
                {Object.entries(agentEvaluations).map(([agentName, metrics]) => (
                  <AgentSection key={agentName} agentName={agentName} metrics={metrics} />
                ))}
              </div>
            </>
          )}

          {hasSummary && (
            <>
              <SectionHeader title="Summary Evaluation" subtitle="Final answer quality — completeness, relevancy, and conciseness" />
              <div className="eval-grid">
                {Object.entries(summaryEval).map(([key, data]) => (
                  <MetricCard key={key} metricKey={key} data={data} />
                ))}
              </div>
            </>
          )}
        </>
      )}

      <div className="eval-note">
        <strong>Pipeline Metrics</strong> run on every query regardless of which agents were used.{' '}
        <strong>Agent Evaluations</strong> show per-agent quality scores — only agents that ran appear.{' '}
        <strong>Summary Evaluation</strong> checks the final synthesised answer for completeness, relevancy, and conciseness.
        All metrics update automatically after each query.
      </div>
    </div>
  )
}
