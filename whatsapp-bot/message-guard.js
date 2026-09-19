const { createHash } = require("node:crypto");
class MessageGuard {
  constructor({ gapMs = 3000, now = Date.now, maxPending = 25, failurePauseMs = 30000, maxSeen = 10000 } = {}) {
    Object.assign(this, {
      gapMs, now, maxPending, failurePauseMs, maxSeen,
      pending: 0, last: 0, tail: Promise.resolve(),
      seen: new Map(), sent: new Map(), counts: new Map(), global: [],
      blocked: new Set(), failures: 0, pausedUntil: 0,
    });
  }
  accept(jid, id) {
    if (!id) return false;
    const now = this.now();
    for (const [key, time] of this.seen) if (now - time >= 3600000) this.seen.delete(key);
    const key = jid + ":" + id;
    if (this.seen.has(key)) return false;
    // The cache is only for replay suppression. Reaching its safety cap must not
    // turn into an hour-long outage where every new customer message is dropped.
    // Map preserves insertion order, so evict the oldest ids before accepting new ones.
    while (this.seen.size >= this.maxSeen) {
      const oldest = this.seen.keys().next().value;
      if (oldest === undefined) break;
      this.seen.delete(oldest);
    }
    this.seen.set(key, now); return true;
  }
  send(contact, payload, deliver, { dedupeKey = null } = {}) {
    if (this.pending >= this.maxPending) return Promise.reject(new Error("Fila cheia"));
    this.pending++;
    const job = this.tail.then(async () => {
      const delay = this.last ? Math.max(0, this.gapMs - (this.now() - this.last)) : 0;
      if (delay) await new Promise(r => setTimeout(r, delay));
      const now = this.now();
      if (this.blocked.has(contact)) throw new Error("Contato pediu para parar");
      if (now < this.pausedUntil) throw new Error("Envios pausados");
      this.global = this.global.filter(t => now - t < 60000);
      for (const [key, times] of this.counts) {
        const recent = times.filter(t => now - t < 60000);
        if (recent.length) this.counts.set(key, recent); else this.counts.delete(key);
      }
      for (const [key, time] of this.sent) if (now - time >= 3600000) this.sent.delete(key);
      const times = this.counts.get(contact) || [];
      // Replies tied to a concrete incoming message carry a dedupeKey. They are
      // user-initiated conversation replies and must never be cut off mid-flow
      // by the outbound anti-spam ceiling. Unsolicited/system sends still obey
      // the global and per-contact limits below.
      if (!dedupeKey && (this.global.length >= 15 || times.length >= 6)) {
        throw new Error("Limite de mensagens atingido");
      }

      const hash = dedupeKey
        ? createHash("sha256").update(contact).update(":").update(String(dedupeKey)).digest("hex")
        : null;
      if (hash && this.sent.has(hash)) return { skipped: true };

      // Space attempts out, but only count/dedupe a message after WhatsApp confirms delivery.
      this.last = now;
      try {
        const result = await deliver();
        const deliveredAt = this.now();
        if (hash) this.sent.set(hash, deliveredAt);
        this.global.push(deliveredAt);
        this.counts.set(contact, [...times, deliveredAt]);
        this.failures = 0;
        return result;
      } catch (e) {
        if (++this.failures >= 3) {
          this.pausedUntil = this.now() + this.failurePauseMs;
          this.failures = 0;
        }
        throw e;
      }
    });
    this.tail = job.catch(() => {});
    return job.finally(() => { this.pending--; });
  }
}
module.exports = { MessageGuard };
