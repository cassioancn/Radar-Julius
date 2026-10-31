"""
Radar Julius - Executador Autônomo de Varredura e Alertas
Pode ser executado via CLI, agendador de tarefas do Windows (Task Scheduler), Cron ou GitHub Actions.
"""
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

load_dotenv()

from database.db import init_db
from services.monitor_service import get_monitor_instance

def main():
    print("=" * 60)
    print(f"🎯 RADAR JULIUS - CICLO DE VARREDURA CONTÍNUA")
    print(f"⏰ Horário: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("=" * 60)

    # 1. Garante inicialização do banco
    init_db()

    # 2. Configurações de WhatsApp
    phone = os.getenv("WHATSAPP_PHONE")
    apikey = os.getenv("WHATSAPP_APIKEY")
    provider = os.getenv("WHATSAPP_PROVIDER", "callmebot")
    api_url = os.getenv("WHATSAPP_API_URL")

    print(f"📱 Provedor WhatsApp configurado: {provider}")
    if phone:
        print(f"📞 Telefone destino: {phone[:4]}***{phone[-4:] if len(phone) > 8 else ''}")
    else:
        print("⚠️ Nenhum telefone configurado no .env (WHATSAPP_PHONE)")

    # 3. Executa o ciclo de varredura
    monitor = get_monitor_instance()
    print("\n🔍 Iniciando varredura em todos os produtos monitorados ativos...")
    results = monitor.run_cycle(
        phone=phone,
        apikey=apikey,
        provider=provider,
        custom_url=api_url
    )

    print(f"\n✅ Varredura concluída! {len(results)} produto(s) verificados.")
    alerts_count = sum(1 for r in results if r.get("alert_dispatched"))
    print(f"🚨 Alertas de WhatsApp disparados: {alerts_count}")

    for idx, r in enumerate(results, start=1):
        p_name = r.get("product_name")
        b_price = r.get("best_price")
        b_store = r.get("best_store")
        alert = "🚨 ALERTA DISPARADO!" if r.get("alert_dispatched") else "OK"
        print(f"  [{idx}] {p_name}: R$ {b_price:.2f} ({b_store}) -> {alert}")

    print("=" * 60)

if __name__ == "__main__":
    main()
