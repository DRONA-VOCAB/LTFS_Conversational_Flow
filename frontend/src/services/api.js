import axios from 'axios'
import { API_BASE_URL, API_ENDPOINTS } from '../config/settings'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

export const createSession = async (customerName) => {
  try {
    const response = await api.post(API_ENDPOINTS.CREATE_SESSION, {
      customer_name: customerName,
    })
    return response.data
  } catch (error) {
    throw new Error(error.response?.data?.detail || 'Failed to create session')
  }
}

export const submitAnswer = async (sessionId, answer) => {
  try {
    const response = await api.post(API_ENDPOINTS.SUBMIT_ANSWER(sessionId), {
      answer: answer,
    })
    return response.data
  } catch (error) {
    throw new Error(error.response?.data?.detail || 'Failed to submit answer')
  }
}

export const getSummary = async (sessionId) => {
  try {
    const response = await api.get(API_ENDPOINTS.GET_SUMMARY(sessionId))
    return response.data
  } catch (error) {
    throw new Error(error.response?.data?.detail || 'Failed to get summary')
  }
}

export const confirmSummary = async (sessionId) => {
  try {
    const response = await api.post(API_ENDPOINTS.CONFIRM_SUMMARY(sessionId), {
      confirmed: true,
    })
    return response.data
  } catch (error) {
    throw new Error(error.response?.data?.detail || 'Failed to confirm summary')
  }
}

export const getCustomers = async () => {
  try {
    const response = await api.get(API_ENDPOINTS.GET_CUSTOMERS)
    return response.data
  } catch (error) {
    throw new Error(error.response?.data?.detail || 'Failed to fetch customers')
  }
}

export default api


