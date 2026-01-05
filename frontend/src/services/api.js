import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

export const createSession = async (customerName) => {
  try {
    const response = await api.post('/sessions', {
      customer_name: customerName,
    })
    return response.data
  } catch (error) {
    throw new Error(error.response?.data?.detail || 'Failed to create session')
  }
}

export const submitAnswer = async (sessionId, answer) => {
  try {
    const response = await api.post(`/sessions/${sessionId}/answer`, {
      answer: answer,
    })
    return response.data
  } catch (error) {
    throw new Error(error.response?.data?.detail || 'Failed to submit answer')
  }
}

export const getSummary = async (sessionId) => {
  try {
    const response = await api.get(`/sessions/${sessionId}/summary`)
    return response.data
  } catch (error) {
    throw new Error(error.response?.data?.detail || 'Failed to get summary')
  }
}

export const confirmSummary = async (sessionId) => {
  try {
    const response = await api.post(`/sessions/${sessionId}/confirm`, {
      confirmed: true,
    })
    return response.data
  } catch (error) {
    throw new Error(error.response?.data?.detail || 'Failed to confirm summary')
  }
}

export const getCustomers = async () => {
  try {
    const response = await api.get('/sessions/customers')
    return response.data
  } catch (error) {
    throw new Error(error.response?.data?.detail || 'Failed to fetch customers')
  }
}

export default api


