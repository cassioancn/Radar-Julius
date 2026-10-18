import os
import json
import random
from datetime import datetime
from typing import Dict, Any, Optional
import requests
from dotenv import load_dotenv

load_dotenv()

JULIUS_QUOTES = [
    "Se você não comprar nada, o desconto é maior: é 100%!",
    "Você acha que eu tô brincando? Cada centavo economizado é um centavo ganho!",
    "Eu não preciso de luxo, preciso de preço baixo!",
    "Esse desconto aí pagou o almoço de amanhã!",
    "Se eu tivesse dois empregos e ainda pagasse preço cheio, eu não seria o Julius!",
    "Economizou R$ {savings:.2f}! Isso dá pra comprar muito pão dormido."
]

def get_julius_quote(savings: float) -> str:
    quote = random.choice(JULIUS_QUOTES)
    return quote.format(savings=savings)

def generate_whatsapp_message(
    product_name: str,
    store_name: str,
    old_price: float,
    new_price: float,
    drop_pct: float,
    savings: float,
    url: str
) -> str:
    """Gera texto pronto para o nó de WhatsApp do n8n (Evolution API / Baileys / Z-API)."""
    return (
        f"🚨 *RADAR JULIUS: QUEDA DE PREÇO DETECTADA!* 🚨\n\n"
        f"🛒 *Produto:* {product_name}\n"
        f"🏪 *Loja:* {store_name}\n"
        f"📉 *Queda de Preço:* -{drop_pct:.1f}%\n"
        f"💰 *Preço Anterior:* ~R$ {old_price:.2f}~\n"
        f"🔥 *Novo Preço:* *R$ {new_price:.2f}*\n"
        f"💵 *Economia Real:* R$ {savings:.2f}\n\n"
        f"🔗 *Link da Oferta:* {url}\n\n"
        f"💬 _\"{get_julius_quote(savings)}\" — Julius Rock_"
    )

def generate_email_html(
    product_name: str,
    store_name: str,
    old_price: float,
    new_price: float,
    drop_pct: float,
    savings: float,
    url: str
) -> str:
    """Gera corpo HTML profissional para o nó de Envio de E-mail do n8n."""
    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; background: #0f172a; color: #f8fafc; border-radius: 12px; padding: 24px; border: 1px solid #334155;">
        <div style="text-align: center; border-bottom: 2px solid #22c55e; padding-bottom: 16px;">
            <h1 style="color: #22c55e; margin: 0; font-size: 26px;">🎯 Radar Julius - Alerta de Oferta!</h1>
            <p style="color: #94a3b8; font-size: 14px; margin-top: 6px;">O menor preço histórico acabou de bater recorde!</p>
        </div>
        
        <div style="padding: 24px 0;">
            <h2 style="color: #ffffff; font-size: 20px; margin-top: 0;">{product_name}</h2>
            <p style="font-size: 16px; color: #cbd5e1;">Detectamos na loja <strong>{store_name}</strong>:</p>
            
            <div style="background: #1e293b; border-radius: 8px; padding: 18px; margin: 16px 0; text-align: center;">
                <span style="text-decoration: line-through; color: #94a3b8; font-size: 18px;">R$ {old_price:.2f}</span>
                <span style="color: #22c55e; font-size: 32px; font-weight: bold; margin-left: 14px;">R$ {new_price:.2f}</span>
                <div style="margin-top: 8px;">
                    <span style="background: #166534; color: #86efac; padding: 4px 10px; border-radius: 20px; font-weight: bold; font-size: 14px;">
                        📉 -{drop_pct:.1f}% DE DESCONTO
                    </span>
                    <span style="color: #38bdf8; font-weight: bold; margin-left: 10px; font-size: 14px;">
                        Economia de R$ {savings:.2f}
                    </span>
                </div>
            </div>
            
            <div style="text-align: center; margin-top: 24px;">
                <a href="{url}" target="_blank" style="background: #22c55e; color: #022c22; text-decoration: none; padding: 14px 28px; border-radius: 8px; font-size: 16px; font-weight: bold; display: inline-block;">
                    👉 Acessar Oferta Agora
                </a>
            </div>
        </div>
        
        <div style="border-top: 1px solid #334155; padding-top: 16px; text-align: center; color: #64748b; font-size: 12px;">
            <p><i>"{get_julius_quote(savings)}" — Julius Rock</i></p>
            <p>Radar Julius • Monitor de Preços Inteligente</p>
        </div>
    </div>
    """

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
    custom_webhook_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Envia payload estruturado para o Webhook do n8n.
    O n8n pode rotear tanto para WhatsApp (Evolution API, Twilio, Z-API) quanto para E-mail (SMTP/Gmail/Resend).
    """
    webhook_url = custom_webhook_url or os.getenv("N8N_WEBHOOK_URL")
    savings = max(0.0, old_price - new_price)

    payload = {
        "event": "PRICE_DROP_ALERT",
        "timestamp": datetime.utcnow().isoformat(),
        "product": {
            "id": product_id,
            "name": product_name,
            "niche": niche
        },
        "pricing": {
            "store_name": store_name,
            "store_type": store_type,
            "old_price": round(old_price, 2),
            "new_price": round(new_price, 2),
            "discount_percentage": round(drop_pct, 1),
            "savings_reais": round(savings, 2),
            "offer_url": url,
            "image_url": image_url
        },
        "location": {
            "city": location_city or "Nacional"
        },
        "julius_quote": get_julius_quote(savings),
        "formatted_messages": {
            "whatsapp": generate_whatsapp_message(
                product_name, store_name, old_price, new_price, drop_pct, savings, url
            ),
            "email_html": generate_email_html(
                product_name, store_name, old_price, new_price, drop_pct, savings, url
            )
        }
    }

    if not webhook_url or "seu-n8n" in webhook_url or not webhook_url.startswith("http"):
        return {
            "success": False,
            "status": "mocked",
            "message": "N8N_WEBHOOK_URL não configurada ou com placeholder. O payload foi gerado com sucesso.",
            "payload": payload
        }

    try:
        response = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=8
        )
        is_success = 200 <= response.status_code < 300
        return {
            "success": is_success,
            "status_code": response.status_code,
            "response": response.text[:200],
            "payload": payload
        }
    except Exception as e:
        return {
            "success": False,
            "status": "error",
            "error": str(e),
            "payload": payload
        }

def test_n8n_connection(webhook_url: str) -> Dict[str, Any]:
    """Testa o disparo de um webhook simulado para o n8n."""
    return dispatch_price_drop_alert(
        product_id=0,
        product_name="[TESTE] Arroz Tipo 1 5kg Camil",
        niche="Alimentos",
        store_name="Atacadão",
        store_type="supermarket",
        old_price=32.90,
        new_price=24.50,
        drop_pct=25.5,
        url="https://www.atacadao.com.br",
        location_city="São Leopoldo - RS",
        custom_webhook_url=webhook_url
    )

