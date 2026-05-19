function getDefaultApiBase() {
  if (!import.meta.env.DEV) return '/api';
  const protocol = window.location.protocol || 'http:';
  const hostname = window.location.hostname || 'localhost';
  const host = hostname.includes(':') ? `[${hostname}]` : hostname;
  return `${protocol}//${host}:8000/api`;
}

const DEFAULT_API_BASE = getDefaultApiBase();
const DEV_AUTH_TOKEN = 'remoire-rebechalovesconnie-4ever';

export const API_BASE = (import.meta.env.VITE_API_BASE || DEFAULT_API_BASE).replace(/\/$/, '');

export function getAuthToken() {
  return localStorage.getItem('remoire_api_token') || DEV_AUTH_TOKEN;
}

export function apiHeaders(extra = {}) {
  const token = getAuthToken();
  return {
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...extra,
  };
}

export function apiUrl(path) {
  return `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`;
}

export function apiFetch(path, options = {}) {
  return fetch(apiUrl(path), {
    ...options,
    headers: apiHeaders(options.headers || {}),
  });
}

export function apiJsonFetch(path, options = {}) {
  return apiFetch(path, {
    ...options,
    headers: apiHeaders({
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    }),
  });
}
