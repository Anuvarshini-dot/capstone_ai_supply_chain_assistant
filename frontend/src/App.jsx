import React from 'react';
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import Home from './pages/Home';
import Incidents from './pages/Incidents';
import Dashboard from './pages/Dashboard';
import Evaluation from './pages/Evaluation';
import { AppProvider } from './context/AppContext';
import './App.css';

function Navbar() {
  return (
    <nav className="navbar">
      <div className="navbar__brand">
        <span className="brand-icon">⚡</span>
        <span className="brand-name">Supply Chain AI</span>
        <span className="brand-tag">Risk Intelligence</span>
      </div>
      <div className="navbar__links">
        <NavLink to="/" end className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
          Query
        </NavLink>
        <NavLink to="/incidents" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
          Incidents
        </NavLink>
        <NavLink to="/dashboard" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
          Dashboard
        </NavLink>
        <NavLink to="/evaluation" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
          Evaluation
        </NavLink>
      </div>
      <div className="navbar__status">
        <span className="status-dot" />
        Live
      </div>
    </nav>
  );
}

export default function App() {
  return (
    <AppProvider>
      <BrowserRouter>
        <div className="app-shell">
          <Navbar />
          <main className="app-main">
            <div className="app-container">
              <Routes>
                <Route path="/" element={<Home />} />
                <Route path="/incidents" element={<Incidents />} />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/evaluation" element={<Evaluation />} />
              </Routes>
            </div>
          </main>
        </div>
      </BrowserRouter>
    </AppProvider>
  );
}
