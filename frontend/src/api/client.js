const API_URL = import.meta.env.DEV ? 'http://localhost:8000' : '';
const TOKEN_KEY = 'lily_auth_token';

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
  apiUrl: API_URL,

  async requestChallenge(identifier) {
    const res = await fetch(`${API_URL}/auth/request`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ identifier }),
    });
    return jsonOrThrow(res);
  },

  async verifyChallenge({ identifier, code, token }) {
    const res = await fetch(`${API_URL}/auth/verify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ identifier, code, token }),
    });
    return jsonOrThrow(res);
  },

  async me() {
    const res = await fetch(`${API_URL}/me`, { headers: authHeaders() });
    return jsonOrThrow(res);
  },

  async getBirth(birthId) {
    const res = await fetch(`${API_URL}/birth/${birthId}`, { headers: authHeaders() });
    return jsonOrThrow(res);
  },

  async getPublicBirth(slug) {
    const res = await fetch(`${API_URL}/b/${slug}`);
    return jsonOrThrow(res);
  },

  async listTimeline(birthId, { afterSequenceId } = {}) {
    const url = new URL(`${API_URL}/birth/${birthId}/timeline`);
    if (afterSequenceId != null) url.searchParams.set('after_sequence_id', afterSequenceId);
    const res = await fetch(url, { headers: authHeaders() });
    return jsonOrThrow(res);
  },

  async listPublicTimeline(slug, { afterSequenceId } = {}) {
    const url = new URL(`${API_URL}/b/${slug}/timeline`);
    if (afterSequenceId != null) url.searchParams.set('after_sequence_id', afterSequenceId);
    const res = await fetch(url);
    return jsonOrThrow(res);
  },

  async startContraction(birthId) {
    const res = await fetch(`${API_URL}/birth/${birthId}/contraction/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({}),
    });
    return jsonOrThrow(res);
  },

  async stopContraction(birthId, eventId, endTimeIso) {
    const res = await fetch(`${API_URL}/birth/${birthId}/contraction/${eventId}/stop`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ end_time: endTimeIso }),
    });
    return jsonOrThrow(res);
  },

  async createTextNote(birthId, body) {
    const res = await fetch(`${API_URL}/birth/${birthId}/event`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ type: 'text_note', body }),
    });
    return jsonOrThrow(res);
  },

  async createMilestone(birthId, { kind, title, body }) {
    const res = await fetch(`${API_URL}/birth/${birthId}/event`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ type: 'milestone', kind, title, body }),
    });
    return jsonOrThrow(res);
  },

  async uploadMedia(birthId, { file, kind, caption }) {
    const form = new FormData();
    form.append('file', file);
    form.append('kind', kind);
    if (caption) form.append('caption', caption);
    const res = await fetch(`${API_URL}/birth/${birthId}/media`, {
      method: 'POST',
      headers: authHeaders(),
      body: form,
    });
    return jsonOrThrow(res);
  },

  async editEvent(birthId, eventId, patch) {
    const res = await fetch(`${API_URL}/birth/${birthId}/event/${eventId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify(patch),
    });
    return jsonOrThrow(res);
  },

  async deleteEvent(birthId, eventId) {
    const res = await fetch(`${API_URL}/birth/${birthId}/event/${eventId}`, {
      method: 'DELETE',
      headers: authHeaders(),
    });
    return jsonOrThrow(res);
  },

  async toggleIgnoreInterval(birthId, eventId) {
    const res = await fetch(`${API_URL}/birth/${birthId}/event/${eventId}/toggle-ignore`, {
      method: 'POST',
      headers: authHeaders(),
    });
    return jsonOrThrow(res);
  },

  mediaUrl(mediaId) {
    return `${API_URL}/media/${mediaId}`;
  },
};
