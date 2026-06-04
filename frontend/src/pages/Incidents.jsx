import React, { useEffect, useState } from 'react';
import IncidentTable from '../components/IncidentTable/IncidentTable';
import { useIncidents } from '../hooks/useSupplyChain';
import './Incidents.css';

const SEVERITY_OPTIONS     = ['', 'low', 'medium', 'high'];
const STATUS_OPTIONS       = ['', 'Delivered', 'Delayed', 'In Transit', 'Cancelled'];
const RISK_TIER_OPTIONS    = ['', 'low', 'medium', 'high'];
const REGION_OPTIONS       = ['', 'USCA', 'Europe', 'LATAM', 'Pacific Asia', 'Africa'];
const INVENTORY_OPTIONS    = ['', 'healthy', 'low', 'critical', 'stockout'];

const EMPTY_FILTERS = {
  supplier_id:      '',
  supplier_name:    '',
  risk_tier:        '',
  shipment_status:  '',
  severity:         '',
  warehouse_region: '',
  inventory_status: '',
};

export default function Incidents() {
  const { loading, error, data, load } = useIncidents();
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [limit, setLimit]     = useState(50);

  useEffect(() => {
    load({ limit });
  }, []);

  const handleSearch = () => {
    const params = {
      limit,
      ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v))
    };
    load(params);
  };

  const handleReset = () => {
    setFilters(EMPTY_FILTERS);
    load({ limit });
  };

  const set = (key) => (e) => setFilters(f => ({ ...f, [key]: e.target.value }));

  return (
    <div className="incidents-page">
      <div className="incidents-header">
        <h2>Incident Explorer</h2>
        <p>Browse and filter all supply chain shipment records in the database</p>
      </div>

      <div className="incidents-filters">
        <div className="filter-grid">
          <div className="filter-field">
            <label>Supplier ID</label>
            <input
              type="text"
              placeholder="e.g. SUP-018"
              value={filters.supplier_id}
              onChange={set('supplier_id')}
            />
          </div>
          <div className="filter-field">
            <label>Supplier Name</label>
            <input
              type="text"
              placeholder="e.g. Apex Supply Co."
              value={filters.supplier_name}
              onChange={set('supplier_name')}
            />
          </div>
          <div className="filter-field">
            <label>Risk Tier</label>
            <select value={filters.risk_tier} onChange={set('risk_tier')}>
              {RISK_TIER_OPTIONS.map(s => <option key={s} value={s}>{s || 'Any'}</option>)}
            </select>
          </div>
          <div className="filter-field">
            <label>Shipment Status</label>
            <select value={filters.shipment_status} onChange={set('shipment_status')}>
              {STATUS_OPTIONS.map(s => <option key={s} value={s}>{s || 'Any'}</option>)}
            </select>
          </div>
          <div className="filter-field">
            <label>Severity</label>
            <select value={filters.severity} onChange={set('severity')}>
              {SEVERITY_OPTIONS.map(s => <option key={s} value={s}>{s || 'Any'}</option>)}
            </select>
          </div>
          <div className="filter-field">
            <label>Warehouse Region</label>
            <select value={filters.warehouse_region} onChange={set('warehouse_region')}>
              {REGION_OPTIONS.map(s => <option key={s} value={s}>{s || 'Any'}</option>)}
            </select>
          </div>
          <div className="filter-field">
            <label>Inventory Status</label>
            <select value={filters.inventory_status} onChange={set('inventory_status')}>
              {INVENTORY_OPTIONS.map(s => <option key={s} value={s}>{s || 'Any'}</option>)}
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
          <button className="btn-primary" onClick={handleSearch} disabled={loading}>
            {loading ? 'Loading...' : 'Apply Filters'}
          </button>
          <button className="btn-ghost" onClick={handleReset}>Reset</button>
        </div>
      </div>

      {error && <div className="error-banner">Error: {error}</div>}

      {data && (
        <IncidentTable
          incidents={data.incidents || []}
          title={`Shipments (${data.total ?? data.incidents?.length ?? 0} found)`}
        />
      )}
    </div>
  );
}
