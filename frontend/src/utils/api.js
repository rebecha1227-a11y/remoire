const DEFAULT_API_BASE = import.meta.env.DEV ? 'http://localhost:8000/api' : '/api';
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
