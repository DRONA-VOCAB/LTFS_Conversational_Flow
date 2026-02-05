/**
 * Application Settings
 * Centralized configuration for backend URLs and API endpoints
 */

// Backend API Base URL
// Use relative URL if served from same origin, otherwise use env var or default
// This allows the app to work whether served from same domain or different port
export const API_BASE_URL =
  import.meta.env.VITE_API_URL || 
  (typeof window !== 'undefined' ? window.location.origin : "http://localhost:8001");

// WebSocket URL (derived from API_BASE_URL)
// Use wss:// for HTTPS, ws:// for HTTP
export const WS_URL = API_BASE_URL.replace(/^https/, "wss").replace(/^http/, "ws") + "/ws/audio";

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
