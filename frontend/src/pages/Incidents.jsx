import React, { useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import IncidentTable from '../components/IncidentTable/IncidentTable'
import { useIncidents } from '../hooks/useSupplyChain'
import { useAppContext } from '../context/AppContext'
import './Incidents.css'

// ── Option lists ──────────────────────────────────────────────────────────────
const RISK_TIER_OPTIONS = ['', 'low', 'medium', 'high']
const REGION_OPTIONS    = ['', 'USCA', 'Europe', 'LATAM', 'Pacific Asia', 'Africa']
const STATUS_OPTIONS    = ['', 'Delivered', 'Delayed', 'In Transit', 'Cancelled']
const SEVERITY_OPTIONS  = ['', 'low', 'medium', 'high']
const INVENTORY_OPTIONS = ['', 'healthy', 'low', 'critical', 'stockout']
const MODE_OPTIONS      = ['', 'Air', 'Sea', 'Rail', 'Road']
const CATEGORY_OPTIONS  = ['', 'Electronics', 'Apparel', 'Footwear', 'Furniture',
                            'Appliances', 'Sporting Goods', 'Toys']

const RISK_COLOR = { high: '#ef4444', medium: '#f59e0b', low: '#22c55e' }

function sel(key, state, setState) {
  return (e) => setState(s => ({ ...s, [key]: e.target.value }))
}

// ── Supplier Profiles Tab ─────────────────────────────────────────────────────
function SupplierProfilesTab({ onDrilldown, filterNames = [] }) {
  const { loading, error, data, load } = useIncidents()
  const [f, setF] = useState({ risk_tier: '', supplier_region: '', supplier_category: '' })

  useEffect(() => { load({ doc_type: 'supplier_profile', limit: 100 }) }, [])

  const apply = () => load({
    doc_type: 'supplier_profile', limit: 100,
    ...Object.fromEntries(Object.entries(f).filter(([, v]) => v)),
  })
  const reset = () => {
    setF({ risk_tier: '', supplier_region: '', supplier_category: '' })
    load({ doc_type: 'supplier_profile', limit: 100 })
  }

  const profiles = data?.incidents || []
  const displayProfiles = filterNames.length > 0
    ? profiles.filter(p => filterNames.some(n =>
        p.metadata?.supplier_name?.toLowerCase() === n.toLowerCase()
      ))
    : profiles

  return (
    <div className="sub-tab-content">
      {filterNames.length > 0 && (
        <div className="drilldown-banner">
          <span>
            🔍 Showing profiles for: <strong>{filterNames.join(', ')}</strong>
          </span>
        </div>
      )}
      <div className="incidents-filters">
        <div className="filter-grid">
          <div className="filter-field">
            <label>Risk Tier</label>
            <select value={f.risk_tier} onChange={sel('risk_tier', f, setF)}>
              {RISK_TIER_OPTIONS.map(o => <option key={o} value={o}>{o || 'Any'}</option>)}
            </select>
          </div>
          <div className="filter-field">
            <label>Region</label>
            <select value={f.supplier_region} onChange={sel('supplier_region', f, setF)}>
              {REGION_OPTIONS.map(o => <option key={o} value={o}>{o || 'Any'}</option>)}
            </select>
          </div>
          <div className="filter-field">
            <label>Category</label>
            <select value={f.supplier_category} onChange={sel('supplier_category', f, setF)}>
              {CATEGORY_OPTIONS.map(o => <option key={o} value={o}>{o || 'Any'}</option>)}
            </select>
          </div>
        </div>
        <div className="filter-actions">
          <button className="btn-primary" onClick={apply} disabled={loading}>
            {loading ? 'Loading…' : 'Apply Filters'}
          </button>
          <button className="btn-ghost" onClick={reset}>Reset</button>
        </div>
      </div>

      {error && <div className="error-banner">Error: {error}</div>}

      {!loading && (
        <div className="profile-count">
          {filterNames.length > 0
            ? `${displayProfiles.length} of ${profiles.length} supplier profiles`
            : `${profiles.length} supplier profiles`}
        </div>
      )}

      <div className="profile-grid">
        {displayProfiles.map(p => {
          const m = p.metadata || {}
          const rc = RISK_COLOR[m.risk_tier] || '#94a3b8'
          return (
            <div key={p.id} className="profile-card">
              <div className="profile-card__header">
                <div className="profile-card__name">
                  <span className="profile-card__icon">🏭</span>
                  <div>
                    <div className="profile-card__title">{m.supplier_name || p.id}</div>
                    <div className="profile-card__sub">
                      {m.supplier_id} · {m.supplier_category} · {m.supplier_region}
                    </div>
                  </div>
                </div>
                <span className="risk-pill"
                  style={{ color: rc, borderColor: rc, background: `${rc}18` }}>
                  {(m.risk_tier || 'unknown').toUpperCase()}
                </span>
              </div>

              <div className="profile-card__metrics">
                <div className="metric">
                  <span className="metric__label">Reliability</span>
                  <span className="metric__value">
                    {m.reliability_score != null ? `${(m.reliability_score * 100).toFixed(0)}%` : '—'}
                  </span>
                </div>
                <div className="metric">
                  <span className="metric__label">On-Time Rate</span>
                  <span className="metric__value">
                    {m.on_time_rate != null ? `${(m.on_time_rate * 100).toFixed(0)}%` : '—'}
                  </span>
                </div>
                <div className="metric">
                  <span className="metric__label">Defect Rate</span>
                  <span className="metric__value"
                    style={{ color: m.defect_rate > 0.08 ? '#ef4444' : 'inherit' }}>
                    {m.defect_rate != null ? `${(m.defect_rate * 100).toFixed(1)}%` : '—'}
                  </span>
                </div>
              </div>

              <button className="drill-btn"
                onClick={() => onDrilldown('supplier', m.supplier_id, m.supplier_name)}>
                View Shipments →
              </button>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Warehouse Profiles Tab ────────────────────────────────────────────────────
function WarehouseProfilesTab({ onDrilldown, filterNames = [] }) {
  const { loading, error, data, load } = useIncidents()
  const [region, setRegion] = useState('')

  useEffect(() => { load({ doc_type: 'warehouse_profile', limit: 20 }) }, [])

  const apply = () => load({
    doc_type: 'warehouse_profile', limit: 20,
    ...(region ? { warehouse_region: region } : {}),
  })
  const reset = () => {
    setRegion('')
    load({ doc_type: 'warehouse_profile', limit: 20 })
  }

  const profiles = data?.incidents || []
  const displayProfiles = filterNames.length > 0
    ? profiles.filter(p => filterNames.some(n =>
        p.metadata?.warehouse_name?.toLowerCase() === n.toLowerCase()
      ))
    : profiles

  return (
    <div className="sub-tab-content">
      {filterNames.length > 0 && (
        <div className="drilldown-banner">
          <span>
            🔍 Showing profiles for: <strong>{filterNames.join(', ')}</strong>
          </span>
        </div>
      )}
      <div className="incidents-filters">
        <div className="filter-grid">
          <div className="filter-field">
            <label>Region</label>
            <select value={region} onChange={e => setRegion(e.target.value)}>
              {REGION_OPTIONS.map(o => <option key={o} value={o}>{o || 'Any'}</option>)}
            </select>
          </div>
        </div>
        <div className="filter-actions">
          <button className="btn-primary" onClick={apply} disabled={loading}>
            {loading ? 'Loading…' : 'Apply Filters'}
          </button>
          <button className="btn-ghost" onClick={reset}>Reset</button>
        </div>
      </div>

      {error && <div className="error-banner">Error: {error}</div>}

      {!loading && (
        <div className="profile-count">
          {filterNames.length > 0
            ? `${displayProfiles.length} of ${profiles.length} warehouse profiles`
            : `${profiles.length} warehouse profiles`}
        </div>
      )}

      <div className="profile-grid">
        {displayProfiles.map(p => {
          const m      = p.metadata || {}
          const atRisk = (m.critical_count || 0) + (m.stockout_count || 0)
          const rc     = atRisk > 3 ? '#ef4444' : atRisk > 0 ? '#f59e0b' : '#22c55e'
          return (
            <div key={p.id} className="profile-card">
              <div className="profile-card__header">
                <div className="profile-card__name">
                  <span className="profile-card__icon">🏪</span>
                  <div>
                    <div className="profile-card__title">{m.warehouse_name || p.id}</div>
                    <div className="profile-card__sub">
                      {m.warehouse_id} · {m.warehouse_city} · {m.warehouse_region}
                    </div>
                  </div>
                </div>
                {atRisk > 0 && (
                  <span className="risk-pill"
                    style={{ color: rc, borderColor: rc, background: `${rc}18` }}>
                    {atRisk} AT RISK
                  </span>
                )}
              </div>

              <div className="profile-card__metrics">
                <div className="metric">
                  <span className="metric__label">Total Products</span>
                  <span className="metric__value">{m.total_products ?? '—'}</span>
                </div>
                <div className="metric">
                  <span className="metric__label">Critical</span>
                  <span className="metric__value"
                    style={{ color: m.critical_count > 0 ? '#f59e0b' : 'inherit' }}>
                    {m.critical_count ?? 0}
                  </span>
                </div>
                <div className="metric">
                  <span className="metric__label">Stockout</span>
                  <span className="metric__value"
                    style={{ color: m.stockout_count > 0 ? '#ef4444' : 'inherit' }}>
                    {m.stockout_count ?? 0}
                  </span>
                </div>
                <div className="metric">
                  <span className="metric__label">Avg Days Supply</span>
                  <span className="metric__value">
                    {m.avg_days_of_supply != null ? `${m.avg_days_of_supply}d` : '—'}
                  </span>
                </div>
              </div>

              <button className="drill-btn"
                onClick={() => onDrilldown('warehouse', m.warehouse_id, m.warehouse_name)}>
                View Shipments →
              </button>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Shipment Incidents Tab ────────────────────────────────────────────────────
const EMPTY_SHIP_FILTERS = {
  supplier_id: '', risk_tier: '', shipment_status: '',
  severity: '', warehouse_region: '', inventory_status: '', shipping_mode: '',
}

function ShipmentIncidentsTab({ drilldown, onClearDrilldown }) {
  const { loading, error, data, load } = useIncidents()
  const { queryIncidents, setQueryIncidents } = useAppContext()
  const [f, setF]         = useState(EMPTY_SHIP_FILTERS)
  const [limit, setLimit] = useState(50)

  // Keep a ref so effect closures always see the latest drilldown
  const drilldownRef = React.useRef(drilldown)
  drilldownRef.current = drilldown

  // Initial load on mount
  useEffect(() => {
    const p = { doc_type: 'shipment', limit: 50 }
    if (drilldownRef.current?.type === 'supplier')  p.supplier_id  = drilldownRef.current.id
    if (drilldownRef.current?.type === 'warehouse') p.warehouse_id = drilldownRef.current.id
    load(p)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Reload (and clear filters) whenever the drill-down changes
  useEffect(() => {
    setF(EMPTY_SHIP_FILTERS)
    const p = { doc_type: 'shipment', limit: 50 }
    if (drilldown?.type === 'supplier')  p.supplier_id  = drilldown.id
    if (drilldown?.type === 'warehouse') p.warehouse_id = drilldown.id
    load(p)
  }, [drilldown?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  const apply = (currentF, currentLimit) => {
    const p = { doc_type: 'shipment', limit: currentLimit }
    // Add only non-empty filters
    if (currentF.supplier_id)     p.supplier_id      = currentF.supplier_id
    if (currentF.risk_tier)       p.risk_tier         = currentF.risk_tier
    if (currentF.shipment_status) p.shipment_status   = currentF.shipment_status
    if (currentF.severity)        p.severity          = currentF.severity
    if (currentF.warehouse_region) p.warehouse_region = currentF.warehouse_region
    if (currentF.inventory_status) p.inventory_status = currentF.inventory_status
    if (currentF.shipping_mode)   p.shipping_mode     = currentF.shipping_mode
    // Keep drill-down constraint
    if (drilldown?.type === 'supplier')  p.supplier_id  = drilldown.id
    if (drilldown?.type === 'warehouse') p.warehouse_id = drilldown.id
    load(p)
  }

  const reset = () => {
    setF(EMPTY_SHIP_FILTERS)
    const p = { doc_type: 'shipment', limit }
    if (drilldown?.type === 'supplier')  p.supplier_id  = drilldown.id
    if (drilldown?.type === 'warehouse') p.warehouse_id = drilldown.id
    load(p)
  }

  return (
    <div className="sub-tab-content">
      {queryIncidents.length > 0 && (
        <div className="drilldown-banner">
          <span>
            📋 Showing <strong>{queryIncidents.length} shipment{queryIncidents.length > 1 ? 's' : ''}</strong> retrieved by your last query
          </span>
          <button className="drilldown-clear" onClick={() => setQueryIncidents([])}>✕ Clear · Show all</button>
        </div>
      )}

      {!queryIncidents.length && drilldown && (
        <div className="drilldown-banner">
          <span>
            {drilldown.type === 'supplier' ? '🏭' : '🏪'}
            {' '}Showing shipments for{' '}
            <strong>{drilldown.name}</strong>
            <span className="drilldown-id"> ({drilldown.id})</span>
          </span>
          <button className="drilldown-clear" onClick={onClearDrilldown}>✕ Clear filter</button>
        </div>
      )}

      <div className="incidents-filters">
        <div className="filter-grid">
          {!drilldown && (
            <div className="filter-field">
              <label>Supplier ID</label>
              <input type="text" placeholder="e.g. SUP-018"
                value={f.supplier_id} onChange={sel('supplier_id', f, setF)} />
            </div>
          )}
          <div className="filter-field">
            <label>Risk Tier</label>
            <select value={f.risk_tier} onChange={sel('risk_tier', f, setF)}>
              {RISK_TIER_OPTIONS.map(o => <option key={o} value={o}>{o || 'Any'}</option>)}
            </select>
          </div>
          <div className="filter-field">
            <label>Status</label>
            <select value={f.shipment_status} onChange={sel('shipment_status', f, setF)}>
              {STATUS_OPTIONS.map(o => <option key={o} value={o}>{o || 'Any'}</option>)}
            </select>
          </div>
          <div className="filter-field">
            <label>Severity</label>
            <select value={f.severity} onChange={sel('severity', f, setF)}>
              {SEVERITY_OPTIONS.map(o => <option key={o} value={o}>{o || 'Any'}</option>)}
            </select>
          </div>
          <div className="filter-field">
            <label>Shipping Mode</label>
            <select value={f.shipping_mode} onChange={sel('shipping_mode', f, setF)}>
              {MODE_OPTIONS.map(o => <option key={o} value={o}>{o || 'Any'}</option>)}
            </select>
          </div>
          <div className="filter-field">
            <label>Warehouse Region</label>
            <select value={f.warehouse_region} onChange={sel('warehouse_region', f, setF)}>
              {REGION_OPTIONS.map(o => <option key={o} value={o}>{o || 'Any'}</option>)}
            </select>
          </div>
          <div className="filter-field">
            <label>Inventory Status</label>
            <select value={f.inventory_status} onChange={sel('inventory_status', f, setF)}>
              {INVENTORY_OPTIONS.map(o => <option key={o} value={o}>{o || 'Any'}</option>)}
            </select>
          </div>
          <div className="filter-field">
            <label>Limit</label>
            <select value={limit} onChange={e => setLimit(Number(e.target.value))}>
              {[20, 50, 100].map(n => <option key={n} value={n}>{n}</option>)}
            </select>
          </div>
        </div>
        <div className="filter-actions">
          <button className="btn-primary" onClick={() => apply(f, limit)} disabled={loading}>
            {loading ? 'Loading…' : 'Apply Filters'}
          </button>
          <button className="btn-ghost" onClick={reset}>Reset</button>
        </div>
      </div>

      {error && <div className="error-banner">Error: {error}</div>}

      {queryIncidents.length > 0 ? (
        <IncidentTable
          incidents={queryIncidents}
          title={`Query Results (${queryIncidents.length} shipment${queryIncidents.length > 1 ? 's' : ''})`}
        />
      ) : data && (
        <IncidentTable
          key={JSON.stringify(data.incidents?.length)}
          incidents={data.incidents || []}
          title={`Shipment Incidents (${data.total ?? data.incidents?.length ?? 0} found)`}
        />
      )}
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export default function Incidents() {
  const location = useLocation()
  const { queryIncidents } = useAppContext()

  // Navigation state injected by ChatMessage "View Profiles" button
  const navState = location.state || {}

  const [activeTab, setActiveTab] = useState(
    navState.tab || (queryIncidents.length > 0 ? 'shipments' : 'suppliers')
  )
  const [drilldown, setDrilldown] = useState(null)
  const [navFilterNames, setNavFilterNames] = useState(navState.filterNames || [])
  const [navWarehouseNames, setNavWarehouseNames] = useState(navState.warehouseNames || [])

  const handleDrilldown = (type, id, name) => {
    setDrilldown({ type, id, name })
    setActiveTab('shipments')
  }

  const handleTabChange = (key) => {
    setActiveTab(key)
    if (navFilterNames.length > 0 && key !== 'suppliers') setNavFilterNames([])
    if (navWarehouseNames.length > 0 && key !== 'warehouses') setNavWarehouseNames([])
  }

  const tabs = [
    { key: 'suppliers',  label: 'Supplier Profiles',  icon: '🏭', hint: '50 profiles' },
    { key: 'warehouses', label: 'Warehouse Profiles',  icon: '🏪', hint: '15 profiles' },
    { key: 'shipments',  label: 'Shipment Incidents',  icon: '🚢', hint: null },
  ]

  return (
    <div className="incidents-page">
      <div className="incidents-header">
        <h2>Data Explorer</h2>
        <p>Browse supplier profiles, warehouse status, and individual shipment incidents</p>
      </div>

      <div className="sub-tabs">
        {tabs.map(t => (
          <button key={t.key}
            className={`sub-tab ${activeTab === t.key ? 'sub-tab--active' : ''}`}
            onClick={() => handleTabChange(t.key)}>
            <span className="sub-tab__icon">{t.icon}</span>
            <span>{t.label}</span>
            {t.hint && <span className="sub-tab__hint">{t.hint}</span>}
            {t.key === 'shipments' && drilldown && (
              <span className="sub-tab__dot" title={`Filtered: ${drilldown.name}`} />
            )}
            {t.key === 'suppliers' && navFilterNames.length > 0 && activeTab === 'suppliers' && (
              <span className="sub-tab__dot" title={`Filtered: ${navFilterNames.join(', ')}`} />
            )}
            {t.key === 'warehouses' && navWarehouseNames.length > 0 && activeTab === 'warehouses' && (
              <span className="sub-tab__dot" title={`Filtered: ${navWarehouseNames.join(', ')}`} />
            )}
          </button>
        ))}
      </div>

      {activeTab === 'suppliers'  && (
        <SupplierProfilesTab onDrilldown={handleDrilldown} filterNames={navFilterNames} />
      )}
      {activeTab === 'warehouses' && <WarehouseProfilesTab onDrilldown={handleDrilldown} filterNames={navWarehouseNames} />}
      {activeTab === 'shipments'  && (
        <ShipmentIncidentsTab
          drilldown={drilldown}
          onClearDrilldown={() => setDrilldown(null)}
        />
      )}
    </div>
  )
}
