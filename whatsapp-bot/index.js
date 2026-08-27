const { default: makeWASocket, useMultiFileAuthState, DisconnectReason, downloadMediaMessage, fetchLatestBaileysVersion } = require("baileys");
const express = require("express");
const pino = require("pino");
const fs = require("fs");
const path = require("path");

const PORT = process.env.BOT_PORT || 3002;
const BACKEND = process.env.BACKEND_URL || "http://localhost:8001";
const AUTH_DIR = path.join(__dirname, "auth_info");

let sock = null;
let lastQR = null;
let connected = false;
let starting = false;

async function start() {
  if (starting) return;
  starting = true;
  try {
    const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
    const { version } = await fetchLatestBaileysVersion().catch(() => ({ version: undefined }));
    sock = makeWASocket({
      version,
      auth: state,
      printQRInTerminal: false,
      logger: pino({ level: "warn" }),
      browser: ["Araujo Deluxe Bot", "Chrome", "1.0.0"],
    });

    sock.ev.on("creds.update", saveCreds);

    sock.ev.on("connection.update", (u) => {
      const { connection, lastDisconnect, qr } = u;
      if (qr) {
        lastQR = qr;
        connected = false;
        console.log("QR code gerado");
      }
      if (connection === "open") {
        connected = true;
        lastQR = null;
        console.log("WhatsApp conectado:", sock.user?.id);
      }
      if (connection === "close") {
        connected = false;
        starting = false;
        const code = lastDisconnect?.error?.output?.statusCode;
        console.log("Conexao fechada, codigo:", code);
        if (code === DisconnectReason.loggedOut) {
          fs.rmSync(AUTH_DIR, { recursive: true, force: true });
          lastQR = null;
          setTimeout(start, 2000);
        } else {
          setTimeout(start, 4000);
        }
      }
    });

    sock.ev.on("messages.upsert", async ({ messages, type }) => {
      if (type !== "notify") return;
      for (const msg of messages) {
        try {
          await handleMessage(msg);
        } catch (e) {
          console.error("Erro ao processar mensagem:", e.message);
        }
      }
    });
  } catch (e) {
    console.error("Erro ao iniciar:", e.message);
    starting = false;
    setTimeout(start, 8000);
  }
}

async function handleMessage(msg) {
  if (!msg.message || msg.key.fromMe) return;
  const jid = msg.key.remoteJid || "";
  if (jid.endsWith("@g.us") || jid.endsWith("@broadcast") || jid.endsWith("@newsletter") || jid === "status@broadcast") return;
  if (!jid.endsWith("@s.whatsapp.net") && !jid.endsWith("@lid")) return;

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

  let image_base64 = null;
  let image_mime = null;
  const doc = m.documentMessage;
  const media = m.imageMessage || (doc && ((doc.mimetype || "").startsWith("image") || doc.mimetype === "application/pdf") ? doc : null);
  if (media) {
    const buffer = await downloadMediaMessage(msg, "buffer", {}, { logger: pino({ level: "silent" }), reuploadRequest: sock.updateMediaMessage });
    image_base64 = buffer.toString("base64");
    image_mime = media.mimetype || "image/jpeg";
  }

  console.log(`Mensagem de ${jid} (tel: ${phone}) texto: "${String(text).slice(0, 60)}" midia: ${!!media}`);

  const res = await fetch(`${BACKEND}/api/whatsapp/incoming`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phone, text, image_base64, image_mime }),
  });
  const data = await res.json();
  if (data.reply) {
    await sock.sendMessage(jid, { text: data.reply });
    console.log(`Resposta enviada para ${jid}`);
  }
}

async function resolveJid(phone) {
  const d = String(phone).replace(/\D/g, "");
  try {
    const results = await sock.onWhatsApp(d);
    if (results && results[0]?.jid) return results[0].jid;
  } catch (e) {}
  return `${d}@s.whatsapp.net`;
}

const app = express();
app.use(express.json({ limit: "25mb" }));

app.get("/status", (req, res) => {
  res.json({ connected, has_qr: !!lastQR, user: sock?.user || null });
});

app.get("/qr", (req, res) => {
  res.json({ qr: lastQR });
});

app.post("/send", async (req, res) => {
  const { phone, message } = req.body;
  try {
    if (!connected) throw new Error("WhatsApp nao conectado");
    const jid = await resolveJid(phone);
    await sock.sendMessage(jid, { text: message });
    res.json({ ok: true });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

app.post("/send-image", async (req, res) => {
  const { phone, caption, base64, mimetype } = req.body;
  try {
    if (!connected) throw new Error("WhatsApp nao conectado");
    const jid = await resolveJid(phone);
    const buffer = Buffer.from(base64, "base64");
    if (mimetype === "application/pdf") {
      await sock.sendMessage(jid, { document: buffer, mimetype, fileName: "comprovante.pdf", caption });
    } else {
      await sock.sendMessage(jid, { image: buffer, caption });
    }
    res.json({ ok: true });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

app.post("/logout", async (req, res) => {
  try {
    if (sock) await sock.logout().catch(() => {});
  } catch (e) {}
  fs.rmSync(AUTH_DIR, { recursive: true, force: true });
  lastQR = null;
  connected = false;
  starting = false;
  setTimeout(start, 1500);
  res.json({ ok: true });
});

app.listen(PORT, () => {
  console.log(`WhatsApp bot service na porta ${PORT}`);
  start();
});
