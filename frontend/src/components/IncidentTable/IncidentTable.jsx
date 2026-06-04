import React, { useState } from 'react';
import './IncidentTable.css';

const SEVERITY_CLASS = { high: 'severity-high', medium: 'severity-medium', low: 'severity-low' };
const RISK_CLASS     = { high: 'severity-high', medium: 'severity-medium', low: 'severity-low' };

export default function IncidentTable({ incidents = [], title = 'Retrieved Incidents' }) {
  const [expanded, setExpanded] = useState(null);
  const [sortKey, setSortKey]   = useState('rerank_score');
  const [sortDir, setSortDir]   = useState('desc');

  if (!incidents.length) {
    return <div className="incident-table empty"><p>No incidents found.</p></div>;
  }

  const handleSort = (key) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortKey(key); setSortDir('desc'); }
  };

  const sorted = [...incidents].sort((a, b) => {
    const av = a.metadata?.[sortKey] ?? a[sortKey] ?? 0;
    const bv = b.metadata?.[sortKey] ?? b[sortKey] ?? 0;
    return sortDir === 'asc' ? av - bv : bv - av;
  });

  const SortIcon = ({ col }) => (
    <span className="sort-icon">{sortKey === col ? (sortDir === 'asc' ? '↑' : '↓') : '↕'}</span>
  );

  return (
    <div className="incident-table">
      <div className="incident-table__header">
        <h3>{title}</h3>
        <span className="count-badge">{incidents.length} records</span>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Supplier</th>
              <th>Risk Tier</th>
              <th>Product</th>
              <th>Status</th>
              <th className="sortable" onClick={() => handleSort('delay_days')}>
                Delay (d) <SortIcon col="delay_days" />
              </th>
              <th>Inventory</th>
              <th className="sortable" onClick={() => handleSort('risk_score')}>
                Risk Score <SortIcon col="risk_score" />
              </th>
              <th>Severity</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((inc, i) => {
              const m      = inc.metadata || {};
              const isOpen = expanded === inc.id;
              return (
                <React.Fragment key={inc.id}>
                  <tr className={isOpen ? 'row-expanded' : ''}>
                    <td className="row-num">{i + 1}</td>
                    <td className="mono">{m.supplier_name || '—'}</td>
                    <td>
                      <span className={`severity-badge ${RISK_CLASS[m.risk_tier] || ''}`}>
                        {m.risk_tier || '—'}
                      </span>
                    </td>
                    <td>{m.product_name || '—'}</td>
                    <td>
                      <span className={`status-tag status-${(m.shipment_status || '').replace('_', '-')}`}>
                        {m.shipment_status || '—'}
                      </span>
                    </td>
                    <td className="num">{m.delay_days ?? '—'}</td>
                    <td>
                      <span className={`severity-badge ${SEVERITY_CLASS[m.inventory_status === 'stockout' ? 'high' : m.inventory_status === 'critical' ? 'high' : m.inventory_status === 'low' ? 'medium' : 'low'] || ''}`}>
                        {m.inventory_status || '—'}
                      </span>
                    </td>
                    <td className="num">{m.risk_score ?? '—'}</td>
                    <td>
                      <span className={`severity-badge ${SEVERITY_CLASS[m.severity] || ''}`}>
                        {m.severity || '—'}
                      </span>
                    </td>
                    <td>
                      <button className="expand-btn" onClick={() => setExpanded(isOpen ? null : inc.id)}>
                        {isOpen ? '▲' : '▼'}
                      </button>
                    </td>
                  </tr>
                  {isOpen && (
                    <tr className="detail-row">
                      <td colSpan={10}>
                        <div className="incident-detail">
                          <p className="incident-text">{inc.text}</p>
                          <div className="incident-meta-grid">
                            <div><span>Warehouse</span>{m.warehouse_name || '—'}</div>
                            <div><span>Region</span>{m.warehouse_region || '—'}</div>
                            <div><span>Shipping Mode</span>{m.shipping_mode || '—'}</div>
                            <div><span>Carrier</span>{m.carrier || m.shipping_mode || '—'}</div>
                            <div><span>Stock Units</span>{m.stock_level_units ?? '—'}</div>
                            <div><span>Days of Supply</span>{m.days_of_supply ?? '—'}</div>
                            <div><span>Stockouts (30d)</span>{m.stockout_count_30d ?? '—'}</div>
                            <div><span>Reliability</span>{m.reliability_score ?? '—'}</div>
                            <div><span>On-Time Rate</span>{m.on_time_delivery_rate ?? '—'}</div>
                            <div><span>Order Date</span>{m.timestamp || '—'}</div>
                            {inc.rerank_score != null && <div><span>Relevance</span>{inc.rerank_score}</div>}
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
