function getDefaultApiBase() {
  if (!import.meta.env.DEV) return '/api';
  const protocol = window.location.protocol || 'http:';
  const hostname = window.location.hostname || 'localhost';
  const host = hostname.includes(':') ? `[${hostname}]` : hostname;
  return `${protocol}//${host}:8000/api`;
}

const DEFAULT_API_BASE = getDefaultApiBase();
const CSRF_COOKIE_NAME = 'remoire_csrf';
const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS']);

export const API_BASE = (import.meta.env.VITE_API_BASE || DEFAULT_API_BASE).replace(/\/$/, '');

function readCookie(name) {
  const prefix = `${encodeURIComponent(name)}=`;
  const match = document.cookie.split('; ').find((entry) => entry.startsWith(prefix));
  return match ? decodeURIComponent(match.slice(prefix.length)) : '';
}

export function apiHeaders(extra = {}, method = 'GET') {
  const headers = { ...extra };
  if (!SAFE_METHODS.has(method.toUpperCase())) {
    const csrfToken = readCookie(CSRF_COOKIE_NAME);
    if (csrfToken) headers['X-CSRF-Token'] = csrfToken;
  }
  return headers;
}

export function apiUrl(path) {
  return `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`;
}

export async function apiFetch(path, options = {}) {
  const method = options.method || 'GET';
  const response = await fetch(apiUrl(path), {
    ...options,
    method,
    credentials: 'include',
    headers: apiHeaders(options.headers || {}, method),
  });
  if (response.status === 401 && !path.startsWith('/auth/')) {
    window.dispatchEvent(new CustomEvent('remoire-auth-required'));
  }
  return response;
}

export function apiJsonFetch(path, options = {}) {
  return apiFetch(path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
  });
}

export function apiErrorMessage(payload, fallback = '请求未能完成') {
  if (typeof payload?.error?.message === 'string' && payload.error.message.trim()) return payload.error.message;
  if (typeof payload?.error === 'string' && payload.error.trim()) return payload.error;
  if (typeof payload?.detail?.message === 'string' && payload.detail.message.trim()) return payload.detail.message;
  if (typeof payload?.detail === 'string' && payload.detail.trim()) return payload.detail;
  return fallback;
}
