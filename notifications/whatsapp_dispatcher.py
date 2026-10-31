import os
import re
import random
import urllib.parse
from datetime import datetime
from typing import Dict, Any, Optional
import requests
from dotenv import load_dotenv

from database.db import get_db
from database.models import NotificationLog

load_dotenv()

JULIUS_QUOTES = [
    "Se você não comprar nada, o desconto é maior: é 100%!",
    "Você acha que eu tô brincando? Cada centavo economizado é um centavo ganho!",
    "Eu não preciso de luxo, preciso de preço baixo!",
    "Esse desconto aí pagou o almoço de amanhã!",
    "Se eu tivesse dois empregos e ainda pagasse preço cheio, eu não seria o Julius!",
    "Economizou R$ {savings:.2f}! Isso dá pra comprar muito pão dormido.",
    "Quem converte não se diverte, mas quem economiza dorme tranquilo!",
    "Eu sei exatamente quanto custou cada gota de suor pra ganhar esse dinheiro."
]

def get_julius_quote(savings: float = 0.0) -> str:
    """Retorna uma citação aleatória do Julius Rock formatada."""
    quote = random.choice(JULIUS_QUOTES)
    try:
        return quote.format(savings=savings)
    except Exception:
        return quote

def clean_phone_number(phone: str) -> str:
    """Remove caracteres não numéricos e formata o telefone para padrão internacional (DDI+DDD+Número)."""
    digits = re.sub(r"\D", "", phone or "")
    # Se o usuário digitou sem DDI (ex: 51999999999), adiciona 55 (Brasil)
    if len(digits) in (10, 11) and not digits.startswith("55"):
        digits = "55" + digits
    return digits

def format_whatsapp_message(
    product_name: str,
    store_name: str,
    old_price: float,
    new_price: float,
    drop_pct: float,
    savings: float,
    url: str,
    location_city: Optional[str] = None
) -> str:
    """Gera mensagem formatada para WhatsApp com negrito, tachado e emojis."""
    loc_info = f" ({location_city})" if location_city and location_city.lower() != "nacional" else ""
    return (
        f"🚨 *RADAR JULIUS: QUEDA DE PREÇO DETECTADA!* 🚨\n\n"
        f"🛒 *Produto:* {product_name}\n"
        f"🏪 *Loja:* {store_name}{loc_info}\n"
        f"📉 *Queda de Preço:* -{drop_pct:.1f}%\n"
        f"💰 *Preço Anterior:* ~R$ {old_price:.2f}~\n"
        f"🔥 *Novo Preço:* *R$ {new_price:.2f}*\n"
        f"💵 *Economia Real:* R$ {savings:.2f}\n\n"
        f"🔗 *Link da Oferta:* {url}\n\n"
        f"💬 _\"{get_julius_quote(savings)}\" — Julius Rock_"
    )

def generate_whatsapp_share_link(phone: Optional[str], message: str) -> str:
    """Gera link de compartilhamento do WhatsApp (wa.me) para uso na web/mobile com 1 toque."""
    encoded_msg = urllib.parse.quote(message)
    clean_p = clean_phone_number(phone) if phone else ""
    if clean_p:
        return f"https://api.whatsapp.com/send?phone={clean_p}&text={encoded_msg}"
    return f"https://api.whatsapp.com/send?text={encoded_msg}"

