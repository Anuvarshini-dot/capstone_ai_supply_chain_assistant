import { useState, useCallback } from 'react';
import { querySupplyChain, fetchIncidents } from '../api/supplyChainApi';
import { useAppContext } from '../context/AppContext';

export function useQuery() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const { addToHistory, setLastResult } = useAppContext();

  const runQuery = useCallback(async (query, filters, topK = 5) => {
    setLoading(true);
    setError(null);
    try {
      const cleanFilters = filters
        ? Object.fromEntries(Object.entries(filters).filter(([, v]) => v))
        : null;
      const data = await querySupplyChain(query, cleanFilters || null, topK);
      setResult(data);
      setLastResult(data);
      addToHistory(query, data);
      return data;
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Query failed';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [addToHistory, setLastResult]);

  return { loading, error, result, runQuery };
}

export function useIncidents() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);

  const load = useCallback(async (params = {}) => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchIncidents(params);
      setData(result);
      return result;
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to load incidents');
    } finally {
      setLoading(false);
    }
  }, []);

  return { loading, error, data, load };
}
