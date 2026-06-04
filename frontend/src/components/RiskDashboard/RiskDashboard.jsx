import React, { useEffect, useState } from 'react';
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts';
import { fetchIncidents } from '../../api/supplyChainApi';
import './RiskDashboard.css';

const COLORS = ['#4f8ef7', '#f59e0b', '#22c55e', '#ef4444', '#a855f7', '#06b6d4'];

function groupBy(arr, key) {
  return arr.reduce((acc, item) => {
    const k = item.metadata?.[key] || 'Unknown';
    acc[k] = (acc[k] || []);
    acc[k].push(item);
    return acc;
  }, {});
}

export default function RiskDashboard() {
  const [incidents, setIncidents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchIncidents({ limit: 100 })
      .then(d => setIncidents(d.incidents || []))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="dash-loading">Loading dashboard data...</div>;
  if (error) return <div className="dash-error">Error: {error}</div>;
  if (!incidents.length) return <div className="dash-empty">No incident data available. Run ingestion first.</div>;

  // Severity distribution
  const severityData = Object.entries(groupBy(incidents, 'severity')).map(([name, items]) => ({
    name: name.charAt(0).toUpperCase() + name.slice(1),
    value: items.length,
  }));

  // Shipment status breakdown
  const statusData = Object.entries(groupBy(incidents, 'shipment_status'))
    .map(([name, items]) => ({ name, count: items.length }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 8);

  // Top suppliers by avg delay
  const supplierGroups = groupBy(incidents, 'supplier_id');
  const supplierDelayData = Object.entries(supplierGroups)
    .map(([supplier, items]) => ({
      supplier: supplier.length > 10 ? supplier.slice(0, 10) + '…' : supplier,
      avgDelay: +(items.reduce((s, i) => s + (i.metadata?.delivery_delay || 0), 0) / items.length).toFixed(1),
      count: items.length,
    }))
    .sort((a, b) => b.avgDelay - a.avgDelay)
    .slice(0, 10);

  // Warehouse inventory levels
  const warehouseGroups = groupBy(incidents, 'warehouse_location');
  const warehouseData = Object.entries(warehouseGroups)
    .map(([warehouse, items]) => ({
      warehouse: warehouse.length > 12 ? warehouse.slice(0, 12) + '…' : warehouse,
      avgInventory: +(items.reduce((s, i) => s + (i.metadata?.inventory_level || 0), 0) / items.length).toFixed(0),
      avgDemand: +(items.reduce((s, i) => s + (i.metadata?.demand_forecast || 0), 0) / items.length).toFixed(0),
    }))
    .sort((a, b) => a.avgInventory - b.avgInventory)
    .slice(0, 8);

  return (
    <div className="risk-dashboard">
      <div className="dash-kpis">
        <KpiCard label="Total Incidents" value={incidents.length} />
        <KpiCard
          label="High Severity"
          value={incidents.filter(i => i.metadata?.severity === 'high').length}
          danger
        />
        <KpiCard
          label="Avg Delay"
          value={`${(incidents.reduce((s, i) => s + (i.metadata?.delivery_delay || 0), 0) / incidents.length).toFixed(1)}d`}
        />
        <KpiCard
          label="Delayed Shipments"
          value={incidents.filter(i => i.metadata?.shipment_status === 'delayed').length}
          warning
        />
      </div>

      <div className="dash-grid">
        <div className="dash-card">
          <h4>Severity Distribution</h4>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={severityData} cx="50%" cy="50%" outerRadius={80} dataKey="value" label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
                {severityData.map((_, i) => (
                  <Cell key={i} fill={['#ef4444', '#f59e0b', '#22c55e'][i] || COLORS[i]} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8 }} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="dash-card">
          <h4>Shipment Status Breakdown</h4>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={statusData} layout="vertical" margin={{ left: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis type="number" tick={{ fill: 'var(--text-muted)', fontSize: 11 }} />
              <YAxis dataKey="name" type="category" tick={{ fill: 'var(--text-muted)', fontSize: 11 }} width={80} />
              <Tooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8 }} />
              <Bar dataKey="count" fill="var(--accent)" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="dash-card wide">
          <h4>Top 10 Suppliers by Average Delivery Delay</h4>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={supplierDelayData} margin={{ bottom: 40 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="supplier" tick={{ fill: 'var(--text-muted)', fontSize: 10 }} angle={-30} textAnchor="end" />
              <YAxis tick={{ fill: 'var(--text-muted)', fontSize: 11 }} />
              <Tooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8 }} />
              <Bar dataKey="avgDelay" name="Avg Delay (days)" fill="#ef4444" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="dash-card wide">
          <h4>Inventory vs Demand by Warehouse</h4>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={warehouseData} margin={{ bottom: 40 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="warehouse" tick={{ fill: 'var(--text-muted)', fontSize: 10 }} angle={-30} textAnchor="end" />
              <YAxis tick={{ fill: 'var(--text-muted)', fontSize: 11 }} />
              <Tooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8 }} />
              <Legend wrapperStyle={{ color: 'var(--text-muted)', fontSize: 12 }} />
              <Bar dataKey="avgInventory" name="Avg Inventory" fill="var(--accent)" radius={[4, 4, 0, 0]} />
              <Bar dataKey="avgDemand" name="Avg Demand Forecast" fill="#f59e0b" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

function KpiCard({ label, value, danger, warning }) {
  return (
    <div className={`kpi-card ${danger ? 'kpi-danger' : warning ? 'kpi-warning' : ''}`}>
      <div className="kpi-value">{value}</div>
      <div className="kpi-label">{label}</div>
    </div>
  );
}
