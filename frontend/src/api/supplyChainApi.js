import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  headers: { 'Content-Type': 'application/json' },
})

export const querySupplyChain = (query, filters = null, topK = 5) =>
  api.post('/api/query', { query, filters, top_k: topK }).then(r => r.data)

export const fetchIncidents = (params = {}) =>
  api.get('/api/incidents', { params }).then(r => r.data)

export const fetchIncidentById = (id) =>
  api.get(`/api/incidents/${id}`).then(r => r.data)

export const findSimilarIncidents = (incidentText, topK = 5) =>
  api.post('/api/incidents/similar', { incident_text: incidentText, top_k: topK }).then(r => r.data)

export const getRecommendations = (query) =>
  api.post('/api/recommendations', { query }).then(r => r.data)

export const checkHealth = () =>
  api.get('/api/health').then(r => r.data)

export default api
