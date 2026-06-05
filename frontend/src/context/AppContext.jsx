import React, { createContext, useContext, useState, useCallback } from 'react';

const AppContext = createContext(null);

export function AppProvider({ children }) {
  const [queryHistory, setQueryHistory] = useState([]);
  const [activeFilters, setActiveFilters] = useState({
    risk_tier: '',
    shipment_status: '',
    shipping_mode: '',
    severity: '',
    inventory_status: '',
    supplier_category: '',
  });
  const [lastResult, setLastResult] = useState(null);
  const [executionLog, setExecutionLog] = useState([]);
  const [messages, setMessages] = useState([]);
  const [queryIncidents, setQueryIncidents] = useState([]);

  const addToHistory = (query, result) => {
    setQueryHistory(prev => [
      { query, result, timestamp: new Date().toISOString() },
      ...prev.slice(0, 9),
    ]);
    if (result?.execution_log?.length) {
      setExecutionLog(result.execution_log);
    }
    // Store shipment-type docs for the Incidents tab to display on demand
    const shipments = (result?.retrieved_incidents || []).filter(
      inc => !inc.metadata?.doc_type || inc.metadata?.doc_type === 'shipment'
    );
    setQueryIncidents(shipments);
  };

  const addMessage = useCallback((msg) => {
    setMessages(prev => [...prev, msg]);
  }, []);

  return (
    <AppContext.Provider value={{
      queryHistory,
      activeFilters,
      setActiveFilters,
      lastResult,
      setLastResult,
      executionLog,
      addToHistory,
      messages,
      addMessage,
      queryIncidents,
      setQueryIncidents,
    }}>
      {children}
    </AppContext.Provider>
  );
}

export const useAppContext = () => useContext(AppContext);
