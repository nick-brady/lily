// Same-origin '/api' prefix in BOTH modes: the vite dev server proxies it to
// the backend over the docker network, and prod nginx does the identical
// rewrite-strip. The prefix matters — /b/{slug} is both an SPA route and an
// API route, so a bare same-origin path could never be proxied safely.
const API_URL = '/api';
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

  async verifyChallenge({ identifier, code, token, inviteToken }) {
    const res = await fetch(`${API_URL}/auth/verify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        identifier,
        code,
        token,
        invite_token: inviteToken,
      }),
    });
    return jsonOrThrow(res);
  },

  async me() {
    const res = await fetch(`${API_URL}/me`, { headers: authHeaders() });
    return jsonOrThrow(res);
  },

  async updateMe({ displayName }) {
    const res = await fetch(`${API_URL}/me`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ display_name: displayName }),
    });
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
    const url = new URL(`${API_URL}/birth/${birthId}/timeline`, window.location.origin);
    if (afterSequenceId != null) url.searchParams.set('after_sequence_id', afterSequenceId);
    const res = await fetch(url, { headers: authHeaders() });
    return jsonOrThrow(res);
  },

  async listPublicTimeline(slug, { afterSequenceId } = {}) {
    const url = new URL(`${API_URL}/b/${slug}/timeline`, window.location.origin);
    if (afterSequenceId != null) url.searchParams.set('after_sequence_id', afterSequenceId);
    // Sending Bearer here is intentional: authed viewers get widened
    // audience visibility on the same public endpoint.
    const res = await fetch(url, { headers: authHeaders() });
    return jsonOrThrow(res);
  },

  async startContraction(birthId, { audienceScope = 'public' } = {}) {
    const res = await fetch(`${API_URL}/birth/${birthId}/contraction/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ audience_scope: audienceScope }),
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

  async createTextNote(birthId, body, { audienceScope = 'public' } = {}) {
    const res = await fetch(`${API_URL}/birth/${birthId}/event`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({
        type: 'text_note',
        body,
        audience_scope: audienceScope,
      }),
    });
    return jsonOrThrow(res);
  },

  async createMilestone(birthId, { kind, title, body, audienceScope = 'public' }) {
    const res = await fetch(`${API_URL}/birth/${birthId}/event`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({
        type: 'milestone',
        kind,
        title,
        body,
        audience_scope: audienceScope,
      }),
    });
    return jsonOrThrow(res);
  },

  async uploadMedia(birthId, { file, kind, caption, audienceScope = 'public' }) {
    const form = new FormData();
    form.append('file', file);
    form.append('kind', kind);
    form.append('audience_scope', audienceScope);
    if (caption) form.append('caption', caption);
    const res = await fetch(`${API_URL}/birth/${birthId}/media`, {
      method: 'POST',
      headers: authHeaders(),
      body: form,
    });
    return jsonOrThrow(res);
  },

  async listGifts(birthId) {
    const res = await fetch(`${API_URL}/birth/${birthId}/gifts`, {
      headers: authHeaders(),
    });
    return jsonOrThrow(res);
  },

  async generateGifts(birthId, renderingId = null) {
    const qs = renderingId ? `?rendering_id=${renderingId}` : '';
    const res = await fetch(`${API_URL}/birth/${birthId}/gifts/generate${qs}`, {
      method: 'POST',
      headers: authHeaders(),
    });
    return jsonOrThrow(res);
  },

  async createGiftCheckout(birthId, renderingId, { recipientKind, giftMessage }) {
    const res = await fetch(
      `${API_URL}/birth/${birthId}/gifts/${renderingId}/checkout`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({
          recipient_kind: recipientKind,
          gift_message: giftMessage || null,
        }),
      },
    );
    return jsonOrThrow(res);
  },

  async createStorageGiftCheckout(birthId, itemId, { giftMessage } = {}) {
    const res = await fetch(
      `${API_URL}/birth/${birthId}/gifts/storage/${itemId}/checkout`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ gift_message: giftMessage || null }),
      },
    );
    return jsonOrThrow(res);
  },

  async confirmGift(slug, sessionId) {
    const res = await fetch(`${API_URL}/b/${slug}/gifts/confirm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId }),
    });
    return jsonOrThrow(res);
  },

  async getShippingAddress(birthId) {
    const res = await fetch(`${API_URL}/birth/${birthId}/shipping-address`, {
      headers: authHeaders(),
    });
    return jsonOrThrow(res);
  },

  async putShippingAddress(birthId, address) {
    const res = await fetch(`${API_URL}/birth/${birthId}/shipping-address`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify(address),
    });
    return jsonOrThrow(res);
  },

  async listGiftOrders(birthId) {
    const res = await fetch(`${API_URL}/birth/${birthId}/gifts/orders`, {
      headers: authHeaders(),
    });
    return jsonOrThrow(res);
  },

  async retryGiftFulfillment(birthId, orderId) {
    const res = await fetch(
      `${API_URL}/birth/${birthId}/gifts/orders/${orderId}/retry-fulfillment`,
      { method: 'POST', headers: authHeaders() },
    );
    return jsonOrThrow(res);
  },

  async listRenderingProducts(birthId, renderingId) {
    const res = await fetch(
      `${API_URL}/birth/${birthId}/gifts/${renderingId}/products`,
      { headers: authHeaders() },
    );
    return jsonOrThrow(res);
  },

  async requestRenderingProductMockup(birthId, renderingId, productKey) {
    const res = await fetch(
      `${API_URL}/birth/${birthId}/gifts/${renderingId}/products/${productKey}/mockup`,
      { method: 'POST', headers: authHeaders() },
    );
    return jsonOrThrow(res);
  },

  async listInvitations(birthId) {
    const res = await fetch(`${API_URL}/birth/${birthId}/invitations`, {
      headers: authHeaders(),
    });
    return jsonOrThrow(res);
  },

  async createInvitation(birthId, payload = {}) {
    const res = await fetch(`${API_URL}/birth/${birthId}/invitations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({
        display_name_hint: payload.displayNameHint,
        email_hint: payload.emailHint,
        phone_hint: payload.phoneHint,
      }),
    });
    return jsonOrThrow(res);
  },

  async listInvitationRedemptions(birthId, invitationId) {
    const res = await fetch(
      `${API_URL}/birth/${birthId}/invitations/${invitationId}/redemptions`,
      { headers: authHeaders() },
    );
    return jsonOrThrow(res);
  },

  async revokeInvitation(birthId, invitationId) {
    const res = await fetch(
      `${API_URL}/birth/${birthId}/invitations/${invitationId}`,
      { method: 'DELETE', headers: authHeaders() },
    );
    return jsonOrThrow(res);
  },

  async removeViewer(birthId, userId) {
    const res = await fetch(
      `${API_URL}/birth/${birthId}/viewers/${userId}`,
      { method: 'DELETE', headers: authHeaders() },
    );
    return jsonOrThrow(res);
  },

  async markBorn(birthId, payload = {}) {
    const res = await fetch(`${API_URL}/birth/${birthId}/born`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({
        occurred_at: payload.occurredAt,
        body: payload.body,
      }),
    });
    return jsonOrThrow(res);
  },

  async listCoParents(familyId) {
    const res = await fetch(`${API_URL}/family/${familyId}/co-parents`, {
      headers: authHeaders(),
    });
    return jsonOrThrow(res);
  },

  async inviteCoParent(familyId, payload = {}) {
    const res = await fetch(`${API_URL}/family/${familyId}/co-parents/invitations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({
        display_name_hint: payload.displayNameHint,
        email_hint: payload.emailHint,
        phone_hint: payload.phoneHint,
      }),
    });
    return jsonOrThrow(res);
  },

  async revokeCoParentInvite(familyId, invitationId) {
    const res = await fetch(
      `${API_URL}/family/${familyId}/co-parents/invitations/${invitationId}`,
      { method: 'DELETE', headers: authHeaders() },
    );
    return jsonOrThrow(res);
  },

  async lookupInvitation(token) {
    const res = await fetch(`${API_URL}/invite/${token}`);
    return jsonOrThrow(res);
  },

  async redeemInvitationAuthed(token) {
    const res = await fetch(`${API_URL}/invite/${token}/redeem`, {
      method: 'POST',
      headers: authHeaders(),
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

  // ---- Reactions ----
  // We expose both the parent surface (/birth/{id}) and the public
  // surface (/b/{slug}). Pages choose based on whether the visitor is
  // a parent operating their dashboard or a viewer on the keepsake.

  async addReaction({ birthId, slug, eventId, kind }) {
    const url = birthId
      ? `${API_URL}/birth/${birthId}/event/${eventId}/reactions`
      : `${API_URL}/b/${slug}/event/${eventId}/reactions`;
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ kind }),
    });
    return jsonOrThrow(res);
  },

  async removeReaction({ birthId, slug, eventId, kind }) {
    const url = birthId
      ? `${API_URL}/birth/${birthId}/event/${eventId}/reactions/${kind}`
      : `${API_URL}/b/${slug}/event/${eventId}/reactions/${kind}`;
    const res = await fetch(url, {
      method: 'DELETE',
      headers: authHeaders(),
    });
    return jsonOrThrow(res);
  },

  // ---- Comments ----

  async listComments({ birthId, slug, eventId }) {
    const url = birthId
      ? `${API_URL}/birth/${birthId}/event/${eventId}/comments`
      : `${API_URL}/b/${slug}/event/${eventId}/comments`;
    const res = await fetch(url, { headers: authHeaders() });
    return jsonOrThrow(res);
  },

  async createComment({ birthId, slug, eventId, body }) {
    const url = birthId
      ? `${API_URL}/birth/${birthId}/event/${eventId}/comments`
      : `${API_URL}/b/${slug}/event/${eventId}/comments`;
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ body }),
    });
    return jsonOrThrow(res);
  },

  async editComment({ birthId, slug, eventId, commentId, body }) {
    const url = birthId
      ? `${API_URL}/birth/${birthId}/event/${eventId}/comments/${commentId}`
      : `${API_URL}/b/${slug}/event/${eventId}/comments/${commentId}`;
    const res = await fetch(url, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ body }),
    });
    return jsonOrThrow(res);
  },

  async deleteComment({ birthId, slug, eventId, commentId }) {
    const url = birthId
      ? `${API_URL}/birth/${birthId}/event/${eventId}/comments/${commentId}`
      : `${API_URL}/b/${slug}/event/${eventId}/comments/${commentId}`;
    const res = await fetch(url, {
      method: 'DELETE',
      headers: authHeaders(),
    });
    return jsonOrThrow(res);
  },

  async checkSlugAvailable(slug) {
    const res = await fetch(`${API_URL}/births/slug-available?slug=${encodeURIComponent(slug)}`);
    return jsonOrThrow(res);
  },

  async createBirth({ babyName, slug, theme = 'lily' }) {
    const res = await fetch(`${API_URL}/births`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ baby_name: babyName, slug, theme }),
    });
    return jsonOrThrow(res);
  },

  async updateBirth(birthId, patch) {
    const res = await fetch(`${API_URL}/birth/${birthId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify(patch),
    });
    return jsonOrThrow(res);
  },

  async createUnlockCheckout(slug) {
    const res = await fetch(`${API_URL}/b/${slug}/unlock/checkout`, {
      method: 'POST',
      headers: authHeaders(),
    });
    return jsonOrThrow(res);
  },

  async confirmUnlock(slug, sessionId) {
    const res = await fetch(`${API_URL}/b/${slug}/unlock/confirm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId }),
    });
    return jsonOrThrow(res);
  },

  async listGuesses({ birthId, slug }) {
    const url = birthId
      ? `${API_URL}/birth/${birthId}/guesses`
      : `${API_URL}/b/${slug}/guesses`;
    const res = await fetch(url, { headers: authHeaders() });
    return jsonOrThrow(res);
  },

  async putGuess({ birthId, slug }, { weight_lbs, length_in }) {
    const url = birthId
      ? `${API_URL}/birth/${birthId}/guess`
      : `${API_URL}/b/${slug}/guess`;
    const res = await fetch(url, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ weight_lbs, length_in }),
    });
    return jsonOrThrow(res);
  },

  mediaUrl(mediaId) {
    return `${API_URL}/media/${mediaId}`;
  },
};
