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
let halted = null, lastLeaseSuccess = 0, leaseRenewing = null;
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
async function renewLease({ initial = false } = {}) {
  if (leaseRenewing) return leaseRenewing;
  leaseRenewing = (async () => {
    try {
      const lease = await apiRequest("/internal/whatsapp/lease", "POST");
      if (!lease.acquired) {
        const error = new Error("Session owned by another instance");
        error.code = "LEASE_TAKEN";
        throw error;
      }
      hasLease = true;
      lastLeaseSuccess = Date.now();
      return true;
    } catch (e) {
      // Keep the socket alive through one short backend/network hiccup while the
      // already-acquired 60s lease is still safely within its validity window.
      const withinGrace = !initial && e.code !== "LEASE_TAKEN" && hasLease &&
        lastLeaseSuccess && Date.now() - lastLeaseSuccess < 40000;
      if (withinGrace) {
        console.warn("Falha temporária ao renovar lease; mantendo conexão:", e.message);
        return false;
      }
      hasLease = false;
      disconnectTransport();
      starting = false;
      schedule();
      throw e;
    } finally {
      leaseRenewing = null;
    }
  })();
  return leaseRenewing;
}
async function start() {
  if (starting || connected || closing || halted) return;
  starting = true;
  try {
    await renewLease({ initial: true });
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
      auth.saveCreds().catch((e) => {
        console.error("Falha temporária ao salvar sessão:", e.message);
        if (current !== sock || closing) return;
        disconnectTransport();
        starting = false;
        schedule();
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
        incomingPending++;
        if (incomingPending === 50) console.warn("Fila de atendimento acima de 50 mensagens; processando sem descartar.");
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
function safeSend(phone, jid, payload, dedupeKey = null) {
  return guard.send(phone, payload, () => {
    if (!connected || !sock || !hasLease || halted) throw new Error("WhatsApp indisponível");
    return sock.sendMessage(jid, payload);
  }, { dedupeKey });
}

function unwrapMessage(message) {
  let current = message || {};
  for (let i = 0; i < 8; i++) {
    const nested =
      current.ephemeralMessage?.message ||
      current.viewOnceMessage?.message ||
      current.viewOnceMessageV2?.message ||
      current.viewOnceMessageV2Extension?.message ||
      current.documentWithCaptionMessage?.message ||
      current.editedMessage?.message ||
      current.deviceSentMessage?.message;
    if (!nested) break;
    current = nested;
  }
  return current;
}

function extractText(message) {
  const direct =
    message.conversation ||
    message.extendedTextMessage?.text ||
    message.imageMessage?.caption ||
    message.videoMessage?.caption ||
    message.documentMessage?.caption ||
    message.buttonsResponseMessage?.selectedButtonId ||
    message.buttonsResponseMessage?.selectedDisplayText ||
    message.listResponseMessage?.singleSelectReply?.selectedRowId ||
    message.listResponseMessage?.title ||
    message.templateButtonReplyMessage?.selectedId ||
    message.templateButtonReplyMessage?.selectedDisplayText;
  if (direct) return String(direct);

  const params = message.interactiveResponseMessage?.nativeFlowResponseMessage?.paramsJson;
  if (params) {
    try {
      const parsed = JSON.parse(params);
      return String(parsed.title || parsed.id || parsed.selectedId || parsed.selectedRowId || parsed.value || "");
    } catch (_) {}
  }
  return "";
}

function detectMessageType(message, text) {
  if (text) return "text";
  if (message.audioMessage) return "audio";
  if (message.stickerMessage) return "sticker";
  if (message.imageMessage) return "image";
  if (message.videoMessage) return "video";
  if (message.documentMessage) return "document";
  if (message.locationMessage || message.liveLocationMessage) return "location";
  if (message.contactMessage || message.contactsArrayMessage) return "contact";
  return "unknown";
}

function buildListPayload(ui, reply) {
  if (!ui || ui.type !== "list" || !Array.isArray(ui.sections)) return null;
  const sections = ui.sections
    .map(section => ({
      title: String(section.title || "").slice(0, 24),
      rows: (section.rows || []).slice(0, 10).map(row => ({
        title: String(row.title || "").slice(0, 24),
        rowId: String(row.id || ""),
        description: row.description ? String(row.description).slice(0, 72) : undefined,
      })).filter(row => row.rowId && row.title),
    }))
    .filter(section => section.rows.length);
  if (!sections.length) return null;
  return {
    title: String(ui.title || "Araújo Deluxe").slice(0, 60),
    text: String(ui.text || "Escolha uma opção"),
    footer: String(ui.footer || "Araújo Deluxe 💛"),
    buttonText: String(ui.button_text || "Abrir menu").slice(0, 20),
    sections,
  };
}

function uiTextFallback(ui, reply) {
  if (!ui || !Array.isArray(ui.sections)) return String(reply || "");
  const rows = ui.sections.flatMap(section => section.rows || []);
  if (!rows.length) return String(reply || "");
  const options = rows.map((row, i) => {
    const desc = row.description ? " — " + row.description : "";
    return "*" + (i + 1) + ".* " + String(row.title || "Opção") + desc;
  });
  return [String(reply || ui.text || "Escolha uma opção"), "", ...options, "", "_Responda com o número ou escreva normalmente o que você precisa._"].join("\n");
}

async function sendBotReply(phone, jid, data, reply, dedupeKey) {
  const listPayload = buildListPayload(data.ui, reply);

  if (!listPayload) {
    await safeSend(phone, jid, { text: reply }, dedupeKey);
    return "text";
  }

  const fallback = uiTextFallback(data.ui, reply);

  // The current Baileys/WhatsApp combination on this account has been observed
  // to accept list payloads while rendering only an empty-looking second bubble.
  // Default to one reliable message. Lists can be re-enabled explicitly after
  // transport-level verification.
  if (process.env.WHATSAPP_INTERACTIVE_LISTS !== "1") {
    await safeSend(phone, jid, { text: fallback }, dedupeKey + ":text");
    return "text-menu";
  }

  try {
    await safeSend(phone, jid, listPayload, dedupeKey + ":list");
    return "interactive-list";
  } catch (e) {
    console.warn("Lista interativa falhou; usando texto:", e.message);
    await safeSend(phone, jid, { text: fallback }, dedupeKey + ":text");
    return "text-fallback";
  }
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

  const m = unwrapMessage(msg.message);
  const text = extractText(m);
  const messageType = detectMessageType(m, text);

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
    const data = await apiRequest("/whatsapp/incoming", "POST", {
      phone,
      text,
      image_base64,
      image_mime,
      push_name: msg.pushName || null,
    });
    if (data.reply) {
      let reply = data.reply;
      if (!text && !image_base64 && messageType === "audio") {
        reply = "Recebi seu áudio 💛 Por enquanto eu não consigo ouvir áudios. Me manda por texto que eu te respondo na hora.";
      } else if (!text && !image_base64 && messageType !== "text") {
        reply = "Recebi sua mensagem 💛 Para eu entender certinho, me manda em texto que eu continuo seu atendimento daqui.";
      }
      if (!introduced.has(phone)) {
        const memoryStatus = await apiRequest("/whatsapp/memory/status/" + encodeURIComponent(phone)).catch(() => null);
        if (!memoryStatus?.returning && !reply.includes("assistente virtual")) {
          reply = "Oi! Sou a assistente virtual do Araújo Deluxe. 💛\n\n" + reply + "\n\nPara parar mensagens: PARAR. Para voltar: REATIVAR.";
        }
      }
      await sendBotReply(phone, jid, data, reply, msg.key.id);
      await apiRequest("/whatsapp/memory/outgoing", "POST", { phone, text: reply }).catch(() => {});
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
    await apiRequest("/whatsapp/memory/outgoing", "POST", { phone: digits, text: req.body.message }).catch(() => {});
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
    if (caption) await apiRequest("/whatsapp/memory/outgoing", "POST", { phone: digits, text: caption }).catch(() => {});
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
