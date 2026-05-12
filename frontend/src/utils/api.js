const DEFAULT_API_BASE = 'http://localhost:8000/api';
const DEFAULT_AUTH_TOKEN = 'remoire-rebechalovesconnie-4ever';

export const API_BASE = (import.meta.env.VITE_API_BASE || DEFAULT_API_BASE).replace(/\/$/, '');

export function getAuthToken() {
  return localStorage.getItem('remoire_api_token') || import.meta.env.VITE_API_TOKEN || DEFAULT_AUTH_TOKEN;
}

export function apiHeaders(extra = {}) {
  return {
    Authorization: `Bearer ${getAuthToken()}`,
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
