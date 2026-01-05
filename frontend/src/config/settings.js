/**
 * Application Settings
 * Centralized configuration for backend URLs and API endpoints
 */

// Backend API Base URL
// Can be overridden by environment variable VITE_API_URL
export const API_BASE_URL =
  import.meta.env.VITE_API_URL || "http://localhost:8000";

// API Endpoints
export const API_ENDPOINTS = {
  // Session endpoints
  CREATE_SESSION: "/sessions",
  SUBMIT_ANSWER: (sessionId) => `/sessions/${sessionId}/answer`,
  GET_SUMMARY: (sessionId) => `/sessions/${sessionId}/summary`,
  CONFIRM_SUMMARY: (sessionId) => `/sessions/${sessionId}/confirm`,
  GET_SESSION_INFO: (sessionId) => `/sessions/${sessionId}`,
  GET_CUSTOMERS: "/sessions/customers",

  // API Documentation
  API_DOCS: "/docs",
};

// Export default settings object
const settings = {
  API_BASE_URL,
  API_ENDPOINTS,
};

export default settings;
