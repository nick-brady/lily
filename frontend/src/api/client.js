import { getAttribution } from '../utils/attribution';

// Same-origin '/api' prefix in BOTH modes: the vite dev server proxies it to
// the backend over the docker network, and prod nginx does the identical
// rewrite-strip. The prefix matters — /b/{slug} is both an SPA route and an
// API route, so a bare same-origin path could never be proxied safely.
const API_URL = '/api';

// Sessions live in an httpOnly cookie set by the backend — never in
// localStorage (Safari's ITP purges script-writable storage after ~7 days
// of not visiting, which would silently sign out occasional visitors).
// Same-origin fetch/EventSource/<img>/<a download> all send the cookie on
// their own, so requests need no auth headers at all.

// One-time cleanup of the retired localStorage token.
try {
  localStorage.removeItem('lily_auth_token');
} catch {
  // storage unavailable (private mode edge cases) — nothing to clean
}

// FastAPI hands us `detail` in three shapes and only one of them is a string.
// Passing the other two to `new Error()` renders "[object Object]" at the user,
// which is how a perfectly good validation message ("that time is in the
// future") reaches someone as gibberish.
function detailMessage(body) {
  const detail = body?.detail;
  if (typeof detail === 'string') return detail;
  // Pydantic validation: a list of {loc, msg}. A body checked against a
  // discriminated union reports one entry per variant, all saying the same
  // thing, so the first readable msg is the message.
  if (Array.isArray(detail)) {
    const first = detail.find((d) => typeof d?.msg === 'string');
    if (first) return first.msg.replace(/^Value error,\s*/, '');
  }
  // Structured app errors, e.g. {code: 'name_required', message: ...}
  if (detail && typeof detail.message === 'string') return detail.message;
  return null;
}

// The error half of `jsonOrThrow`, split out so responses that aren't JSON —
// the design preview returns a PNG — can fail the same way.
async function throwFrom(res) {
  let detail = res.statusText;
  let code;
  try {
    const body = await res.json();
    detail = detailMessage(body) || JSON.stringify(body);
    // Machine-readable half of a structured detail, e.g. 'name_required'.
    // Callers that need to branch shouldn't have to match on prose.
    if (typeof body?.detail?.code === 'string') code = body.detail.code;
  } catch {
    // empty or non-JSON body, keep statusText
  }
  const err = new Error(detail);
  err.status = res.status;
  if (code) err.code = code;
  throw err;
}

