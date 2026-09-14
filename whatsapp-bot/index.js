const express = require("express");
const pino = require("pino");
const crypto = require("node:crypto");
const { MessageGuard } = require("./message-guard");
const { usePersistentAuth } = require("./session-store");
const guard = new MessageGuard();
const introduced = new Set();
const secret = process.env.WHATSAPP_INTERNAL_TOKEN || process.env.JWT_SECRET;
if (!secret) throw new Error("Segredo interno do bot ausente");
const token = process.env.WHATSAPP_INTERNAL_TOKEN ||
  crypto.createHmac("sha256", process.env.JWT_SECRET).update("whatsapp-internal").digest("hex");
const instance = crypto.randomUUID();
const PORT = process.env.BOT_PORT || 3002;
const BACKEND = (process.env.BACKEND_URL || "http://127.0.0.1:8001").replace(/\/+$/, "");
let baileys, downloadMediaMessage;
let sock = null, auth = null, lastQR = null, connected = false, starting = false;
let timer = null, heartbeat = null, attempts = 0, closing = false, hasLease = false;
let halted = null;
let incomingTail = Promise.resolve(), incomingPending = 0;

async function apiRequest(path, method = "GET", body) {
  const response = await fetch(BACKEND + "/api" + path, {
    method,
    headers: { "Content-Type": "application/json", "X-Bot-Token": token, "X-Bot-Instance": instance },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(20000),
  });
  if (!response.ok) throw new Error("API HTTP " + response.status);
  return response.json();
}
async function storageRequest(method, body) {
  let error;
  for (let attempt = 0; attempt < 3; attempt++) {
    try { return await apiRequest("/internal/whatsapp/session", method, body); }
    catch (e) { error = e; if (attempt < 2) await new Promise(r => setTimeout(r, 500 * (attempt + 1))); }
  }
  throw error;
}
function schedule() {
  if (timer || closing || halted) return;
  const delay = Math.min(300000, 5000 * 2 ** Math.min(attempts++, 6));
  timer = setTimeout(() => { timer = null; start(); }, delay);
}
function disconnectTransport() {
  connected = false;
  lastQR = null;
  clearInterval(heartbeat); heartbeat = null;
  const previous = sock; sock = null;
  if (previous) {
    previous.ev.removeAllListeners("connection.update");
    previous.ev.removeAllListeners("messages.upsert");
    previous.ev.removeAllListeners("creds.update");
    previous.end(new Error("Local transport closed; session preserved"));
  }
}
async function renewLease() {
  try {
    const lease = await apiRequest("/internal/whatsapp/lease", "POST");
    if (!lease.acquired) throw new Error("Session owned by another instance");
    hasLease = true;
  } catch (e) {
    hasLease = false;
    disconnectTransport();
    starting = false;
    schedule();
    throw e;
  }
}
async function start() {
  if (starting || connected || closing || halted) return;
  starting = true;
  try {
    await renewLease();
    auth = await usePersistentAuth({ baileys, request: storageRequest, secret });
    if (closing) return;
    const current = baileys.default({
      auth: auth.state, logger: pino({ level: "warn" }),
      browser: ["Araújo Deluxe", "Chrome", "1.0.0"],
      markOnlineOnConnect: false,
      syncFullHistory: false,
    });
    sock = current;
    heartbeat = setInterval(() => { renewLease().catch(() => {}); }, 15000);
    current.ev.on("creds.update", () => {
      auth.saveCreds().catch(() => {
        halted = "Falha ao salvar sessão. Verifique o banco antes de reconectar.";
        disconnectTransport();
      });
    });
    current.ev.on("connection.update", ({ connection, lastDisconnect, qr }) => {
      if (current !== sock || closing) return;
      if (qr) { lastQR = qr; connected = false; }
      if (connection === "open") { connected = true; lastQR = null; attempts = 0; starting = false; }
      if (connection === "close") {
        const code = lastDisconnect?.error?.output?.statusCode;
        disconnectTransport(); starting = false;
        const stopped = ["loggedOut", "forbidden", "connectionReplaced", "badSession"]
          .map(key => baileys.DisconnectReason[key]).filter(value => value !== undefined);
        if (stopped.includes(code)) {
          halted = "Sessão encerrada ou recusada pelo WhatsApp. A reconexão automática foi pausada.";
        } else schedule();
      }
    });
    current.ev.on("messages.upsert", ({ messages, type }) => {
      if (type !== "notify" || closing) return;
      for (const msg of messages) {
        if (incomingPending >= 20) break;
        incomingPending++;
        incomingTail = incomingTail.then(() => handleMessage(msg))
          .catch(e => console.error("Falha no atendimento:", e.message))
          .finally(() => { incomingPending--; });
      }
    });
  } catch (e) {
    console.error("Bot não iniciou:", e.message);
    starting = false;
    disconnectTransport();
    schedule();
  }
}
function safeSend(phone, jid, payload) {
  return guard.send(phone, payload, () => {
    if (!connected || !sock || !hasLease || halted) throw new Error("WhatsApp indisponível");
    return sock.sendMessage(jid, payload);
  });
}
async function handleMessage(msg) {
  if (!msg.message || msg.key.fromMe) return;
  const jid = msg.key.remoteJid || "";
  if (jid.endsWith("@g.us") || jid.endsWith("@broadcast") || jid.endsWith("@newsletter") || jid === "status@broadcast") return;
  if (!jid.endsWith("@s.whatsapp.net") && !jid.endsWith("@lid")) return;

  if (!guard.accept(jid, msg.key.id)) return;
  const alt = msg.key.remoteJidAlt || msg.key.senderPn || msg.key.participantAlt || "";
  const phoneSource = jid.endsWith("@lid") && alt ? alt : jid;
  const phone = String(phoneSource).split("@")[0].split(":")[0];

  const m =
    msg.message.ephemeralMessage?.message ||
    msg.message.viewOnceMessage?.message ||
    msg.message.viewOnceMessageV2?.message ||
    msg.message.documentWithCaptionMessage?.message ||
    msg.message;
  const text = m.conversation || m.extendedTextMessage?.text || m.imageMessage?.caption || m.documentMessage?.caption || "";

  const command = text.trim().toLowerCase();
  if (["parar", "sair", "stop", "não quero receber mensagens", "nao quero receber mensagens"].includes(command)) guard.blocked.add(phone);
  if (["reativar", "voltar"].includes(command)) guard.blocked.delete(phone);
  if (guard.blocked.has(phone) && !["parar", "sair", "stop", "não quero receber mensagens", "nao quero receber mensagens"].includes(command)) return;

  let image_base64 = null;
  let image_mime = null;
  const doc = m.documentMessage;
  const media = m.imageMessage || (doc && ((doc.mimetype || "").startsWith("image") || doc.mimetype === "application/pdf") ? doc : null);
  if (media) {
    const buffer = await downloadMediaMessage(msg, "buffer", {}, { logger: pino({ level: "silent" }), reuploadRequest: sock.updateMediaMessage });
    image_base64 = buffer.toString("base64");
    image_mime = media.mimetype || "image/jpeg";
  }



  const current = sock;
  if (!current || !connected) return;
  // Presence reflects actual processing; no fake human identity or artificial typing delay.
  const showTyping = !guard.blocked.has(phone);
  if (showTyping) await current.sendPresenceUpdate("composing", jid).catch(() => {});
  try {
    const data = await apiRequest("/whatsapp/incoming", "POST", { phone, text, image_base64, image_mime });
    if (data.reply) {
      let reply = data.reply;
      if (!introduced.has(phone) && !reply.includes("assistente virtual")) {
        reply = "Oi! Sou a assistente virtual do Araújo Deluxe. 💛\n\n" + reply + "\n\nPara parar mensagens: PARAR. Para voltar: REATIVAR.";
      }
      await safeSend(phone, jid, { text: reply });
      if (introduced.size >= 10000) introduced.clear();
      introduced.add(phone);
    }
  } finally {
    if (showTyping) await current.sendPresenceUpdate("paused", jid).catch(() => {});
  }
}


