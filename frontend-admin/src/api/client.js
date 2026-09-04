// Deliberately a copy, not an import from ../frontend — the two Vite roots
// stay decoupled, and the admin app needs exactly these four calls. Same
// same-origin '/api' convention (vite proxy in dev, nginx rewrite in prod).
const API_URL = '/api';
const TOKEN_KEY = 'lily_admin_token';

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

function authHeaders() {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function jsonOrThrow(res) {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      // empty body, keep statusText
    }
    const err = new Error(detail);
    err.status = res.status;
    throw err;
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  async requestChallenge(identifier) {
    const res = await fetch(`${API_URL}/auth/request`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ identifier }),
    });
    return jsonOrThrow(res);
  },

  async verifyChallenge({ identifier, code }) {
    const res = await fetch(`${API_URL}/auth/verify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ identifier, code }),
    });
    return jsonOrThrow(res);
  },

  async googleAuth({ credential }) {
    const res = await fetch(`${API_URL}/auth/google`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ credential }),
    });
    return jsonOrThrow(res);
  },

  async me() {
    const res = await fetch(`${API_URL}/me`, { headers: authHeaders() });
    return jsonOrThrow(res);
  },

  async getOverview({ startDate, endDate } = {}) {
    const params = new URLSearchParams();
    if (startDate) params.set('start_date', startDate);
    if (endDate) params.set('end_date', endDate);
    const qs = params.toString();
    const res = await fetch(
      `${API_URL}/admin/stats/overview${qs ? `?${qs}` : ''}`,
      { headers: authHeaders() },
    );
    return jsonOrThrow(res);
  },

  // The last stretch of app_logs. `levels` and `services` are arrays;
  // `since`/`before` are ISO datetimes; `q` is a word in the message.
  async getLogs({ levels, services, since, q, before, limit } = {}) {
    const params = new URLSearchParams();
    if (levels?.length) params.set('levels', levels.join(','));
    if (services?.length) params.set('services', services.join(','));
    if (since) params.set('since', since);
    if (before) params.set('before', before);
    if (q) params.set('q', q);
    if (limit) params.set('limit', String(limit));
    const qs = params.toString();
    const res = await fetch(`${API_URL}/admin/logs${qs ? `?${qs}` : ''}`, {
      headers: authHeaders(),
    });
    return jsonOrThrow(res);
  },

  // Every order, newest first, with money in and out and the printer's state.
  async getOrders() {
    const res = await fetch(`${API_URL}/admin/orders`, { headers: authHeaders() });
    return jsonOrThrow(res);
  },

  // Send a draft to print (our money moves at the partner), or cancel it and
  // refund the buyer. Both return the updated order row.
  async approveOrder(orderId) {
    const res = await fetch(`${API_URL}/admin/orders/${orderId}/approve`, { method: 'POST', headers: authHeaders() });
    return jsonOrThrow(res);
  },

  async cancelOrder(orderId) {
    const res = await fetch(`${API_URL}/admin/orders/${orderId}/cancel`, { method: 'POST', headers: authHeaders() });
    return jsonOrThrow(res);
  },

  // Public. Answers 503 with the same body when something is down, so read
  // the body either way rather than throwing on status.
  async getHealth() {
    const res = await fetch(`${API_URL}/health`);
    try {
      return await res.json();
    } catch {
      return { status: 'degraded', db: 'error', revision: null, worker: { seen_at: null, ok: false } };
    }
  },
};