async function jsonOrThrow(res) {
  if (!res.ok) await throwFrom(res);
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

  async verifyChallenge({ identifier, code, inviteToken }) {
    const res = await fetch(`${API_URL}/auth/verify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        identifier,
        code,
        invite_token: inviteToken,
        // First-touch attribution; the backend records it only when this
        // verify creates a brand-new user.
        ...getAttribution(),
      }),
    });
    return jsonOrThrow(res);
  },

  // "Continue with Google" — a login method, not a separate identity; the
  // backend resolves the verified email to the same user row as the OTP path.
  async googleAuth({ credential, inviteToken }) {
    const res = await fetch(`${API_URL}/auth/google`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        credential,
        invite_token: inviteToken,
        ...getAttribution(),
      }),
    });
    return jsonOrThrow(res);
  },

  async logout() {
    const res = await fetch(`${API_URL}/auth/logout`, { method: 'POST' });
    return jsonOrThrow(res); // 204 → null
  },

  // Birth-events text opt-in. The backend sends the confirmation text
  // before recording consent, so a success here means the number is real.
  async setNotifyPhone(phone) {
    const res = await fetch(`${API_URL}/me/notify-phone`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phone }),
    });
    return jsonOrThrow(res);
  },

  async clearNotifyPhone() {
    const res = await fetch(`${API_URL}/me/notify-phone`, { method: 'DELETE' });
    return jsonOrThrow(res);
  },

  // Fire-and-forget page-view ping (self-hosted analytics). keepalive lets
  // the request survive an immediate navigation away.
  async track(payload) {
    await fetch(`${API_URL}/track`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      keepalive: true,
    });
  },

  async me() {
    const res = await fetch(`${API_URL}/me`, {});
    return jsonOrThrow(res);
  },

  async updateMe({ displayName }) {
    const res = await fetch(`${API_URL}/me`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ display_name: displayName }),
    });
    return jsonOrThrow(res);
  },

  // Always available, never behind any paywall — the counterpart of the
  // free data export.
  async deleteAccount({ removeContributions = false } = {}) {
    const res = await fetch(
      `${API_URL}/me?remove_contributions=${removeContributions}`,
      { method: 'DELETE' }
    );
    return jsonOrThrow(res); // 204 → null
  },

  async getBirth(birthId) {
    const res = await fetch(`${API_URL}/birth/${birthId}`, {});
    return jsonOrThrow(res);
  },

  async getPublicBirth(slug) {
    const res = await fetch(`${API_URL}/b/${slug}`);
    return jsonOrThrow(res);
  },

  async listTimeline(birthId, { afterSequenceId } = {}) {
    const url = new URL(`${API_URL}/birth/${birthId}/timeline`, window.location.origin);
    if (afterSequenceId != null) url.searchParams.set('after_sequence_id', afterSequenceId);
    const res = await fetch(url, {});
    return jsonOrThrow(res);
  },

  async listPublicTimeline(slug, { afterSequenceId } = {}) {
    const url = new URL(`${API_URL}/b/${slug}/timeline`, window.location.origin);
    if (afterSequenceId != null) url.searchParams.set('after_sequence_id', afterSequenceId);
    // Sending Bearer here is intentional: authed viewers get widened
    // audience visibility on the same public endpoint.
    const res = await fetch(url, {});
    return jsonOrThrow(res);
  },

  async startContraction(birthId, { audienceScope = 'group_targeted' } = {}) {
    const res = await fetch(`${API_URL}/birth/${birthId}/contraction/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ audience_scope: audienceScope }),
    });
    return jsonOrThrow(res);
  },

  async stopContraction(birthId, eventId, endTimeIso) {
    const res = await fetch(`${API_URL}/birth/${birthId}/contraction/${eventId}/stop`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ end_time: endTimeIso }),
    });
    return jsonOrThrow(res);
  },

  async createTextNote(birthId, body, { audienceScope = 'group_targeted', occurredAt = null } = {}) {
    const res = await fetch(`${API_URL}/birth/${birthId}/event`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        type: 'text_note',
        body,
        audience_scope: audienceScope,
        ...(occurredAt ? { occurred_at: occurredAt } : {}),
      }),
    });
    return jsonOrThrow(res);
  },

  async createMilestone(birthId, { kind, title, body, audienceScope = 'group_targeted', occurredAt = null }) {
    const res = await fetch(`${API_URL}/birth/${birthId}/event`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        type: 'milestone',
        kind,
        title,
        body,
        audience_scope: audienceScope,
        ...(occurredAt ? { occurred_at: occurredAt } : {}),
      }),
    });
    return jsonOrThrow(res);
  },

  async uploadMedia(birthId, { file, kind, caption, audienceScope = 'group_targeted', occurredAt = null }) {
    const form = new FormData();
    form.append('file', file);
    form.append('kind', kind);
    form.append('audience_scope', audienceScope);
    if (caption) form.append('caption', caption);
    if (occurredAt) form.append('occurred_at', occurredAt);
    const res = await fetch(`${API_URL}/birth/${birthId}/media`, {
      method: 'POST',
      body: form,
    });
    return jsonOrThrow(res);
  },

  async listGifts(birthId) {
    const res = await fetch(`${API_URL}/birth/${birthId}/gifts`, {});
    return jsonOrThrow(res);
  },

  async generateGifts(birthId, renderingId = null) {
    const qs = renderingId ? `?rendering_id=${renderingId}` : '';
    const res = await fetch(`${API_URL}/birth/${birthId}/gifts/generate${qs}`, {
      method: 'POST',
    });
    return jsonOrThrow(res);
  },

  async reviewShippingAddress(birthId, address) {
    const res = await fetch(`${API_URL}/birth/${birthId}/gifts/address-review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ address }),
    });
    return jsonOrThrow(res);
  },

  async createGiftCheckout(
    birthId,
    renderingId,
    { recipientKind, giftMessage, familyAddress, selfAddress },
  ) {
    const res = await fetch(
      `${API_URL}/birth/${birthId}/gifts/${renderingId}/checkout`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          recipient_kind: recipientKind,
          gift_message: giftMessage || null,
          family_address: familyAddress || null,
          self_address: selfAddress || null,
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
        headers: { 'Content-Type': 'application/json' },
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
    const res = await fetch(`${API_URL}/birth/${birthId}/shipping-address`, {});
    return jsonOrThrow(res);
  },

  async putShippingAddress(birthId, address) {
    const res = await fetch(`${API_URL}/birth/${birthId}/shipping-address`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(address),
    });
    return jsonOrThrow(res);
  },

  async listGiftOrders(birthId) {
    const res = await fetch(`${API_URL}/birth/${birthId}/gifts/orders`, {});
    return jsonOrThrow(res);
  },

  async retryGiftFulfillment(birthId, orderId) {
    const res = await fetch(
      `${API_URL}/birth/${birthId}/gifts/orders/${orderId}/retry-fulfillment`,
      { method: 'POST' },
    );
    return jsonOrThrow(res);
  },

  async listRenderingProducts(birthId, renderingId) {
    const res = await fetch(
      `${API_URL}/birth/${birthId}/gifts/${renderingId}/products`,
      {},
    );
    return jsonOrThrow(res);
  },

  async requestRenderingProductMockup(birthId, renderingId, productKey) {
    const res = await fetch(
      `${API_URL}/birth/${birthId}/gifts/${renderingId}/products/${productKey}/mockup`,
      { method: 'POST' },
    );
    return jsonOrThrow(res);
  },

  async listInvitations(birthId) {
    const res = await fetch(`${API_URL}/birth/${birthId}/invitations`, {});
    return jsonOrThrow(res);
  },

  async createInvitation(birthId, payload = {}) {
    const res = await fetch(`${API_URL}/birth/${birthId}/invitations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
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
      {},
    );
    return jsonOrThrow(res);
  },

  async revokeInvitation(birthId, invitationId) {
    const res = await fetch(
      `${API_URL}/birth/${birthId}/invitations/${invitationId}`,
      { method: 'DELETE' },
    );
    return jsonOrThrow(res);
  },

  async removeViewer(birthId, userId) {
    const res = await fetch(
      `${API_URL}/birth/${birthId}/viewers/${userId}`,
      { method: 'DELETE' },
    );
    return jsonOrThrow(res);
  },

  async markBorn(birthId, payload = {}) {
    const res = await fetch(`${API_URL}/birth/${birthId}/born`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        occurred_at: payload.occurredAt,
        body: payload.body,
      }),
    });
    return jsonOrThrow(res);
  },

  async listCoParents(familyId) {
    const res = await fetch(`${API_URL}/family/${familyId}/co-parents`, {});
    return jsonOrThrow(res);
  },

  async inviteCoParent(familyId, payload = {}) {
    const res = await fetch(`${API_URL}/family/${familyId}/co-parents/invitations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
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
      { method: 'DELETE' },
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
    });
    return jsonOrThrow(res);
  },

  async editEvent(birthId, eventId, patch) {
    const res = await fetch(`${API_URL}/birth/${birthId}/event/${eventId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    });
    return jsonOrThrow(res);
  },

  async deleteEvent(birthId, eventId) {
    const res = await fetch(`${API_URL}/birth/${birthId}/event/${eventId}`, {
      method: 'DELETE',
    });
    return jsonOrThrow(res);
  },

  async toggleIgnoreInterval(birthId, eventId) {
    const res = await fetch(`${API_URL}/birth/${birthId}/event/${eventId}/toggle-ignore`, {
      method: 'POST',
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
      headers: { 'Content-Type': 'application/json' },
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
    });
    return jsonOrThrow(res);
  },

  // ---- Comments ----

  async listComments({ birthId, slug, eventId }) {
    const url = birthId
      ? `${API_URL}/birth/${birthId}/event/${eventId}/comments`
      : `${API_URL}/b/${slug}/event/${eventId}/comments`;
    const res = await fetch(url, {});
    return jsonOrThrow(res);
  },

  async createComment({ birthId, slug, eventId, body }) {
    const url = birthId
      ? `${API_URL}/birth/${birthId}/event/${eventId}/comments`
      : `${API_URL}/b/${slug}/event/${eventId}/comments`;
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
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
      headers: { 'Content-Type': 'application/json' },
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
    });
    return jsonOrThrow(res);
  },

  async checkSlugAvailable(slug) {
    const res = await fetch(`${API_URL}/births/slug-available?slug=${encodeURIComponent(slug)}`);
    return jsonOrThrow(res);
  },

  async createBirth({ babyName, slug, theme = 'lily', familyId = null, dueDate = null }) {
    const res = await fetch(`${API_URL}/births`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        baby_name: babyName,
        slug,
        theme,
        family_id: familyId,
        due_date: dueDate || null,
      }),
    });
    return jsonOrThrow(res);
  },

  async updateBirth(birthId, patch) {
    const res = await fetch(`${API_URL}/birth/${birthId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    });
    return jsonOrThrow(res);
  },

  async deleteBirth(birthId) {
    const res = await fetch(`${API_URL}/birth/${birthId}`, { method: 'DELETE' });
    return jsonOrThrow(res);
  },

  // Membership is family-wide rather than per-birth, so this covers every page
  // in the family — the caller names them all rather than saying "family".
  async leaveFamily(familyId) {
    const res = await fetch(`${API_URL}/family/${familyId}/membership`, {
      method: 'DELETE',
    });
    return jsonOrThrow(res);
  },

  async listGuesses({ birthId, slug }) {
    const url = birthId
      ? `${API_URL}/birth/${birthId}/guesses`
      : `${API_URL}/b/${slug}/guesses`;
    const res = await fetch(url, {});
    return jsonOrThrow(res);
  },

  async putGuess({ birthId, slug }, body) {
    const url = birthId
      ? `${API_URL}/birth/${birthId}/guess`
      : `${API_URL}/b/${slug}/guess`;
    // body may carry weight_lbs/length_in/sex_guess/date_guess. Fields the
    // form doesn't own right now are simply absent — the server preserves
    // whatever the guess row already holds for absent fields.
    const res = await fetch(url, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    return jsonOrThrow(res);
  },

  async listGiftPhotos(birthId) {
    const res = await fetch(`${API_URL}/birth/${birthId}/gifts/photos`, {});
    return jsonOrThrow(res);
  },

  async uploadGiftPhoto(birthId, file) {
    const body = new FormData();
    body.append('file', file);
    const res = await fetch(`${API_URL}/birth/${birthId}/gifts/photos`, {
      method: 'POST',
      body,
    });
    return jsonOrThrow(res);
  },

  // A design draft: { mediaId, removed, text }. `mediaId` picks a photo,
  // `removed` takes it off, neither hands the choice back to the auto-pick.
  _designBody(draft = {}) {
    return JSON.stringify({
      media_id: draft.mediaId ?? null,
      removed: Boolean(draft.removed),
      photo_slots: draft.slots || {},
      // the book's middle section as arranged; null keeps the automatic plan
      pages: draft.pages ?? null,
      text: draft.text || {},
      product_key: draft.productKey ?? null,
    });
  },

  // The book's page plan for a draft — which pages exist and which photo
  // slots each holds — without drawing anything.
  async bookPlan(birthId, renderingId, draft) {
    const res = await fetch(`${API_URL}/birth/${birthId}/gifts/${renderingId}/book-plan`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: this._designBody(draft),
    });
    return jsonOrThrow(res);
  },

  // Renders the draft and returns an object URL. Nothing is saved — this is
  // what the editor debounces onto while someone types.
  async previewGiftDesign(birthId, renderingId, draft, { signal, full, page } = {}) {
    const qs = new URLSearchParams();
    if (full) qs.set('full', 'true');
    if (page) qs.set('page', page);   // one page of a many-page design (the book)
    const res = await fetch(
      `${API_URL}/birth/${birthId}/gifts/${renderingId}/preview${qs.toString() ? `?${qs}` : ''}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: this._designBody(draft),
        signal,
      },
    );
    if (!res.ok) await throwFrom(res);
    // The fitted type sizes ride in a header, since the body is the PNG.
    let fit = null;
    try {
      fit = JSON.parse(res.headers.get('X-Text-Fit') || 'null');
    } catch {
      // a preview without it still previews
    }
    return { url: URL.createObjectURL(await res.blob()), fit };
  },

  async saveGiftDesign(birthId, renderingId, draft) {
    const res = await fetch(
      `${API_URL}/birth/${birthId}/gifts/${renderingId}/design`,
      {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: this._designBody(draft),
      },
    );
    return jsonOrThrow(res);
  },

  async refreshGiftMockup(birthId, renderingId) {
    const res = await fetch(
      `${API_URL}/birth/${birthId}/gifts/${renderingId}/mockup`,
      { method: 'POST' },
    );
    return jsonOrThrow(res);
  },

  mediaUrl(mediaId) {
    return `${API_URL}/media/${mediaId}`;
  },

  // Browser-navigated download; the session cookie rides along, so no
  // token ever appears in the URL (or the access logs). The export is
  // always free — it must never gain a paywall check.
  birthExportUrl(birthId) {
    return `${API_URL}/birth/${birthId}/export`;
  },
};
