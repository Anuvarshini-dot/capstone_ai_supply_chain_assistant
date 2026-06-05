import React, { useEffect, useState } from 'react'
import {
  BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import { fetchIncidents } from '../../api/supplyChainApi'
import './RiskDashboard.css'

// ── Colors ────────────────────────────────────────────────────────────────────
const C = { high: '#ef4444', medium: '#f59e0b', low: '#22c55e',
            accent: '#4f8ef7', purple: '#a855f7', teal: '#06b6d4' }
const TOOLTIP = {
  contentStyle: {
    background: 'var(--bg-card)', border: '1px solid var(--border)',
    borderRadius: 8, color: 'var(--text-primary)', fontSize: 12,
  },
}
const RISK_COLORS     = { High: C.high, Medium: C.medium, Low: C.low }
const STATUS_COLORS   = { Delivered: C.low, Delayed: C.high, 'In Transit': C.accent, Cancelled: C.purple }
const SEVERITY_COLORS = { High: C.high, Medium: C.medium, Low: C.low }

// ── Helpers ───────────────────────────────────────────────────────────────────
const avg = (arr, fn) => arr.length ? arr.reduce((s, x) => s + fn(x), 0) / arr.length : 0
const pct = (v, d = 1) => `${(v * 100).toFixed(d)}%`
const cap = s => s ? s.charAt(0).toUpperCase() + s.slice(1) : s

// ── Shared sub-components ─────────────────────────────────────────────────────
function SectionHeader({ icon, title, description, accent }) {
  return (
    <div className="section-header" style={{ '--section-accent': accent }}>
      <div className="section-header__left">
        <span className="section-header__icon">{icon}</span>
        <div>
          <div className="section-header__title">{title}</div>
          <div className="section-header__desc">{description}</div>
        </div>
      </div>
    </div>
  )
}

function KpiRow({ items }) {
  return (
    <div className="section-kpis">
      {items.map((k, i) => (
        <div key={i} className="section-kpi" style={{ '--kpi-color': k.color || 'var(--text-primary)' }}>
          <div className="section-kpi__value">{k.value}</div>
          <div className="section-kpi__label">{k.label}</div>
          {k.sub && <div className="section-kpi__sub">{k.sub}</div>}
        </div>
      ))}
    </div>
  )
}

function ChartCard({ title, description, children, wide, half }) {
  return (
    <div className={`dash-card ${wide ? 'wide' : ''} ${half ? 'half' : ''}`}>
      <div className="dash-card__title">{title}</div>
      {description && <div className="dash-card__desc">{description}</div>}
      {children}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────
export default function RiskDashboard() {
  const [sup,  setSup]  = useState([])
  const [wh,   setWh]   = useState([])
  const [ship, setShip] = useState([])
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)

  useEffect(() => {
    Promise.all([
      fetchIncidents({ doc_type: 'supplier_profile',  limit: 100 }),
      fetchIncidents({ doc_type: 'warehouse_profile', limit: 20  }),
      fetchIncidents({ doc_type: 'shipment',          limit: 200 }),
    ])
      .then(([s, w, sh]) => {
        setSup(s.incidents  || [])
        setWh(w.incidents   || [])
        setShip(sh.incidents || [])
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="dash-state">Loading dashboard…</div>
  if (error)   return <div className="dash-state dash-state--error">Error: {error}</div>
  if (!sup.length && !ship.length)
    return <div className="dash-state">No data — run ingestion first.</div>

  const SM = sup.map(s  => s.metadata || {})
  const WM = wh.map(w   => w.metadata || {})
  const SH = ship.map(s => s.metadata || {})

  // ── SUPPLIER data ──────────────────────────────────────────────────────────
  const highRiskCount  = SM.filter(m => m.risk_tier === 'high').length
  const medRiskCount   = SM.filter(m => m.risk_tier === 'medium').length
  const avgOnTime      = avg(SM, m => m.on_time_rate  || 0)
  const avgDefect      = avg(SM, m => m.defect_rate   || 0)
  const avgReliability = avg(SM, m => m.reliability_score || 0)

  const riskTierData = ['high', 'medium', 'low'].map(t => ({
    name: cap(t), value: SM.filter(m => m.risk_tier === t).length,
  })).filter(d => d.value > 0)

  const worstSuppliers = [...SM]
    .filter(m => m.supplier_name && m.reliability_score != null)
    .sort((a, b) => a.reliability_score - b.reliability_score)
    .slice(0, 10)
    .map(m => ({
      name:        m.supplier_name.split(' ').slice(0, 2).join(' '),
      Reliability: +(m.reliability_score * 100).toFixed(0),
      'On-Time':   +(m.on_time_rate * 100).toFixed(0),
    }))

  const catMap = {}
  SM.forEach(m => {
    const cat = m.supplier_category || 'Other'
    if (!catMap[cat]) catMap[cat] = { defect: 0, n: 0 }
    catMap[cat].defect += m.defect_rate || 0; catMap[cat].n++
  })
  const categoryData = Object.entries(catMap)
    .map(([cat, { defect, n }]) => ({ category: cat, 'Defect Rate %': +(defect / n * 100).toFixed(2) }))
    .sort((a, b) => b['Defect Rate %'] - a['Defect Rate %'])

  // ── SHIPMENT data ──────────────────────────────────────────────────────────
  const delayedCount = SH.filter(m => m.shipment_status === 'Delayed').length
  const cancelCount  = SH.filter(m => m.shipment_status === 'Cancelled').length
  const lateCount    = SH.filter(m => m.is_late === 1 || m.is_late === '1').length
  const avgDelay     = avg(SH, m => Number(m.delay_days) || 0)
  const onTimePct    = SH.length ? ((SH.length - lateCount) / SH.length * 100).toFixed(1) : 0

  const statusMap = {}
  SH.forEach(m => { const s = m.shipment_status || 'Unknown'; statusMap[s] = (statusMap[s] || 0) + 1 })
  const statusData = Object.entries(statusMap)
    .map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value)

  const sevMap = {}
  SH.forEach(m => { const s = cap(m.severity || 'unknown'); sevMap[s] = (sevMap[s] || 0) + 1 })
  const severityData = Object.entries(sevMap)
    .map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value)

  const modeMap = {}
  SH.forEach(m => {
    const mode = m.shipping_mode || 'Unknown'
    if (!modeMap[mode]) modeMap[mode] = { total: 0, n: 0 }
    modeMap[mode].total += Number(m.delay_days) || 0; modeMap[mode].n++
  })
  const modeData = Object.entries(modeMap)
    .map(([mode, { total, n }]) => ({ mode, 'Avg Delay (days)': +(total / n).toFixed(1) }))
    .sort((a, b) => b['Avg Delay (days)'] - a['Avg Delay (days)'])

  // ── WAREHOUSE data ─────────────────────────────────────────────────────────
  const whAtRisk       = WM.filter(m => (m.critical_count || 0) + (m.stockout_count || 0) > 0).length
  const totalStockouts = WM.reduce((s, m) => s + (m.stockout_count || 0), 0)
  const totalCritical  = WM.reduce((s, m) => s + (m.critical_count || 0), 0)
  const avgDaysSupply  = avg(WM, m => m.avg_days_of_supply || 0)

  const whHealthData = [...WM]
    .filter(m => m.warehouse_name)
    .sort((a, b) => ((b.critical_count || 0) + (b.stockout_count || 0))
                  - ((a.critical_count || 0) + (a.stockout_count || 0)))
    .map(m => ({
      name:     m.warehouse_name
                  .replace(/Distribution |Fulfillment |Logistics |Supply |Regional /gi, '')
                  .trim().slice(0, 13),
      Healthy:  Math.max(0, (m.total_products || 0) - (m.critical_count || 0) - (m.stockout_count || 0)),
      Critical: m.critical_count || 0,
      Stockout: m.stockout_count || 0,
    }))

  return (
    <div className="risk-dashboard">

      {/* ════════════════════════════════════════════════════════
          SECTION 1 — SUPPLIER INTELLIGENCE
          ════════════════════════════════════════════════════════ */}
      <div className="dash-section" style={{ '--section-accent': C.accent }}>
        <SectionHeader
          icon="🏭"
          accent={C.accent}
          title="Supplier Intelligence"
          description={`Tracks performance and risk across ${SM.length} active suppliers.
            High defect rates, low reliability scores, or a high-risk tier signal
            procurement exposure and potential disruptions.`}
        />

        <KpiRow items={[
          { label: 'Total Suppliers',   value: SM.length,                color: C.accent },
          { label: 'High Risk',         value: highRiskCount,
            sub: `${medRiskCount} medium`,
            color: highRiskCount > 10 ? C.high : highRiskCount > 5 ? C.medium : C.low },
          { label: 'Avg Reliability',   value: pct(avgReliability),
            color: avgReliability >= 0.75 ? C.low : avgReliability >= 0.6 ? C.medium : C.high },
          { label: 'Avg On-Time Rate',  value: pct(avgOnTime),
            color: avgOnTime >= 0.8 ? C.low : avgOnTime >= 0.65 ? C.medium : C.high },
          { label: 'Avg Defect Rate',   value: pct(avgDefect, 2),
            color: avgDefect > 0.08 ? C.high : avgDefect > 0.04 ? C.medium : C.low },
        ]} />

        <div className="dash-row dash-row--thirds">
          <ChartCard
            title="Risk Tier Breakdown"
            description="How suppliers are distributed across risk tiers. A high share of 'High' tier indicates systemic procurement risk.">
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie data={riskTierData} cx="50%" cy="50%"
                  innerRadius={52} outerRadius={78} dataKey="value" paddingAngle={3}
                  label={({ name, percent }) => `${name} ${(percent*100).toFixed(0)}%`}
                  labelLine={false}>
                  {riskTierData.map((d, i) => <Cell key={i} fill={RISK_COLORS[d.name] || C.accent} />)}
                </Pie>
                <Tooltip {...TOOLTIP} />
              </PieChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard
            title="Defect Rate by Category"
            description="Average defect rate per product category. Identifies which supply segments carry the most quality risk."
            half>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={categoryData} layout="vertical" margin={{ left: 8, right: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis type="number" tick={{ fill: 'var(--text-muted)', fontSize: 11 }}
                  tickFormatter={v => `${v}%`} />
                <YAxis dataKey="category" type="category"
                  tick={{ fill: 'var(--text-muted)', fontSize: 11 }} width={100} />
                <Tooltip {...TOOLTIP} formatter={v => `${v}%`} />
                <Bar dataKey="Defect Rate %" fill={C.purple} radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        </div>

        <ChartCard
          wide
          title="10 Lowest Reliability Suppliers"
          description="Suppliers sorted by reliability score (ascending). Low reliability combined with low on-time rate indicates a high-risk vendor that warrants immediate review or substitution.">
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={worstSuppliers} layout="vertical"
              margin={{ left: 10, right: 30, top: 4, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis type="number" domain={[0, 100]}
                tick={{ fill: 'var(--text-muted)', fontSize: 11 }}
                tickFormatter={v => `${v}%`} />
              <YAxis dataKey="name" type="category"
                tick={{ fill: 'var(--text-muted)', fontSize: 11 }} width={130} />
              <Tooltip {...TOOLTIP} formatter={v => `${v}%`} />
              <Legend wrapperStyle={{ fontSize: 12, color: 'var(--text-muted)' }} />
              <Bar dataKey="Reliability" fill={C.accent} radius={[0, 4, 4, 0]} />
              <Bar dataKey="On-Time"     fill={C.teal}   radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      {/* ════════════════════════════════════════════════════════
          SECTION 2 — SHIPMENT PERFORMANCE
          ════════════════════════════════════════════════════════ */}
      <div className="dash-section" style={{ '--section-accent': C.medium }}>
        <SectionHeader
          icon="🚢"
          accent={C.medium}
          title="Shipment Performance"
          description={`Analysis of ${SH.length} sampled shipments.
            Delayed or high-severity shipments directly impact customer fulfilment.
            Shipping mode and route patterns reveal where delays are systemic.`}
        />

        <KpiRow items={[
          { label: 'Shipments Sampled', value: SH.length,          color: C.accent },
          { label: 'Delayed',           value: delayedCount,
            sub: `${((delayedCount / SH.length) * 100).toFixed(0)}% of sample`,
            color: delayedCount > SH.length * 0.2 ? C.high : C.medium },
          { label: 'Cancelled',         value: cancelCount,
            color: cancelCount > SH.length * 0.05 ? C.high : C.low },
          { label: 'On-Time Rate',      value: `${onTimePct}%`,
            color: Number(onTimePct) >= 80 ? C.low : Number(onTimePct) >= 65 ? C.medium : C.high },
          { label: 'Avg Delay',         value: `${avgDelay.toFixed(1)}d`,
            color: avgDelay > 4 ? C.high : avgDelay > 2 ? C.medium : C.low },
        ]} />

        <div className="dash-row">
          <ChartCard
            title="Shipment Status"
            description="Overall delivery outcome split. A large 'Delayed' or 'Cancelled' share signals fulfilment risk.">
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie data={statusData} cx="50%" cy="50%"
                  innerRadius={52} outerRadius={78} dataKey="value" paddingAngle={3}
                  label={({ name, percent }) => `${name} ${(percent*100).toFixed(0)}%`}
                  labelLine={false}>
                  {statusData.map((d, i) => <Cell key={i} fill={STATUS_COLORS[d.name] || C.accent} />)}
                </Pie>
                <Tooltip {...TOOLTIP} />
              </PieChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard
            title="Severity Distribution"
            description="Risk severity of sampled shipments. High-severity shipments need immediate attention — they indicate critical delays or stockout risk.">
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie data={severityData} cx="50%" cy="50%"
                  innerRadius={52} outerRadius={78} dataKey="value" paddingAngle={3}
                  label={({ name, percent }) => `${name} ${(percent*100).toFixed(0)}%`}
                  labelLine={false}>
                  {severityData.map((d, i) => <Cell key={i} fill={SEVERITY_COLORS[d.name] || C.accent} />)}
                </Pie>
                <Tooltip {...TOOLTIP} />
              </PieChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard
            title="Avg Delay by Shipping Mode"
            description="Which transport mode causes the most delays on average. Use this to weigh cost vs. reliability when choosing carriers.">
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={modeData} margin={{ bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="mode" tick={{ fill: 'var(--text-muted)', fontSize: 12 }} />
                <YAxis tick={{ fill: 'var(--text-muted)', fontSize: 11 }}
                  tickFormatter={v => `${v}d`} />
                <Tooltip {...TOOLTIP} formatter={v => `${v} days`} />
                <Bar dataKey="Avg Delay (days)" fill={C.high} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        </div>
      </div>

      {/* ════════════════════════════════════════════════════════
          SECTION 3 — WAREHOUSE & INVENTORY
          ════════════════════════════════════════════════════════ */}
      <div className="dash-section" style={{ '--section-accent': C.low }}>
        <SectionHeader
          icon="🏪"
          accent={C.low}
          title="Warehouse & Inventory Health"
          description={`Inventory status across all ${WM.length} warehouses.
            Products in 'Critical' or 'Stockout' state risk unfulfilled orders.
            Low days-of-supply signals an imminent replenishment need.`}
        />

        <KpiRow items={[
          { label: 'Warehouses',        value: WM.length,                color: C.accent },
          { label: 'At Risk',           value: whAtRisk,
            sub: `of ${WM.length} warehouses`,
            color: whAtRisk > WM.length * 0.5 ? C.high : whAtRisk > 0 ? C.medium : C.low },
          { label: 'Critical Products', value: totalCritical,
            color: totalCritical > 10 ? C.high : totalCritical > 5 ? C.medium : C.low },
          { label: 'Active Stockouts',  value: totalStockouts,
            color: totalStockouts > 5 ? C.high : totalStockouts > 0 ? C.medium : C.low },
          { label: 'Avg Days of Supply',value: `${avgDaysSupply.toFixed(1)}d`,
            color: avgDaysSupply < 14 ? C.high : avgDaysSupply < 30 ? C.medium : C.low },
        ]} />

        <ChartCard
          wide
          title="Inventory Health per Warehouse"
          description="Stacked breakdown of each warehouse's product inventory: green = healthy stock, amber = critical (below reorder point), red = stockout (zero stock). Warehouses are sorted by most at-risk first.">
          <ResponsiveContainer width="100%" height={270}>
            <BarChart data={whHealthData} margin={{ bottom: 35, right: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="name"
                tick={{ fill: 'var(--text-muted)', fontSize: 10 }}
                angle={-25} textAnchor="end" interval={0} />
              <YAxis tick={{ fill: 'var(--text-muted)', fontSize: 11 }} />
              <Tooltip {...TOOLTIP} />
              <Legend wrapperStyle={{ fontSize: 12, color: 'var(--text-muted)' }} />
              <Bar dataKey="Healthy"  stackId="a" fill={C.low}    />
              <Bar dataKey="Critical" stackId="a" fill={C.medium} />
              <Bar dataKey="Stockout" stackId="a" fill={C.high}   radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

    </div>
  )
}