function jidFor(phone) {
  const digits = String(phone || "").replace(/\D/g, "");
  if (!/^\d{8,15}$/.test(digits)) throw new Error("Telefone inválido");
  return { digits, jid: digits + "@s.whatsapp.net" };
}
const app = express();
app.use((req, res, next) => {
  const received = Buffer.from(req.get("X-Bot-Token") || "");
  const expected = Buffer.from(token);
  if (received.length !== expected.length || !crypto.timingSafeEqual(received, expected))
    return res.status(401).json({ error: "Não autorizado" });
  next();
});
app.use(express.json({ limit: "25mb" }));
app.get("/status", (req, res) => res.json({
  connected, has_qr: !!lastQR, user: sock?.user || null,
  session_storage: "encrypted_database", halted,
  protections: { enabled: true, pending: guard.pending, paused: Date.now() < guard.pausedUntil,
    per_minute: 15, per_contact_per_minute: 6 },
}));
app.get("/qr", (req, res) => res.json({ qr: lastQR }));
app.post("/send", async (req, res) => {
  try {
    const { digits, jid } = jidFor(req.body.phone);
    if (typeof req.body.message !== "string" || !req.body.message.trim()) throw new Error("Mensagem vazia");
    await safeSend(digits, jid, { text: req.body.message });
    res.json({ ok: true });
  } catch (e) { res.status(503).json({ ok: false, error: e.message }); }
});
app.post("/send-image", async (req, res) => {
  try {
    const { digits, jid } = jidFor(req.body.phone);
    const { caption, base64, mimetype } = req.body;
    if (typeof base64 !== "string" || base64.length > 11000000) throw new Error("Mídia inválida");
    const buffer = Buffer.from(base64, "base64");
    const payload = mimetype === "application/pdf"
      ? { document: buffer, mimetype, fileName: "comprovante.pdf", caption }
      : { image: buffer, caption };
    await safeSend(digits, jid, payload);
    res.json({ ok: true });
  } catch (e) { res.status(503).json({ ok: false, error: e.message }); }
});
app.post("/logout", async (req, res) => {
  try {
    if (!hasLease) throw new Error("Sessão em uso por outra instância");
    clearTimeout(timer); timer = null;
    halted = "Trocando sessão";
    const previous = sock;
    disconnectTransport();
    if (auth) await auth.flush();
    // This is the only path that intentionally deletes stored credentials.
    await storageRequest("DELETE");
    if (previous) await previous.logout().catch(() => {});
    auth = null; halted = null; starting = false;
    schedule();
    res.json({ ok: true });
  } catch (e) { res.status(503).json({ ok: false, error: e.message }); }
});
async function shutdown() {
  if (closing) return;
  closing = true;
  clearTimeout(timer);
  disconnectTransport();
  if (auth) await auth.flush().catch(() => {});
  await apiRequest("/internal/whatsapp/lease", "DELETE").catch(() => {});
  process.exit(0);
}
process.on("SIGTERM", shutdown);
process.on("SIGINT", shutdown);
app.listen(PORT, process.env.BOT_HOST || "127.0.0.1", async () => {
  try {
    baileys = await import("baileys");
    downloadMediaMessage = baileys.downloadMediaMessage;
    await start();
  } catch (e) { console.error("Falha ao carregar Baileys:", e.message); process.exit(1); }
});
