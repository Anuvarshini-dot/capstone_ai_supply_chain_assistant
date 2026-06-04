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
  const [messages, setMessages] = useState([]);

  const addToHistory = (query, result) => {
    setQueryHistory(prev => [
      { query, result, timestamp: new Date().toISOString() },
      ...prev.slice(0, 9),
    ]);
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
      addToHistory,
      messages,
      addMessage,
    }}>
      {children}
    </AppContext.Provider>
  );
}

export const useAppContext = () => useContext(AppContext);
