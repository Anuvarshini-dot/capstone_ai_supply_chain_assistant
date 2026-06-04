import React from 'react';
import RiskDashboard from '../components/RiskDashboard/RiskDashboard';
import './Dashboard.css';

export default function Dashboard() {
  return (
    <div className="dashboard-page">
      <div className="dashboard-header">
        <h2>Risk Dashboard</h2>
        <p>Real-time supply chain risk analytics across all incidents</p>
      </div>
      <RiskDashboard />
    </div>
  );
}
