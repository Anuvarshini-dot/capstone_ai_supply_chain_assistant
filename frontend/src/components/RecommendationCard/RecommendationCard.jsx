import React, { useState } from 'react'
import './RecommendationCard.css'

const CATEGORY_ICON = {
  supplier:          '🏭',
  shipment:          '🚢',
  inventory:         '📦',
  'cross-functional':'🔗',
}

const PRIORITY_CONFIG = {
  1: { label: 'Critical', color: '#ef4444', bg: 'rgba(239,68,68,0.1)' },
  2: { label: 'High',     color: '#f59e0b', bg: 'rgba(245,158,11,0.1)' },
  3: { label: 'Moderate', color: '#4f8ef7', bg: 'rgba(79,142,247,0.1)' },
}

export default function RecommendationCard({ recommendation, index }) {
  const [expanded, setExpanded] = useState(false)
  const { title, description, priority, category, evidence, judge_scores } = recommendation

  const cfg    = PRIORITY_CONFIG[priority] || PRIORITY_CONFIG[3]
  const icon   = CATEGORY_ICON[category]   || '⚠'
  const total  = judge_scores?.total ?? null
  const maxScore = 15

  return (
    <div className="rec-card" style={{ '--priority-color': cfg.color, '--priority-bg': cfg.bg }}>

      {/* Concern header — question style */}
      <button className="rec-header" onClick={() => setExpanded(v => !v)}>
        <div className="rec-header__left">
          <span className="rec-icon">{icon}</span>
          <div className="rec-header__text">
            <span className="rec-priority-tag" style={{ color: cfg.color, background: cfg.bg }}>
              {cfg.label}
            </span>
            {/* Title phrased as a concern/question */}
            <p className="rec-concern">{title}</p>
          </div>
        </div>
        <div className="rec-header__right">
          {total !== null && (
            <span className="rec-score" title="LLM judge score">
              {total}/{maxScore}
            </span>
          )}
          <span className="rec-chevron">{expanded ? '▲' : '▼'}</span>
        </div>
      </button>

      {/* Expandable detail */}
      {expanded && (
        <div className="rec-body">
          <p className="rec-description">{description}</p>

          {evidence && (
            <div className="rec-evidence">
              <span className="rec-evidence__label">Supporting evidence</span>
              <p>{evidence}</p>
            </div>
          )}

          {judge_scores && (
            <div className="rec-scores">
              <ScoreRow label="Actionability"      value={judge_scores.actionability} />
              <ScoreRow label="Evidence grounding" value={judge_scores.evidence_grounding} />
              <ScoreRow label="Specificity"        value={judge_scores.specificity} />
              {judge_scores.rationale && (
                <p className="rec-rationale">{judge_scores.rationale}</p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function ScoreRow({ label, value }) {
  const pct   = ((value || 0) / 5) * 100
  const color = pct >= 70 ? 'var(--success)' : pct >= 40 ? 'var(--warning)' : 'var(--danger)'
  return (
    <div className="score-row">
      <span>{label}</span>
      <div className="score-bar">
        <div className="score-bar__fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="score-num">{value}/5</span>
    </div>
  )
}
