import React, { useState } from 'react';
import { useAppContext } from '../../context/AppContext';
import './QueryPanel.css';

const SEVERITY_OPTIONS = ['', 'low', 'medium', 'high'];
const STATUS_OPTIONS = ['', 'delayed', 'in_transit', 'delivered', 'pending'];
const SAMPLE_QUERIES = [
  'Supplier delivery delays are increasing for critical components',
  'Warehouse inventory approaching stockout levels',
  'Port congestion is impacting shipment schedules',
  'Transportation costs increased unexpectedly across regions',
  'Demand spikes causing fulfillment bottlenecks',
];

export default function QueryPanel({ onSubmit, loading }) {
  const { activeFilters, setActiveFilters } = useAppContext();
  const [query, setQuery] = useState('');
  const [topK, setTopK] = useState(5);
  const [showFilters, setShowFilters] = useState(false);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!query.trim() || loading) return;
    onSubmit(query.trim(), activeFilters, topK);
  };

  const handleSample = (q) => {
    setQuery(q);
  };

  const handleFilterChange = (key, val) => {
    setActiveFilters(prev => ({ ...prev, [key]: val }));
  };

  const clearFilters = () => {
    setActiveFilters({ supplier_id: '', warehouse_location: '', shipment_status: '', severity: '' });
  };

  const activeCount = Object.values(activeFilters).filter(Boolean).length;

  return (
    <div className="query-panel">
      <div className="query-panel__header">
        <h2>Supply Chain Risk Query</h2>
        <p className="query-panel__subtitle">
          Describe a supply chain concern in plain English
        </p>
      </div>

      <form onSubmit={handleSubmit} className="query-form">
        <div className="query-form__input-row">
          <textarea
            className="query-form__textarea"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="e.g. Supplier delivery delays are increasing for critical components in the Chicago warehouse..."
            rows={3}
            disabled={loading}
          />
          <button
            type="submit"
            className={`query-form__submit ${loading ? 'loading' : ''}`}
            disabled={loading || !query.trim()}
          >
            {loading ? <span className="spinner" /> : 'Analyze'}
          </button>
        </div>

        <div className="query-form__controls">
          <button
            type="button"
            className={`btn-ghost ${showFilters ? 'active' : ''}`}
            onClick={() => setShowFilters(v => !v)}
          >
            Filters {activeCount > 0 && <span className="badge">{activeCount}</span>}
          </button>
          <label className="topk-label">
            Results:
            <select value={topK} onChange={e => setTopK(Number(e.target.value))} className="topk-select">
              {[3, 5, 8, 10].map(n => <option key={n} value={n}>{n}</option>)}
            </select>
          </label>
        </div>

        {showFilters && (
          <div className="query-filters">
            <div className="filter-row">
              <div className="filter-field">
                <label>Supplier ID</label>
                <input
                  type="text"
                  placeholder="e.g. SUP-001"
                  value={activeFilters.supplier_id}
                  onChange={e => handleFilterChange('supplier_id', e.target.value)}
                />
              </div>
              <div className="filter-field">
                <label>Warehouse</label>
                <input
                  type="text"
                  placeholder="e.g. Chicago"
                  value={activeFilters.warehouse_location}
                  onChange={e => handleFilterChange('warehouse_location', e.target.value)}
                />
              </div>
              <div className="filter-field">
                <label>Shipment Status</label>
                <select
                  value={activeFilters.shipment_status}
                  onChange={e => handleFilterChange('shipment_status', e.target.value)}
                >
                  {STATUS_OPTIONS.map(s => <option key={s} value={s}>{s || 'Any'}</option>)}
                </select>
              </div>
              <div className="filter-field">
                <label>Severity</label>
                <select
                  value={activeFilters.severity}
                  onChange={e => handleFilterChange('severity', e.target.value)}
                >
                  {SEVERITY_OPTIONS.map(s => <option key={s} value={s}>{s || 'Any'}</option>)}
                </select>
              </div>
            </div>
            {activeCount > 0 && (
              <button type="button" className="btn-ghost small" onClick={clearFilters}>
                Clear filters
              </button>
            )}
          </div>
        )}
      </form>

      <div className="sample-queries">
        <span className="sample-queries__label">Try:</span>
        {SAMPLE_QUERIES.map((q, i) => (
          <button key={i} className="sample-chip" onClick={() => handleSample(q)}>
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}
