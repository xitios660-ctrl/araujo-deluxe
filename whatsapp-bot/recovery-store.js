"use strict";

const { codec } = require("./session-store");

const STORAGE_KEY = "recovery-state-v1";
const MAX_SEEN = 2000;
const MAX_OUTBOX = 200;
const SEEN_TTL_MS = 7 * 24 * 60 * 60 * 1000;

function emptyState() {
  return {
    version: 1,
    seen: [],
    outbox: [],
    last_disconnect_at: null,
    last_reconnect_at: null,
  };
}

function sanitizeState(value) {
  const state = value && typeof value === "object" ? value : {};
  return {
    version: 1,
    seen: Array.isArray(state.seen) ? state.seen.slice(-MAX_SEEN) : [],
    outbox: Array.isArray(state.outbox) ? state.outbox.slice(-MAX_OUTBOX) : [],
    last_disconnect_at: state.last_disconnect_at || null,
    last_reconnect_at: state.last_reconnect_at || null,
  };
}

async function createRecoveryStore({ request, secret, now = Date.now }) {
  const crypt = codec(secret);
  const loaded = await request("GET");
  const entry = (loaded.entries || []).find(item => item.key === STORAGE_KEY);
  let state = emptyState();
  if (entry?.value) {
    try {
      state = sanitizeState(JSON.parse(crypt.decrypt(entry.value)));
    } catch (error) {
      console.warn("Memória de recuperação inválida; iniciando uma nova:", error.message);
    }
  }

  let tail = Promise.resolve();

  function prune() {
    const cutoff = now() - SEEN_TTL_MS;
    state.seen = state.seen
      .filter(item => item && item.id && Number(item.at || 0) >= cutoff)
      .slice(-MAX_SEEN);
    state.outbox = state.outbox
      .filter(item => item && item.id && item.phone && item.jid && typeof item.text === "string")
      .slice(-MAX_OUTBOX);
  }

  async function persist() {
    prune();
    const value = crypt.encrypt(JSON.stringify(state));
    await request("POST", { entries: [{ key: STORAGE_KEY, value }] });
  }

  function mutate(fn) {
    const job = tail.then(async () => {
      fn();
      await persist();
    });
    tail = job.catch(() => {});
    return job;
  }

  function hasSeen(id) {
    prune();
    return state.seen.some(item => item.id === id);
  }

  function rememberSeen(id) {
    const at = now();
    state.seen = state.seen.filter(item => item.id !== id);
    state.seen.push({ id, at });
  }

  return {
    hasSeen,
    async markHandled(id) {
      if (!id) return;
      await mutate(() => rememberSeen(id));
    },
    async queueReply({ id, phone, jid, text }) {
      if (!id || !phone || !jid || typeof text !== "string" || !text.trim()) return;
      await mutate(() => {
        rememberSeen(id);
        const existing = state.outbox.find(item => item.id === id);
        if (existing) {
          existing.phone = String(phone);
          existing.jid = String(jid);
          existing.text = text;
          existing.updated_at = now();
          return;
        }
        state.outbox.push({
          id,
          phone: String(phone),
          jid: String(jid),
          text,
          created_at: now(),
          updated_at: now(),
          attempts: 0,
        });
      });
    },
    async noteAttempt(id) {
      await mutate(() => {
        const item = state.outbox.find(value => value.id === id);
        if (item) {
          item.attempts = Number(item.attempts || 0) + 1;
          item.updated_at = now();
        }
      });
    },
    async markDelivered(id) {
      if (!id) return;
      await mutate(() => {
        rememberSeen(id);
        state.outbox = state.outbox.filter(item => item.id !== id);
      });
    },
    pendingReplies() {
      prune();
      return state.outbox
        .slice()
        .sort((a, b) => Number(a.created_at || 0) - Number(b.created_at || 0));
    },
    async recordDisconnect() {
      await mutate(() => { state.last_disconnect_at = new Date(now()).toISOString(); });
    },
    async recordReconnect() {
      await mutate(() => { state.last_reconnect_at = new Date(now()).toISOString(); });
    },
    status() {
      prune();
      return {
        pending_replies: state.outbox.length,
        remembered_message_ids: state.seen.length,
        last_disconnect_at: state.last_disconnect_at,
        last_reconnect_at: state.last_reconnect_at,
      };
    },
    flush: () => tail,
  };
}

module.exports = { createRecoveryStore, STORAGE_KEY };