def send_whatsapp_message(
    message: str,
    phone: Optional[str] = None,
    apikey: Optional[str] = None,
    provider: Optional[str] = None,
    custom_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Envia a mensagem de WhatsApp diretamente via código Python.
    Provedores suportados:
    1. 'callmebot' (100% gratuito para alertas pessoais, zero servidor necessário)
    2. 'evolution' ou 'z-api' (instância própria de WhatsApp)
    3. 'generic_webhook' (qualquer endpoint HTTP POST)
    """
    prov = (provider or os.getenv("WHATSAPP_PROVIDER", "callmebot")).lower()
    target_phone = clean_phone_number(phone or os.getenv("WHATSAPP_PHONE", ""))
    target_apikey = apikey or os.getenv("WHATSAPP_APIKEY", "")

    # Se nenhum número de telefone estiver configurado
    if not target_phone:
        return {
            "success": False,
            "status": "missing_phone",
            "message": "Nenhum número de WhatsApp configurado para envio.",
            "provider": prov
        }

    # 1. Provedor CallMeBot (100% Grátis)
    if prov == "callmebot":
        if not target_apikey:
            return {
                "success": False,
                "status": "missing_apikey",
                "message": "Chave de API do CallMeBot não fornecida. Solicite sua chave gratuita enviando 'I allow callmebot to send me messages' para +34 644 87 21 57 no WhatsApp.",
                "provider": "callmebot"
            }
        
        try:
            encoded_text = urllib.parse.quote(message)
            url = f"https://api.callmebot.com/whatsapp.php?phone={target_phone}&text={encoded_text}&apikey={target_apikey}"
            resp = requests.get(url, timeout=15)
            
            # CallMeBot retorna 200 com mensagem HTML/texto
            if resp.status_code == 200 and ("queued" in resp.text.lower() or "success" in resp.text.lower() or "ok" in resp.text.lower() or "message sent" in resp.text.lower()):
                return {
                    "success": True,
                    "status": "sent",
                    "message": "Mensagem enviada com sucesso via CallMeBot!",
                    "provider": "callmebot",
                    "response": resp.text[:200]
                }
            elif resp.status_code == 200:
                # Mesmo com texto genérico, status 200 no CallMeBot costuma indicar sucesso
                return {
                    "success": True,
                    "status": "sent",
                    "message": "Requisição aceita pelo CallMeBot.",
                    "provider": "callmebot",
                    "response": resp.text[:200]
                }
            else:
                return {
                    "success": False,
                    "status": f"http_{resp.status_code}",
                    "message": f"Erro CallMeBot HTTP {resp.status_code}: {resp.text[:200]}",
                    "provider": "callmebot"
                }
        except Exception as e:
            return {
                "success": False,
                "status": "error",
                "message": f"Erro de conexão com CallMeBot: {str(e)}",
                "provider": "callmebot"
            }

    # 2. Provedor Evolution API / Z-API / Instância Própria
    elif prov in ("evolution", "zapi", "custom", "generic_webhook"):
        endpoint = custom_url or os.getenv("WHATSAPP_API_URL")
        if not endpoint:
            return {
                "success": False,
                "status": "missing_endpoint",
                "message": "URL da API do WhatsApp não configurada.",
                "provider": prov
            }
        
        headers = {
            "Content-Type": "application/json"
        }
        if target_apikey:
            headers["apikey"] = target_apikey
            headers["Authorization"] = f"Bearer {target_apikey}"

        payload = {
            "number": target_phone,
            "phone": target_phone,
            "message": message,
            "text": message
        }

        try:
            resp = requests.post(endpoint, json=payload, headers=headers, timeout=15)
            if resp.status_code in (200, 201):
                return {
                    "success": True,
                    "status": "sent",
                    "message": "Mensagem enviada com sucesso para instância WhatsApp!",
                    "provider": prov,
                    "response": resp.text[:200]
                }
            else:
                return {
                    "success": False,
                    "status": f"http_{resp.status_code}",
                    "message": f"Erro na API WhatsApp HTTP {resp.status_code}: {resp.text[:200]}",
                    "provider": prov
                }
        except Exception as e:
            return {
                "success": False,
                "status": "error",
                "message": f"Erro ao conectar com a API WhatsApp: {str(e)}",
                "provider": prov
            }

    return {
        "success": False,
        "status": "unsupported_provider",
        "message": f"Provedor '{prov}' não suportado.",
        "provider": prov
    }

def dispatch_price_drop_alert(
    product_id: int,
    product_name: str,
    niche: str,
    store_name: str,
    store_type: str,
    old_price: float,
    new_price: float,
    drop_pct: float,
    url: str,
    location_city: Optional[str] = None,
    image_url: Optional[str] = None,
    phone: Optional[str] = None,
    apikey: Optional[str] = None,
    provider: Optional[str] = None,
    custom_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Formata a notificação, despacha via WhatsApp direto em código e salva o log na tabela NotificationLog.
    """
    savings = max(0.0, old_price - new_price)
    
    # 1. Monta mensagem
    message = format_whatsapp_message(
        product_name=product_name,
        store_name=store_name,
        old_price=old_price,
        new_price=new_price,
        drop_pct=drop_pct,
        savings=savings,
        url=url,
        location_city=location_city
    )

    # 2. Despacha mensagem via WhatsApp
    dispatch_res = send_whatsapp_message(
        message=message,
        phone=phone,
        apikey=apikey,
        provider=provider,
        custom_url=custom_url
    )

    status_str = "sent" if dispatch_res.get("success") else dispatch_res.get("status", "failed")
    channel_str = f"whatsapp_{dispatch_res.get('provider', 'direct')}"

    # 3. Persiste no banco de dados (tabela NotificationLog)
    try:
        with get_db() as db:
            log_entry = NotificationLog(
                product_id=product_id,
                store_name=store_name,
                old_price=round(old_price, 2),
                new_price=round(new_price, 2),
                drop_pct=round(drop_pct, 1),
                status=status_str,
                channel=channel_str,
                sent_at=datetime.utcnow(),
                response_payload=str(dispatch_res.get("message", ""))
            )
            db.add(log_entry)
            db.commit()
    except Exception as db_err:
        print(f"[Radar Julius] Aviso ao persistir NotificationLog: {db_err}")

    share_link = generate_whatsapp_share_link(phone or os.getenv("WHATSAPP_PHONE"), message)

    return {
        "success": dispatch_res.get("success", False),
        "status": status_str,
        "message": dispatch_res.get("message"),
        "provider": dispatch_res.get("provider"),
        "savings": savings,
        "whatsapp_message": message,
        "share_link": share_link
    }

def test_whatsapp_connection(
    phone: str,
    apikey: Optional[str] = None,
    provider: str = "callmebot",
    custom_url: Optional[str] = None
) -> Dict[str, Any]:
    """Envia uma mensagem de teste do Julius Rock para verificar a integração com WhatsApp."""
    now_str = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
    test_msg = (
        f"🎯 *RADAR JULIUS: TESTE DE ALERTA WHATSAPP* 🎯\n\n"
        f"Fala, economizador! Sua integração direta via código está 100% OPERACIONAL!\n\n"
        f"📅 *Data:* {now_str}\n"
        f"💡 *Lembrete:* \"{get_julius_quote(50.0)}\"\n\n"
        f"Assim que o robô detectar qualquer queda de preço em seus produtos monitorados, você receberá a notificação instantaneamente aqui!"
    )
    return send_whatsapp_message(
        message=test_msg,
        phone=phone,
        apikey=apikey,
        provider=provider,
        custom_url=custom_url
    )

